import duckdb

con = duckdb.connect("data/sp500.duckdb")

print(con.sql("SHOW TABLES"))
print(con.sql("SELECT * FROM prices WHERE ticker = 'NVDA' ORDER BY date DESC LIMIT 10"))
print(con.sql("SELECT * FROM membership ORDER BY date DESC LIMIT 5"))

import duckdb
import pandas as pd

con = duckdb.connect("data/sp500.duckdb")
A = con.sql("SELECT * FROM fundamentals_annual").df()
Q = con.sql("SELECT * FROM fundamentals_quarterly").df()

for t in ["AMZN", "GOOGL", "MSFT"]:
    print(f"\n=== {t} annual (USD bn) ===")
    d = A[A["ticker"] == t].sort_values("year")
    print((d.set_index("year")[["revenue", "capex", "depreciation"]] / 1e9).round(1).tail(10).to_string())

    print(f"--- {t} last 8 quarters (USD bn) ---")
    q = Q[Q["ticker"] == t].sort_values("end").tail(8)
    print((q.set_index("end")[["revenue", "capex", "depreciation"]] / 1e9).round(1).to_string())