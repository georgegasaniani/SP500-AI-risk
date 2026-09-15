import re, time, requests, pandas as pd

HEADERS = {"User-Agent": "Giorgos george.gasaniani@gmail.com"}
TICKERS = ["SPG","V","CMCSA","UPS","CME","ACN","TAP","MA","BRK-B","IBKR","F","REGN",
           "HSY","NKE","AOS","CHTR","WDAY","FOXA","FOX","ARES","STZ","TSN","ERIE"]

r = requests.get("https://www.sec.gov/files/company_tickers.json", headers=HEADERS)
lookup = {v["ticker"].replace(".", "-"): str(v["cik_str"]).zfill(10) for v in r.json().values()}

out = []
for t in TICKERS:
    cik = lookup.get(t)
    if not cik:
        out.append({"ticker": t, "shares": None, "note": "no CIK"}); continue
    sub = requests.get(f"https://data.sec.gov/submissions/CIK{cik}.json", headers=HEADERS).json()
    time.sleep(0.12)
    rec = sub["filings"]["recent"]
    idx = next((i for i, f in enumerate(rec["form"]) if f in ("10-Q", "10-K")), None)
    acc = rec["accessionNumber"][idx].replace("-", "")
    doc = rec["primaryDocument"][idx]
    url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{doc}"
    html = requests.get(url, headers=HEADERS).text
    time.sleep(0.12)
    text = re.sub(r"<[^>]+>", " ", html)
    nums = re.findall(r"([\d,]{7,})\s+shares", text)
    out.append({"ticker": t, "shares": nums[0] if nums else None,
                "date": rec["filingDate"][idx], "url": url})

df = pd.DataFrame(out)
df.to_csv("data/manual_shares.csv", index=False)
print(df.to_string())