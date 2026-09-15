import duckdb
import numpy as np
import pandas as pd
from scipy import stats

con = duckdb.connect("data/sp500.duckdb")
r = con.sql("SELECT ret FROM index_returns WHERE ret IS NOT NULL ORDER BY date").df()["ret"].values

losses = -r                                   # work with losses as positive numbers
u = np.percentile(losses, 95)                 # threshold: worst 5% of days
exc = losses[losses > u] - u                  # excesses over the threshold
n, nu_exc = len(losses), len(exc)
print(f"threshold: {u:.2%}  ({nu_exc} exceedances of {n} days)")

xi, loc, beta = stats.genpareto.fit(exc, floc=0)
print(f"shape xi:  {xi:.3f}")
print(f"scale beta:{beta:.4f}")

def evt_var(p):
    return u + (beta / xi) * (((n / nu_exc) * (1 - p)) ** (-xi) - 1)

def evt_es(p):
    v = evt_var(p)
    return (v + beta - xi * u) / (1 - xi)

print(f"\n{'level':>8} {'EVT VaR':>10} {'EVT ES':>10} {'historical':>12}")
for p in (0.975, 0.99, 0.995, 0.999):
    hist = -np.percentile(r, (1 - p) * 100)
    print(f"{p:>8.1%} {evt_var(p):>10.2%} {evt_es(p):>10.2%} {hist:>12.2%}")

print("\nHow often does a one-day fall of this size occur?")
for loss in (0.05, 0.10, 0.15, 0.20):
    if loss > u:
        prob = (nu_exc / n) * (1 + xi * (loss - u) / beta) ** (-1 / xi)
        print(f"  -{loss:.0%}: once every {1 / (prob * 252):,.1f} years")