import duckdb
import numpy as np
import pandas as pd
from scipy import stats

con = duckdb.connect("data/sp500.duckdb")
r = con.sql("SELECT ret FROM index_returns WHERE ret IS NOT NULL").df()["ret"].values
sd = r.std()

# Fat tails: observed vs normal-model expectation
rows = []
for k in (2, 3, 4, 5):
        rows.append({"threshold": f"-{k} sd",
                 "daily_return": -k * sd,
                 "observed": int((r < -k * sd).sum()),
                 "normal_model": round(stats.norm.cdf(-k) * len(r), 2)})
pd.DataFrame(rows).to_csv("data/bi/tail_counts.csv", index=False)


# EVT return periods
losses = -r
u = np.percentile(losses, 95)
exc = losses[losses > u] - u
xi, _, beta = stats.genpareto.fit(exc, floc=0)
rows = []
for loss in (0.05, 0.075, 0.10, 0.15, 0.20):
    p = (len(exc) / len(losses)) * (1 + xi * (loss - u) / beta) ** (-1 / xi)
    rows.append({"daily_fall": loss, "years_between": 1 / (p * 252)})
pd.DataFrame(rows).to_csv("data/bi/evt_return_periods.csv", index=False)


print("exported 4 methodology files")