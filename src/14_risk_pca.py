import duckdb
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA


con=duckdb.connect("data/sp500.duckdb")

AI = ["NVDA", "AVGO", "MU", "MSFT", "GOOGL", "AMZN", "META"]

q = f"""
    SELECT date, ticker, ret FROM prices
    WHERE ticker IN ({",".join(f"'{t}'" for t in AI)})
      AND date >= '2015-01-01' AND ret IS NOT NULL
"""
print(q)
df = con.sql(q).df()


wide=df.pivot(index="date",columns="ticker",values="ret").dropna()
print(f"{len(wide)} days, {wide.shape[1]} stocks")

print("\nCorrelation matrix:")
print(wide.corr().round(2))

X = (wide - wide.mean()) / wide.std()      
p = PCA().fit(X)
print("\nVariance explained by each component:")
for i, v in enumerate(p.explained_variance_ratio_, 1):
    print(f"  PC{i}: {v:.1%}")

print("\nPC1 loadings (how much each stock moves with the common factor):")
print(pd.Series(p.components_[0], index=wide.columns).round(3).sort_values(ascending=False))

mkt = con.sql("""
    SELECT date, ret AS mkt FROM index_returns
    WHERE ret IS NOT NULL AND date >= '2015-01-01'
""").df()
mkt["date"] = pd.to_datetime(mkt["date"])

wide2 = wide.copy()
wide2.index = pd.to_datetime(wide2.index)
joined = wide2.join(mkt.set_index("date")["mkt"], how="inner").dropna()

resid = pd.DataFrame(index=joined.index)
betas = {}
for t in AI:
    b = np.polyfit(joined["mkt"], joined[t], 1)      # slope, intercept
    betas[t] = b[0]
    resid[t] = joined[t] - (b[0] * joined["mkt"] + b[1])

print("\nMarket betas:")
print(pd.Series(betas).round(2).sort_values(ascending=False))

R = (resid - resid.mean()) / resid.std()
p2 = PCA().fit(R)
print("\nVariance explained, market-adjusted:")
for i, v in enumerate(p2.explained_variance_ratio_[:4], 1):
    print(f"  PC{i}: {v:.1%}")

print("\nPC1 loadings, market-adjusted:")
print(pd.Series(p2.components_[0], index=resid.columns).round(3).sort_values(ascending=False))

print(f"\nAverage residual correlation: {resid.corr().values[np.triu_indices(7, 1)].mean():.2f}")


pd.DataFrame({
    "component": [f"PC{i}" for i in range(1, 4)],
    "raw": p.explained_variance_ratio_[:3],
    "market_adjusted": p2.explained_variance_ratio_[:3],
}).to_csv("data/bi/pca_variance.csv", index=False)