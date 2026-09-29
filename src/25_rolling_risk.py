import duckdb
import numpy as np
import pandas as pd

con = duckdb.connect("data/sp500.duckdb")

dates = con.sql("""
    SELECT DISTINCT date FROM weights
    WHERE date >= '2016-01-01' ORDER BY date
""").df()["date"]
month_ends = pd.Series(dates).groupby(pd.to_datetime(dates).dt.to_period("M")).last()

rets_all = con.sql("SELECT date, ticker, ret FROM prices WHERE ret IS NOT NULL").df()
wide_all = rets_all.pivot(index="date", columns="ticker", values="ret")

rows = []
for days in (252, 504, 756):
    for d in month_ends:
        w = con.sql(f"SELECT ticker, weight FROM weights WHERE date = '{d}'").df()
        win = wide_all.loc[str(pd.Timestamp(d) - pd.Timedelta(days=days)):str(d)].dropna(axis=1)
        w = w[w["ticker"].isin(win.columns)].set_index("ticker")["weight"]
        if len(w) < 100 or len(win) < days * 0.6:
            continue
        w = w / w.sum()
        win = win[w.index]

        cov = win.cov().values * 252
        v = w.values
        pv = v @ cov @ v
        share = v * (cov @ v) / pv
        out = pd.DataFrame({"weight": v, "risk": share}, index=w.index).sort_values("weight", ascending=False)

        rows.append({"date": d, "window_days": days,
                     "volatility": np.sqrt(pv),
                     "top10_weight": out.head(10)["weight"].sum(),
                     "top10_risk": out.head(10)["risk"].sum()})
    print(f"{days}-day window done")

R = pd.DataFrame(rows)
R.to_csv("data/bi/rolling_risk.csv", index=False)
con.execute("CREATE OR REPLACE TABLE rolling_risk AS SELECT * FROM R")

piv = R.pivot(index="date", columns="window_days", values="top10_risk")
print("\nTop 10 risk share by window length:")
print((piv * 100).round(1).tail(18).to_string())
print("\nMonth-to-month standard deviation of changes:")
print((piv.diff().std() * 100).round(2).to_string())