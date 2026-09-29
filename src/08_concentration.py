"""Index weights and concentration, real and reconstructed.

  weights / concentration          REAL: the fund's daily holdings (05_holdings.py)
  weights_sec / concentration_sec  RECONSTRUCTED: traded price x SEC share count over the
                                   membership list. This was the project's original method.
                                   It is kept as an independent check, and to show what it
                                   missed (companies that changed ticker, re-registered, or
                                   were acquired got no share count and silently dropped out).

Days without a holdings file (iShares has none for January to June 2017) are bridged:
the last known weights move with each company's daily return, companies leave on the
day the membership file removes them, and new members enter with their weight from the
next available file.
"""
import duckdb
import numpy as np
import pandas as pd

con = duckdb.connect("data/sp500.duckdb")
AI = ["NVDA", "AVGO", "MU", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "FB"]

# ------------------------------------------------ membership on every trading day
# (moved here from 01: it needs the price table, which 06 builds)
con.execute("""
    CREATE OR REPLACE TABLE membership_daily AS
    WITH days AS (SELECT DISTINCT date FROM prices WHERE ticker = 'SPY'),
         changes AS (SELECT DISTINCT date FROM membership),
         mapped AS (SELECT d.date, (SELECT MAX(c.date) FROM changes c WHERE c.date <= d.date) AS as_of
                    FROM days d)
    SELECT mapped.date, replace(m.ticker, '.', '-') AS ticker
    FROM mapped JOIN membership m ON m.date = mapped.as_of
""")

# ------------------------------------------------ reconstructed weights (original method)
con.execute("""
    CREATE OR REPLACE TABLE mktcap_sec AS
    SELECT p.date, p.ticker, p.close_raw, s.shares, p.close_raw * s.shares AS mktcap
    FROM (SELECT * FROM prices WHERE date >= '2015-01-01') p
    -- one count per company and filing date (a few filings report several, e.g. one per
    -- share class; without this the choice between them was random from run to run)
    ASOF JOIN (SELECT ticker, filed, shares FROM
                 (SELECT *, ROW_NUMBER() OVER (PARTITION BY ticker, filed ORDER BY date DESC, shares DESC) AS rn
                  FROM shares) WHERE rn = 1) s
      ON p.ticker = s.ticker AND p.date >= s.filed
""")
con.execute("""
    CREATE OR REPLACE TABLE weights_sec AS
    SELECT m.date, m.ticker, c.mktcap, c.mktcap / SUM(c.mktcap) OVER (PARTITION BY m.date) AS weight
    FROM membership_daily m JOIN mktcap_sec c USING (date, ticker)
    WHERE c.mktcap > 0
""")

# ------------------------------------------------ real weights, with bridged gaps
hold = con.sql("SELECT date, ticker, weight FROM holdings").df()
days = con.sql(f"""SELECT DISTINCT date FROM prices WHERE ticker = 'SPY'
                   AND date >= '{hold['date'].min()}' AND date <= '{hold['date'].max()}' ORDER BY 1""").df()["date"]
have = set(hold["date"])
ret = con.sql("SELECT date, ticker, ret FROM prices WHERE ret IS NOT NULL").df()
ret = ret[ret["date"].isin(days)].set_index(["date", "ticker"])["ret"]
mem = con.sql("SELECT date, ticker FROM membership_daily").df()
mem = mem.groupby("date")["ticker"].apply(set)
ever_member = set().union(*mem.values)

bridged, w, n_bridged = [], None, 0
by_day = hold.groupby("date")
for d in days:
    if d in have:
        w = by_day.get_group(d).set_index("ticker")["weight"]
        continue
    if w is None:
        continue
    r = ret.reindex(pd.MultiIndex.from_product([[d], w.index])).fillna(0.0).values
    w = w * (1 + r)
    if d in mem.index:
        w = w[w.index.isin(mem[d]) | ~w.index.isin(ever_member)]  # removals on the day
        nxt = hold[hold["date"] > d]
        if len(nxt):
            nxt = nxt[nxt["date"] == nxt["date"].min()].set_index("ticker")["weight"]
            new = [t for t in mem[d] if t not in w.index and t in nxt.index]
            if new:
                w = pd.concat([w, nxt[new]])
    w = w / w.sum()
    bridged.append(pd.DataFrame({"date": d, "ticker": w.index, "weight": w.values}))
    n_bridged += 1
weights_df = pd.concat([hold.assign(source="ivv")] + [b.assign(source="bridged") for b in bridged])
# (A data frame named like an existing table would not be read: DuckDB takes the table.)
con.execute("CREATE OR REPLACE TABLE weights AS SELECT * FROM weights_df")
print(f"real weights: {weights_df['date'].nunique()} days ({n_bridged} bridged across missing files)")


def concentration(table, out):
    con.execute(f"""
        CREATE OR REPLACE TABLE {out} AS
        WITH ranked AS (SELECT date, ticker, weight,
                               ROW_NUMBER() OVER (PARTITION BY date ORDER BY weight DESC) AS rnk
                        FROM {table})
        SELECT date, COUNT(*) AS n_stocks,
               SUM(CASE WHEN rnk <= 10 THEN weight END) AS top10,
               SUM(CASE WHEN rnk <= 5 THEN weight END) AS top5,
               1.0 / SUM(weight * weight) AS effective_n,
               SUM(CASE WHEN ticker IN ({",".join(f"'{t}'" for t in AI)}) THEN weight ELSE 0 END) AS ai_weight
        FROM ranked GROUP BY date ORDER BY date
    """)


concentration("weights", "concentration")
concentration("weights_sec", "concentration_sec")

print("\nReal vs reconstructed, yearly averages:")
print(con.sql("""
    SELECT year(r.date) AS yr, ROUND(AVG(r.top10) * 100, 1) AS top10_real, ROUND(AVG(s.top10) * 100, 1) AS top10_sec,
           ROUND(AVG(r.effective_n), 0) AS eff_n_real, ROUND(AVG(s.effective_n), 0) AS eff_n_sec,
           ROUND(AVG(r.ai_weight) * 100, 1) AS ai_real
    FROM concentration r LEFT JOIN concentration_sec s USING (date)
    WHERE r.date >= '2015-01-01' GROUP BY 1 ORDER BY 1
""").df().to_string(index=False))

# Sanity checks: weights sum to 1 every day; largest single weight plausible.
chk = con.sql("""SELECT MAX(ABS(s - 1)) AS err, MAX(mx) AS mx FROM
                 (SELECT date, SUM(weight) s, MAX(weight) mx FROM weights GROUP BY 1)""").df().iloc[0]
print(f"\nweights sum error {chk.err:.1e}; largest single weight ever {chk.mx:.1%}")
assert chk.err < 1e-6 and chk.mx < 0.15
print("Largest companies on the latest day:")
print(con.sql("""SELECT ticker, ROUND(weight * 100, 2) AS weight_pct FROM weights
                 WHERE date = (SELECT MAX(date) FROM weights) ORDER BY weight DESC LIMIT 10""").df().to_string(index=False))
