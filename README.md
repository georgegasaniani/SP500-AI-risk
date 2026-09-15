# Is the S&P 500 secretly an AI bet?

If you own an ordinary S&P 500 index fund, how much of your money actually
depends on a handful of AI companies, and what would it cost you if those
companies fell hard?

I built the dataset from scratch to find out. This repository has the whole
pipeline: index membership, prices, SEC filings, the risk models, and a Power
BI report.

Period covered: January 2015 to September 2026, which is 2,939 trading days.


## What I found

**The index is about half as diversified as it was in 2015.** The ten largest
companies have gone from 20.6% of the index to 38.2%. Measured by the effective
number of stocks, which asks how many equally weighted holdings would give the
same concentration, it has fallen from 108 to 47.

**Those ten companies now carry 55% of the index's risk on 38% of its weight,
and that gap is new.** Until 2017 they contributed risk roughly in proportion
to their size. The gap opened after that and has widened since. This is the
finding I did not expect, and it only shows up if you compute the decomposition
rolling through time rather than as a snapshot.

**The risk is concentrated in semiconductors, not in large companies
generally.** Nvidia, Broadcom, Micron and AMD are about 13% of the index and
27% of its risk. Apple and Microsoft, the two largest non-chip holdings, are
essentially risk-neutral relative to their weight.

**A 25% fall in the AI group would cost an index investor 16 to 19%**, not the
7.6% the weights suggest, because the spillover to everything else is larger
than the direct hit. Defensive holdings lose most of their defensiveness on
exactly the days you would want them: Johnson & Johnson's sensitivity to the AI
group doubles on the most turbulent 10% of days.

**Today's weighting costs about 2.9 percentage points of annualised
volatility** compared with an equal-weighted version of the same 500 companies.
Same companies, same return behaviour, different weights.

**On the fundamentals, capital spending is growing two to four times faster
than revenue** at Microsoft, Amazon, Alphabet and Meta, and roughly three
quarters of that cost has not yet reached their reported profits. But they are
funding it from their own cash flow rather than debt, which is a real
difference from the dot-com telecoms. Nvidia's revenue now equals a growing
share of what these four spend, which is the channel connecting the
fundamentals to the risk findings.

---

## How it was built

```
src/
  01_membership.py          index constituents, expanded to every trading day
  02_prices_yf.py           daily prices from yfinance, resumable in batches
  04_prices_tiingo.py       prices from Tiingo for the tickers yfinance missed
  06_merge_prices.py        one price table: raw prices and daily returns
  07_shares.py              shares outstanding from the SEC XBRL API
  09_manual_shares.py       cover-page share counts for companies the API lacks
  10_merge_manual_shares.py folds those in
  08_concentration.py       market caps, weights, concentration measures
  11_validate_spy.py        rebuilt index return vs SPY, year by year
  12_risk_l1.py             normality tests, tail counts
  13_risk_l2.py             EWMA and GARCH(1,1)-t volatility
  14_risk_pca.py            PCA on the AI group, raw and market-adjusted
  15_risk_decomp.py         Euler risk decomposition
  16_stress_test.py         shock scenarios, normal and stressed betas
  17_var_es.py              VaR and Expected Shortfall, three methods
  18_backtest.py            Kupiec and Christoffersen tests
  19_rolling_backtest.py    rolling out-of-sample VaR backtest
  20_evt.py                 Generalized Pareto fit to the tail
  21_counterfactual.py      what the current weighting costs
  22_fundamentals.py        SEC financials for the AI group
  23_capex_analysis.py      capex vs revenue, depreciation gap
  25_rolling_risk.py        risk decomposition rolling through time
  24_export_for_bi.py       CSV exports for the Power BI report
```

Python, SQL and DuckDB. Everything is stored in a single DuckDB file and
queried with SQL. Prices come from yfinance and Tiingo, company data from the
SEC's XBRL API, index membership from the fja05680/sp500 dataset.

Methods: GARCH(1,1) with Student-t errors for conditional volatility,
principal component analysis for the factor structure, Euler decomposition for
splitting index risk between constituents, Extreme Value Theory for the tail,
and rolling out-of-sample backtesting to check the VaR model actually worked.

## The dashboard

A five-page Power BI report covering the findings and the methods behind them.
<img width="2239" height="1240" alt="Screenshot (64)" src="https://github.com/user-attachments/assets/d727f1a1-3304-4503-b072-6650ce89b0f9" />
<img width="2238" height="1253" alt="Screenshot (65)" src="https://github.com/user-attachments/assets/b1a0bbbe-05a5-4d23-80f3-b725e1459aed" />
<img width="2237" height="1242" alt="Screenshot (66)" src="https://github.com/user-attachments/assets/61f5f90d-fd4d-4448-87f4-3ac298bdb097" />
<img width="2228" height="1235" alt="Screenshot (69)" src="https://github.com/user-attachments/assets/006a519f-0e9d-4da1-850b-19871c44aad3" />
<img width="2240" height="1242" alt="Screenshot (70)" src="https://github.com/user-attachments/assets/908e4472-4975-4533-a9c1-f2016278d489" />


## Does it work?

The most important check is whether the rebuilt index matches reality. I
compared its total return against SPY, year by year.

