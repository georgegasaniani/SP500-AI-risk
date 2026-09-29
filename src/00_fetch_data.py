"""Download everything the pipeline needs. Safe to re-run: it only fetches what is missing.

The holdings archive from November 2006 is already in data/raw/ivv_holdings/ (one file per year)
(downloaded once, 29 Sep 2026), so a run fetches only the days since the last one, a
fresh copy of the Yahoo prices and the SEC facts: a few minutes. On a fresh clone without
that file it backfills all ~5,200 weekdays first (about 15-20 minutes).

Run from the project folder:
    .venv\\Scripts\\python src\\00_fetch_data.py            (everything)
    .venv\\Scripts\\python src\\00_fetch_data.py --only ivv  (one part: ivv, yahoo, sec, membership)

What it downloads and why:
  1. Index membership history (fja05680 on GitHub): cross-check of index changes.
  2. iShares Core S&P 500 ETF (IVV) holdings: month ends from November 2006, every
     trading day from May 2012 (BlackRock has no files for January to early July 2017).
     IVV fully replicates the S&P 500, so its holdings are the real index weights:
     every company, correct share classes, free-float adjusted. This replaces
     rebuilding weights from SEC share counts, which missed companies that changed
     ticker, re-registered, or were acquired.
  3. Yahoo prices for current members and benchmarks (the S&P 500 index itself, its
     total-return version ^SP500TR, SPY, IVV): dividend-adjusted returns and long
     histories for the risk models.
  4. SEC company facts for the AI group (revenue, capex, cash flow).
"""
import argparse
import datetime as dt
import io
import json
import shutil
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

RAW = Path("data/raw")
IVV_DIR = RAW / "ivv"
# One parquet file per year in a folder: small files are quick to rewrite and to copy.
# pandas reads the whole folder as one table.
IVV_TABLE = RAW / "ivv_holdings"
# BlackRock's archive has month-end files from November 2006, daily files from May 2012,
# and nothing from January to early July 2017.
START = dt.date(2006, 11, 1)
SEC_HEADERS = {"User-Agent": "Giorgos george.gasaniani@gmail.com"}
IVV_URL = ("https://www.blackrock.com/varnish-api/blk-one01-product-data/product-data/api/v1/"
           "get-fund-document?appType=PRODUCT_PAGE&appSubType=ISHARES&targetSite=us-ishares"
           "&locale=en_US&portfolioId=239726&userType=individual&asOfDate={d}&component=holdings")
FJA_URL = ("https://raw.githubusercontent.com/fja05680/sp500/master/"
           "S%26P%20500%20Historical%20Components%20%26%20Changes%20(Updated).csv")
AI = ["NVDA", "AVGO", "MU", "MSFT", "GOOGL", "AMZN", "META"]
report = {"started": dt.datetime.now().isoformat(timespec="seconds")}


def session():
    """A browser-like HTTP session. curl_cffi (installed with yfinance) looks like Chrome,
    which avoids the bot filters some sites use; plain requests is the fallback."""
    try:
        from curl_cffi import requests as creq
        return creq.Session(impersonate="chrome")
    except ImportError:
        import requests
        s = requests.Session()
        s.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/140 Safari/537.36"
        return s


def get(s, url, headers=None, tries=5):
    """GET with retries and growing pauses for rate limits and server hiccups."""
    for k in range(tries):
        try:
            r = s.get(url, headers=headers, timeout=60)
            if r.status_code == 200:
                return r
            if r.status_code in (403, 429, 500, 502, 503, 504):
                time.sleep(2 * (k + 1) ** 2)
                continue
            return r
        except Exception:
            time.sleep(2 * (k + 1) ** 2)
    return None


# ---------------------------------------------------------------- 1. membership
def fetch_membership():
    s = session()
    r = get(s, FJA_URL)
    if r is None or r.status_code != 200 or not r.text.startswith("date,tickers"):
        print("  membership: download failed, keeping the old file")
        report["membership"] = "failed"
        return
    out = RAW / "sp500_history.csv"
    if out.exists():
        out.replace(RAW / "sp500_history_prev.csv")
    out.write_text(r.text, encoding="utf-8")
    last = r.text.strip().splitlines()[-1].split(",")[0]
    print(f"  membership: saved, last change dated {last}")
    report["membership"] = f"ok, last row {last}"


