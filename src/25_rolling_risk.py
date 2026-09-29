"""Risk decomposition rolling through time: does the top 10's share of RISK exceed
their share of WEIGHT, and since when?

At every month end: that day's real index weights, and the covariance of daily returns
over the previous 252 / 504 / 756 TRADING days.

Fix from the first version: windows were `pd.Timedelta(days=252)`, i.e. calendar days
(252 calendar days is about 174 trading days, eight months). They are now counted in
trading days. The weights are the fund's real holdings, so companies that the first
version was missing (Meta before 2022, Exxon, Disney, BlackRock...) are included.
"""
import duckdb
import numpy as np
import pandas as pd

from config import AI, MIN_COVERAGE

con = duckdb.connect("data/sp500.duckdb")
dates = con.sql("SELECT DISTINCT date FROM weights WHERE date >= '2012-01-01' ORDER BY date").df()["date"]
month_ends = pd.Series(dates).groupby(pd.to_datetime(dates).dt.to_period("M")).last()
W = con.sql("SELECT date, ticker, weight FROM weights").df()
W = W[W["date"].isin(set(month_ends))].groupby("date")
rets = con.sql("SELECT date, ticker, ret FROM prices WHERE ret IS NOT NULL AND date >= '2008-01-01'").df()
wide_all = rets.pivot(index="date", columns="ticker", values="ret").sort_index()
trading_days = wide_all.index

rows = []
for days in (252, 504, 756):
    for d in month_ends:
        end = trading_days.searchsorted(pd.Timestamp(d), side="right")
        if end < days:
            continue
        win = wide_all.iloc[end - days:end]
        w = W.get_group(d).set_index("ticker")["weight"]
        ok = [t for t in w.index if t in win.columns and win[t].notna().mean() >= MIN_COVERAGE]
        left_out = 1 - w[ok].sum()
        ww = w[ok] / w[ok].sum()
        cov = win[ww.index].cov().values * 252
        v = ww.values
        pv = v @ cov @ v
        share = pd.Series(v * (cov @ v) / pv, index=ww.index)
        top = ww.nlargest(10).index
        ai = [t for t in ww.index if t in AI]
        rows.append({"date": d, "window_days": days, "volatility": np.sqrt(pv),
                     "top10_weight": ww[top].sum(), "top10_risk": share[top].sum(),
                     "weight_left_out": left_out, "ai_weight": ww[ai].sum(), "ai_risk": share[ai].sum()})
    print(f"{days}-day window done")

R = pd.DataFrame(rows)
R.to_csv("data/bi/rolling_risk.csv", index=False)
con.execute("CREATE OR REPLACE TABLE rolling_risk AS SELECT * FROM R")

piv = R.pivot(index="date", columns="window_days", values="top10_risk")
print("\nTop 10 risk share by window length (last 18 month ends):")
print((piv * 100).round(1).tail(18).to_string())
gap = R[R["window_days"] == 252].assign(gap=lambda d: d["top10_risk"] - d["top10_weight"])
print("\nRisk share minus weight share (252 days), yearly average, percentage points:")
print((gap.groupby(pd.to_datetime(gap["date"]).dt.year)["gap"].mean() * 100).round(1).to_string())
print(f"\nlargest weight left out of a window: {R['weight_left_out'].max():.2%}")