| Year | Mine | SPY | Difference |
|---|---|---|---|
| 2015 | 1.84% | 1.23% | +0.61 |
| 2016 | 12.83% | 12.00% | +0.83 |
| 2017 | 23.34% | 21.71% | +1.63 |
| 2018 | -3.16% | -4.57% | +1.41 |
| 2019 | 31.66% | 31.22% | +0.44 |
| 2020 | 20.75% | 18.33% | +2.41 |
| 2021 | 28.21% | 28.73% | -0.51 |
| 2022 | -18.31% | -18.18% | -0.14 |
| 2023 | 27.56% | 26.18% | +1.38 |
| 2024 | 26.23% | 24.89% | +1.34 |
| 2025 | 18.09% | 17.72% | +0.37 |
| 2026 | 11.77% | 12.78% | -1.01 |

Every year within 2.5 percentage points, most within 1.5. The small positive
bias has a known cause: I weight by total shares outstanding while the real
index uses free float, which gives slightly more weight to companies with
concentrated ownership.

The VaR model was also tested properly. Refitting on a rolling 252-day window
and forecasting one day ahead, so no prediction uses information that did not
exist at the time, it passes the Kupiec test at 97.5%, 99% and 99.5% over 1,939
out-of-sample days. It is mildly optimistic at every level, with a few more
exceptions than expected, but not enough to fail.

---

## The data problems, which were most of the work

I had assumed the data would be the easy part. It took most of the project, and
it is the part I learned the most from.

**Ticker symbols get recycled.** When a company is acquired or goes bankrupt,
its symbol is freed up and can be reassigned years later. So asking for a
company that left the index in 1999 can return prices belonging to an unrelated
business. I found 185 of these by comparing each ticker's index membership
start against the start of its price history.

**My two price sources meant opposite things by the word "close".** Tiingo
gives the raw traded price; yfinance gives a price already adjusted for splits.
Merging them without noticing would have put half the companies on a different
scale with no error anywhere. I rebuilt the raw price by multiplying each
yfinance price by every split that happened afterwards, and checked it against
dates I could verify by hand.

**One company filed a share count that was wrong by a factor of a million.**
Arthur J. Gallagher reported 189 trillion shares for two quarters in 2020, with
correct figures either side. That single error gave it 99.7% of the index
weight.

**My fix for that broke Nvidia.** A filter comparing each value to the
company's median caught the bad filings but also deleted Nvidia's post-split
share counts, because a 10-for-1 split looks identical to a filing error if you
compare against a long-run median. It took three attempts to write a filter
that caught real errors and left real splits alone.

**Twenty-three current index members have no structured share data after about
2010**, including Visa, Mastercard, Berkshire and Nike. I checked Visa directly:
it has two records, from 2009 and 2010, and no alternative field anywhere in
its filings. I filled these in from the filings themselves and verified each
one by multiplying by the current price to check the result was a plausible
company size.

The thing I keep coming back to is that the dangerous errors are not the ones
that crash. They are the ones that produce plausible-looking numbers.

---

## What I would not claim

**I weight by total shares, not free float.** The real index excludes shares
held by insiders and founders. Float data is not freely available. This is the
main reason my index runs slightly ahead of SPY each year.

**The analysis starts in 2015.** Share-count coverage falls to 52.5% in 1998,
and before 2009 every market cap would be guessed. I wanted the dot-com
comparison and I do not have it.

**Fifteen companies use a single current share count** held constant across the
whole period. I measured what this costs: 0.4 to 1.9 percentage points on the
top-ten figure, with the trend unaffected.

**Alphabet's pre-2022 share count is today's figure divided by twenty**, the
split ratio, rather than the actual historical count.

**About 190 tickers have no price data at all**, and another 155 or so might
carry data belonging to a different company. Both are concentrated in dead
tickers and early years, so probably outside my window, but I did not verify
this directly.

**The stress tests are linear**, fitted on historical average behaviour. Real
selloffs have rising correlations beyond even the stressed-beta adjustment, so
the larger scenarios probably understate the damage.

**Extreme Value Theory gives single-day probabilities only.** A sustained
decline over months is a different thing and I did not model it.

**Nothing here is a prediction.** I have not forecast whether AI stocks will
fall or when. What I measured is exposure: if you own an index fund, how much
of your money rides on one story, and what various shocks would cost you.

---

## Running it

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

The SEC requires a user-agent header with a contact email. Set yours in
`src/07_shares.py` before running. Tiingo needs a free API key in the
`TIINGO_API_KEY` environment variable.

Scripts run in numerical order, with one exception: `10_merge_manual_shares.py`
must run after `07_shares.py` and before `08_concentration.py`, because it adds
share counts the SEC API does not provide and `07` rebuilds the table from
scratch.

Data is not in the repository. Tiingo's licence is personal-use only, and the
price tables are several hundred megabytes.

---

## Files

- `docs/writeup.md` — the full analysis, with every number and how it was
  reached
- `docs/limitations.md` — a running log of compromises made along the way
- `dashboard/` — the Power BI report
- `src/` — the pipeline

---

## What I would do next

The most obvious gap is the pre-2009 share counts. Every filing on EDGAR has
the number on its cover page going back to the mid-nineties, including for
companies that no longer exist. Parsing those would extend the concentration
history to the dot-com era and make the comparison I originally wanted
possible.

After that, a table restricting each ticker's prices to the periods it was
actually in the index, which would settle the recycled-symbol question properly
rather than leaving it bounded but unverified.

And on the modelling side, a copula to measure whether these stocks crash
together more than correlation implies, and an equal-weighted version of every
concentration finding as a systematic robustness check.
