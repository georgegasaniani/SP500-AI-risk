import os
import time
from pathlib import Path
import duckdb
import pandas as pd
import requests

TOKEN=os.environ["TIINGO_API_KEY"]

tickers=pd.read_csv("data/tiingo_list.csv")["ticker"].tolist()
out=Path("data/raw/tiingo")
out.mkdir(parents=True,exist_ok=True)
print(len(tickers),"tickers to download")


failed = []
for n, t in enumerate(tickers,1):
    path = out / f"{t}.parquet"
    if path.exists():
        continue
    r=requests.get(f"https://api.tiingo.com/tiingo/daily/{t}/prices",
                   params={"startDate":"1998-01-01","token":TOKEN})
    if r.status_code == 429:
        print("Rate limited, Stopping. Run again later to continue")
        break
    if r.status_code !=200 or not r.json():
        failed.append(t)
        print(f"{n}/{len(tickers)} {t}: no data ({r.status_code})")
        time.sleep(72)
        continue
    df=pd.DataFrame(r.json())
    df["ticker"]=t
    df.to_parquet(path, index=False)
    print(f"{n}/{len(tickers)} {t}: {len(df)} rows, {df['date'].min()[:10]} to {df['date'].max()[:10]}")
    time.sleep(72)


con = duckdb.connect("data/sp500.duckdb")
con.execute("""
    CREATE OR REPLACE TABLE prices_tiingo AS
    SELECT * FROM read_parquet('data/raw/tiingo/*.parquet', union_by_name=True)
""")
got = con.sql("SELECT COUNT(DISTINCT ticker) AS n FROM prices_tiingo").df()["n"][0]
print(f"\nTiingo table: {got} tickers. Failed: {failed}")    