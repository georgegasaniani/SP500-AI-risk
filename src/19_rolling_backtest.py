import duckdb
import numpy as np
import pandas as pd
from scipy import stats
from arch import arch_model

con = duckdb.connect("data/sp500.duckdb")
df = con.sql("SELECT date, ret FROM index_returns WHERE ret IS NOT NULL ORDER BY date").df()
r = pd.Series(df["ret"].values * 100)

WINDOW, STEP = 1000, 20
rows = []
params = None

for t in range(WINDOW, len(r)):
    if (t - WINDOW) % STEP == 0:                       # refit monthly
        res = arch_model(r[t - WINDOW:t], vol="Garch", p=1, q=1, dist="t").fit(disp="off")
        params = res.params
        print(f"  refit at day {t} ({df['date'].iloc[t]}), nu={params['nu']:.2f}")

    # one-step-ahead variance from the last fitted parameters
    window = r[t - WINDOW:t]
    resid = window - params["mu"]
    var_t = params["omega"] + params["alpha[1]"] * resid.iloc[-1] ** 2 \
            + params["beta[1]"] * window.var()
    sigma = np.sqrt(var_t) / 100
    nu = params["nu"]

    row = {"date": df["date"].iloc[t], "ret": r.iloc[t] / 100, "sigma": sigma, "nu": nu}
    for a in (0.025, 0.01, 0.005):
        q = stats.t.ppf(a, nu) / np.sqrt(nu / (nu - 2))
        row[f"var_{a}"] = params["mu"] / 100 + sigma * q
    rows.append(row)

bt = pd.DataFrame(rows)
print(f"\nout-of-sample days tested: {len(bt)}")

for a in (0.025, 0.01, 0.005):
    hits = bt["ret"] < bt[f"var_{a}"]
    n, x, exp = len(hits), hits.sum(), a * len(hits)
    pi = x / n
    lr = -2 * (np.log((1 - a) ** (n - x) * a ** x) - np.log((1 - pi) ** (n - x) * pi ** x))
    p = 1 - stats.chi2.cdf(lr, 1)
    print(f"\n{1-a:.1%} level: {x} exceptions, expected {exp:.0f} ({pi:.2%} vs {a:.1%})")
    print(f"  Kupiec LR {lr:.2f}, p {p:.4f}  {'PASS' if p > 0.05 else 'FAIL'}")

con.execute("CREATE OR REPLACE TABLE rolling_backtest AS SELECT * FROM bt")


rows = []
for a in (0.025, 0.01, 0.005):
    hits = bt["ret"] < bt[f"var_{a}"]
    n, x, exp = len(hits), int(hits.sum()), a * len(hits)
    pi = x / n
    lr = -2 * (np.log((1 - a) ** (n - x) * a ** x) - np.log((1 - pi) ** (n - x) * pi ** x))
    p = 1 - stats.chi2.cdf(lr, 1)
    rows.append({"level": f"{1-a:.1%}", "exceptions": x, "expected": round(exp),
                 "result": "Pass" if p > 0.05 else "Fail"})
pd.DataFrame(rows).to_csv("data/bi/backtest.csv", index=False)