import duckdb
import pandas as pd
from pathlib import Path

con = duckdb.connect("data/sp500.duckdb")
out = Path("data/bi")
out.mkdir(parents=True, exist_ok=True)


con.sql("""
    SELECT date, n_stocks, top10, top5, effective_n
    FROM concentration ORDER BY date
""").df().to_csv(out / "concentration.csv", index=False)


con.sql("""
    SELECT ticker, mktcap, weight FROM weights
    WHERE date = (SELECT MAX(date) FROM weights) ORDER BY weight DESC
""").df().to_csv(out / "weights_today.csv", index=False)


con.sql("SELECT date, ewma_vol, garch_vol FROM volatility ORDER BY date").df() \
   .to_csv(out / "volatility.csv", index=False)


A = con.sql("SELECT * FROM fundamentals_annual ORDER BY ticker, year").df()
A["capex_pct_revenue"] = A["capex"] / A["revenue"]
A["dep_over_capex"] = A["depreciation"] / A["capex"]
A.to_csv(out / "fundamentals_annual.csv", index=False)

HYPER = ["MSFT", "AMZN", "GOOGL", "META"]
h = A[A["ticker"].isin(HYPER)].groupby("year")[["revenue", "capex", "depreciation"]].sum()
nv = A[A["ticker"] == "NVDA"].set_index("year")["revenue"]
link = pd.DataFrame({"hyper_capex": h["capex"], "nvda_revenue": nv}).dropna()
link = link[link["hyper_capex"] > 0]
link["nvda_share_of_capex"] = link["nvda_revenue"] / link["hyper_capex"]
link.reset_index().to_csv(out / "capex_nvda_link.csv", index=False)

pd.DataFrame([
    {"weighting": "Current (2026)", "volatility": 0.1728},
    {"weighting": "Equal-weighted", "volatility": 0.1437},
    {"weighting": "2015 weights", "volatility": 0.1251},
]).to_csv(out / "counterfactual.csv", index=False)
con.sql('SELECT * FROM fundamentals_quarterly ORDER BY ticker, "end"').df() \
   .to_csv(out / "fundamentals_quarterly.csv", index=False)

print("exported:", [f.name for f in out.iterdir()])