# ---------------------------------------------------------------- 2. IVV holdings
def weekdays(a, b):
    d = a
    while d <= b:
        if d.weekday() < 5:
            yield d
        d += dt.timedelta(days=1)


def stored_days():
    """Days already saved (True) or known to have no holdings (False), from the year zips
    and the holdings table. A saved .csv only counts if it is a real holdings file (they
    are ~80 KB; BlackRock's 'no holdings for this date' answer is ~300 bytes).
    The 2006-2026 backfill was downloaded once through a browser (29 Sep 2026) and stored
    straight into the table, so days in the table count as saved even without a zip copy."""
    have = {}
    for z in IVV_DIR.glob("ivv_*.zip"):
        with zipfile.ZipFile(z) as f:
            for info in f.infolist():
                key = info.filename.split(".")[0]
                real = info.filename.endswith(".csv") and info.file_size > 5000
                have[key] = have.get(key, False) or real
    if IVV_TABLE.exists():
        for d in pd.read_parquet(IVV_TABLE, columns=["date"])["date"].unique():
            have[pd.Timestamp(d).strftime("%Y%m%d")] = True
    return have


def classify(key, text):
    """'csv' if the text is the holdings file for that very day; 'empty' if BlackRock says
    it has none (weekends, holidays, the gap in its archive, a day not published yet);
    None if the answer is not a holdings file at all (an error page): retried next run."""
    for line in text.splitlines()[:15]:
        if line.startswith("Fund Holdings as of"):
            asof = line.split(",", 1)[1].strip().strip('"')
            if asof == "-":
                return "empty"
            try:
                same_day = dt.datetime.strptime(asof, "%b %d, %Y").strftime("%Y%m%d") == key
            except ValueError:
                return None
            return "csv" if same_day and "Ticker,Name" in text else "empty"
    return None


def fetch_ivv():
    IVV_DIR.mkdir(parents=True, exist_ok=True)
    have = stored_days()
    today = dt.date.today()
    recent = today - dt.timedelta(days=10)          # recent empty days may simply be unpublished yet
    todo = [d for d in weekdays(START, today)
            if d.strftime("%Y%m%d") not in have
            or (not have[d.strftime("%Y%m%d")] and d >= recent)]
    print(f"  IVV: {len(have)} days stored, {len(todo)} to fetch")
    s = session()

    def one(d):
        key = d.strftime("%Y%m%d")
        r = get(s, IVV_URL.format(d=key))
        if r is None or r.status_code != 200:
            return key, None, None
        return key, classify(key, r.text), r.text

    got = empty = failed = streak = 0
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(one, d) for d in todo]
        for n, fut in enumerate(as_completed(futures), 1):
            if fut.cancelled():
                continue
            key, kind, text = fut.result()
            if kind is None:
                failed += 1
                streak += 1
                if streak >= 30:            # the site is refusing us: stop instead of retrying for hours
                    print("  IVV: 30 failures in a row, stopping. Run the script again later;"
                          " it continues where it stopped.")
                    for f in futures:
                        f.cancel()
                    break
                continue
            streak = 0
            with zipfile.ZipFile(IVV_DIR / f"ivv_{key[:4]}.zip", "a", zipfile.ZIP_DEFLATED) as z:
                if kind == "csv":
                    z.writestr(f"{key}.csv", text)
                    got += 1
                elif f"{key}.empty" not in z.namelist():
                    z.writestr(f"{key}.empty", "")
                    empty += 1
            if n % 250 == 0:
                print(f"    {n}/{len(todo)}  saved {got}, holidays/empty {empty}, failed {failed}")
    print(f"  IVV: saved {got} new days, {empty} empty (holidays/gaps), {failed} failed")
    report["ivv"] = {"new_days": got, "empty": empty, "failed": failed}
    build_ivv_table()


