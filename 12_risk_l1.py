import duckdb
import numpy as np
import pandas as pd
from scipy import stats


con=duckdb.connect("data/sp500.duckdb")
idx=con.sql("SELECT date, ret FROM index_returns WHERE ret IS NOT NULL ORDER BY date").df()
r=idx["ret"].values

print(f"days: {len(r)}")
print(f"mean daily:      {r.mean():.5f}")
print(f"daily vol:       {r.std():.5f}")
print(f"annualised vol:  {r.std() * np.sqrt(252):.4f}")
print(f"skewness:        {stats.skew(r):.3f}")
print(f"excess kurtosis: {stats.kurtosis(r):.3f}")

jb, p =stats.jarque_bera(r)
print(f"Jarque-Bera:       {jb:.0f}    (p={p:.2e})")

sd=r.std()
for k in (3,4,5):
    actual = (r< -k * sd).sum()
    excpected=stats.norm.cdf(-k)*len(r)
    print(f"days below  -{k}  sd: actual {actual}, normal predicts {excpected:.2f}")

print("\nWorst 5 days:")
print(idx.nsmallest(5,"ret").to_string(index=False))