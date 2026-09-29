import duckdb
import pandas as pd
from pathlib import Path

con = duckdb.connect("data/sp500.duckdb")
out = Path("data/bi")
out.mkdir(parents=True, exist_ok=True)


con.sql("""
    SELECT date, n_stocks, top10, top5, effective_n, ai_weight
    FROM concentration ORDER BY date
""").df().to_csv(out / "concentration.csv", index=False)

# The rebuilt index against the real one, year by year (11_validate_spy.py)
con.sql("""
    -- only the days both series have (the official series starts a day later than the
    -- rebuilt one, which once put an extra day into 2009's comparison)
    WITH j AS (SELECT year(o.date) AS year, o.ret AS o_ret, r.ret AS r_ret, o.method, r.coverage
               FROM index_returns o JOIN index_rebuilt r ON CAST(r.date AS DATE) = CAST(o.date AS DATE))
    SELECT year, ANY_VALUE(method) AS series, EXP(SUM(LN(1 + o_ret))) - 1 AS official,
           EXP(SUM(LN(1 + r_ret))) - 1 AS rebuilt,
           (EXP(SUM(LN(1 + r_ret))) - 1) - (EXP(SUM(LN(1 + o_ret))) - 1) AS difference,
           AVG(coverage) AS weight_with_return
    FROM j GROUP BY 1 ORDER BY 1
""").df().to_csv(out / "index_check.csv", index=False)


# Same first three columns as the first version (the Power BI report reads them by
# position). mktcap: price x SEC total shares, where the SEC has a share count; weight:
# the real index weight. Added at the end: company name, sector, and the fund's holding.
con.sql("""
    SELECT w.ticker, m.mktcap, w.weight, h.name, h.sector, h.market_value AS fund_market_value
    FROM weights w
    LEFT JOIN holdings h USING (date, ticker)
    LEFT JOIN mktcap_sec m USING (date, ticker)
    WHERE w.date = (SELECT MAX(date) FROM weights) ORDER BY w.weight DESC
""").df().to_csv(out / "weights_today.csv", index=False)


con.sql("SELECT date, ewma_vol, garch_vol FROM volatility ORDER BY date").df() \
   .to_csv(out / "volatility.csv", index=False)


A = con.sql("SELECT * FROM fundamentals_annual ORDER BY ticker, year").df()
A["capex_pct_revenue"] = A["capex"] / A["revenue"]
A["dep_over_capex"] = A["depreciation"] / A["capex"]
A.to_csv(out / "fundamentals_annual.csv", index=False)

# calendar-year aligned (built in 23_capex_analysis.py); the old version compared
# Nvidia's fiscal year (ending in January) with the hyperscalers' following calendar year
con.sql("SELECT * FROM capex_link ORDER BY year").df().to_csv(out / "capex_nvda_link.csv", index=False)

# counterfactual.csv is written by 21_counterfactual.py (it was overwritten here with fixed numbers)
con.sql("""SELECT date, n_stocks, top10, top5, effective_n, ai_weight FROM concentration_sec ORDER BY date""").df() \
   .to_csv(out / "concentration_reconstructed.csv", index=False)
con.sql('SELECT * FROM fundamentals_quarterly ORDER BY ticker, "end"').df() \
   .to_csv(out / "fundamentals_quarterly.csv", index=False)

print("exported:", [f.name for f in out.iterdir()])