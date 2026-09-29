# Audit of the first version

September 2026. Every script and data source of the first version (published 15 September
2026) was checked. This file lists what was wrong, how much it moved the results, and
what replaced it. Running limitations are in [`limitations.md`](../limitations.md).

## What changed in the results

| | First version | Corrected |
|---|---|---|
| Ten largest holdings, share of the index, 2015 average | 20.6% | **17.3%** |
| Ten largest holdings, share of the index, latest | 38.2% (11 Sep 2026) | **38.9%** (25 Sep 2026) |
| Effective number of stocks, 2015 average → latest | 108 → 47 | **145 → 44** |
| Ten largest holdings, share of risk (past year) | 55.5% | **53.3%** |
| AI group, share of weight / share of risk (past year) | 29% / 43% | **30% / 45%** |
| Nvidia, Broadcom, Micron, AMD: weight / risk (since 2024) | 13% / 27% | **14% / 29%** |
| Index loss if the AI group falls 25% | 16 to 19% | **16 to 17%** |
| Johnson & Johnson's sensitivity to the AI group on turbulent days | doubles (0.13 → 0.26) | **rises about 40% (0.13 → 0.18)** |
| Volatility cost of today's weighting vs equal weights | 2.9 points | **3.3 points** |
| Nvidia's revenue as a share of the four hyperscalers' capex | 12% → 59% | **21% (2015) → 57% (2025); 59% over the last four quarters** |
| Rebuilt index vs reality | within 2.5 points a year of SPY | **within 0.24 points a year of the S&P 500 Total Return index since 2015** |
| One-day 97.5% VaR backtest | passes | **fails: 68 exceptions where 49 were expected** |

The main story holds and is stronger: the index is now less than a third as diversified as in
2015 (the first version said half). The first version overstated 2015 concentration because it
was missing many of that year's mid-sized members (D1 below).

## Data

**D1. Companies silently missing from the index (critical).**
Weights were built as price × SEC share count over the membership list, and a company only got
a share count if its ticker was in the SEC's list of *today's* tickers. 202 tickers were missing
on more than 5% of their index days since 2015 (14% of all company-days); only 71% of members
had a weight in 2015 and 87% in 2020. The largest cases:
- Facebook/Meta: no weight at all from 2 January 2015 to 8 June 2022 (ticker FB). Yahoo's "FB"
  today is a different security.
- Exxon Mobil: absent until August 2026. Its cover-page share count exists in one filing, and
  `07_shares.py` used the fallback tag only when the cover tag was completely empty.
- Companies that re-registered under a new holding company, losing their history before the
  change: Disney (before 2019), Broadcom (2018), BlackRock (October 2024), Cigna, Apache,
  DuPont, Dow, Baker Hughes, Xerox, TechnipFMC, Bunge.
- Renamed tickers: Anthem, Marsh McLennan, Fiserv, CenturyLink, United Technologies, Harris,
  BB&T, Willis Towers Watson, Everest Re, FleetCor, PerkinElmer, AmerisourceBergen,
  Symantec/NortonLifeLock, HCP/Healthpeak and others.
- About 100 acquired or delisted companies had prices but no share count: Celgene, Allergan,
  Time Warner, Monsanto, Twitter, Activision, Electronic Arts, Xilinx, Citrix...

Direction: 2015 was missing many mid-sized members, so its top-10 share was too high (20.6%
instead of 17.3%) and its effective number of stocks too low (108 instead of 145). The rise in
concentration was understated.

Fix: the weights now come from the daily holdings of the iShares Core S&P 500 ETF (IVV), which
fully replicates the index: every member, float-adjusted weights, the tickers used at the time.
The files go back to November 2006 (month ends until April 2012, daily after). The SEC rebuild
is kept as `concentration_sec` for comparison.

**D2. Total shares instead of free float.** The index weights companies by the shares available
to the public. Founder-held companies (Alphabet, Meta, Tesla, Berkshire) were overweighted.
Fixed by D1's holdings, which are float-adjusted by construction.

**D3. Recycled tickers carrying another company's prices**: IR (Ingersoll-Rand, now TT, against
Gardner Denver's prices in 2017-20), DD and DOW (old against new DuPont and Dow), SNDK (old
against new SanDisk), FOXA/FOX (21st Century Fox against Fox Corp). Fix: on every day a company
was held, the external price must agree with the fund's own recorded price within 3%; otherwise
the successor ticker (`reference/ticker_aliases.csv`) or the fund's price is used.

**D4. Mixed-source returns.** `06_merge_prices.py` computed daily returns *before* removing the
Yahoo rows of tickers also downloaded from Tiingo, so on overlapping days a "return" compared two
data sources. It also made results depend on row order: the published top-10 risk share (55.5%)
reproduces as 54.8% from the same raw files. Fix: returns are computed inside one source.

