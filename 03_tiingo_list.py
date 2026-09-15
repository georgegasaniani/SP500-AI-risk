import duckdb
import pandas as pd

con=duckdb.connect("data/sp500.duckdb")

late=con.sql("""
    WITH mem AS (
        SELECT replace(ticker, '.', '-') AS ticker,
               MIN(date) AS mem_start, MAX(date) AS mem_end
        FROM membership
        WHERE date >= '1998-01-01'
        GROUP BY 1
    ),
    yf AS (
        SELECT ticker, MIN(date) AS yf_start, MAX(date) AS yf_end
        FROM prices_yf
        GROUP BY 1
    )
    SELECT mem.ticker, mem.mem_start,mem.mem_end, yf.yf_start, yf.yf_end
    FROM mem JOIN yf USING (ticker)
    WHERE yf.yf_start > mem.mem_start + INTERVAL 10 DAY
    ORDER BY mem.mem_start
""").df()

print(len(late),"tickers start on YAhoo after they joined the index")
print(late.head(20))


failed = pd.read_csv("data/failed_yf.csv")["ticker"]
tiingo_list = sorted(set(failed) | set(late["ticker"]))
mem = con.sql("""
    SELECT replace(ticker, '.', '-') AS ticker,
           MIN(date) AS mem_start, MAX(date) AS mem_end
    FROM membership WHERE date >= '1998-01-01'
    GROUP BY 1
""").df()
yf_start = con.sql("SELECT ticker, MIN(date) AS yf_start FROM prices_yf GROUP BY 1").df()

cand = (pd.DataFrame({"ticker": tiingo_list})
          .merge(mem, on="ticker", how="left")
          .merge(yf_start, on="ticker", how="left"))
cand["gap_end"] = cand[["yf_start", "mem_end"]].min(axis=1)
cand["missing_days"] = (cand["gap_end"] - cand["mem_start"]).dt.days
cand = cand.sort_values("missing_days", ascending=False)

cand.head(480).to_csv("data/tiingo_list.csv", index=False)
cand.iloc[480:].to_csv("data/fill_list.csv", index=False)
print(cand.iloc[480:][["ticker", "mem_start", "mem_end", "missing_days"]].to_string())


tiingo=pd.read_csv("data/raw/supported_tickers.zip")
tiingo=tiingo[tiingo["priceCurrency"].fillna("USD")=="USD"]
tiingo["ticker"]=tiingo["ticker"].str.upper()
tiingo["startDate"]=pd.to_datetime(tiingo["startDate"], errors="coerce" )


cov=cand.merge(tiingo[["ticker","startDate","endDate"]], on="ticker",how="left")
cov["useful"]=cov["startDate"]<= cov["mem_start"] + pd.Timedelta(days=30)
useful=cov.groupby("ticker")["useful"].any()

print("\nOn Tiingo's list at all:" , cov.dropna(subset=["startDate"])["ticker"].nunique(), "of" , len(useful))
print("Tiingo covers the dates we need:",useful.sum(), "of", len(useful))


final=sorted(useful[useful].index)
pd.Series(final, name="ticker").to_csv("data/tiingo_list.csv",index=False)

fill=sorted(set(cand["ticker"]) - set(final))
pd.Series(fill,name="ticker").to_csv("data/fill_list.csv",index=False)
print(len(final),"to request from Tiingo", len(fill), "to fill with industry returns")