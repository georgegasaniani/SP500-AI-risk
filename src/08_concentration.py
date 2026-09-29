import duckdb

con = duckdb.connect("data/sp500.duckdb")

START = "2015-01-01"


con.execute("""
    CREATE OR REPLACE TABLE mktcap AS
    SELECT p.date, p.ticker, p.close_raw,
           (SELECT s.shares FROM shares s
            WHERE s.ticker = p.ticker AND s.filed <= p.date
            ORDER BY s.filed DESC LIMIT 1) AS shares,
           p.close_raw * (SELECT s.shares FROM shares s
                          WHERE s.ticker = p.ticker AND s.filed <= p.date
                          ORDER BY s.filed DESC LIMIT 1) AS mktcap
    FROM prices p
    WHERE p.date >= '""" + START + """'
""")


con.execute("""
    CREATE OR REPLACE TABLE weights AS
    SELECT m.date, m.ticker, c.mktcap,
           c.mktcap / SUM(c.mktcap) OVER (PARTITION BY m.date) AS weight
    FROM membership_daily m
    JOIN mktcap c ON c.ticker = m.ticker AND c.date = m.date
    WHERE c.mktcap IS NOT NULL
""")



con.execute("""
    CREATE OR REPLACE TABLE concentration AS
    WITH ranked AS (
        SELECT date, ticker, weight,
               ROW_NUMBER() OVER (PARTITION BY date ORDER BY weight DESC) AS rnk
        FROM weights
    )
    SELECT date,
           COUNT(*) AS n_stocks,
           SUM(CASE WHEN rnk <= 10 THEN weight END) AS top10,
           SUM(CASE WHEN rnk <= 5  THEN weight END) AS top5,
           1.0 / SUM(weight * weight) AS effective_n
    FROM ranked GROUP BY date
""")



print(con.sql("""
    SELECT year(date) AS yr,
           ROUND(AVG(top10), 3) AS top10,
           ROUND(AVG(top5), 3)  AS top5,
           ROUND(AVG(effective_n), 1) AS eff_n,
           ROUND(AVG(n_stocks), 0) AS n
    FROM concentration GROUP BY 1 ORDER BY 1
"""))

# Coverage: what share of index members have a real market cap each year.
print(con.sql("""
    WITH mem AS (SELECT DISTINCT year(date) AS yr, ticker FROM membership_daily
                 WHERE date >= '""" + START + """')
    SELECT yr, COUNT(*) AS members,
           COUNT(*) FILTER (WHERE ticker IN (SELECT DISTINCT ticker FROM weights)) AS covered
    FROM mem GROUP BY 1 ORDER BY 1
"""))

# Largest companies on the most recent day, as a sanity check on the numbers.
print(con.sql("""
    SELECT ticker, ROUND(weight, 4) AS weight, ROUND(mktcap / 1e9, 0) AS mktcap_bn
    FROM weights WHERE date = (SELECT MAX(date) FROM weights)
    ORDER BY weight DESC LIMIT 10
"""))



print(con.sql("""
    SELECT m.ticker,
           (SELECT COUNT(*) FROM shares s WHERE s.ticker = m.ticker) AS share_records,
           (SELECT MAX(filed) FROM shares s WHERE s.ticker = m.ticker) AS last_filed
    FROM (SELECT DISTINCT ticker FROM membership_daily WHERE date = (SELECT MAX(date) FROM membership_daily)) m
    WHERE m.ticker NOT IN (SELECT DISTINCT ticker FROM weights WHERE date = (SELECT MAX(date) FROM weights))
       OR (SELECT MAX(filed) FROM shares s WHERE s.ticker = m.ticker) < '2024-01-01'
    ORDER BY 3
"""))

print(con.sql("""
    WITH manual_tickers AS (SELECT DISTINCT ticker FROM shares WHERE source = 'manual'),
    excl AS (
        SELECT date, ticker,
               mktcap / SUM(mktcap) OVER (PARTITION BY date) AS weight
        FROM weights WHERE ticker NOT IN (SELECT ticker FROM manual_tickers)
    ),
    ranked_excl AS (
        SELECT date, weight, ROW_NUMBER() OVER (PARTITION BY date ORDER BY weight DESC) AS rnk
        FROM excl
    ),
    conc_excl AS (
        SELECT date, SUM(CASE WHEN rnk <= 10 THEN weight END) AS top10_excl
        FROM ranked_excl GROUP BY date
    )
    SELECT year(c.date) AS yr,
           ROUND(AVG(c.top10), 4) AS top10_with_manual,
           ROUND(AVG(e.top10_excl), 4) AS top10_without,
           ROUND(AVG(c.top10) - AVG(e.top10_excl), 4) AS diff
    FROM concentration c JOIN conc_excl e USING (date)
    GROUP BY 1 ORDER BY 1
"""))

print(con.sql("""
    SELECT MIN(total) AS min_sum, MAX(total) AS max_sum
    FROM (SELECT date, SUM(weight) AS total FROM weights GROUP BY 1)
"""))

print(con.sql("""
    SELECT date, ticker, ROUND(close_raw, 0) AS price, shares, ROUND(mktcap / 1e9, 0) AS mktcap_bn
    FROM mktcap WHERE ticker = 'GOOGL' AND date IN ('2015-06-15', '2021-06-15', '2026-09-11')
"""))








