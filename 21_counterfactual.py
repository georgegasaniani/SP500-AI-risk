import duckdb
import numpy as np
import pandas as pd

con = duckdb.connect("data/sp500.duckdb")
DATE = con.sql("SELECT MAX(date) AS d FROM weights").df()["d"][0]

rets = con.sql(f"""
    SELECT date, ticker, ret FROM prices
    WHERE ticker IN (SELECT ticker FROM weights WHERE date = '{DATE}')
      AND date >= '2024-01-01' AND ret IS NOT NULL
""").df()
wide = rets.pivot(index="date", columns="ticker", values="ret").dropna(axis=1)
cov = wide.cov().values * 252

w_now = con.sql(f"SELECT ticker, weight FROM weights WHERE date = '{DATE}'").df()
w_now = w_now[w_now["ticker"].isin(wide.columns)].set_index("ticker")["weight"]
w_now = (w_now / w_now.sum())[wide.columns]

w_eq = pd.Series(1 / len(wide.columns), index=wide.columns)

# 2015 weights, restricted to companies still present today
w_2015 = con.sql("""
    SELECT ticker, AVG(weight) AS weight FROM weights
    WHERE year(date) = 2015 GROUP BY 1
""").df().set_index("ticker")["weight"]
w_2015 = w_2015.reindex(wide.columns).fillna(0)
w_2015 = w_2015 / w_2015.sum()

def vol(w):
    v = w.values
    return np.sqrt(v @ cov @ v)

def eff_n(w):
    return 1 / (w ** 2).sum()

print(f"{'weighting':<28} {'volatility':>11} {'effective N':>12} {'top 10':>8}")
for label, w in [("today's actual", w_now),
                 ("equal-weighted", w_eq),
                 ("2015 weights, today's cov", w_2015)]:
    top10 = w.nlargest(10).sum()
    print(f"{label:<28} {vol(w):>11.2%} {eff_n(w):>12.1f} {top10:>8.1%}")

print(f"\nConcentration cost vs equal-weighted: "
      f"{vol(w_now) - vol(w_eq):+.2%} of annualised volatility "
      f"({vol(w_now) / vol(w_eq) - 1:+.1%} relative)")
print(f"Concentration cost vs 2015 weighting: "
      f"{vol(w_now) - vol(w_2015):+.2%} ({vol(w_now) / vol(w_2015) - 1:+.1%} relative)")


pd.DataFrame([
    {"weighting": "Current (2026)", "volatility": vol(w_now)},
    {"weighting": "Equal-weighted", "volatility": vol(w_eq)},
    {"weighting": "2015 weights", "volatility": vol(w_2015)},
]).to_csv("data/bi/counterfactual.csv", index=False)