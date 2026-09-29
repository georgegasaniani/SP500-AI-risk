"""Stress test: what a fall in the AI group costs an index investor.

Each company's beta to the AI group (the group's own weighted return) gives its
expected move when the group falls: E[r_i | AI falls x] = beta_i * x. Summing
weight x beta over the index gives the index loss.

Changes from the first version:
  - real index weights (fund holdings)
  - each company's beta uses all of its own history since START (at least ~2 years),
    instead of dropping every company with any missing day (which removed everything
    listed after 2015)
  - "stressed" betas are estimated on the days the AI GROUP made its biggest moves.
    The first version picked days by the INDEX move; because the index contains the
    common market factor, that selection raises every stock's beta mechanically, even
    when nothing about the relationship changes. Both versions are printed.
"""
import duckdb
import numpy as np
import pandas as pd

from config import AI, START

con = duckdb.connect("data/sp500.duckdb")
DATE = con.sql("SELECT MAX(date) AS d FROM weights").df()["d"][0]
w = con.sql(f"SELECT ticker, weight FROM weights WHERE date = '{DATE}'").df().set_index("ticker")["weight"]
rets = con.sql(f"""SELECT date, ticker, ret FROM prices WHERE ret IS NOT NULL AND date >= '{START}'
                   AND ticker IN (SELECT ticker FROM weights WHERE date = '{DATE}')""").df()
wide = rets.pivot(index="date", columns="ticker", values="ret").sort_index()

# The AI group's own return, weighted within the group with today's weights
ai_cols = [t for t in AI if t in wide.columns and t in w.index]
ai_w = w[ai_cols] / w[ai_cols].sum()
ai_ret = (wide[ai_cols].fillna(0) * ai_w).sum(axis=1)
idx_ret = con.sql(f"SELECT date, ret FROM index_returns WHERE date >= '{START}'").df().set_index("date")["ret"]


def betas(mask=None, min_obs=500):
    out = {}
    for t in wide.columns:
        y = wide[t]
        ok = y.notna() if mask is None else (y.notna() & mask)
        if ok.sum() >= (min_obs if mask is None else min_obs // 10):
            out[t] = np.polyfit(ai_ret[ok], y[ok], 1)[0]
    return pd.Series(out)


b = betas()
covered = w.reindex(b.index).dropna()
print(f"companies with a beta: {len(b)} ({covered.sum():.1%} of index weight); "
      f"recent listings without enough history get the index-weighted average beta")
wb = w.copy()
beta_full = b.reindex(w.index)
# Companies with too little history (recent listings): use the index-weighted average beta
beta_full = beta_full.fillna((b * covered).sum() / covered.sum())

SHOCK = -0.25
amp = (wb * beta_full).sum()
direct = w[ai_cols].sum() * SHOCK
print(f"\nAI group weight:        {w[ai_cols].sum():.1%}")
print(f"Direct hit only:        {direct:.2%}")
print(f"With spillover:         {amp * SHOCK:.2%}   (amplification {amp:.3f})")

# Stressed betas: the 10% of days with the largest AI-group moves (up or down)
big_ai = ai_ret.abs() >= ai_ret.abs().quantile(0.90)
s_b = betas(big_ai).reindex(w.index).fillna(beta_full)
s_amp = (wb * s_b).sum()
# For comparison: the first version's selection, the 10% largest INDEX moves
big_idx = idx_ret.reindex(wide.index).abs() >= idx_ret.abs().quantile(0.90)
s_b_old = betas(big_idx.fillna(False)).reindex(w.index).fillna(beta_full)

print(f"\nAmplification, all days:                    {amp:.3f}")
print(f"Amplification, big AI-group days (correct):  {s_amp:.3f}")
print(f"Amplification, big index days (old method):  {(wb * s_b_old).sum():.3f}")

print("\nScenarios:")
rows = []
for s in (-0.05, -0.10, -0.15, -0.25, -0.40, -0.50):
    rows.append({"shock": s, "naive_weight_only": w[ai_cols].sum() * s,
                 "index_normal": amp * s, "index_stressed": s_amp * s})
    print(f"  AI group {s:+.0%} -> index {amp * s:+.2%} (stressed {s_amp * s:+.2%})")
print(f"\nReverse stress test: a 25% index loss needs an AI-group fall of {-0.25 / amp:.1%} "
      f"({-0.25 / s_amp:.1%} with stressed betas)")

comp = pd.DataFrame({"weight": w, "beta_normal": beta_full, "beta_stressed": s_b,
                     "beta_stressed_old_method": s_b_old}).sort_values("weight", ascending=False)
print("\nLargest non-AI holdings:")
print(comp[~comp.index.isin(ai_cols)].head(10).round(3).to_string())

pd.DataFrame(rows).to_csv("data/bi/stress_scenarios.csv", index=False)
comp.index.name = None                      # same layout as the first version's file (Power BI)
comp.to_csv("data/bi/ai_sensitivity.csv")
