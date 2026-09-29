# Known limitations

A running log of the compromises made in this project, with the likely
direction of error where I could work it out. Written as they happened rather
than reconstructed at the end. The September 2026 audit fixed several of the
original entries; those are kept at the bottom, marked as fixed, so the history
stays readable. [`docs/audit.md`](docs/audit.md) has the full list.

Index weights: November 2006 to 25 September 2026. Risk models: 2 January 2015
to 28 September 2026, 2,951 trading days.

---

## Method

**The weights are one fund's holdings, not S&P's own index file.** They come
from the published daily holdings of the iShares Core S&P 500 ETF (IVV), which
fully replicates the index: every member, at its float-adjusted index weight.
A fund can differ from its index by cash, timing of changes and securities
lending. Measured: weights taken from the holdings, times each company's
return, reproduce the S&P 500 Total Return index within 0.24 percentage points
in every year since 2015, with a tracking error of 0.29% a year (0.02% since
2021).

**The fund's archive has month-end files only before May 2012, and no files
from January to early July 2017.** Days in between are estimated: the last
known weights move with each company's daily return, companies leave on the day
the membership file removes them, and new members enter with their weight in
the next file. In 2017 this covers 98% of the weight. Before 2012 daily returns
exist for only 70 to 83% of the index, because companies that left before then
are missing from the price sources, so the daily concentration history before
2012 is approximate; the month-end values themselves are exact.

**Twelve files dated on market holidays and one incomplete file (3 October
2012, 396 companies instead of about 500) are dropped.** Lines that are not
company shares (cash, futures, rights, unlisted leftovers) are removed: 312
lines, 0.0003% of value.

**"Ten largest holdings" counts share classes separately**, as the index does:
Alphabet's GOOGL and GOOG are two holdings. Treating Alphabet as one company
would move it up the ranking and raise the top-10 share by about 1.5 points
today.

**The AI group** is Nvidia, Microsoft, Alphabet (both classes), Amazon, Meta,
Broadcom and Micron. It is a judgement call. AMD, Oracle, Tesla and others have
AI exposure too, so the group's share of weight and risk is a lower bound on
"AI" in the index.

**Company financials start in 2009** because the SEC's structured data does.
Concentration runs from 2006, risk analysis from 2015, business finance from
2009. Different sections therefore cover different periods.

---

## Data coverage

**Prices come from three sources plus the fund**: a fresh Yahoo download
(78% of held company-days since 2006), the original Yahoo download (8%), Tiingo
(8%), and the fund's own recorded prices (6%) where no outside source agrees.
On every day a company was held, the outside price must agree with the fund's
price within 3%. A ticker reused by a different company fails this check.

**Renamed companies use their successor's price history** (Facebook's comes
from META), from `reference/ticker_aliases.csv`. The list was built by hand from
the index changes; a rename it misses falls back to the fund's prices on held
days and has no history outside them.

**Stitched histories outside held days are not verified.** A company's prices
from before it joined or after it left the index come from the source that
matched the fund most often while it was held. If that ticker belonged to a
different company at other times, those outside days could be wrong. They are
used only for covariance windows and betas at the edges of a company's time in
the index.

---

## Data quality

**Returns outside -99% to +1000% are set to missing.** A few genuine extreme
moves exist (Moderna +177% on 19 August 2026, confirmed by the fund's own
prices) and are kept.

**Held company-days without a return: 0.5%**, mostly a company's first day in
the index or the day after a gap in the files. Index returns renormalise over
the companies that have one.

**The SEC share-count rebuild** (the first version's method, kept as a check
in `concentration_sec`) still has all the problems described in the audit:
companies that changed ticker, re-registered or were acquired have no count.
It is not used for any result.

**Amazon's depreciation** is pinned to the narrow `Depreciation` tag. Amazon
reports under two tags with different definitions, and mixing them produced an
implausible series. All four hyperscalers use the same definition.

**Amazon does not report research and development** in a comparable way, using
"Technology and Infrastructure" instead, so it is missing from that comparison.

**2017 is missing from the Nvidia-versus-capex comparison.** During 2017
Amazon switched the tag it reports capex under, from purchases of property and
equipment to a broader "productive assets" figure (restating 2016 from $6.7bn
to $7.8bn), so its 2017 quarters cannot be rebuilt on one definition, and a
group total without Amazon would be too low. Amazon's capex before 2017 is on
the narrower definition, about 14% lower. The growth rates in the README use
years after the switch.

