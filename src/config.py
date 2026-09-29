"""Settings shared by every script, so the same choice is never made twice differently."""

# Risk models and stress tests start here. The fund holdings reach back to 2009, and
# the concentration history uses all of it; risk numbers keep the project's 2015 start
# so they stay comparable with the first version.
START = "2015-01-01"

# Covariance window for risk decompositions: 252 TRADING days (one year).
WINDOW = 252

# The AI group. GOOGL and GOOG are two share classes of Alphabet; FB is Meta before
# its 2022 ticker change.
AI = ["NVDA", "AVGO", "MU", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "FB"]

# Minimum share of a window a stock needs real returns for, to enter a covariance
# matrix. Stocks below it are left out and their weight is reported.
MIN_COVERAGE = 0.9
