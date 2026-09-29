import duckdb
con=duckdb.connect("data/sp500.duckdb")

con.execute("""
    CREATE OR REPLACE TABLE index_returns AS
    WITH lagged AS (
          SELECT date,ticker,
                  LAG(weight) OVER (PARTITION BY ticker ORDER BY date) AS w_prev
            FROM weights
    )           
    SELECT p.date, SUM(l.w_prev * p.ret) AS ret
    FROM lagged l
    JOIN prices p ON p.ticker = l.ticker AND p.date=l.date
    WHERE l.w_prev IS NOT NULL AND p.ret IS NOT NULL
    GROUP BY p.date
""")


print(con.sql("""
      WITH mine AS (
           SELECT year(date) AS yr, EXP(SUM(LN(1+ret))) - 1 AS my_ret
           FROM index_returns WHERE ret > -1 GROUP BY 1
        ),
        spy AS (
            SELECT year(date) AS yr, EXP(SUM(LN(1+ret))) - 1 AS spy_ret
            FROM prices WHERE ticker = 'SPY' AND ret IS NOT NULL AND ret > -1
               AND date >= '2015-01-01' GROUP BY 1
        )
        SELECT yr, ROUND(100* my_ret,2) AS mine_pct,ROUND(100* spy_ret,2) AS spy_pct,
               ROUND(100*(my_ret - spy_ret), 2) AS diff_pp
        FROM mine JOIN spy USING (yr) ORDER BY yr
"""))

print(con.sql("""
    SELECT date, ticker, weight FROM weights
    WHERE ticker = 'NVDA' AND date BETWEEN '2024-02-20' AND '2024-02-26' ORDER BY date
"""))