"""Charts for the README, redrawn on every update (docs/charts/*.png).

  concentration.png   top-10 share and effective number of stocks: the real index
                      (fund holdings) and the first version's rebuild (SEC share counts)
  risk_vs_weight.png  top 10: share of index risk vs share of index weight, month by month
  ai_group.png        the AI group: share of weight and share of risk, month by month
"""
import textwrap
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import PercentFormatter

OUT = Path("docs/charts")
OUT.mkdir(parents=True, exist_ok=True)
con = duckdb.connect("data/sp500.duckdb", read_only=True)

BLUE, GREY, ORANGE, RED = "#1f4e79", "#9a9a9a", "#d9822b", "#b03a2e"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#e6e6e6", "grid.linewidth": 0.8,
                     "axes.titleweight": "bold", "axes.titlesize": 11, "legend.frameon": False})


def finish(fig, ax, name, note):
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    lines = textwrap.wrap(note, 125)
    fig.text(0.01, 0.01, "\n".join(lines), fontsize=8, color="#666666", ha="left", va="bottom")
    fig.tight_layout(rect=(0, 0.035 * len(lines) + 0.01, 1, 1))
    fig.savefig(OUT / name, dpi=150)
    plt.close(fig)


# ------------------------------------------------ concentration
real = con.sql("SELECT date, top10, effective_n FROM concentration ORDER BY date").df()
sec = con.sql("SELECT date, top10, effective_n FROM concentration_sec ORDER BY date").df()
for d in (real, sec):
    d["date"] = pd.to_datetime(d["date"])
last = real.iloc[-1]
fig, (a1, a2) = plt.subplots(2, 1, figsize=(8, 6.4), sharex=True)
a1.plot(real["date"], real["top10"], color=BLUE, lw=1.6, label="Real index (fund holdings)")
a1.plot(sec["date"], sec["top10"], color=GREY, lw=1.2, ls="--", label="First version (SEC share counts)")
a1.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
a1.set_title("Share of the S&P 500 in its ten largest holdings")
a1.legend(loc="upper left")
a1.annotate(f"{last.top10:.1%}", (last.date, last.top10), xytext=(6, 0), textcoords="offset points",
            va="center", color=BLUE, fontweight="bold")
a2.plot(real["date"], real["effective_n"], color=BLUE, lw=1.6)
a2.plot(sec["date"], sec["effective_n"], color=GREY, lw=1.2, ls="--")
a2.set_title("Effective number of stocks (1 / sum of squared weights)")
a2.annotate(f"{last.effective_n:.0f}", (last.date, last.effective_n), xytext=(6, 0),
            textcoords="offset points", va="center", color=BLUE, fontweight="bold")
a2.set_ylim(bottom=0)
finish(fig, a2, "concentration.png",
       f"Daily, {real['date'].min():%b %Y} to {last.date:%d %b %Y}. Source: iShares Core S&P 500 ETF (IVV) "
       f"holdings; SEC XBRL share counts.")

# ------------------------------------------------ rolling risk vs weight
roll = con.sql("SELECT * FROM rolling_risk WHERE window_days = 252 ORDER BY date").df()
roll["date"] = pd.to_datetime(roll["date"])
# Start once almost every holding has a full year of returns: in 2012-13 about 16% of the
# weight had not (companies later delisted, with no price source), which distorts the shares.
if "weight_left_out" in roll.columns:
    first_ok = roll.loc[roll["weight_left_out"] < 0.05, "date"].min()
    roll = roll[roll["date"] >= first_ok].reset_index(drop=True)


def risk_chart(wcol, rcol, title, name, colour, note=""):
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.plot(roll["date"], roll[rcol], color=colour, lw=1.8, label="share of index risk")
    ax.plot(roll["date"], roll[wcol], color=BLUE, lw=1.4, label="share of index weight")
    ax.fill_between(roll["date"], roll[wcol], roll[rcol], where=roll[rcol] >= roll[wcol],
                    color=colour, alpha=0.12, lw=0)
    ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    ax.set_title(title)
    ax.legend(loc="upper left")
    r = roll.iloc[-1]
    for col, c in ((rcol, colour), (wcol, BLUE)):
        ax.annotate(f"{r[col]:.0%}", (r.date, r[col]), xytext=(6, 0), textcoords="offset points",
                    va="center", color=c, fontweight="bold")
    finish(fig, ax, name, note + "Month ends; Euler risk shares from the previous 252 trading days' returns "
                                 "and that day's real weights. Starts when under 5% of the weight lacks a full year of returns.")


risk_chart("top10_weight", "top10_risk", "Ten largest holdings: share of risk vs share of weight",
           "risk_vs_weight.png", RED)
if "ai_risk" in roll.columns:
    risk_chart("ai_weight", "ai_risk", "AI group: share of risk vs share of weight", "ai_group.png", ORANGE,
               "AI group: Nvidia, Microsoft, Alphabet, Amazon, Meta, Broadcom, Micron. ")
print("charts written:", ", ".join(sorted(p.name for p in OUT.glob("*.png"))))