---

## Modelling

**The VaR model fails its backtest.** A GARCH(1,1) with Student-t errors,
refitted every 20 days on the previous 1,000 days, has 3.5% exceptions at the
97.5% level (2.5% expected), 1.5% at 99% and 1.0% at 99.5%, and fails the
Kupiec test at all three. The exceptions are not bunched (Christoffersen
passes) and the last 250 days are in the Basel green zone. The full-sample VaR
and Expected Shortfall figures are descriptive, not forecasts.

**Stress tests are linear**, fitted on historical behaviour. Real selloffs have
rising correlations beyond even the stressed-beta adjustment, so the larger
scenarios probably understate the damage. These are floors rather than central
estimates.

**Stressed betas use the 10% of days with the largest AI-group moves**, up or
down. Using only large falls would be cleaner but halves the sample.

**Extreme Value Theory gives single-day probabilities only.** A sustained
decline over weeks or months is a different object and is not modelled. The
2022 selloff took a year to deliver -18%, and no daily model captures that.

**Risk decompositions use a 252-trading-day covariance window.** Month-to-month
variation is about 2 percentage points, so today's figure should not be quoted
to one decimal as though it were precise; the trend since 2018 is the solid
claim. Companies need returns on 90% of the window to be included; the weight
left out is reported and is under 0.1% for the past year. Before April 2013 it
was around 16%, so the risk charts start there.

**The counterfactual's 2015-weighted case** uses today's companies with 2015's
weights renormalised, so companies that have since left the index are dropped
and new entrants get zero weight. It is 2015's weighting philosophy applied to
today's survivors, not a genuine 2015 portfolio.

**Depreciation schedules are not adjusted.** These companies choose the useful
life they depreciate servers over, and several have extended it in recent
years, which flatters earnings. If AI hardware becomes obsolete faster than
assumed, the eventual charge is larger than the figures here imply.

**Fiscal years differ.** Microsoft's ends in June, Micron's in August,
Broadcom's in October or November, Nvidia's in January, and the rest in
December. Annual comparisons are approximate; the Nvidia-versus-capex
comparison is rebuilt by calendar year from quarterly data.

**Nvidia's revenue as a share of hyperscaler capex overstates the direct
dependency**, since Nvidia sells to other cloud providers, enterprises and
governments too. The rise from about a fifth to 57% is the meaningful part,
not the level.

---

## Reproducibility

**Data is not in the repository.** Tiingo's licence is personal-use only, and
the price tables run to several hundred megabytes. `update.py` downloads
everything on its first run (about 20 minutes).

**The fund's download address is not an official API.** iShares changed it at
least once (the old `.ajax` link now returns a web page). If downloads stop,
`data/raw/fetch_report.json` says so, and `update.py` warns when the newest
holdings file is more than a week old.

**`09_manual_shares.py` is not part of the run.** It drafted
`reference/manual_shares.csv`, which was then checked by hand; re-running it
would overwrite that work.

---

## What is not claimed

Nothing here is a prediction. No forecast is made about whether AI stocks will
fall or when. What is measured is exposure: if you own an index fund, how much
of your money rides on one story, and what various shocks would cost you.

---

## Fixed in the September 2026 audit

These were limitations of the first version. They are kept here so the log
stays honest; the audit report has the details and the size of each effect.

- ~~Total shares outstanding, not free float.~~ Fixed: the fund's holdings are
  float-adjusted.
- ~~The analysis starts in 2015 because share counts are unreliable before.~~
  Concentration now runs from November 2006.
- ~~About 190 tickers with no price data; about 155 that might carry another
  company's data.~~ Weights no longer depend on them, and every price is
  checked against the fund's price on held days.
- ~~Coverage rose from 72.6% of members in 2015 to 97.7% in 2026.~~ The fund's
  holdings include every member on every day.
- ~~Fifteen companies with a single constant share count; Alphabet's history as
  today's count divided by twenty.~~ Only affects the SEC cross-check now.
- ~~The rolling VaR model passes the Kupiec test.~~ It did not test a GARCH
  forecast; the corrected backtest fails (see Modelling).
- ~~Rolling risk decomposition uses a 252-day window.~~ It was 252 calendar
  days (about 174 trading days); now 252 trading days.
- ~~Stressed betas on the most turbulent 10% of index days.~~ Selecting on the
  index inflated the betas mechanically; now selected on AI-group days.