def parse_ivv(key, text):
    if classify(key, text) != "csv":
        return None
    lines = text.splitlines()
    head = {l.split(",", 1)[0]: l.split(",", 1)[1].strip('"') for l in lines[:9] if "," in l}
    start = next(i for i, l in enumerate(lines) if l.startswith("Ticker,Name"))
    df = pd.read_csv(io.StringIO("\n".join(lines[start:])), dtype=str, on_bad_lines="skip")
    df = df[df["Asset Class"] == "Equity"].copy()
    for c in ["Market Value", "Weight (%)", "Quantity", "Price"]:
        df[c] = pd.to_numeric(df[c].str.replace(",", ""), errors="coerce")
    out = pd.DataFrame({"date": pd.to_datetime(key), "ticker_raw": df["Ticker"], "name": df["Name"],
                        "sector": df["Sector"], "market_value": df["Market Value"],
                        "weight_pct": df["Weight (%)"], "quantity": df["Quantity"],
                        "price": df["Price"], "exchange": df.get("Exchange")})
    fund_shares = pd.to_numeric(head.get("Shares Outstanding", "").replace(",", ""), errors="coerce")
    out["fund_shares"] = fund_shares
    return out


def write_ivv_table(h):
    """Write the table as one file per year into a new folder, then swap it in, so an
    interrupted run never leaves a half-written table."""
    tmp = IVV_TABLE.with_name(IVV_TABLE.name + "_new")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    for year, part in h.groupby(h["date"].dt.year):
        part.sort_values(["ticker_raw", "date"]).to_parquet(tmp / f"{year}.parquet", index=False)
    if IVV_TABLE.exists():
        shutil.rmtree(IVV_TABLE)
    tmp.rename(IVV_TABLE)


def build_ivv_table():
    """All saved days -> one compact parquet file for the pipeline. Days downloaded into
    the year zips are parsed; days only in the existing table (the browser backfill) are
    kept as they are."""
    parts = []
    for z in sorted(IVV_DIR.glob("ivv_*.zip")):
        with zipfile.ZipFile(z) as f:
            for n in sorted(f.namelist()):
                if n.endswith(".csv"):
                    try:
                        df = parse_ivv(n[:8], f.read(n).decode("utf-8", "replace"))
                        if df is not None and len(df):
                            parts.append(df)
                    except Exception as e:
                        print(f"    could not parse {n}: {e}")
    if IVV_TABLE.exists():
        old = pd.read_parquet(IVV_TABLE)
        new_days = set(pd.concat([p["date"] for p in parts]).unique()) if parts else set()
        parts.insert(0, old[~old["date"].isin(new_days)])
    if not parts:
        return
    h = pd.concat(parts, ignore_index=True).sort_values("date", kind="stable").reset_index(drop=True)
    write_ivv_table(h)
    days = h.groupby("date").size()
    print(f"  IVV table: {len(days)} days, {h.ticker_raw.nunique()} tickers, "
          f"{days.index.min().date()} to {days.index.max().date()}")
    report["ivv_table"] = {"days": int(len(days)), "first": str(days.index.min().date()),
                           "last": str(days.index.max().date())}


# ---------------------------------------------------------------- 3. Yahoo prices
def yahoo_tickers():
    t = set()
    p = IVV_TABLE
    if p.exists():
        h = pd.read_parquet(p, columns=["date", "ticker_raw"])
        last = h["date"].max()
        t |= set(h.loc[h["date"] >= last - pd.Timedelta(days=400), "ticker_raw"])
    m = RAW / "sp500_history.csv"
    if m.exists():
        mem = pd.read_csv(m)
        t |= set(mem["tickers"].iloc[-1].split(","))
    clean = {x.replace("*", "").strip().replace(" ", "-").replace(".", "-").replace("/", "-")
             for x in t if isinstance(x, str)}
    # iShares and old tickers -> the ticker Yahoo uses today (BRKB -> BRK-B, BK -> BNY).
    # Without this Yahoo is asked for names it does not know and reports them as failed.
    a = pd.read_csv("reference/ticker_aliases.csv")
    alias = dict(zip(a["ticker"].str.replace("/", "-", regex=False), a["price_ticker"]))
    clean = {alias.get(x, x) for x in clean}
    # drop cash lines ("-") and non-share lines iShares lists with a suffix (rights, "-US")
    clean = {x for x in clean if x[:1].isalpha() and not x.endswith(("-US", "-UW"))}
    # benchmarks: the S&P 500 price index, its total-return version, and two S&P 500 funds
    return sorted(clean | {"SPY", "IVV", "^GSPC", "^SP500TR"})


