import duckdb
import numpy as np
import pandas as pd
from arch import arch_model

con=duckdb.connect("data/sp500.duckdb")
idx=con.sql("SELECT date, ret FROM index_returns WHERE ret IS NOT NULL ORDER BY date").df()
idx["date"]=pd.to_datetime(idx["date"])
r=idx.set_index("date")["ret"]*100

lam=0.94
var=np.empty(len(r))
var[0]=r.var()
for t in range(1,len(r)):
    var[t]=lam * var[t-1] + (1-lam) * r.iloc[t-1]**2
idx["ewma_vol"]=np.sqrt(var*252) 

am=arch_model(r,vol="Garch",p=1,q=1,dist="t")
res=am.fit(disp="off")
print(res.summary())
idx["garch_vol"]=res.conditional_volatility.values*np.sqrt(252)


print("\nAnnualised volatility by year (%):")
print(idx.assign(yr=idx["date"].dt.year)
         .groupby("yr")[["ewma_vol", "garch_vol"]].mean().round(1))

print("\nHighest GARCH volatility days:")
print(idx.nlargest(5, "garch_vol")[["date", "garch_vol"]].to_string(index=False))

con.execute("CREATE OR REPLACE TABLE volatility AS SELECT * FROM idx")