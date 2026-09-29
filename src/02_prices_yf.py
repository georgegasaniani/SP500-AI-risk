import time
from pathlib import Path

import duckdb
import pandas as pd
import yfinance as yf

con=duckdb.connect("data/sp500.duckdb")

tickers=con.sql("""
     SELECT DISTINCT ticker FROM membership
     WHERe date >= '1998-01-01' ORDER BY ticker
""").df()["ticker"].str.replace(".","-", regex=False).tolist()
tickers.append("SPY")

out=Path("data/raw/yf")
out.mkdir(parents=True, exist_ok=True)

for i in range(0,len(tickers), 50):
    path=out /f"batch_{i // 50:03d}.parquet"
    if path.exists():
        continue
    df=yf.download(tickers[i:i+50], start="1998-01-01",auto_adjust=False,
               actions=True, progress=False, threads=True)
    if df.empty:
        print(f"batch {i // 50 + 1}: nothing returned, will retry on the next run")
        time.sleep(60)
        continue
    df = df.stack(level=1).reset_index()
    df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]
    df=df.dropna(subset=["close"])
    df.to_parquet(path, index=False)

    print(f"batch {i // 50+1}: {df['ticker'].nunique()} of {len(tickers[i:i + 50])} tickers have data")

    time.sleep(5)


con.execute("""
    CREATE OR REPLACE TABLE prices_yf AS
    SELECT * EXCLUDE (__index_level_0__)
    FROM read_parquet('data/raw/yf/batch_*.parquet', union_by_name=True)
""")

got=set(con.sql("SELECT DISTINCT ticker FROM prices_yf").df()["ticker"])
failed=[t for t in tickers if t not in got]
pd.Series(failed, name="ticker").to_csv("data/failed_yf.csv",index=False)
print(f"\nDone; {len(got)} tickers downloaded, {len(failed)} failed")

funds = con.sql("SELECT DISTINCT ticker FROM prices_yf WHERE capital_gains > 0").df()
print("Tickers with capital gains (probably funds, not companies):", funds["ticker"].tolist())

# Fresh Yahoo batches written by 00_fetch_data.py (current members and benchmarks,
# up to the latest trading day). Each run of 00 writes a new dated set; for every
# ticker keep only the rows from its newest file.
if list(Path("data/raw/yf2").glob("*.parquet")):
    con.execute("""
        CREATE OR REPLACE TABLE prices_yf2 AS
        WITH r AS (SELECT *, filename FROM read_parquet('data/raw/yf2/*.parquet',
                                                        union_by_name=True, filename=true)),
             newest AS (SELECT ticker, MAX(filename) AS f FROM r GROUP BY 1)
        SELECT r.* EXCLUDE (filename) FROM r JOIN newest n ON r.ticker = n.ticker AND r.filename = n.f
    """)
    n = con.sql("SELECT COUNT(DISTINCT ticker) AS t, MAX(date) AS d FROM prices_yf2").df().iloc[0]
    print(f"fresh Yahoo prices: {n.t} tickers, up to {n.d}")