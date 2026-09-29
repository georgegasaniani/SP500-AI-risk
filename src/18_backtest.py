"""In-sample VaR backtests: Kupiec (right number of exceptions) and Christoffersen
(exceptions not bunched together).

These use models fitted on the whole period, so they are descriptive only; the honest
out-of-sample test is 19_rolling_backtest.py.

Changes from the first version: likelihoods are computed in logs (multiplying thousands
of probabilities can underflow to zero), and Christoffersen's test no longer reports
FAIL when there are no back-to-back exceptions (that case is a pass).
"""
import duckdb
import numpy as np
import pandas as pd
from scipy import stats

con = duckdb.connect("data/sp500.duckdb")
df = con.sql("SELECT date, ret, garch_var FROM var_estimates ORDER BY date").df()
ALPHA = 0.025


def xlogy(x, y):
    """x * log(y), with 0 * log(0) = 0."""
    return 0.0 if x == 0 else x * np.log(y)


def kupiec(hits, alpha):
    n, x = len(hits), int(hits.sum())
    pi = x / n
    ll0 = xlogy(n - x, 1 - alpha) + xlogy(x, alpha)
    ll1 = xlogy(n - x, 1 - pi) + xlogy(x, pi)
    lr = -2 * (ll0 - ll1)
    return lr, 1 - stats.chi2.cdf(lr, 1)


def christoffersen(hits):
    h = hits.astype(int).values
    prev, cur = h[:-1], h[1:]
    n00 = int(((prev == 0) & (cur == 0)).sum()); n01 = int(((prev == 0) & (cur == 1)).sum())
    n10 = int(((prev == 1) & (cur == 0)).sum()); n11 = int(((prev == 1) & (cur == 1)).sum())
    p01 = n01 / max(n00 + n01, 1); p11 = n11 / max(n10 + n11, 1)
    p = (n01 + n11) / max(n00 + n01 + n10 + n11, 1)
    ll0 = xlogy(n00 + n10, 1 - p) + xlogy(n01 + n11, p)
    ll1 = xlogy(n00, 1 - p01) + xlogy(n01, p01) + xlogy(n10, 1 - p11) + xlogy(n11, p11)
    lr = -2 * (ll0 - ll1)
    return lr, 1 - stats.chi2.cdf(lr, 1)


static_hist = pd.Series(np.percentile(df["ret"], 2.5), index=df.index)
static_norm = pd.Series(df["ret"].mean() + stats.norm.ppf(ALPHA) * df["ret"].std(), index=df.index)
for label, var in [("GARCH-t (in-sample)", df["garch_var"]),
                   ("historical (static)", static_hist), ("normal (static)", static_norm)]:
    hits = df["ret"] < var
    lr_k, p_k = kupiec(hits, ALPHA)
    lr_c, p_c = christoffersen(hits)
    print(f"\n{label}")
    print(f"  exceptions: {hits.sum()} of {len(hits)} ({hits.mean():.2%}, expected {ALPHA:.1%})")
    print(f"  Kupiec         LR {lr_k:7.2f}  p {p_k:.4f}  {'PASS' if p_k > 0.05 else 'FAIL'}")
    print(f"  Christoffersen LR {lr_c:7.2f}  p {p_c:.4f}  {'PASS' if p_c > 0.05 else 'FAIL'}")
