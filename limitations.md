# Known limitations

A running log of the compromises made in this project, with the likely
direction of error where I could work it out. Written as they happened rather
than reconstructed at the end.

Analysis period: 2 January 2015 to 11 September 2026, 2,939 trading days.

---

## Method

**Total shares outstanding, not free float.** The real S&P 500 weights
companies by shares available to trade, excluding stakes held by founders,
families and governments. Float data is not freely available, so this project
uses total shares. That overweights companies with concentrated ownership,
which over this period were disproportionately the tech winners. This is the
main driver of the 0.4 to 2.4 percentage point annual tracking difference
against SPY, and it is a permanent limitation rather than a fixable gap.

**The analysis starts in 2015.** SEC share-count coverage falls to 52.5% of
index members in 1998 and 72.6% in 2015, reaching 97.7% by 2026. The SEC's
structured data begins in 2009 and only covers companies still filing, so every
company that died or was acquired is absent. Before 2009 every market cap would
rest on a guessed share count. The dot-com comparison was dropped as a result.
The dot-com era still enters the project through returns in the stress tests,
which do not require historical weights.

**Fifteen companies use a single current share count** held constant across the
whole window, because the SEC's structured data stops for them around 2010.
These include Visa, Mastercard, Berkshire Hathaway, Comcast, UPS and Ford.
Measured cost: including them shifts the top-ten figure by 0.4 to 1.9
percentage points depending on the year, with the trend unaffected. The error
runs one way, since these are mostly established companies that have bought back
shares, so their earlier size is understated.

**Alphabet's pre-2022 share count is today's figure divided by twenty**, the
split ratio, rather than the actual historical count. That probably understates
Alphabet's market cap in 2015 to 2021 by ten or fifteen percent due to buybacks
since.

**Dual-class handling varies by company** and is documented per case. Where
both classes are index members with their own prices (Alphabet, Fox, News
Corp), each ticker gets its own class count. Where only one class is listed,
the total is used if the excluded class has real economic value (Berkshire,
UPS, Nike) and only the listed class if it does not (Accenture's Class X, which
is a governance instrument). Berkshire counts both classes in B-equivalent
terms.

**Company financials start in 2009** for the same XBRL reason. Concentration
and risk analysis run from 2015; the business-finance analysis from 2009.
Different sections therefore cover different periods.

**The index divisor is not replicated.** The real index uses an adjustment
factor that changes with additions, removals and share issuance. This affects
the index level more than returns.

---

## Data coverage

**Two price sources.** yfinance for 790 tickers, Tiingo for 156. Where both had
a ticker, Tiingo's version is used, because those tickers were requested from
Tiingo precisely because Yahoo's data was wrong. A `source` column records
which is which. An overlap comparison of tickers present in both sources was
never run.

**About 190 tickers have no price data at all.** Mostly small companies
acquired or bankrupt between 1998 and 2008. Outside the analysis window, so no
effect on results, but it means the pre-2015 data cannot be rescued without
parsing EDGAR filings directly.

**About 155 tickers may carry data from the wrong company** because ticker
symbols get reused. The clear cases, where the price history starts after index
membership began, were sent to Tiingo and 30 were successfully replaced. The
remainder are still in the table. These are concentrated in dead tickers and
early years, so probably outside the 2015 to 2026 window, but this was not
verified directly. A table restricting each ticker's prices to its actual
membership periods would settle it and was not built.

**Stitched histories are not detected.** Where one ticker passed from one
company to another with continuous data, such as T moving from the old AT&T to
SBC in 2005, no check catches it.

**Coverage rises through the window**, from 72.6% of index members in 2015 to
97.7% in 2026, because the missing companies are ones that later left the index
and stopped filing. There is residual survivorship bias in the early years. The
SPY tracking result bounds the damage but does not measure this directly.

**Tiingo did not have 373 of the 531 problem tickers**, either missing entirely
(195) or with data starting too late to cover the membership period (178).

---

## Data quality

**6,428 returns (0.13%) set to NULL** because they fell outside -99% to +1000%.
Concentrated in fifteen dead or acquired tickers, where both sources keep stale
data with frozen prices and adjusted closes of zero or near zero. The threshold
is a judgement call, and implausible values below it remain in the same
tickers.

