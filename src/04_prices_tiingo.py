import os
import time
from pathlib import Path
import duckdb
import pandas as pd
import requests

TOKEN=os.environ.get("TIINGO_API_KEY")  # only needed to download missing files

tickers=pd.read_csv("data/tiingo_list.csv")["ticker"].tolist()
out=Path("data/raw/tiingo")
out.mkdir(parents=True,exist_ok=True)
print(len(tickers),"tickers to download")

# Tickers Tiingo answered with no data are remembered, so later runs do not ask again
# (each request costs a 72-second wait on the free tier). Delete the file to retry them.
NO_DATA = out / "no_data.csv"
known_no_data = set(pd.read_csv(NO_DATA)["ticker"]) if NO_DATA.exists() else set()
no_data = []


failed = []
for n, t in enumerate(tickers,1):
    path = out / f"{t}.parquet"
    if path.exists():
        continue
    if t in known_no_data:
        failed.append(t)
        continue
    if not TOKEN:
        failed.append(t)
        continue
    r=requests.get(f"https://api.tiingo.com/tiingo/daily/{t}/prices",
                   params={"startDate":"1998-01-01","token":TOKEN})
    if r.status_code == 429:
        print("Rate limited, Stopping. Run again later to continue")
        break
    if r.status_code !=200 or not r.json():
        failed.append(t)
        if r.status_code in (200, 404):
            no_data.append(t)
        print(f"{n}/{len(tickers)} {t}: no data ({r.status_code})")
        time.sleep(72)
        continue
    df=pd.DataFrame(r.json())
    df["ticker"]=t
    df.to_parquet(path, index=False)
    print(f"{n}/{len(tickers)} {t}: {len(df)} rows, {df['date'].min()[:10]} to {df['date'].max()[:10]}")
    time.sleep(72)


if no_data:
    pd.Series(sorted(known_no_data | set(no_data)), name="ticker").to_csv(NO_DATA, index=False)

con = duckdb.connect("data/sp500.duckdb")
con.execute("""
    CREATE OR REPLACE TABLE prices_tiingo AS
    SELECT * FROM read_parquet('data/raw/tiingo/*.parquet', union_by_name=True)
""")
got = con.sql("SELECT COUNT(DISTINCT ticker) AS n FROM prices_tiingo").df()["n"][0]
print(f"\nTiingo table: {got} tickers. Failed: {failed}")    