def fetch_yahoo():
    import yfinance as yf
    out = RAW / "yf2"
    out.mkdir(parents=True, exist_ok=True)
    tickers = yahoo_tickers()
    print(f"  Yahoo: {len(tickers)} tickers")
    stamp = dt.date.today().strftime("%Y%m%d")
    failed = []
    for i in range(0, len(tickers), 50):
        path = out / f"{stamp}_batch_{i // 50:03d}.parquet"
        if path.exists():
            continue
        batch = tickers[i:i + 50]
        df = yf.download(batch, start="2009-01-01", auto_adjust=False, actions=True,
                         progress=False, threads=True)
        if df is None or df.empty:
            print(f"    batch {i // 50}: nothing returned (rate limit?), re-run later")
            time.sleep(60)
            continue
        df = df.stack(level=1).reset_index()
        df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]
        df = df.dropna(subset=["close"])
        df.to_parquet(path, index=False)
        failed += sorted(set(batch) - set(df["ticker"]))
        print(f"    batch {i // 50 + 1}/{(len(tickers) + 49) // 50}: {df['ticker'].nunique()} of {len(batch)}")
        time.sleep(5)
    report["yahoo"] = {"tickers": len(tickers), "failed": failed}
    print(f"  Yahoo: done, {len(failed)} tickers returned nothing: {' '.join(failed[:30])}")
    # Keep this run and the previous one (the pipeline uses the newest file per ticker;
    # the previous run is a fallback for any ticker that failed today). Older runs go.
    stamps = sorted({p.name[:8] for p in out.glob("*_batch_*.parquet")})
    for old in stamps[:-2]:
        for p in out.glob(f"{old}_batch_*.parquet"):
            p.unlink()


# ---------------------------------------------------------------- 4. SEC
def fetch_sec():
    import requests
    d = RAW / "sec"
    d.mkdir(parents=True, exist_ok=True)
    r = requests.get("https://www.sec.gov/files/company_tickers.json", headers=SEC_HEADERS, timeout=60)
    r.raise_for_status()                       # an error page must not replace the saved file
    lookup = {v["ticker"]: str(v["cik_str"]).zfill(10) for v in r.json().values()}
    (d / "company_tickers.json").write_text(r.text, encoding="utf-8")
    for t in AI:
        cik = lookup.get(t)
        if not cik:
            print(f"    SEC: no CIK for {t}")
            continue
        rr = requests.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
                          headers=SEC_HEADERS, timeout=120)
        try:
            rr.raise_for_status()
            rr.json()
        except Exception as e:
            print(f"    SEC: {t} failed ({e!r}), keeping the old file")
            continue
        (d / f"companyfacts_{t}.json").write_text(rr.text, encoding="utf-8")
        time.sleep(0.2)
    print(f"  SEC: company tickers + facts for {len(AI)} AI-group companies saved")
    report["sec"] = "ok"


PARTS = {"membership": fetch_membership, "ivv": fetch_ivv, "yahoo": fetch_yahoo, "sec": fetch_sec}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=list(PARTS))
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    for name, fn in PARTS.items():
        if args.only and name != args.only:
            continue
        print(f"[{name}]")
        try:
            fn()
        except Exception as e:
            print(f"  {name} FAILED: {e!r}")
            report[name] = f"failed: {e!r}"
    report["finished"] = dt.datetime.now().isoformat(timespec="seconds")
    (RAW / "fetch_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("\nDone. Summary written to data/raw/fetch_report.json")
