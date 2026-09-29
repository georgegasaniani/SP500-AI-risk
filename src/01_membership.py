"""Index membership history (fja05680/sp500), one row per change date and ticker.

The file lists the tickers as they were on each date (Facebook appears as FB until
2022). 00_fetch_data.py keeps it up to date. The daily version of this table is built
in 08_concentration.py, because it needs the list of trading days from the price table.
"""
import duckdb
import pandas as pd

raw = pd.read_csv("data/raw/sp500_history.csv", parse_dates=["date"])
members = (raw.assign(ticker=raw["tickers"].str.split(",")).explode("ticker")[["date", "ticker"]])
members["ticker"] = members["ticker"].str.strip()

con = duckdb.connect("data/sp500.duckdb")
con.execute("CREATE OR REPLACE TABLE membership AS SELECT * FROM members")
con.execute("ALTER TABLE membership ALTER date TYPE DATE")

print(con.sql("""
    SELECT COUNT(DISTINCT ticker) AS tickers, MIN(date) AS first_date, MAX(date) AS last_date
    FROM membership WHERE date >= '1998-01-01'
"""))