**D5. The first download's last day was not a closing price.** The Yahoo download ran during US
trading on 11 September 2026, so that day's "close" was a live price.

**D6. Spin-offs and new listings had no weight until their first quarterly filing**, weeks to
months after they joined: GE Vernova, Kenvue, Solventum, Veralto and others. Fixed by D1.

**D7. The hand-checked share counts lived only on the PC** (`data/manual_shares.csv`), and
`run_all.py` re-ran `09_manual_shares.py`, which would have overwritten them with raw regex
output. Moved to `reference/manual_shares.csv`; 09 is no longer part of the run.

## Models and code

**M1. The rolling VaR backtest was not a GARCH forecast.** `19_rolling_backtest.py` used the
window's sample variance where the recursion needs yesterday's *conditional* variance, and a
1,000-day window while the README said 252. The corrected forecasts match the `arch` library's
own one-day forecasts exactly. The corrected model **fails** the Kupiec test at every level
(3.5% exceptions against 2.5% at 97.5%; 1.5% against 1.0% at 99%): a GARCH(1,1)-t fitted on four
years underestimates the tail. Exceptions are not bunched (Christoffersen passes), and the last
250 days are in the Basel green zone (3 exceptions at 99%). The first version's "pass" came from
the wrong model.

**M2. Rolling risk windows were calendar days.** "252 days" was about 174 trading days (eight
months). Now 252 trading days.

**M3. Stressed betas were selected on large *index* moves.** The index contains the market
factor, so conditioning on big index days mechanically raises every stock's beta to the AI group.
Selected now on large moves of the AI group itself. This is where "J&J's sensitivity doubles"
came from: on the corrected days it rises by about 40%. Amplification of an AI-group shock: 0.66
on all days, 0.68 on big AI days, 0.80 with the old selection.

**M4. Risk decomposition, stress test and counterfactual dropped every company with a missing
day** in the window: everything listed after the window start (Uber, Airbnb, Palantir...)
vanished and the rest was renormalised. Now a company needs 90% of the window, and the weight
left out is reported (under 0.1% for the past year).

**M5. `counterfactual.csv` was overwritten** by `24_export_for_bi.py` with hard-coded numbers.

**M6. Index returns dropped a company's return on the day it left the index**, and did not
renormalise for missing returns.

**M7. Nvidia's revenue was compared with the wrong year of hyperscaler capex.** Nvidia's fiscal
year ends in January, so its "2024" is mostly calendar 2023. Now compared by calendar year from
quarterly data. Group sums also skipped missing companies silently.

**M8. Backtest statistics**: Christoffersen returned NaN (printed as FAIL) when there were no
back-to-back exceptions, and likelihoods multiplied raw probabilities (underflow).

**M9. `22_fundamentals.py` appended the last tag's records twice** and did not prioritise tags.
One effect remains: Amazon switched its capex tag during 2017, so 2017 is left out of the
Nvidia-versus-capex comparison (see `limitations.md`).

**M10. The pipeline could not run from a clone**: scripts at the repository root while
`run_all.py` looked in `src/`, a hard-coded `C:\Users\...` path, `membership_daily` built from a
prices table that did not exist yet, no `requirements.txt`.

**M11. Index-level risk (volatility, VaR, ES, GARCH, EVT) was computed on the rebuilt index**,
with D1's gaps. It now uses the official S&P 500 Total Return index; the rebuilt index is a
check.

## How the corrected numbers were checked

- **Against the real index.** Previous day's weights × each company's return that day, compared
  with the S&P 500 Total Return index: within 0.24 points a year since 2015, 0.04 points since
  2021; tracking error 0.29% a year since 2015 and 0.02% since 2021 (`data/bi/index_check.csv`).
  The fund's own holdings valued at the fund's prices match the S&P 500 price index with the
  same accuracy.
- **Independently.** A separate script, written without access to the pipeline or its results,
  recomputed the headline numbers from the raw files. Every one agreed:

  | | Pipeline | Independent |
  |---|---|---|
  | Ten largest, share of weight, 25 Sep 2026 | 38.94% | 38.94% |
  | Ten largest, share of risk (past 252 days) | 53.32% | 53.32% |
  | AI group, share of weight / risk | 29.9% / 45.5% | 29.9% / 45.5% |
  | Effective number of stocks, latest | 44.0 | 44.0 |
  | S&P 500 TR since 2015: volatility / VaR 97.5% / ES 97.5% | 17.65% / 2.28% / 3.45% | 17.65% / 2.28% / 3.45% |

- **Automatic checks in the pipeline**: weights sum to 1 every day, no weight above 15%, every
  price agrees with the fund's price on held days, the index check above, and the backtest's
  forecasts against `arch`.
