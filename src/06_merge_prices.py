"""Daily prices and returns: one checked source per company and day.

Sources, in order of preference:
  yf2     fresh Yahoo download (00_fetch_data.py)
  yf      original Yahoo download (02_prices_yf.py)
  tiingo  Tiingo download (04_prices_tiingo.py), mainly delisted companies
  ivv     the fund's own recorded closing price, for days the company was held

What changed from the first version, and why:
  1. Returns are computed inside ONE source per ticker. The old version computed them
     over mixed Yahoo and Tiingo rows, so on overlapping days the "return" compared two
     data sources instead of two days (Dell, Dow, IHS Markit and others were affected).
  2. Renamed companies use their successor's price history (FB -> META, reference/
     ticker_aliases.csv), because Yahoo keeps the history under the new ticker only.
  3. On every day a company was in the index, the external price must agree with the
     fund's own recorded price (within 3%). A ticker later reused by a different company
     fails this check and is replaced by the fund's price for those days.
  4. Where no external source agrees, the return comes from the fund's recorded prices,
     adjusted for stock splits.
  5. Every company the fund ever held gets its price history from outside its time in the
     index too (from the source that matched while it was held), so that covariance
     windows at past dates and betas have full histories.
"""
import duckdb
import numpy as np
import pandas as pd

from common import split_factor

con = duckdb.connect("data/sp500.duckdb")
tables = set(con.sql("SHOW TABLES").df()["name"])
PRIORITY = {"yf2": 0, "yf": 1, "tiingo": 2}


def yahoo(table, source):
    """Yahoo 'close' is split-adjusted. Undo it (multiply by every later split) to get
    the price that actually traded, which is what the fund records."""
    df = con.sql(f"""
        SELECT CAST(date AS DATE) AS date, ticker, close, adj_close,
               EXP(SUM(LN(CASE WHEN stock_splits > 0 THEN stock_splits ELSE 1 END))
                   OVER (PARTITION BY ticker ORDER BY date
                         ROWS BETWEEN 1 FOLLOWING AND UNBOUNDED FOLLOWING)) AS later_splits
        FROM {table} WHERE close IS NOT NULL""").df()
    df["close_raw"] = df["close"] * df["later_splits"].fillna(1.0)
    df["source"] = source
    return df[["date", "ticker", "close_raw", "adj_close", "source"]]


parts = []
if "prices_yf2" in tables:
    parts.append(yahoo("prices_yf2", "yf2"))
parts.append(yahoo("prices_yf", "yf"))
if "prices_tiingo" in tables:
    ti = con.sql("""SELECT CAST(date[1:10] AS DATE) AS date, ticker, close AS close_raw,
                           adjClose AS adj_close FROM prices_tiingo""").df()
    ti["source"] = "tiingo"
    parts.append(ti)
ext = pd.concat(parts, ignore_index=True).dropna(subset=["adj_close"])
ext = ext.sort_values(["source", "ticker", "date"]).drop_duplicates(["source", "ticker", "date"])

# Fix 1: the return belongs to one source (the previous row of the SAME source and ticker).
ext["ret"] = ext.groupby(["source", "ticker"])["adj_close"].pct_change(fill_method=None)
bad = ~np.isfinite(ext["ret"]) | (ext["ret"] > 10) | (ext["ret"] < -0.99)
ext.loc[bad, "ret"] = np.nan
ext["prio"] = ext["source"].map(PRIORITY)
print(f"external rows: {len(ext):,} ({ext.groupby('source').ticker.nunique().to_dict()} tickers)")

# ------------------------------------------------ days the company was in the index
held = con.sql("SELECT date, ticker, price, quantity FROM holdings").df()
alias = pd.read_csv("reference/ticker_aliases.csv")[["ticker", "price_ticker"]]
cands = pd.concat([held[["ticker"]].drop_duplicates().assign(price_ticker=lambda d: d["ticker"], cprio=0),
                   alias.assign(cprio=1)]).drop_duplicates(["ticker", "price_ticker"])

# Fixes 2 and 3: try the ticker itself, then its successor, in every source, and keep the
# first candidate whose raw close agrees with the fund's recorded price that day.
m = (held.merge(cands, on="ticker")
         .merge(ext.rename(columns={"ticker": "price_ticker"}), on=["price_ticker", "date"]))
m["agrees"] = (m["close_raw"] / m["price"] - 1).abs() < 0.03
m = m[m["agrees"] & m["ret"].notna()]
m = m.sort_values(["date", "ticker", "cprio", "prio"]).drop_duplicates(["date", "ticker"])
chosen = m[["date", "ticker", "price_ticker", "source", "ret"]]

