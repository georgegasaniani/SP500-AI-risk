import duckdb
import numpy as np
import pandas as pd

con = duckdb.connect("data/sp500.duckdb")
DATE = con.sql("SELECT MAX(date) AS d FROM weights").df()["d"][0]
AI = ["NVDA", "AVGO", "MU", "MSFT", "GOOGL", "GOOG", "AMZN", "META"]

w = con.sql(f"SELECT ticker, weight FROM weights WHERE date = '{DATE}'").df()
rets = con.sql(f"""
    SELECT date, ticker, ret FROM prices
    WHERE ticker IN (SELECT ticker FROM weights WHERE date = '{DATE}')
      AND date >= '2015-01-01' AND ret IS NOT NULL
""").df()

wide = rets.pivot(index="date", columns="ticker", values="ret").dropna(axis=1)
w = w[w["ticker"].isin(wide.columns)].set_index("ticker")["weight"]
w = w / w.sum()
wide = wide[w.index]

# The AI group's own return series, weighted within the group
ai_cols = [t for t in AI if t in wide.columns]
ai_w = w[ai_cols] / w[ai_cols].sum()
ai_ret = (wide[ai_cols] * ai_w).sum(axis=1)

SHOCK = -0.25

# Each company's sensitivity to the AI group
betas = {}
for t in wide.columns:
    betas[t] = np.polyfit(ai_ret, wide[t], 1)[0]
betas = pd.Series(betas)

direct = (w[ai_cols] * SHOCK).sum()
full = (w * betas * SHOCK).sum()

print(f"AI group weight:        {w[ai_cols].sum():.1%}")
print(f"Direct hit only:        {direct:.2%}")
print(f"With contagion:         {full:.2%}")
print(f"Contagion adds:         {full - direct:.2%}")
print(f"\nOn a EUR 10,000 index holding: EUR {abs(full) * 10000:,.0f} loss")

print("\nSensitivity to the AI group, largest non-AI holdings:")
non_ai = betas[~betas.index.isin(ai_cols)]
top = w[~w.index.isin(ai_cols)].nlargest(10).index
print(pd.DataFrame({"weight": w[top], "ai_beta": non_ai[top],
                    "implied_move": non_ai[top] * SHOCK}).round(3).to_string())



print("\nShock scale:")
for s in (-0.10, -0.15, -0.25, -0.40, -0.50):
    loss = (w * betas * s).sum()
    print(f"  AI group {s:+.0%}  ->  index {loss:+.2%}   (EUR {abs(loss)*10000:,.0f} on EUR 10,000)")

amp = (w * betas).sum()
print(f"\nAmplification factor: {amp:.3f}")
print(f"  Every 1% fall in the AI group costs the index {abs(amp):.2f}%")
print(f"  Reverse stress test: a 25% index loss needs an AI shock of {-0.25 / amp:.1%}")






idx_ret = (wide * w).sum(axis=1)
cut = idx_ret.abs().quantile(0.90)
stressed_days = idx_ret.abs() >= cut
print(f"\nStressed days: {stressed_days.sum()} of {len(idx_ret)} "
      f"(index moves beyond +/-{cut:.2%})")

s_betas = {}
for t in wide.columns:
    s_betas[t] = np.polyfit(ai_ret[stressed_days], wide[t][stressed_days], 1)[0]
s_betas = pd.Series(s_betas)

s_amp = (w * s_betas).sum()
print(f"\nNormal-conditions amplification:  {amp:.3f}")
print(f"Stressed amplification:           {s_amp:.3f}")

print("\nScenarios under stressed betas:")
for s in (-0.10, -0.25, -0.40):
    print(f"  AI group {s:+.0%}  ->  index {(w * s_betas * s).sum():+.2%}")
print(f"\nReverse test (stressed): a 25% index loss needs an AI shock of {-0.25 / s_amp:.1%}")

print("\nBiggest beta increases under stress (largest non-AI holdings):")
comp = pd.DataFrame({"weight": w, "normal": betas, "stressed": s_betas})
comp["change"] = comp["stressed"] - comp["normal"]
print(comp[~comp.index.isin(ai_cols)].nlargest(10, "weight").round(3).to_string())



ai_weight = w[ai_cols].sum()
rows = []
for s in (-0.05, -0.10, -0.15, -0.25, -0.40, -0.50):
    rows.append({"shock": s,
                 "naive_weight_only": ai_weight * s,
                 "index_normal": (w * betas * s).sum(),
                 "index_stressed": (w * s_betas * s).sum()})
pd.DataFrame(rows).to_csv("data/bi/stress_scenarios.csv", index=False)
pd.DataFrame({"weight": w, "beta_normal": betas, "beta_stressed": s_betas}) \
  .sort_values("weight", ascending=False).to_csv("data/bi/ai_sensitivity.csv")