**Share counts are filtered against a rolling local median** of seventeen
nearby filings, keeping values within a factor of ten. This catches isolated
misfilings (Arthur J. Gallagher reported 189 trillion shares for two quarters
in 2020) and consecutive ones, while leaving legitimate stock splits alone. It
took three attempts to find a rule that did all three.

**`close_raw` is the actual traded price**, rebuilt for yfinance tickers by
multiplying the split-adjusted close by all subsequent splits. Verified against
known values: AAPL 2013-06-03 = $450.72, NVDA 2019-06-03 = $133.78.

**Adjusted close is not stored.** Its level is meaningless (Yahoo's 1998
adjusted close for Yahoo Inc is $1.14 against a raw price of $66.25), so daily
returns are computed once during the merge and stored instead. This removes the
possibility of confusing two price columns rather than documenting the hazard.

**Amazon's depreciation** required pinning to the narrow `Depreciation` tag.
Amazon reports under two tags with different definitions, one covering property
and equipment and the other including amortisation of intangibles, and mixing
them produced an implausible series. All four hyperscalers now use the same
definition.

**Amazon does not report research and development** in a comparable way, using
"Technology and Infrastructure" instead, so it is missing from that comparison.

---

## Modelling

**Stress tests are linear**, fitted on historical average behaviour. Real
selloffs have rising correlations beyond even the stressed-beta adjustment, so
the larger scenarios probably understate the damage. These are floors rather
than central estimates.

**Stressed betas use the most turbulent 10% of days measured in absolute
terms**, which mixes sharp falls with sharp rallies. Using only large down days
would be cleaner but halves the sample.

**Extreme Value Theory gives single-day probabilities only.** A sustained
decline over weeks or months is a different object and is not modelled. The
2022 selloff took a year to deliver -18%, and no daily model captures that.

**The GARCH parameters reported are fitted on the full period.** The backtest
uses rolling refits on a 252-day window. The VaR and Expected Shortfall figures
in the summary are in-sample and should be read as descriptive.

**The rolling VaR model is mildly optimistic** at every confidence level: 2.99%
exceptions against 2.5% expected, 1.19% against 1.0%, 0.77% against 0.5%.
Consistently a few too many, though not enough to fail the Kupiec test.

**The rolling risk decomposition uses a 252-day covariance window.** Month-to-
month variation is about 2 percentage points. Lengthening the window to 504 or
756 days reduces that only to 1.99 and 1.67, so the movement is real rather
than an estimation artefact. But today's figure should not be quoted to one
decimal as though it were precise; the trend since 2017 is the solid claim.

**The counterfactual's 2015-weighted case** uses today's companies with 2015's
weights renormalised, so companies that have since left the index are dropped
and new entrants get zero weight. It is 2015's weighting philosophy applied to
today's survivors, not a genuine 2015 portfolio.

**Depreciation schedules are not adjusted.** These companies choose the useful
life they depreciate servers over, and several have extended those assumptions
in recent years, which flatters earnings. If AI hardware is obsolete faster
than the assumed life, the eventual charge is larger than the figures here
imply.

**Fiscal years differ.** Microsoft's ends in June, Micron's in August,
Broadcom's in October or November, Nvidia's in January, and the rest in
December. Annual comparisons are therefore approximate. Trailing-twelve-month
figures end at different dates per company.

**Nvidia's revenue as a share of hyperscaler capex overstates the direct
dependency**, since Nvidia sells to other cloud providers, enterprises and
governments too. The rise from 12% to 59% is the meaningful part, not the
level.

---

## Reproducibility

**Data is not in the repository.** Tiingo's licence is personal-use only, and
the price tables run to several hundred megabytes. Anyone cloning this would
need their own Tiingo API key and several hours of downloading to reproduce it.

**Script ordering has one non-obvious dependency.** `10_merge_manual_shares.py`
must run after `07_shares.py`, which rebuilds the shares table from scratch,
and before `08_concentration.py`. Running them out of order causes Alphabet to
be double-counted with no error message. `run_all.py` handles this.

---

## What is not claimed

Nothing here is a prediction. No forecast is made about whether AI stocks will
fall or when. What is measured is exposure: if you own an index fund, how much
of your money rides on one story, and what various shocks would cost you.