# Fix 4: fund-price returns for held days with no agreeing source. A split multiplies the
# fund's quantity of the stock by k while dividing its price by k, so the split-adjusted
# return is p_t * k / p_{t-1} - 1. k is the stock's change in quantity relative to the
# fund's overall change that day (inflows and outflows change every quantity alike).
flow = con.sql("SELECT date, flow FROM ivv_days").df()
h = held.merge(flow, on="date", how="left").sort_values(["ticker", "date"]).reset_index(drop=True)
g = h.groupby("ticker")
h["gap"] = (h["date"] - g["date"].shift()).dt.days
h["pr"] = h["price"] / g["price"].shift()
h["k"] = split_factor(h["quantity"] / g["quantity"].shift() / h["flow"], h["pr"])
h["ret"] = h["pr"] * h["k"] - 1
h.loc[h["gap"] > 7, "ret"] = np.nan            # no return across a missing stretch of files
fund = h[["date", "ticker", "ret", "price"]].assign(source="ivv", price_ticker=h["ticker"])
print(f"stock splits found in the fund's files: {(h['k'] != 1).sum()}")

held_rows = held[["date", "ticker", "price"]].merge(chosen, on=["date", "ticker"], how="left")
need = held_rows["ret"].isna()
held_rows = pd.concat([held_rows[~need],
                       held_rows[need].drop(columns=["ret", "source", "price_ticker"])
                       .merge(fund[["date", "ticker", "ret", "source", "price_ticker"]], on=["date", "ticker"], how="left")])
held_rows = held_rows.rename(columns={"price": "close_raw"})

# ------------------------------------------------ days outside the index (fix 5)
# Risk models need each company's history from before it joined and after it left:
# betas since 2015 for today's members, three-year covariance windows at past month ends.
# Use the source that matched the fund's prices most often while the company was held
# (for a renamed company that is its successor's history, e.g. FB -> META).
pick = (held_rows[held_rows["source"] != "ivv"].groupby(["ticker", "price_ticker", "source"])
        .size().reset_index(name="n").sort_values("n").drop_duplicates("ticker", keep="last"))
out = (pick.merge(ext.rename(columns={"ticker": "price_ticker"}), on=["price_ticker", "source"])
           [["date", "ticker", "close_raw", "ret", "source", "price_ticker"]])
out = out.merge(held_rows[["date", "ticker"]], on=["date", "ticker"], how="left", indicator=True)
out = out[out["_merge"] == "left_only"].drop(columns="_merge")

# Benchmarks: the S&P 500 price index, its total-return version, and two S&P 500 funds
BENCH = ["^GSPC", "^SP500TR", "SPY", "IVV"]
bench = ext[ext["ticker"].isin(BENCH)].sort_values("prio").drop_duplicates(["ticker", "date"])
bench = bench.assign(price_ticker=bench["ticker"])[["date", "ticker", "close_raw", "ret", "source", "price_ticker"]]
print("benchmarks: " + ", ".join(f"{t} {'yes' if t in set(bench['ticker']) else 'MISSING'}" for t in BENCH))

prices_df = pd.concat([held_rows.assign(held=True), out.assign(held=False), bench.assign(held=False)],
                      ignore_index=True)
prices_df = prices_df.sort_values(["ticker", "date", "held"]).drop_duplicates(["ticker", "date"], keep="last")
# (A data frame named like an existing table would not be read: DuckDB takes the table.)
con.execute("CREATE OR REPLACE TABLE prices AS SELECT * FROM prices_df")

# Checks
s = con.sql("""SELECT source, COUNT(*) AS n FROM prices WHERE held GROUP BY 1 ORDER BY 2 DESC""").df()
tot = s["n"].sum()
print("held company-days by return source:",
      ", ".join(f"{r.source} {r.n / tot:.1%}" for r in s.itertuples()))
miss = con.sql("SELECT COUNT(*) FILTER (WHERE ret IS NULL) * 1.0 / COUNT(*) AS m FROM prices WHERE held").df()["m"][0]
print(f"held company-days without a return: {miss:.2%} (first day in the index, or after a gap)")
recyc = (m.assign(same=m["price_ticker"] == m["ticker"]).query("not same")
          .groupby(["ticker", "price_ticker"]).size().sort_values(ascending=False))
print("renamed tickers priced from their successor (company-days):",
      ", ".join(f"{a}->{b} {n}" for (a, b), n in recyc.head(25).items()))
