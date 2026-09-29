"""Index returns for the risk models, and the checks that the rebuilt index matches reality.

index_returns   (used by every index-level risk script: 12, 13, 14, 16, 17, 19, 20, 26, 27)
    The S&P 500 Total Return index (^SP500TR): the real index, dividends included. If it
    is missing, the S&P 500 price index (^GSPC); failing both, the rebuilt index below.
    Column `method` says which. The first version used its own rebuild from SEC share
    counts here, which missed companies (Meta 2015-22, Exxon, Disney...) and drifted.

index_rebuilt
    Yesterday's real weights (fund holdings, bridged in the 2017 gap) times today's
    company returns (06_merge_prices.py). Risk shares, betas and stress tests are built
    from these same weights and returns, so matching the real index tests them.

index_holdings
    The change in value of the previous day's fund holdings at the fund's own prices.
    Tests the holdings themselves: it should match the S&P 500 price index almost exactly
    (differences on spin-off days, when the spun-off shares are not in the previous file).

index_returns_sec
    The first version's reconstruction (SEC share counts x membership list), for comparison.
"""
import duckdb
import numpy as np
import pandas as pd

from common import split_factor

con = duckdb.connect("data/sp500.duckdb")


def weighted_return(weights_table):
    """Return on day t = sum of w(t-1) x r(t) over the companies held at t-1.
    (The first version only used companies still in the weights table on day t, so a
    company's return on the day it left the index was lost.)"""
    return con.sql(f"""
        WITH d AS (SELECT DISTINCT date FROM {weights_table}),
             p AS (SELECT date, LAG(date) OVER (ORDER BY date) AS prev FROM d)
        SELECT CAST(p.date AS DATE) AS date, SUM(w.weight * r.ret) / SUM(w.weight) AS ret,
               SUM(w.weight) AS coverage
        FROM p JOIN {weights_table} w ON w.date = p.prev
               JOIN prices r ON r.ticker = w.ticker AND r.date = p.date
        WHERE r.ret IS NOT NULL
        GROUP BY 1 ORDER BY 1""").df()


rebuilt = weighted_return("weights")
sec = weighted_return("weights_sec")

# Buy-and-hold value of the previous file's holdings, at the fund's prices
h = con.sql("""SELECT h.date, h.ticker, h.price, h.quantity, h.market_value, d.flow
               FROM holdings h JOIN ivv_days d USING (date)""").df().sort_values(["ticker", "date"])
g = h.groupby("ticker")
h["prev_date"], h["prev_mv"] = g["date"].shift(), g["market_value"].shift()
h["pr"] = h["price"] / g["price"].shift()
h["k"] = split_factor(h["quantity"] / g["quantity"].shift() / h["flow"], h["pr"])
file_days = np.sort(h["date"].unique())
prev_file = pd.Series(file_days[:-1], index=file_days[1:])
h = h[(h["prev_date"] == h["date"].map(prev_file)) & ((h["date"] - h["prev_date"]).dt.days <= 5)]
hold_ret = (h.assign(v=h["prev_mv"] * h["pr"] * h["k"]).groupby("date")[["v", "prev_mv"]].sum()
              .pipe(lambda x: x["v"] / x["prev_mv"] - 1).rename("ret").reset_index())
hold_ret["date"] = pd.to_datetime(hold_ret["date"]).dt.date

bench = con.sql("""SELECT CAST(date AS DATE) AS date, ticker, ret FROM prices
                   WHERE ticker IN ('^SP500TR', '^GSPC', 'SPY') AND ret IS NOT NULL""").df()
bench = bench.pivot(index="date", columns="ticker", values="ret")

# ------------------------------------------------ index_returns
for tk, method, label in [("^SP500TR", "sp500_total_return", "S&P 500 Total Return index (^SP500TR)"),
                          ("^GSPC", "sp500_price", "S&P 500 price index (^GSPC), no dividends"),
                          (None, "rebuilt", "rebuilt from real weights (the official index was not downloaded)")]:
    if tk is None or (tk in bench.columns and bench[tk].notna().sum() > 1000):
        break
if tk:
    idx = bench[[tk]].dropna().rename(columns={tk: "ret"}).reset_index()
else:
    idx = rebuilt[["date", "ret"]].copy()
idx["method"] = method
# (data frame names differ from every table name: DuckDB would read a same-named table instead)
con.execute("CREATE OR REPLACE TABLE index_returns AS SELECT * FROM idx ORDER BY date")
con.execute("CREATE OR REPLACE TABLE index_rebuilt AS SELECT * FROM rebuilt")
con.execute("CREATE OR REPLACE TABLE index_holdings AS SELECT * FROM hold_ret")
con.execute("CREATE OR REPLACE TABLE index_returns_sec AS SELECT * FROM sec")
print(f"Index returns for the risk models: {label}, {idx['date'].min()} to {idx['date'].max()} "
      f"({len(idx):,} days)")


# ------------------------------------------------ checks
def compare(a, b, a_name, b_name, since="2009-01-01"):
    """Yearly compounded returns of two daily series over the days both have."""
    j = (pd.DataFrame({"a": a.set_index("date")["ret"]}).join(b.set_index("date")["ret"].rename("b"), how="inner")
           .dropna())
    j = j[pd.to_datetime(j.index) >= pd.Timestamp(since)]
    if j.empty:
        return None, None
    yr = pd.to_datetime(j.index).year
    y = (1 + j).groupby(yr).prod() - 1
    y = (y * 100).round(2).rename(columns={"a": a_name, "b": b_name})
    y[f"{b_name} diff"] = (y[b_name] - y[a_name]).round(2)
    te = (j["b"] - j["a"]).std() * np.sqrt(252)
    return y, te


out = []
checks = [("^SP500TR", rebuilt, "sp500_tr", "rebuilt", "rebuilt index vs S&P 500 Total Return"),
          ("^GSPC", hold_ret, "sp500_price", "holdings", "fund holdings vs S&P 500 price index"),
          ("SPY", sec, "spy_tr", "sec_rebuild", "first version's SEC rebuild vs SPY (total return)")]
te_lines = []
for tk, series, a_name, b_name, label in checks:
    if tk not in bench.columns or series.empty:
        te_lines.append(f"  {label}: not available ({tk} missing)")
        continue
    y, te = compare(bench[[tk]].dropna().rename(columns={tk: "ret"}).reset_index(), series, a_name, b_name)
    if y is None:
        te_lines.append(f"  {label}: no overlapping days")
        continue
    out.append(y)
    te_lines.append(f"  {label}: {te:.2%} a year")
if out:
    print("\nYearly returns, %:")
    print(pd.concat(out, axis=1).to_string())
print("\nTracking error (annualised standard deviation of the daily differences):")
print("\n".join(te_lines))
print(f"\nrebuilt index: lowest share of yesterday's weight with a return today "
      f"{rebuilt['coverage'].min():.2%} ({rebuilt.loc[rebuilt['coverage'].idxmin(), 'date']})")
