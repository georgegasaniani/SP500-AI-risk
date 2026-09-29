import duckdb
import pandas as pd

con=duckdb.connect("data/sp500.duckdb")
manual=pd.read_csv("data/manual_shares.csv")
manual["shares"]=manual["shares"].astype(str).str.replace(",","").astype(float)
manual["filed"] = pd.to_datetime(manual["date"]).fillna(pd.Timestamp("2015-01-01"))
manual["date"] = manual["filed"]
manual["source"]="manual"
manual=manual[["ticker", "date","shares", "filed","source"]]


con.execute("ALTER TABLE shares ADD COLUMN IF NOT EXISTS source VARCHAR DEFAULT 'sec'")

con.execute("DELETE FROM shares WHERE ticker IN ('GOOGL', 'GOOG')")

con.execute("""
    INSERT INTO shares
    SELECT m.ticker, m.date, m.shares, m.filed, m.source
    FROM manual m
    WHERE m.ticker IN ('GOOGL', 'GOOG')
       OR NOT EXISTS (
        SELECT 1 FROM shares s
        WHERE s.ticker = m.ticker AND s.filed >= '2014-01-01'
    )
""")

print(con.sql("SELECT source, COUNT(*) AS rows,COUNT(DISTINCT ticker) AS tickers FROM shares GROUP BY 1"))
print(con.sql("SELECT ticker,shares FROM shares WHERE source= 'manual' ORDER BY ticker"))

##THE CORRECT ORDER IS FIRST TO RUN 07 THEN 10 AND THEN 08