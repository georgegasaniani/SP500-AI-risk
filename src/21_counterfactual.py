"""How much of today's index volatility comes from concentration?

Same covariance (daily returns since 2024), three sets of weights:
  - today's real index weights
  - equal weights
  - the 2015 weights of the companies still in the index

Changes from the first version:
  - companies with a few missing days are kept (pairwise covariance); only companies
    with returns on fewer than 90% of the days are left out, and their weight is printed.
    The first version dropped every company with any gap.
  - 2015 weights: renamed companies are matched to today's ticker (FB -> META, ANTM -> ELV),
    so Meta is part of the 2015 weighting; each company's 2015 weight is its average over
    all 2015 trading days (0 on days before it joined), not only the days it was present.
"""
import duckdb
import numpy as np
import pandas as pd

from config import MIN_COVERAGE

con = duckdb.connect("data/sp500.duckdb")
DATE = con.sql("SELECT MAX(date) AS d FROM weights").df()["d"][0]
w_all = con.sql(f"SELECT ticker, weight FROM weights WHERE date = '{DATE}'").df().set_index("ticker")["weight"]
rets = con.sql(f"""
    SELECT date, ticker, ret FROM prices
    WHERE ticker IN (SELECT ticker FROM weights WHERE date = '{DATE}')
      AND date >= '2024-01-01' AND ret IS NOT NULL
""").df()
wide = rets.pivot(index="date", columns="ticker", values="ret").sort_index()
ok = wide.columns[wide.notna().mean() >= MIN_COVERAGE]
left_out = w_all.drop(ok, errors="ignore")
wide = wide[ok]
cov = wide.cov().values * 252                   # pairwise
print(f"covariance: {len(wide)} days since 2024, {len(ok)} companies; "
      f"left out (too little history): {len(left_out)} = {left_out.sum():.2%} of today's weight")

w_now = w_all.reindex(ok).fillna(0)
w_now = w_now / w_now.sum()
w_eq = pd.Series(1 / len(ok), index=ok)

alias = pd.read_csv("reference/ticker_aliases.csv").set_index("ticker")["price_ticker"].to_dict()
w15 = con.sql("""SELECT ticker, SUM(weight) / (SELECT COUNT(DISTINCT date) FROM weights WHERE year(date) = 2015)
                        AS weight
                 FROM weights WHERE year(date) = 2015 GROUP BY 1""").df()
w15["ticker"] = w15["ticker"].map(lambda t: alias.get(t, t))
w15 = w15.groupby("ticker")["weight"].sum()
kept = w15.reindex(ok).fillna(0)
print(f"2015 weights: companies still in the index today carry {kept.sum():.1%} of the 2015 index")
w_2015 = kept / kept.sum()


def vol(w):
    v = w.values
    return np.sqrt(v @ cov @ v)


def eff_n(w):
    return 1 / (w ** 2).sum()


print(f"\n{'weighting':<28} {'volatility':>11} {'effective N':>12} {'top 10':>8}")
for label, w in [("today's actual", w_now), ("equal-weighted", w_eq), ("2015 weights, today's cov", w_2015)]:
    print(f"{label:<28} {vol(w):>11.2%} {eff_n(w):>12.1f} {w.nlargest(10).sum():>8.1%}")

print(f"\nConcentration cost vs equal-weighted: {vol(w_now) - vol(w_eq):+.2%} of annualised volatility "
      f"({vol(w_now) / vol(w_eq) - 1:+.1%} relative)")
print(f"Concentration cost vs 2015 weighting: {vol(w_now) - vol(w_2015):+.2%} "
      f"({vol(w_now) / vol(w_2015) - 1:+.1%} relative)")

pd.DataFrame([
    {"weighting": f"Current ({pd.Timestamp(DATE).year})", "volatility": vol(w_now), "effective_n": eff_n(w_now),
     "top10": w_now.nlargest(10).sum()},
    {"weighting": "Equal-weighted", "volatility": vol(w_eq), "effective_n": eff_n(w_eq), "top10": w_eq.nlargest(10).sum()},
    {"weighting": "2015 weights", "volatility": vol(w_2015), "effective_n": eff_n(w_2015),
     "top10": w_2015.nlargest(10).sum()},
]).to_csv("data/bi/counterfactual.csv", index=False)
