import json
import time
import duckdb
import pandas as pd
import requests

HEADERS={"User-Agent": "Giorgos george.gasaniani@gmail.com"}

con=duckdb.connect("data/sp500.duckdb")
tickers=con.sql("SELECT DISTINCT ticker FROM prices ORDER BY ticker").df()["ticker"].tolist()

r=requests.get("https://www.sec.gov/files/company_tickers.json",headers=HEADERS)
lookup={v["ticker"]: str(v["cik_str"]).zfill(10) for v in r.json().values()}
matched={t: lookup[t] for t in tickers if t in lookup}
print(f"{len(matched)} of {len(tickers)} tickers mathed to a CIK")

from pathlib import Path

if not Path("data/raw/shares.parquet").exists():
    rows = []
    for n, (t, cik) in enumerate(matched.items(), 1):
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        r = requests.get(url, headers=HEADERS)
        time.sleep(0.12)
        if r.status_code != 200:
            continue
        facts = r.json().get("facts", {})
        recs = (facts.get("dei", {})
                     .get("EntityCommonStockSharesOutstanding", {})
                     .get("units", {})
                     .get("shares", []))
        if not recs:
            recs = (facts.get("us-gaap", {})
                         .get("WeightedAverageNumberOfSharesOutstandingBasic", {})
                         .get("units", {})
                         .get("shares", []))
        for unit in recs:
            rows.append({"ticker": t, "date": unit.get("end"), "shares": unit.get("val"),
                         "filed": unit.get("filed"), "form": unit.get("form")})
        if n % 50 == 0:
            print(f"{n}/{len(matched)}  rows so far: {len(rows)}")


if Path("data/raw/shares.parquet").exists():
    df = pd.read_parquet("data/raw/shares.parquet")
else:
    df = pd.DataFrame(rows)
    df.to_parquet("data/raw/shares.parquet", index=False)

print(f"{len(df)} sahre-count records for {df['ticker'].nunique()} tickers")

print(df.shape, list(df.columns))
print(df.head(3))
df = df.dropna(subset=["shares", "date"])
df["date"] = pd.to_datetime(df["date"])
df["filed"] = pd.to_datetime(df["filed"])
con.execute("CREATE OR REPLACE TABLE shares AS SELECT * FROM df")


con.execute("ALTER TABLE shares ALTER date TYPE DATE")
con.execute("ALTER TABLE shares ALTER filed TYPE DATE")

print(con.sql("""
     SELECT ticker,date,COUNT(*) AS n FROM shares
     GROUP BY 1,2 HAVING n> 1 ORDER BY n DESC LIMIT 10
"""))
print(con.sql("""
    SELECT ticker, MIN(date) AS first, MAX(date) AS last, COUNT(*) AS n
    FROM shares WHERE ticker IN ('AAPL', 'NVDA', 'MSFT') GROUP BY 1
"""))
print(con.sql("SELECT ticker, date, shares FROM shares WHERE ticker = 'NVDA' ORDER BY date DESC LIMIT 3"))      

print(con.sql("""
    SELECT ticker, date, shares, filed, form FROM shares
    WHERE ticker = 'SMCI' AND date = '2019-11-30' ORDER BY filed
"""))

con.execute("""
    CREATE OR REPLACE TABLE shares AS
    SELECT ticker, date, MAX(shares) AS shares, MIN(filed) AS filed
    FROM shares GROUP BY 1, 2
""")
print(con.sql("SELECT COUNT(*) AS rows, COUNT(DISTINCT ticker) AS tickers FROM shares"))

con.execute("""
    CREATE OR REPLACE TABLE shares AS
    WITH ctx AS (
        SELECT *, MEDIAN(shares) OVER (
                     PARTITION BY ticker ORDER BY filed
                     ROWS BETWEEN 8 PRECEDING AND 8 FOLLOWING) AS local_med
        FROM shares
    )
    SELECT ticker, date, shares, filed FROM ctx
    WHERE shares BETWEEN local_med / 10 AND local_med * 10
""")

print(con.sql("SELECT COUNT(*) AS rows, COUNT(DISTINCT ticker) AS tickers FROM shares"))

print(con.sql("SELECT date, shares FROM shares WHERE ticker = 'AJG' AND date >= '2020-01-01' AND date <= '2020-12-31'"))
print(con.sql("SELECT date, shares FROM shares WHERE ticker = 'NVDA' ORDER BY filed DESC LIMIT 3"))