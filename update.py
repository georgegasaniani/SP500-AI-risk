"""Update everything: new data, the whole analysis, the charts, and the numbers in the README.

Run from the project folder:
    .venv\\Scripts\\python update.py              download what is new, then rerun everything
    .venv\\Scripts\\python update.py --no-fetch   rerun the analysis on the data already downloaded

Takes about 10 minutes. Afterwards open the Power BI report and press Refresh: it reads the
CSV files in data/bi, which this has just rewritten.

Steps:
  1. src/00_fetch_data.py   new fund-holdings days since the last run, a fresh copy of the
                            Yahoo price histories, SEC company facts, the membership file
  2. run_all.py             the whole pipeline, from the raw files to data/bi/*.csv
                            (its last step redraws docs/charts/*.png)
  3. README.md              the block between <!-- numbers:start --> and <!-- numbers:end -->
"""
import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

BI = Path("data/bi")
START, END = "<!-- numbers:start -->", "<!-- numbers:end -->"


def run(args):
    print(f"\n=== {' '.join(args)}", flush=True)
    if subprocess.run([sys.executable] + args).returncode != 0:
        sys.exit(f"\nStopped: {' '.join(args)} failed, so nothing after it ran. "
                 f"The error is printed above.")


def check_fetch():
    """Warn about anything the download step could not get."""
    p = Path("data/raw/fetch_report.json")
    if not p.exists():
        return
    rep = json.loads(p.read_text(encoding="utf-8"))
    for part in ("membership", "ivv", "yahoo", "sec"):
        v = rep.get(part)
        if isinstance(v, str) and "fail" in v:
            print(f"WARNING: the {part} download failed ({v}); the old files were used.")
    if isinstance(rep.get("ivv"), dict) and rep["ivv"].get("failed"):
        print(f"WARNING: {rep['ivv']['failed']} holdings days could not be downloaded; "
              f"they will be tried again next time.")


def numbers():
    """The README block: the latest values next to January 2015."""
    conc = pd.read_csv(BI / "concentration.csv", parse_dates=["date"])
    roll = pd.read_csv(BI / "rolling_risk.csv", parse_dates=["date"])
    roll = roll[roll["window_days"] == 252]
    summ = pd.read_csv(BI / "summary_metrics.csv").set_index("metric")["value"]
    stress = pd.read_csv(BI / "stress_scenarios.csv").set_index("shock")
    meta = pd.read_csv(BI / "report_meta.csv").iloc[0]

    now = conc.iloc[-1]
    then = conc[conc["date"] >= "2015-01-01"].iloc[0]
    r_now = roll.iloc[-1]
    r_then = roll[roll["date"] >= "2015-01-01"].iloc[0]
    s25 = stress.iloc[abs(stress.index + 0.25).argmin()]          # the -25% scenario
    rows = [
        ("Ten largest holdings, share of the index", f"{now.top10:.1%}", f"{then.top10:.1%}"),
        ("Effective number of stocks", f"{now.effective_n:.0f}", f"{then.effective_n:.0f}"),
        ("AI group, share of the index", f"{now.ai_weight:.1%}", f"{then.ai_weight:.1%}"),
        ("Ten largest holdings, share of risk (past 252 trading days)", f"{r_now.top10_risk:.1%}",
         f"{r_then.top10_risk:.1%}"),
        ("AI group, share of risk (past 252 trading days)", f"{r_now.ai_risk:.1%}", f"{r_then.ai_risk:.1%}"),
    ]
    lines = [START,
             f"*Updated {dt.date.today():%d %b %Y} by `update.py`; index holdings to {now.date:%d %b %Y}.*",
             "",
             f"| | {now.date:%b %Y} | {then.date:%b %Y} |", "|---|---|---|"]
    lines += [f"| {a} | {b} | {c} |" for a, b, c in rows]
    lines += ["",
              f"A 25% fall in the AI group costs an index investor about {-s25.index_normal:.1%} "
              f"({-s25.index_stressed:.1%} with betas from turbulent days); the weights alone suggest "
              f"{-s25.naive_weight_only:.1%}.",
              f"Since {pd.Timestamp(meta.start):%B %Y}: annualised volatility "
              f"{summ['Annualised volatility (%)']:.1f}%, one-day 97.5% VaR "
              f"{-summ['VaR 97.5%, 1-day (%)']:.2f}%, Expected Shortfall "
              f"{-summ['Expected Shortfall 97.5% (%)']:.2f}% (S&P 500 total return index).",
              END]
    return "\n".join(lines)


def update_readme(block):
    p = Path("README.md")
    text = p.read_text(encoding="utf-8")
    if START not in text or END not in text:
        print("README.md has no <!-- numbers:start --> / <!-- numbers:end --> markers; not changed.")
        return
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    p.write_text(head + block + tail, encoding="utf-8")
    print("README.md numbers updated.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-fetch", action="store_true", help="skip downloads; rerun the analysis only")
    args = ap.parse_args()
    if not args.no_fetch:
        run(["src/00_fetch_data.py"])
        check_fetch()
    run(["run_all.py"])
    block = numbers()
    update_readme(block)
    print("\n" + block.replace(START, "").replace(END, "").strip())
    last = pd.read_csv(BI / "concentration.csv", parse_dates=["date"])["date"].max()
    if (pd.Timestamp.today() - last).days > 7:
        print(f"\nNOTE: the newest holdings file is from {last:%d %b %Y}. If that is more than a few "
              f"days ago, iShares may have changed its download page: check data/raw/fetch_report.json.")
    print("\nDone. Charts: docs/charts/. Now open the Power BI report and press Refresh.")
