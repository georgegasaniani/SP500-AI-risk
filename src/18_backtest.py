import duckdb
import numpy as np
import pandas as pd
from scipy import stats

con = duckdb.connect("data/sp500.duckdb")
df = con.sql("SELECT date, ret, garch_var FROM var_estimates ORDER BY date").df()

ALPHA = 0.025

def kupiec(hits, alpha):
    n, x = len(hits), hits.sum()
    if x == 0:
        return np.nan, np.nan
    pi = x / n
    lr = -2 * (np.log((1 - alpha) ** (n - x) * alpha ** x)
               - np.log((1 - pi) ** (n - x) * pi ** x))
    return lr, 1 - stats.chi2.cdf(lr, 1)

def christoffersen(hits):
    h = hits.astype(int).values
    n00 = n01 = n10 = n11 = 0
    for i in range(1, len(h)):
        if h[i-1] == 0 and h[i] == 0: n00 += 1
        elif h[i-1] == 0 and h[i] == 1: n01 += 1
        elif h[i-1] == 1 and h[i] == 0: n10 += 1
        else: n11 += 1
    if n01 == 0 or n11 == 0:
        return np.nan, np.nan
    p01, p11 = n01 / (n00 + n01), n11 / (n10 + n11)
    p = (n01 + n11) / (n00 + n01 + n10 + n11)
    lr = -2 * (np.log((1 - p) ** (n00 + n10) * p ** (n01 + n11))
               - np.log((1 - p01) ** n00 * p01 ** n01 * (1 - p11) ** n10 * p11 ** n11))
    return lr, 1 - stats.chi2.cdf(lr, 1)

for label, var in [("GARCH-t", df["garch_var"]),
                   ("historical (static)", pd.Series(np.percentile(df["ret"], 2.5), index=df.index)),
                   ("normal (static)", pd.Series(df["ret"].mean() + stats.norm.ppf(ALPHA) * df["ret"].std(), index=df.index))]:
    hits = df["ret"] < var
    lr_k, p_k = kupiec(hits, ALPHA)
    lr_c, p_c = christoffersen(hits)
    print(f"\n{label}")
    print(f"  exceptions: {hits.sum()} of {len(hits)} "
          f"({hits.mean():.2%}, expected {ALPHA:.1%})")
    print(f"  Kupiec        LR {lr_k:7.2f}  p {p_k:.4f}  {'PASS' if p_k > 0.05 else 'FAIL'}")
    print(f"  Christoffersen LR {lr_c:7.2f}  p {p_c:.4f}  {'PASS' if p_c > 0.05 else 'FAIL'}")



 