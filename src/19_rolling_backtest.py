"""Out-of-sample VaR backtest with a rolling GARCH(1,1)-t model.

Every 20 trading days the model is refitted on the previous 1,000 days (about four
years; GARCH needs long samples to estimate persistence). Each day's forecast uses only
information available the day before:

    sigma2_t = omega + alpha * (r_{t-1} - mu)^2 + beta * sigma2_{t-1}

where sigma2_{t-1} is yesterday's CONDITIONAL variance, carried forward day by day
with the fitted parameters.

Fix from the first version: it used the window's plain sample variance in place of
sigma2_{t-1}. That forecast hardly reacts to volatility clusters, so it was not testing
a GARCH model. The window is 1,000 days (the README said 252).

Tests: Kupiec (number of exceptions), Christoffersen (exceptions not bunched), and the
Basel traffic light for 99% VaR over the last 250 days.
"""
import duckdb
import numpy as np
import pandas as pd
from arch import arch_model
from scipy import stats

from config import START

con = duckdb.connect("data/sp500.duckdb")
df = con.sql(f"SELECT date, ret FROM index_returns WHERE ret IS NOT NULL AND date >= '{START}' ORDER BY date").df()
r = pd.Series(df["ret"].values * 100)                 # percent: better-scaled for the optimiser

WINDOW, STEP = 1000, 20
rows, s2 = [], None
for t in range(WINDOW, len(r)):
    if (t - WINDOW) % STEP == 0:
        res = arch_model(r[t - WINDOW:t], vol="Garch", p=1, q=1, dist="t").fit(disp="off")
        mu, om = res.params["mu"], res.params["omega"]
        a, b, nu = res.params["alpha[1]"], res.params["beta[1]"], res.params["nu"]
        s2 = res.conditional_volatility.iloc[-1] ** 2  # yesterday's conditional variance
    eps = r.iloc[t - 1] - mu
    s2 = om + a * eps ** 2 + b * s2                    # forecast for day t, rolled forward daily
    sigma = np.sqrt(s2) / 100
    row = {"date": df["date"].iloc[t], "ret": r.iloc[t] / 100, "sigma": sigma, "nu": nu}
    for lvl in (0.025, 0.01, 0.005):
        q = stats.t.ppf(lvl, nu) / np.sqrt(nu / (nu - 2))
        row[f"var_{lvl}"] = mu / 100 + sigma * q
    rows.append(row)
bt = pd.DataFrame(rows)
print(f"out-of-sample days tested: {len(bt)} ({bt['date'].iloc[0]} to {bt['date'].iloc[-1]})")


def xlogy(x, y):
    return 0.0 if x == 0 else x * np.log(y)


def kupiec(hits, a):
    n, x = len(hits), int(hits.sum()); pi = x / n
    lr = -2 * ((xlogy(n - x, 1 - a) + xlogy(x, a)) - (xlogy(n - x, 1 - pi) + xlogy(x, pi)))
    return lr, 1 - stats.chi2.cdf(lr, 1)


def christoffersen(hits):
    h = hits.astype(int).values; p_, c_ = h[:-1], h[1:]
    n00, n01 = int(((p_ == 0) & (c_ == 0)).sum()), int(((p_ == 0) & (c_ == 1)).sum())
    n10, n11 = int(((p_ == 1) & (c_ == 0)).sum()), int(((p_ == 1) & (c_ == 1)).sum())
    p01, p11 = n01 / max(n00 + n01, 1), n11 / max(n10 + n11, 1)
    p = (n01 + n11) / max(len(c_), 1)
    ll0 = xlogy(n00 + n10, 1 - p) + xlogy(n01 + n11, p)
    ll1 = xlogy(n00, 1 - p01) + xlogy(n01, p01) + xlogy(n10, 1 - p11) + xlogy(n11, p11)
    lr = -2 * (ll0 - ll1)
    return lr, 1 - stats.chi2.cdf(lr, 1)


out = []
for lvl in (0.025, 0.01, 0.005):
    hits = bt["ret"] < bt[f"var_{lvl}"]
    lk, pk = kupiec(hits, lvl)
    lc, pc = christoffersen(hits)
    print(f"\n{1 - lvl:.1%} VaR: {int(hits.sum())} exceptions, expected {lvl * len(hits):.0f} "
          f"({hits.mean():.2%} vs {lvl:.1%})")
    print(f"  Kupiec LR {lk:.2f} p {pk:.4f} {'PASS' if pk > 0.05 else 'FAIL'} | "
          f"Christoffersen LR {lc:.2f} p {pc:.4f} {'PASS' if pc > 0.05 else 'FAIL'}")
    out.append({"level": f"{1 - lvl:.1%}", "exceptions": int(hits.sum()), "expected": round(lvl * len(hits)),
                "result": "Pass" if pk > 0.05 else "Fail",      # first four columns as in the first version
                "kupiec_p": round(pk, 4), "christoffersen": "Pass" if pc > 0.05 else "Fail",
                "christoffersen_p": round(pc, 4)})

last = bt.tail(250)
exc99 = int((last["ret"] < last["var_0.01"]).sum())
zone = "green" if exc99 <= 4 else ("yellow" if exc99 <= 9 else "red")
print(f"\nBasel traffic light (99% VaR, last 250 days): {exc99} exceptions -> {zone}")

con.execute("CREATE OR REPLACE TABLE rolling_backtest AS SELECT * FROM bt")
pd.DataFrame(out).to_csv("data/bi/backtest.csv", index=False)
