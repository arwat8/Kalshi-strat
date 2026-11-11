"""Fetch everything the paper trader needs: Kalshi ladders, books and trades, ZQ, and EFFR.

Every fetch returns plain Python data and never raises on a dead source. It returns None plus a
reason, so one failing source never stops the rest of the daily snapshot from being saved.
"""
import csv
import datetime as dt
import json
import os
import time
import urllib.request

from . import config as C

UA = {"User-Agent": "Mozilla/5.0 (kalshi-strat paper trader; one request per day)",
      "Accept": "application/json"}
MONTH_CODE = "FGHJKMNQUVXZ"


def _get(url, tries=3, pause=2.0):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except Exception as e:          # network, HTTP or JSON error
            last = e
            time.sleep(pause * (i + 1))
    return {"_error": repr(last)}


# --- Kalshi -----------------------------------------------------------------------------
def kalshi_open_markets():
    out, cur = [], ""
    while True:
        r = _get(f"{C.KALSHI_API}/markets?series_ticker={C.KALSHI_SERIES}&status=open&limit=1000"
                 + (f"&cursor={cur}" if cur else ""))
        if "_error" in r:
            return None, r["_error"]
        out += r.get("markets", [])
        cur = r.get("cursor", "")
        if not cur:
            return out, None


def kalshi_book(ticker, depth=50):
    """{'yes_bids': [(price, qty)...], 'no_bids': [...]}, best first. A NO bid at p is a YES offer at 1-p."""
    r = _get(f"{C.KALSHI_API}/markets/{ticker}/orderbook?depth={depth}")
    if "_error" in r:
        return None
    b = r.get("orderbook_fp") or r.get("orderbook") or {}
    yes = [(float(p), float(q)) for p, q in (b.get("yes_dollars") or [])]
    no = [(float(p), float(q)) for p, q in (b.get("no_dollars") or [])]
    return {"yes_bids": sorted(yes, key=lambda x: -x[0]), "no_bids": sorted(no, key=lambda x: -x[0])}


def kalshi_trades(ticker, min_ts):
    """All trades on a contract since min_ts (unix seconds): [{'yes_price', 'count', 'ts'}...]."""
    out, cur = [], ""
    while True:
        r = _get(f"{C.KALSHI_API}/markets/trades?ticker={ticker}&min_ts={int(min_ts)}&limit=1000"
                 + (f"&cursor={cur}" if cur else ""))
        if "_error" in r:
            return out
        for t in r.get("trades", []):
            out.append({"yes_price": float(t.get("yes_price_dollars") or t.get("yes_price", 0)),
                        "count": float(t.get("count_fp") or t.get("count", 0)),
                        "ts": t.get("created_time")})
        cur = r.get("cursor", "")
        if not cur:
            return out


def kalshi_market(ticker):
    r = _get(f"{C.KALSHI_API}/markets/{ticker}")
    return None if "_error" in r else r.get("market")


# --- EFFR and the upper bound ---------------------------------------------------------------
def effr_history(n=90):
    """Last n EFFR fixings. Returns ({date: effr}, {date: upper_bound}, error)."""
    r = _get(C.NYFED_EFFR.format(n=n))
    if "_error" in r:
        return None, None, r["_error"]
    effr, ub = {}, {}
    for x in r.get("refRates", []):
        d = x.get("effectiveDate")
        if d and x.get("percentRate") is not None:
            effr[d] = float(x["percentRate"])
        if d and x.get("targetRateTo") is not None:
            ub[d] = float(x["targetRateTo"])
    return effr, ub, None


# --- ZQ -------------------------------------------------------------------------------------
def zq_settlement(year, month, trade_date):
    """ZQ settlement for contract month (year, month) on trade_date: (price, source) or (None, reason).

    Order: CME public settlements, then Yahoo Finance, then data/manual_zq.csv.
    """
    reasons = []
    r = _get(C.CME_SETTLE.format(d=trade_date.strftime("%m/%d/%Y")))
    if "_error" not in r:
        label = dt.date(year, month, 1).strftime("%b %y").upper()          # e.g. "JAN 27"
        for row in r.get("settlements", []):
            if str(row.get("month", "")).upper().startswith(label):
                try:
                    return float(str(row["settle"]).replace("'", "")), "cme"
                except (KeyError, ValueError):
                    pass
        reasons.append("cme: month not found")
    else:
        reasons.append(f"cme: {r['_error'][:80]}")

    sym = f"ZQ{MONTH_CODE[month - 1]}{year % 100:02d}.CBT"
    y = _get(C.YAHOO_CHART.format(sym=sym))
    try:
        res = y["chart"]["result"][0]
        stamps = res["timestamp"]
        closes = res["indicators"]["quote"][0]["close"]
        for ts, px in sorted(zip(stamps, closes), reverse=True):
            if px is not None and dt.datetime.utcfromtimestamp(ts).date() <= trade_date:
                return float(px), "yahoo"
        reasons.append("yahoo: no close for date")
    except Exception:
        reasons.append(f"yahoo: {str(y.get('_error', 'bad response'))[:80]}")

    if os.path.exists(C.MANUAL_ZQ):
        with open(C.MANUAL_ZQ) as f:
            for row in csv.DictReader(f):
                if row["date"] == trade_date.isoformat() and row["zq_month"] == f"{year}-{month:02d}":
                    return float(row["settle"]), "manual"
        reasons.append("manual: no row")
    return None, "; ".join(reasons)
