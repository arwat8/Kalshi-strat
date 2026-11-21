"""Fetch ZQ settlements and EFFR for the 2-week replay. Runs on GitHub Actions (the workspace
cannot reach CME, Yahoo, NY Fed or FRED). Prints coverage counts only, never prices, so the
replay stays blind until it runs.

Output: replay/raw/zq.json, replay/raw/effr.json, replay/raw/external_coverage.json
"""
import csv
import datetime as dt
import io
import json
import os
import time
import urllib.request

OUT = "replay/raw"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
      "Accept": "application/json, text/csv, */*"}
MONTH_CODE = "FGHJKMNQUVXZ"
MONTHS = [(2026, 11), (2026, 12), (2027, 1), (2027, 2), (2027, 3), (2027, 4), (2027, 5), (2027, 6)]
DAYS = [dt.date(2026, 11, 2) + dt.timedelta(days=i) for i in range(20)]
DAYS = [d for d in DAYS if d.weekday() < 5]
CME = "https://www.cmegroup.com/CmeWS/mvc/Settlements/Futures/Settlements/305/FUT?tradeDate={d}"
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={p1}&period2={p2}&interval=1d"
NYFED = "https://markets.newyorkfed.org/api/rates/unsecured/effr/last/120.json"
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"


def get(url, as_json=True, tries=3):
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                body = r.read().decode()
                return (json.loads(body) if as_json else body), None
        except Exception as e:
            last = repr(e)[:160]
            time.sleep(2 * (i + 1))
    return None, last


def main():
    os.makedirs(OUT, exist_ok=True)
    cov = {"cme": {}, "yahoo": {}, "effr": {}, "errors": []}
    zq = {"cme": {}, "yahoo": {}}

    # CME daily settlements (product 305 = 30-Day Fed Funds)
    for d in DAYS:
        r, err = get(CME.format(d=d.strftime("%m/%d/%Y")))
        if r is None:
            cov["errors"].append(f"cme {d}: {err}")
            continue
        for y, m in MONTHS:
            label = dt.date(y, m, 1).strftime("%b %y").upper()
            for row in r.get("settlements", []):
                if str(row.get("month", "")).upper().startswith(label):
                    try:
                        px = float(str(row["settle"]).replace("'", ""))
                    except (KeyError, ValueError):
                        continue
                    zq["cme"].setdefault(f"{y}-{m:02d}", {})[d.isoformat()] = px
    for k, v in zq["cme"].items():
        cov["cme"][k] = len(v)

    # Yahoo daily bars (proxy; 'close' may be last trade rather than official settlement)
    p1 = int(dt.datetime(2026, 10, 26, tzinfo=dt.timezone.utc).timestamp())
    p2 = int(dt.datetime(2026, 11, 22, tzinfo=dt.timezone.utc).timestamp())
    for y, m in MONTHS:
        sym = f"ZQ{MONTH_CODE[m - 1]}{y % 100:02d}.CBT"
        r, err = get(YAHOO.format(sym=sym, p1=p1, p2=p2))
        try:
            res = r["chart"]["result"][0]
            off = int(res["meta"].get("gmtoffset", -21600))
            closes = res["indicators"]["quote"][0]["close"]
            out = {}
            for ts, px in zip(res["timestamp"], closes):
                if px is not None:
                    out[dt.datetime.utcfromtimestamp(ts + off).date().isoformat()] = float(px)
            zq["yahoo"][f"{y}-{m:02d}"] = out
            cov["yahoo"][f"{y}-{m:02d}"] = len(out)
        except Exception:
            cov["errors"].append(f"yahoo {sym}: {err or 'bad response'}")

    # EFFR + upper bound: NY Fed, FRED as backup
    effr = {"nyfed": None, "fred_effr": None, "fred_ub": None}
    r, err = get(NYFED)
    if r is not None:
        effr["nyfed"] = r.get("refRates", [])
        cov["effr"]["nyfed_rows"] = len(effr["nyfed"])
    else:
        cov["errors"].append(f"nyfed: {err}")
    for key, sid in (("fred_effr", "EFFR"), ("fred_ub", "DFEDTARU")):
        body, err = get(FRED.format(sid=sid), as_json=False)
        if body:
            rows = {}
            for row in csv.reader(io.StringIO(body)):
                if len(row) == 2 and row[0][:2] == "20" and row[1] not in (".", ""):
                    rows[row[0]] = float(row[1])
            rows = {k: v for k, v in rows.items() if k >= "2026-07-01"}
            effr[key] = rows
            cov["effr"][key] = len(rows)
        else:
            cov["errors"].append(f"fred {sid}: {err}")

    json.dump(zq, open(f"{OUT}/zq.json", "w"), indent=1)
    json.dump(effr, open(f"{OUT}/effr.json", "w"), indent=1)
    json.dump(cov, open(f"{OUT}/external_coverage.json", "w"), indent=1)
    print(json.dumps(cov, indent=1))           # counts and errors only


if __name__ == "__main__":
    main()
