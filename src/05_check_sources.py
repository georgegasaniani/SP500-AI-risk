import duckdb

con=duckdb.connect("data/sp500.duckdb")
print(con.sql("DESCRIBE prices_yf"))
print(con.sql("DESCRIBE prices_tiingo"))
print(con.sql("SELECT * FROM prices_tiingo LIMIT 3"))