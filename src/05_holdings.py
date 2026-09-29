"""Real index composition from the iShares Core S&P 500 ETF (IVV) holdings.

IVV fully replicates the S&P 500: it holds every company in proportion to its
free-float market cap. Its daily holdings file is therefore the index itself,
including companies that later changed ticker, merged or were delisted.

Input : data/raw/ivv_holdings/        (one file per year, built by 00_fetch_data.py)
Output: holdings       one row per company per trading day with a file:
                       ticker, name, sector, price, quantity, market value, weight
        ivv_days       one row per day: number of companies, equity value, and the fund's
                       overall change in share quantities that day ("flow", used to tell
                       stock splits apart from money flowing in or out of the fund)

Not used: the fund's "equity value per fund share". Its daily change should be the index
return, but the fund-share count in the file is often out of step with the holdings by a
day, which puts errors of 1-2% on days with large inflows or outflows. Checked against the
S&P 500 in September 2026: the buy-and-hold value of the previous day's holdings matched
the index to 0.0003% a day; value per share missed by up to 1.9%.
"""
import os

import duckdb
import pandas as pd

con = duckdb.connect("data/sp500.duckdb")
raw = pd.read_parquet("data/raw/ivv_holdings")
print(f"raw: {len(raw):,} rows, {raw['date'].nunique()} days")

# 1. Clean tickers. iShares writes Berkshire as "BRKB" or "BRK B", Brown-Forman as
#    "BF/B" or "BFB", and marks some early tickers with "*". Renames (FB -> META)
#    are NOT handled here: the holdings keep the ticker used on that day.
t = (raw["ticker_raw"].astype(str).str.replace("*", "", regex=False).str.strip()
     .str.replace(" ", "-", regex=False).str.replace(".", "-", regex=False)
     .str.replace("/", "-", regex=False))
raw["ticker"] = t.replace({"BRKB": "BRK-B", "BFB": "BF-B", "UAC-C": "UA"})

# 2. Keep real share lines only: drop rights, when-issued lines and warrants,
#    and positions valued at (almost) nothing, such as delisted stubs.
junk = raw["name"].str.contains("WHEN ISSUED|SUBSCRIPTION R|RIGHTS|WARRANT", case=False, na=False)
junk |= raw["ticker"].isin(["-", ""]) | raw["ticker"].str.endswith(("-WI", "-W"))
junk |= (raw["market_value"] <= 0) | (raw["price"] <= 0.05)
print(f"dropped {junk.sum():,} non-share rows ({raw.loc[junk, 'market_value'].sum() / raw['market_value'].sum():.4%} of value)")
h = raw[~junk].copy()

# 3. Two lines with the same ticker on one day (rare data glitch): add them up.
h = (h.groupby(["date", "ticker"], as_index=False)
       .agg(name=("name", "last"), sector=("sector", "last"), price=("price", "last"),
            quantity=("quantity", "sum"), market_value=("market_value", "sum"),
            fund_shares=("fund_shares", "last")))

# 4. Trading days only. BlackRock also publishes files on some market holidays
#    (Juneteenth, for example) that repeat the previous day's prices; kept, they would add
#    days with a fake zero return. A day is dropped if the S&P 500 / SPY price history has
#    no close that day, or if nearly every price is unchanged from the previous file.
tables = set(con.sql("SHOW TABLES").df()["name"])
cal = set()
for tb in ("prices_yf2", "prices_yf"):
    if tb in tables:
        cal |= set(pd.to_datetime(con.sql(f"""SELECT DISTINCT CAST(date AS DATE) AS d FROM {tb}
                                             WHERE ticker IN ('SPY', '^GSPC') AND close IS NOT NULL""").df()["d"]))
h = h.sort_values(["ticker", "date"])
same = h["price"].eq(h.groupby("ticker")["price"].shift())
unchanged = same.groupby(h["date"]).mean()
not_trading = set(unchanged[unchanged > 0.9].index)
if cal:
    not_trading |= {d for d in pd.to_datetime(h["date"].unique()) if min(cal) <= d <= max(cal) and d not in cal}
print(f"dropped {len(not_trading)} files dated on market holidays: "
      f"{', '.join(sorted(pd.Timestamp(d).strftime('%Y-%m-%d') for d in not_trading)[:12])}")
h = h[~h["date"].isin(not_trading)].copy()

# 5. Incomplete files: a day listing far fewer companies than usual (a broken download or a
#    publishing glitch) is dropped; 08_concentration.py bridges it like any missing day.
n_day = h.groupby("date")["ticker"].size()
min_n = int(os.environ.get("HOLDINGS_MIN_N", 400))      # real files hold 500+ companies
assert n_day.median() >= min_n, "most holdings files look incomplete: check the download (00_fetch_data.py)"
short = n_day[n_day < 0.9 * n_day.rolling(21, center=True, min_periods=1).median()]
if len(short):
    print(f"WARNING: dropped {len(short)} incomplete files (far fewer companies than the days around them): "
          + ", ".join(f"{d:%Y-%m-%d} ({n})" for d, n in short.head(10).items()))
h = h[~h["date"].isin(short.index)].copy()

# 6. Weight = the company's share of the equity value that day.
h["weight"] = h["market_value"] / h.groupby("date")["market_value"].transform("sum")

# 7. The fund's overall change in quantities between consecutive files. When money flows
#    in, the fund buys a bit more of every stock: all quantities rise by the same factor.
#    A split changes one stock's quantity by a much larger factor (06_merge_prices.py).
h = h.sort_values(["ticker", "date"])
prev_day = h.groupby("ticker")["date"].shift()
q_ratio = (h["quantity"] / h.groupby("ticker")["quantity"].shift()).where(prev_day.notna())
days = h.groupby("date").agg(n=("ticker", "size"), equity_value=("market_value", "sum"),
                             fund_shares=("fund_shares", "last")).reset_index()
days["flow"] = days["date"].map(q_ratio.groupby(h["date"]).median())

con.execute("CREATE OR REPLACE TABLE holdings AS SELECT * FROM h")
con.execute("CREATE OR REPLACE TABLE ivv_days AS SELECT * FROM days")
con.execute("ALTER TABLE holdings ALTER date TYPE DATE")
con.execute("ALTER TABLE ivv_days ALTER date TYPE DATE")

# Checks: weights sum to 1, company count near 500, no day with a missing chunk.
chk = con.sql("""SELECT MIN(n) mn, MAX(n) mx, MIN(date) d0, MAX(date) d1, COUNT(*) n_days,
                        MAX(ABS(s - 1)) max_sum_err
                 FROM (SELECT date, COUNT(*) n, SUM(weight) s FROM holdings GROUP BY 1)""").df().iloc[0]
print(f"holdings: {chk.n_days} days {chk.d0} to {chk.d1}, {chk.mn}-{chk.mx} companies per day, "
      f"weight sum error {chk.max_sum_err:.1e}")
assert chk.mx <= 520, "a day with more than 520 companies: duplicated rows?"
if chk.mn < 480:
    print("WARNING: some days hold fewer than 480 companies")
gaps = con.sql("""SELECT d, gap FROM (SELECT date d, date - LAG(date) OVER (ORDER BY date) gap FROM ivv_days)
                  WHERE gap > 5 ORDER BY gap DESC LIMIT 5""").df()
print("longest gaps between holdings files (days):")
print(gaps.to_string(index=False))
