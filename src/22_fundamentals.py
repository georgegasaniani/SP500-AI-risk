import time
from pathlib import Path

import duckdb
import pandas as pd
import requests

HEADERS = {"User-Agent": "Giorgos george.gasaniani@gmail.com"}
AI = ["NVDA", "AVGO", "MU", "MSFT", "GOOGL", "AMZN", "META"]

FIELDS = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax",
                "Revenues", "SalesRevenueNet"],
    "net_income": ["NetIncomeLoss"],
    "op_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment",
              "PaymentsToAcquireProductiveAssets"],
    "rnd": ["ResearchAndDevelopmentExpense"],
    "depreciation": ["Depreciation"],
    "dep_and_amort": ["DepreciationDepletionAndAmortization"],
}

con = duckdb.connect("data/sp500.duckdb")
r = requests.get("https://www.sec.gov/files/company_tickers.json", headers=HEADERS)
lookup = {v["ticker"]: str(v["cik_str"]).zfill(10) for v in r.json().values()}

cache = Path("data/raw/fundamentals.parquet")
if not cache.exists():
    rows = []
    for t in AI:
        cik = lookup[t]
        facts = requests.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
                             headers=HEADERS).json()["facts"].get("us-gaap", {})
        time.sleep(0.2)
        for metric, tags in FIELDS.items():
            for tag in tags:
                recs = facts.get(tag, {}).get("units", {}).get("USD", [])
                for u in recs:
                    if u.get("form") in ("10-Q", "10-K") and u.get("start"):
                        rows.append({"ticker": t, "metric": metric, "tag": tag,
                                     "start": u["start"], "end": u["end"],
                                     "val": u["val"], "filed": u["filed"], "form": u["form"]})
            for u in recs:
                if u.get("form") in ("10-Q", "10-K") and u.get("start"):
                    rows.append({"ticker": t, "metric": metric, "tag": tag,
                                 "start": u["start"], "end": u["end"],
                                 "val": u["val"], "filed": u["filed"], "form": u["form"]})
        print(f"{t}: {len([r for r in rows if r['ticker'] == t])} records")

    df = pd.DataFrame(rows)
    df.to_parquet(cache, index=False)
else:
    df = pd.read_parquet(cache)

print(f"\n{len(df)} records")
print(df.groupby(["ticker", "metric"])["val"].count().unstack().fillna(0).astype(int))
print("\nTags used:")
print(df.groupby("metric")["tag"].unique())



df["start"] = pd.to_datetime(df["start"])
df["end"] = pd.to_datetime(df["end"])
df["filed"] = pd.to_datetime(df["filed"])
df["days"] = (df["end"] - df["start"]).dt.days

def clean(lo, hi):
    s = df[(df["days"] >= lo) & (df["days"] <= hi)].copy()
    return (s.sort_values("filed")
             .drop_duplicates(subset=["ticker", "metric", "end"], keep="first"))


ann = clean(350, 380)
A = ann.pivot_table(index=["ticker", "end"], columns="metric", values="val").reset_index()
A["fcf"] = A["op_cash_flow"] - A["capex"]
A["year"] = A["end"].dt.year
print(f"annual: {len(A)} company-years")
print(A.groupby("ticker")["year"].agg(["count", "min", "max"]))


INCOME = ["revenue", "net_income", "rnd"]
CASH = ["capex", "op_cash_flow", "depreciation"]

qi = clean(80, 100)
qi = qi[qi["metric"].isin(INCOME)]


cum = df[df["metric"].isin(CASH)].copy()
cum = (cum.sort_values("filed")
          .drop_duplicates(subset=["ticker", "metric", "start", "end"], keep="first"))
cum = cum[cum["days"] <= 380]
cum = cum.sort_values(["ticker", "metric", "start", "end"])


cum["prev_val"] = cum.groupby(["ticker", "metric", "start"])["val"].shift()
cum["prev_end"] = cum.groupby(["ticker", "metric", "start"])["end"].shift()
cum["q_val"] = cum["val"] - cum["prev_val"].fillna(0)
cum["q_days"] = (cum["end"] - cum["prev_end"].fillna(cum["start"])).dt.days
qc = cum[(cum["q_days"] >= 80) & (cum["q_days"] <= 100)][["ticker", "metric", "end", "q_val"]]
qc = qc.rename(columns={"q_val": "val"})

Q = pd.concat([qi[["ticker", "metric", "end", "val"]], qc])
Q = Q.drop_duplicates(subset=["ticker", "metric", "end"], keep="first")
Q = Q.pivot_table(index=["ticker", "end"], columns="metric", values="val").reset_index()
Q["fcf"] = Q["op_cash_flow"] - Q["capex"]
print(f"\nquarterly: {len(Q)} company-quarters")
print(Q.groupby("ticker")["end"].agg(["count", "min", "max"]))

print("\nNVDA recent quarters (USD bn):")
nv = Q[Q["ticker"] == "NVDA"].sort_values("end").tail(8)
print((nv.set_index("end")[["revenue", "net_income", "op_cash_flow", "capex", "fcf"]] / 1e9).round(2).to_string())

fy_end = (A[A["revenue"].notna()]
            .assign(md=lambda d: d["end"].dt.strftime("%m"))
            .groupby("ticker")["md"].agg(lambda s: s.mode()[0]))
print("fiscal year-end month:")
print(fy_end)

fy_month = fy_end.astype(int)
A = A[A.apply(lambda r: abs(r["end"].month - fy_month[r["ticker"]]) in (0, 1, 11), axis=1)]
A = A.sort_values("end").drop_duplicates(subset=["ticker", "year"], keep="last")
print(f"\nannual after fiscal-year filter: {len(A)} company-years")
print(A.groupby("ticker")["year"].agg(["count", "min", "max"]))




INCOME_Q4 = ["revenue", "net_income", "rnd"]
fy = A[["ticker", "end", "year"] + [c for c in INCOME_Q4 if c in A.columns]].copy()

filled = []
for _, row in fy.iterrows():
    t, ye = row["ticker"], row["end"]
    prior = Q[(Q["ticker"] == t) & (Q["end"] > ye - pd.Timedelta(days=340)) & (Q["end"] < ye - pd.Timedelta(days=20))]
    if len(prior) != 3:
        continue
    rec = {"ticker": t, "end": ye}
    for m in INCOME_Q4:
        if m in row and pd.notna(row[m]) and prior[m].notna().all():
            rec[m] = row[m] - prior[m].sum()
    filled.append(rec)

q4 = pd.DataFrame(filled)
Q = Q.merge(q4, on=["ticker", "end"], how="outer", suffixes=("", "_q4"))
for m in INCOME_Q4:
    if f"{m}_q4" in Q.columns:
        Q[m] = Q[m].fillna(Q[f"{m}_q4"])
        Q = Q.drop(columns=[f"{m}_q4"])

print(f"\nquarterly after Q4 fill: {len(Q)}")
print("NVDA recent quarters (USD bn):")
nv = Q[Q["ticker"] == "NVDA"].sort_values("end").tail(8)
print((nv.set_index("end")[["revenue", "net_income", "op_cash_flow", "capex", "fcf"]] / 1e9).round(2).to_string())

con.execute("CREATE OR REPLACE TABLE fundamentals_annual AS SELECT * FROM A")
con.execute("CREATE OR REPLACE TABLE fundamentals_quarterly AS SELECT * FROM Q")





