"""Fetch Kalshi data for the 2-week replay: markets, hourly candles, trade prints.
Prints coverage counts only, never prices.

Output: replay/raw/kalshi_markets.json, replay/raw/kalshi_candles/<ticker>.json,
        replay/raw/kalshi_trades/<ticker>.json, replay/raw/kalshi_coverage.json
"""
import datetime as dt
import json
import os
import time
import urllib.request

API = "https://api.elections.kalshi.com/trade-api/v2"
OUT = "replay/raw"
EVENTS = ["KXFED-26DEC", "KXFED-27JAN", "KXFED-27MAR"]
CANDLE_START = dt.datetime(2026, 7, 1, tzinfo=dt.timezone.utc)     # history for stale-quote classification
TRADE_START = dt.datetime(2026, 11, 9, 5, 0, tzinfo=dt.timezone.utc)  # 00:00 ET on the first replay day
END = dt.datetime(2026, 11, 21, 5, 0, tzinfo=dt.timezone.utc)        # 00:00 ET Nov 21


def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30) as r:
                return json.loads(r.read())
        except Exception:
            time.sleep(1.5 * (i + 1))
    return None


def main():
    os.makedirs(f"{OUT}/kalshi_candles", exist_ok=True)
    os.makedirs(f"{OUT}/kalshi_trades", exist_ok=True)
    markets, cov = [], {"markets": {}, "candles": {}, "trades": {}, "failures": []}
    for ev in EVENTS:
        r = get(f"{API}/markets?event_ticker={ev}&limit=1000")
        ms = (r or {}).get("markets", [])
        keep = [{k: m.get(k) for k in ("ticker", "event_ticker", "floor_strike", "open_time", "close_time",
                                       "created_time", "status")} for m in ms]
        markets += keep
        cov["markets"][ev] = len(keep)
    json.dump(markets, open(f"{OUT}/kalshi_markets.json", "w"), indent=1)

    s, e = int(CANDLE_START.timestamp()), int(END.timestamp())
    for m in markets:
        t = m["ticker"]
        r = get(f"{API}/series/KXFED/markets/{t}/candlesticks?start_ts={s}&end_ts={e}&period_interval=60")
        if r is None:
            cov["failures"].append(f"candles {t}")
            continue
        c = r.get("candlesticks", [])
        json.dump(c, open(f"{OUT}/kalshi_candles/{t}.json", "w"))
        cov["candles"][t] = len(c)

        out, cur, ok = [], "", True
        while True:
            r = get(f"{API}/markets/trades?ticker={t}&min_ts={int(TRADE_START.timestamp())}"
                    f"&max_ts={e}&limit=1000" + (f"&cursor={cur}" if cur else ""))
            if r is None:
                ok = False
                break
            out += r.get("trades", [])
            cur = r.get("cursor") or ""
            if not cur:
                break
        if not ok:
            cov["failures"].append(f"trades {t}")
        json.dump(out, open(f"{OUT}/kalshi_trades/{t}.json", "w"))
        cov["trades"][t] = len(out)
    json.dump(cov, open(f"{OUT}/kalshi_coverage.json", "w"), indent=1)
    print("markets:", cov["markets"])
    print("tickers with candles:", sum(1 for v in cov["candles"].values() if v), "of", len(markets))
    print("tickers with trades in window:", sum(1 for v in cov["trades"].values() if v))
    print("failures:", cov["failures"])


if __name__ == "__main__":
    main()
