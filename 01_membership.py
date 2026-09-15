import pandas as pd, duckdb

raw=pd.read_csv(r"C:\Users\lalib\OneDrive\Documents\sp500-ai-risk\data\raw\sp500_history.csv",parse_dates=["date"])
members=(raw.assign(ticker=raw["tickers"].str.split(","))
         .explode("ticker")[["date","ticker"]])
members["ticker"]=members["ticker"].str.strip()


con=duckdb.connect("data/sp500.duckdb")
con.execute("CREATE OR REPLACE TABLE membership AS SELECT * FROM members")


print(con.sql("""
    SELECT COUNT(DISTINCT ticker) as tickers,
           MIN(date) AS first_date, MAX(date) AS last_date
    FROM membership WHERE date >= '1998-01-01'
    """))

con.execute("ALTER TABLE membership ALTER date TYPE DATE")

con.execute("""
    CREATE OR REPLACE TABLE membership_daily AS
    WITH days AS (SELECT DISTINCT date FROM prices),
         changes AS (SELECT DISTINCT date FROM membership),
         mapped AS (
             SELECT d.date,
                    (SELECT MAX(c.date) FROM changes c WHERE c.date <= d.date) AS as_of
             FROM days d
         )
    SELECT mapped.date, replace(m.ticker, '.', '-') AS ticker
    FROM mapped
    JOIN membership m ON m.date = mapped.as_of
""")

print(con.sql("""
    SELECT year(date) AS yr, COUNT(DISTINCT date) AS days,
           ROUND(AVG(n), 1) AS avg_members
    FROM (SELECT date, COUNT(*) AS n FROM membership_daily GROUP BY 1)
    GROUP BY 1 ORDER BY 1
"""))