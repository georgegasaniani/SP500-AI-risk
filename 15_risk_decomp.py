import duckdb
import numpy as np
import pandas as pd

con=duckdb.connect("data/sp500.duckdb")
DATE=con.sql("SELECT MAX(date) AS d FROM weights").df()["d"][0]


w=con.sql(f"SELECT ticker,weight FROM weights WHERE date= '{DATE}'").df()

rets=con.sql(f"""
     SELECT date,ticker,ret FROM prices
      WHERE ticker IN (SELECT ticker FROM weights WHERE date = '{DATE}')
         AND date >= '2024-01-01' AND ret IS NOT NULL
""").df()


wide=rets.pivot(index="date",columns="ticker",values="ret").dropna(axis=1)
w=w[w["ticker"].isin(wide.columns)].set_index("ticker")["weight"]
w=w/w.sum()
wide=wide[w.index]

cov=wide.cov().values * 252
wv=w.values
port_var=wv @ cov @ wv
print(f"Portofolio Volatility: {np.sqrt(port_var):.1%}")


mcr=cov @ wv
risk_share=wv * mcr / port_var

out=pd.DataFrame({"weight": wv, "risk_share":risk_share}, index=w.index)
out["ratio"]=out["risk_share"]/out["weight"]
out=out.sort_values("weight", ascending=False)

print(f"\nRisk shares sum to {risk_share.sum():.4f}")
print(f"\nTop 10 bt weight: {out.head(10)["weight"].sum():.1%} of weight,"
      f"{out.head(10)['risk_share'].sum():.1%} of risk")


AI = ["NVDA", "AVGO", "MU", "MSFT", "GOOGL", "GOOG", "AMZN", "META"]
ai=out[out.index.isin(AI)]
print(f"AI group:         {ai['weight'].sum():.1%} of weight,"
      f"{ai['risk_share'].sum():.1%} of risk")

print("\nTop 15 companies:")
print((out.head(15) * 100).round(2).to_string())



def decomp(start, end, label):
    rets = con.sql(f"""
        SELECT date, ticker, ret FROM prices
        WHERE ticker IN (SELECT ticker FROM weights WHERE date = '{DATE}')
          AND date >= '{start}' AND date <= '{end}' AND ret IS NOT NULL
    """).df()
    wide = rets.pivot(index="date", columns="ticker", values="ret").dropna(axis=1)
    ww = con.sql(f"SELECT ticker, weight FROM weights WHERE date = '{DATE}'").df()
    ww = ww[ww["ticker"].isin(wide.columns)].set_index("ticker")["weight"]
    ww = ww / ww.sum()
    wide = wide[ww.index]

    cov = wide.cov().values * 252
    v = ww.values
    pv = v @ cov @ v
    share = v * (cov @ v) / pv

    out = pd.DataFrame({"weight": v, "risk": share}, index=ww.index).sort_values("weight", ascending=False)
    ai = out[out.index.isin(AI)]
    print(f"{label:22} vol {np.sqrt(pv):5.1%}  |  top10 {out.head(10)['weight'].sum():5.1%} wt "
          f"{out.head(10)['risk'].sum():5.1%} risk  |  AI {ai['weight'].sum():5.1%} wt {ai['risk'].sum():5.1%} risk")
    return out

print()
full = decomp("2015-01-01", "2026-12-31", "full window")
_    = decomp("2020-02-01", "2020-06-30", "covid crash")
_    = decomp("2022-01-01", "2022-12-31", "2022 selloff")
_    = decomp("2024-01-01", "2026-12-31", "recent (2024+)")




out.to_csv("data/bi/risk_decomposition.csv")

windows = []
for label, start, end in [("full", "2015-01-01", "2026-12-31"),
                          ("covid", "2020-02-01", "2020-06-30"),
                          ("selloff2022", "2022-01-01", "2022-12-31"),
                          ("recent", "2024-01-01", "2026-12-31")]:
    d = decomp(start, end, label)
    ai = d[d.index.isin(AI)]
    windows.append({"window": label,
                    "top10_weight": d.head(10)["weight"].sum(),
                    "top10_risk": d.head(10)["risk"].sum(),
                    "ai_weight": ai["weight"].sum(),
                    "ai_risk": ai["risk"].sum()})
pd.DataFrame(windows).to_csv("data/bi/risk_by_window.csv", index=False)