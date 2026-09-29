import duckdb
import numpy as np
import pandas as pd
from scipy import stats

con = duckdb.connect("data/sp500.duckdb")

r = con.sql("SELECT ret FROM index_returns WHERE ret IS NOT NULL AND date >= '2015-01-01'").df()["ret"].values
asof = con.sql("SELECT MAX(date) AS d FROM weights").df()["d"][0]

roll = con.sql("SELECT * FROM rolling_risk WHERE window_days = 252 ORDER BY date").df()
latest_roll = roll.iloc[-1]

conc = con.sql("""
    SELECT effective_n, top10, top5, n_stocks FROM concentration
    ORDER BY date DESC LIMIT 1
""").df().iloc[0]

metrics = [
    {"metric": "Annualised volatility (%)", "value": r.std() * np.sqrt(252) * 100},
    {"metric": "VaR 97.5%, 1-day (%)", "value": np.percentile(r, 2.5) * 100},
    {"metric": "Expected Shortfall 97.5% (%)", "value": r[r <= np.percentile(r, 2.5)].mean() * 100},
    {"metric": "Top 10 weight (%)", "value": latest_roll["top10_weight"] * 100},
    {"metric": "Top 10 risk contribution (%)", "value": latest_roll["top10_risk"] * 100},
    {"metric": "Effective number of constituents", "value": conc["effective_n"]},
]
pd.DataFrame(metrics).to_csv("data/bi/summary_metrics.csv", index=False)
meta = con.sql("""SELECT MIN(date) AS start, MAX(date) AS last, ANY_VALUE(method) AS series
                   FROM index_returns WHERE ret IS NOT NULL AND date >= '2015-01-01'""").df().iloc[0]
pd.DataFrame([{"asof": asof, "start": meta.start, "days": len(r), "index_series": meta.series,
               "index_last_day": meta["last"]}]).to_csv("data/bi/report_meta.csv", index=False)

print(pd.DataFrame(metrics).to_string(index=False))