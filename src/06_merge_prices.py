import duckdb

con=duckdb.connect("data/sp500.duckdb")
con.execute("""
    CREATE OR REPLACE TABLE prices AS
    WITH yf AS (
        SELECT date,ticker,close,adj_close,volume,
               EXP(SUM(LN(CASE WHEN stock_splits > 0 THEN stock_splits  ELSE 1 END))
               OVER (PARTITION BY ticker ORDER BY date
                     ROWS BETWEEN 1 FOLLOWING AND UNBOUNDED FOLLOWING)) AS future_splits
        FROM prices_yf
    )
    SELECT date,ticker,
            close * COALESCE(future_splits,1) AS close_raw,
            adj_close AS adj_close,
            volume, 'yf' AS source
    FROM yf
""")                                      


con.execute("""
    INSERT INTO prices
    SELECT CAST(date[1:10] AS DATE) AS date,ticker,
           close AS close_raw, adjClose AS adj_close,
           volume, 'tiingo' AS source
    FROM prices_tiingo
    """)

con.execute("ALTER TABLE prices ALTER date TYPE DATE")


con.execute("""
    CREATE OR REPLACE TABLE prices AS
    SELECT date, ticker, close_raw, volume, source,
           adj_close / LAG(adj_close) OVER (PARTITION BY ticker ORDER BY date) - 1 AS ret
    FROM prices
""")


con.execute("""
    UPDATE prices SET ret = NULL
    WHERE NOT isfinite(ret) OR ret > 10 OR ret < -0.99
""")

con.execute("""
    DELETE FROM prices WHERE source = 'yf' AND ticker IN (
        SELECT DISTINCT ticker FROM prices WHERE source = 'tiingo'
    )
""")


print(con.sql("""
    SELECT source, COUNT(DISTINCT ticker) AS tickers, COUNT(*) AS rows,
              MIN(date) AS first , MAX(date) AS last
    FROM prices GROUP BY source
    """))

print(con.sql("""
     SELECT ticker, date, close_raw,ret FROM prices
    WHERE (ticker ='NVDA' AND date = '2019-06-03')
       OR (ticker ='AAPL' AND date = '2013-06-03')
       OR (ticker ='AABA' AND date = '1998-01-02')
    ORDER BY ticker
    """))          


print(con.sql("""
    SELECT COUNT(*) AS bad FROM prices
    WHERE close_raw <= 0 OR close_raw is NULL OR ret is NULL
    """))


print(con.sql("""
    SELECT COUNT(*) AS dupes FROM (
        SELECT ticker, date, COUNT(*) AS n FROM prices GROUP BY 1, 2 HAVING n > 1
    )
"""))

print(con.sql("""
    SELECT ticker, date, close_raw, ret, source FROM prices
    WHERE ret > 1 OR ret < -0.5
    ORDER BY ABS(ret) DESC LIMIT 20
"""))


print(con.sql("SELECT COUNT(*) AS nulled_returns FROM prices WHERE ret IS NULL"))
print(con.sql("""
    SELECT ticker, COUNT(*) AS nulled FROM prices WHERE ret IS NULL
    GROUP BY 1 ORDER BY nulled DESC LIMIT 15
"""))