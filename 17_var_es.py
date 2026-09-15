import duckdb
import numpy as np
import pandas as pd
from scipy import stats
from arch import arch_model

con = duckdb.connect("data/sp500.duckdb")
idx = con.sql("SELECT date, ret FROM index_returns WHERE ret IS NOT NULL ORDER BY date").df()
r = idx["ret"].values
ALPHA = 0.025

# 1. Historical
h_var = np.percentile(r, ALPHA * 100)
h_es = r[r <= h_var].mean()

# 2. Parametric normal
mu, sd = r.mean(), r.std()
z = stats.norm.ppf(ALPHA)
n_var = mu + z * sd
n_es = mu - sd * stats.norm.pdf(z) / ALPHA

print(f"{'method':<20} {'VaR 97.5%':>10} {'ES 97.5%':>10}")
print(f"{'historical':<20} {h_var:>10.2%} {h_es:>10.2%}")
print(f"{'parametric normal':<20} {n_var:>10.2%} {n_es:>10.2%}")

# 3. GARCH-t, one-day-ahead conditional
am = arch_model(pd.Series(r * 100), vol="Garch", p=1, q=1, dist="t")
res = am.fit(disp="off")
nu = res.params["nu"]
sigma = res.conditional_volatility / 100

t_q = stats.t.ppf(ALPHA, nu) / np.sqrt(nu / (nu - 2))       # standardised t quantile
g_var = res.params["mu"] / 100 + sigma * t_q

pdf = stats.t.pdf(stats.t.ppf(ALPHA, nu), nu)
es_mult = -(nu + stats.t.ppf(ALPHA, nu) ** 2) / (nu - 1) * pdf / ALPHA / np.sqrt(nu / (nu - 2))
g_es = res.params["mu"] / 100 + sigma * es_mult

print(f"{'GARCH-t (average)':<20} {g_var.mean():>10.2%} {g_es.mean():>10.2%}")
print(f"{'GARCH-t (today)':<20} {g_var.iloc[-1]:>10.2%} {g_es.iloc[-1]:>10.2%}")
print(f"{'GARCH-t (Mar 2020)':<20} {g_var.min():>10.2%} {g_es.min():>10.2%}")

print(f"\nStudent-t degrees of freedom: {nu:.2f}")
print(f"Historical ES is {h_es / n_es:.2f}x the normal model's")

idx["garch_var"] = g_var.values
con.execute("CREATE OR REPLACE TABLE var_estimates AS SELECT * FROM idx")


print("\n--- quantile check ---")
print(f"nu: {nu:.2f}")
print(f"t quantile raw:  {stats.t.ppf(ALPHA, nu):.4f}")
print(f"standardised:    {t_q:.4f}")
print(f"normal equiv:    {stats.norm.ppf(ALPHA):.4f}")
print(f"ES multiplier:   {es_mult:.4f}")