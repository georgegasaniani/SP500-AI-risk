import duckdb
import numpy as np
import pandas as pd

con = duckdb.connect("data/sp500.duckdb")
A = con.sql("SELECT * FROM fundamentals_annual").df()
Q = con.sql("SELECT * FROM fundamentals_quarterly").df()

HYPER = ["MSFT", "AMZN", "GOOGL", "META"]


A["capex_pct"] = A["capex"] / A["revenue"]
piv = A[A["ticker"].isin(HYPER + ["NVDA", "AVGO", "MU"])].pivot_table(
    index="year", columns="ticker", values="capex_pct")
print("Capex as % of revenue:")
print((piv * 100).round(1).tail(12).to_string())


def cagr(s, years):
    s = s.dropna()
    if len(s) < years + 1:
        return np.nan
    return (s.iloc[-1] / s.iloc[-1 - years]) ** (1 / years) - 1

print("\nAnnualised growth (last 3 years / last 5 years):")
rows = []
for t in HYPER + ["NVDA", "AVGO", "MU"]:
    d = A[A["ticker"] == t].sort_values("year")
    rows.append({"ticker": t,
                 "rev_3y": cagr(d["revenue"], 3), "capex_3y": cagr(d["capex"], 3),
                 "rev_5y": cagr(d["revenue"], 5), "capex_5y": cagr(d["capex"], 5)})
g = pd.DataFrame(rows).set_index("ticker")
g["gap_3y"] = g["capex_3y"] - g["rev_3y"]
print((g * 100).round(1).to_string())


h = (A[A["ticker"].isin(HYPER)].groupby("year")[["revenue", "capex", "op_cash_flow", "fcf"]]
       .sum().replace(0, np.nan).dropna())
h["capex_pct"] = 100 * h["capex"] / h["revenue"]
h["fcf_margin"] = 100 * h["fcf"] / h["revenue"]
print("\nHyperscaler group (USD bn, last 10 years):")
print(pd.concat([(h[["revenue", "capex", "op_cash_flow", "fcf"]] / 1e9).round(0),
                 h[["capex_pct", "fcf_margin"]].round(1)], axis=1).tail(10).to_string())


nv = A[A["ticker"] == "NVDA"].set_index("year")["revenue"]
comp = pd.DataFrame({"hyper_capex": h["capex"], "nvda_revenue": nv}).dropna()
comp["ratio"] = comp["nvda_revenue"] / comp["hyper_capex"]
print("\nHyperscaler capex vs Nvidia revenue (USD bn):")
print(pd.concat([(comp[["hyper_capex", "nvda_revenue"]] / 1e9).round(0),
                 comp[["ratio"]].round(3)], axis=1).tail(8).to_string())



print("\nTrailing twelve months, most recent four quarters (USD bn):")
ttm = []
for t in HYPER + ["NVDA", "AVGO", "MU"]:
    d = Q[Q["ticker"] == t].sort_values("end")
    d = d.dropna(subset=["revenue", "capex"]).tail(4)
    if len(d) < 4:
        print(f"  {t}: only {len(d)} complete quarters, skipped")
        continue
    ttm.append({"ticker": t, "through": d["end"].max().date(),
                "revenue": d["revenue"].sum(), "capex": d["capex"].sum(),
                "op_cash_flow": d["op_cash_flow"].sum(), "fcf": d["fcf"].sum()})

T = pd.DataFrame(ttm).set_index("ticker")
T["capex_pct"] = 100 * T["capex"] / T["revenue"]
T["fcf_margin"] = 100 * T["fcf"] / T["revenue"]
print(pd.concat([T[["through"]],
                 (T[["revenue", "capex", "op_cash_flow", "fcf"]] / 1e9).round(0),
                 T[["capex_pct", "fcf_margin"]].round(1)], axis=1).to_string())

hyp = T[T.index.isin(HYPER)]
print(f"\nHyperscaler group TTM: revenue ${hyp['revenue'].sum()/1e9:.0f}bn, "
      f"capex ${hyp['capex'].sum()/1e9:.0f}bn ({100*hyp['capex'].sum()/hyp['revenue'].sum():.1f}% of revenue), "
      f"FCF ${hyp['fcf'].sum()/1e9:.0f}bn")
print(f"Nvidia TTM revenue as share of hyperscaler capex: "
      f"{T.loc['NVDA','revenue'] / hyp['capex'].sum():.3f}")





A = con.sql("SELECT * FROM fundamentals_annual").df()
Q = con.sql("SELECT * FROM fundamentals_quarterly").df()

h = (A[A["ticker"].isin(HYPER)].groupby("year")[["revenue", "capex", "depreciation", "op_cash_flow"]]
       .sum().replace(0, np.nan).dropna())
h["dep_pct_rev"] = 100 * h["depreciation"] / h["revenue"]
h["capex_pct_rev"] = 100 * h["capex"] / h["revenue"]
h["dep_over_capex"] = h["depreciation"] / h["capex"]

print("Hyperscaler group: depreciation vs capex (USD bn and %):")
print(pd.concat([(h[["revenue", "capex", "depreciation"]] / 1e9).round(0),
                 h[["capex_pct_rev", "dep_pct_rev", "dep_over_capex"]].round(2)],
                axis=1).tail(10).to_string())

print("\nAnnualised growth, last 3 years (%):")
rows = []
for t in HYPER:
    d = A[A["ticker"] == t].sort_values("year")
    rows.append({"ticker": t, "revenue": cagr(d["revenue"], 3),
                 "capex": cagr(d["capex"], 3), "depreciation": cagr(d["depreciation"], 3)})
print((pd.DataFrame(rows).set_index("ticker") * 100).round(1).to_string())




print("\nTrailing twelve months (USD bn):")
rows = []
for t in HYPER + ["NVDA"]:
    d = Q[Q["ticker"] == t].sort_values("end").dropna(subset=["revenue", "capex", "depreciation"]).tail(4)
    if len(d) < 4:
        continue
    rows.append({"ticker": t, "revenue": d["revenue"].sum(), "capex": d["capex"].sum(),
                 "depreciation": d["depreciation"].sum()})
T = pd.DataFrame(rows).set_index("ticker")
T["dep_pct_rev"] = 100 * T["depreciation"] / T["revenue"]
T["dep_over_capex"] = T["depreciation"] / T["capex"]
print(pd.concat([(T[["revenue", "capex", "depreciation"]] / 1e9).round(0),
                 T[["dep_pct_rev", "dep_over_capex"]].round(2)], axis=1).to_string())

