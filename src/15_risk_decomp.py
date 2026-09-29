"""Euler risk decomposition: how much of the index's risk each company carries.

Risk share of company i = w_i * (Sigma w)_i / (w' Sigma w). The shares add up to 1, so
"the top 10 are X% of the weight but Y% of the risk" compares like with like.

Weights: today's real index weights (fund holdings). Covariance: daily returns over a
window; the headline table uses 2024 to today ("recent"), as in the first version.

Changes from the first version:
  - real index weights instead of SEC share counts x price (total shares, several
    companies missing)
  - a company with a few missing days is kept (pairwise covariance). The first version
    dropped every company with any gap in the window, which removed everything listed
    after the window start. Companies with returns on fewer than 90% of the window's days
    are still left out; how much weight that is gets printed and exported.
"""
import duckdb
import numpy as np
import pandas as pd

from config import AI, MIN_COVERAGE, START, WINDOW

con = duckdb.connect("data/sp500.duckdb")
DATE = con.sql("SELECT MAX(date) AS d FROM weights").df()["d"][0]
w_all = con.sql(f"SELECT ticker, weight FROM weights WHERE date = '{DATE}'").df().set_index("ticker")["weight"]
rets = con.sql(f"""SELECT date, ticker, ret FROM prices WHERE ret IS NOT NULL AND date >= '{START}'
                   AND ticker IN (SELECT ticker FROM weights WHERE date = '{DATE}')""").df()
wide_all = rets.pivot(index="date", columns="ticker", values="ret").sort_index()


def decomp(win, label):
    """Decompose on one window of returns; returns a per-company table."""
    ok = win.columns[win.notna().mean() >= MIN_COVERAGE]
    left_out = w_all.drop(ok, errors="ignore")
    ww = w_all.reindex(ok).dropna()
    ww = ww / ww.sum()
    cov = win[ww.index].cov().values * 252          # pairwise: tolerates a few missing days
    v = ww.values
    pv = v @ cov @ v
    share = v * (cov @ v) / pv
    out = pd.DataFrame({"weight": v, "risk_share": share}, index=ww.index).sort_values("weight", ascending=False)
    ai = out[out.index.isin(AI)]
    print(f"{label:12} {win.index.min():%Y-%m-%d} to {win.index.max():%Y-%m-%d} | vol {np.sqrt(pv):5.1%} | "
          f"top10 {out.head(10)['weight'].sum():5.1%} wt {out.head(10)['risk_share'].sum():5.1%} risk | "
          f"AI {ai['weight'].sum():5.1%} wt {ai['risk_share'].sum():5.1%} risk | "
          f"left out {len(left_out)} = {left_out.sum():.2%}")
    return out, np.sqrt(pv), left_out.sum()


print(f"weights as of {DATE:%Y-%m-%d}")
windows = [("full", wide_all),
           ("covid", wide_all.loc["2020-02-01":"2020-06-30"]),
           ("selloff2022", wide_all.loc["2022-01-01":"2022-12-31"]),
           ("recent", wide_all.loc["2024-01-01":]),
           (f"last{WINDOW}", wide_all.tail(WINDOW))]
rows, tables = [], {}
for label, win in windows:
    out, vol, left = decomp(win, label)
    ai = out[out.index.isin(AI)]
    rows.append({"window": label, "top10_weight": out.head(10)["weight"].sum(),
                 "top10_risk": out.head(10)["risk_share"].sum(), "ai_weight": ai["weight"].sum(),
                 "ai_risk": ai["risk_share"].sum(), "volatility": vol, "weight_left_out": left})
    tables[label] = out

main = tables["recent"]
main["ratio"] = main["risk_share"] / main["weight"]
print(f"\nRisk shares sum to {main['risk_share'].sum():.4f}")
print("Top 15 companies (recent window, 2024 to today), %:")
print((main.head(15) * 100).round(2).to_string())
chips = main[main.index.isin(["NVDA", "AVGO", "MU", "AMD"])]
print(f"\nChip makers (NVDA, AVGO, MU, AMD): {chips['weight'].sum():.1%} of weight, "
      f"{chips['risk_share'].sum():.1%} of risk")

main.to_csv("data/bi/risk_decomposition.csv")
pd.DataFrame(rows).to_csv("data/bi/risk_by_window.csv", index=False)
