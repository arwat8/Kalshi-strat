"""Daily orchestrator. Run with:  python -m paper.run [auto|snapshot|eod|report]

auto (what GitHub Actions calls every 15 minutes on weekdays):
  - between 2:50 and 3:45pm ET, if today has no snapshot yet: save the Kalshi snapshot
  - after 5:30pm ET, if today has a snapshot but no end-of-day run: run eod
  - on Saturdays: write the weekly report
snapshot: full order book for every contract on the next few Fed meetings, timestamped.
eod:      pull EFFR and ZQ settlements, apply the frozen rules to today's snapshot, open paper
          positions, advance resting orders, settle finished positions, write the equity mark.
mark:     intraday mark of open positions for the dashboard (auto runs it on every weekday call).
"""
import csv
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

from . import config as C
from . import data_sources as S
from .broker import open_position, settle, update_resting, zq_final
from .marks import equity_point, mark_position, upsert_point, yes_mid
from .strategy import evaluate, zq_month_for

ET = ZoneInfo("America/New_York")
DATA = "data"
POS = os.path.join(DATA, "positions.json")


def _now():
    return dt.datetime.now(ET)


def _path(*p):
    full = os.path.join(DATA, *p)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    return full


def _load(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


def _save(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=1, default=str)


def _append_csv(name, row):
    path = _path(name)
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row))
        if new:
            w.writeheader()
        w.writerow(row)


def _meeting_date(close_time):
    return dt.datetime.fromisoformat(close_time.replace("Z", "+00:00")).astimezone(ET).date()


# --- snapshot -----------------------------------------------------------------------------
def snapshot(now):
    markets, err = S.kalshi_open_markets()
    if markets is None:
        _append_csv("source_log.csv", {"time": now.isoformat(), "step": "snapshot", "source": "kalshi", "ok": 0, "note": err})
        return False
    events = {}
    for m in markets:
        events.setdefault(m["event_ticker"], []).append(m)
    cal = sorted({_meeting_date(ms[0]["close_time"]) for ms in events.values()})
    upcoming = [e for e in sorted(events, key=lambda e: _meeting_date(events[e][0]["close_time"]))
                if _meeting_date(events[e][0]["close_time"]) > now.date()][: C.MEETINGS_AHEAD]
    out = {"time": now.isoformat(), "calendar": [d.isoformat() for d in cal], "events": {}}
    last = _load(_path("last_quotes.json"), {})          # last two-sided mid seen for each contract
    for e in upcoming:
        ladder = []
        for m in sorted(events[e], key=lambda m: m.get("floor_strike") or 0):
            bk = S.kalshi_book(m["ticker"])
            yb = bk["yes_bids"][0][0] if bk and bk["yes_bids"] else None
            ya = 1 - bk["no_bids"][0][0] if bk and bk["no_bids"] else None
            if yb is not None and ya is not None:
                last[m["ticker"]] = {"mid": round((yb + ya) / 2, 4), "date": now.date().isoformat()}
            stale = last.get(m["ticker"], {}).get("mid")
            if stale is None and m.get("last_price_dollars") not in (None, ""):
                stale = float(m["last_price_dollars"])     # Kalshi's last traded price as a fallback
            ladder.append({"ticker": m["ticker"], "strike": m.get("floor_strike"), "book": bk, "stale_mid": stale})
        out["events"][e] = {"meeting": _meeting_date(events[e][0]["close_time"]).isoformat(), "ladder": ladder}
    _save(_path("snapshots", f"{now.date()}.json"), out)
    _save(_path("last_quotes.json"), last)
    _append_csv("source_log.csv", {"time": now.isoformat(), "step": "snapshot", "source": "kalshi", "ok": 1,
                                   "note": f"{len(upcoming)} meetings"})
    return True


# --- end of day ---------------------------------------------------------------------------
def eod(now):
    today = now.date()
    snap = _load(_path("snapshots", f"{today}.json"), None)
    if snap is None:
        return False
    effr, ub, err = S.effr_history(90)
    _append_csv("source_log.csv", {"time": now.isoformat(), "step": "eod", "source": "nyfed_effr",
                                   "ok": int(effr is not None), "note": err or f"{len(effr)} days"})
    cal = [dt.date.fromisoformat(d) for d in snap["calendar"]]
    positions = _load(POS, [])
    zq_cache, evals = {}, []

    for e, info in snap["events"].items():
        meeting = dt.date.fromisoformat(info["meeting"])
        y, m = zq_month_for(meeting, cal)
        if (y, m) not in zq_cache:
            zq_cache[(y, m)] = S.zq_settlement(y, m, today)
            px, src = zq_cache[(y, m)]
            _append_csv("source_log.csv", {"time": now.isoformat(), "step": "eod", "source": f"zq {y}-{m:02d}",
                                           "ok": int(px is not None), "note": src})
        px = zq_cache[(y, m)][0]
        ev = evaluate(today, meeting, cal, info["ladder"], px, effr or {}, ub or {})
        ev["event"], ev["snapshot_time"] = e, snap["time"]
        evals.append(ev)
        row = {k: ev.get(k) for k in ("date", "event", "meeting", "zq_month", "eligible", "reason",
                                      "next_meeting_only", "direction", "N", "g", "zq_settle", "trade")}
        for d in ("L", "H"):
            for mode in ("top", "walk"):
                r = ev.get(f"{d}_{mode}") or {}
                row[f"{d}_{mode}_gap_bp"], row[f"{d}_{mode}_signal_bp"] = r.get("G"), r.get("signal")
        _append_csv("signals.csv", row)
        if ev.get("trade") and not any(p["meeting"] == ev["meeting"] for p in positions):
            books = {x["ticker"]: x["book"] for x in info["ladder"]}
            positions.append(open_position(ev, books, now.isoformat()))

    # advance resting orders and settle what has finished
    for p in positions:
        if p["status"] != "open":
            continue
        if p["fills"]["rest"]["status"] == "working":
            since = dt.datetime.fromisoformat(p["fills"]["rest"]["placed"]).timestamp()
            trades = {lg["ticker"]: S.kalshi_trades(lg["ticker"], since) for lg in p["legs"]}
            y, m = map(int, p["zq_month"].split("-"))
            zpx = zq_cache.get((y, m), S.zq_settlement(y, m, today))[0]
            update_resting(p, trades, today, zpx)
        if dt.date.fromisoformat(p["meeting"]) < today and effr:
            results = {}
            for lg in p["legs"]:
                mk = S.kalshi_market(lg["ticker"]) or {}
                results[lg["ticker"]] = mk.get("result")
            F = zq_final(p["zq_month"], effr)
            if F is not None and all(v in ("yes", "no") for v in results.values()):
                settle(p, results, F)
                p["settled_on"] = today.isoformat()

    # mark open positions for the dashboard (measurement only)
    mids = {x["ticker"]: yes_mid(x["book"]) for info in snap["events"].values() for x in info["ladder"]}
    last = _load(_path("last_quotes.json"), {})
    for p in positions:
        if p["status"] != "open":
            continue
        pm = {}
        for lg in p["legs"]:
            t = lg["ticker"]
            if mids.get(t) is not None:
                pm[t] = mids[t]
            else:                                    # meeting passed: resolved value, else last mid
                res = (S.kalshi_market(t) or {}).get("result")
                pm[t] = 1.0 if res == "yes" else 0.0 if res == "no" else last.get(t, {}).get("mid")
        y, m = map(int, p["zq_month"].split("-"))
        zpx = zq_cache.get((y, m), S.zq_settlement(y, m, today))[0]
        p["mark"] = {"date": today.isoformat(), "zq_px": zpx, "mids": pm, "pnl": mark_position(p, pm, zpx)}
    eq = _load(_path("equity.json"), {"start_capital": C.START_CAPITAL, "points": []})
    eq["start_capital"], eq["updated"] = C.START_CAPITAL, now.isoformat()
    eq["points"] = upsert_point(eq["points"], equity_point(positions, today.isoformat()))
    _save(_path("equity.json"), eq)

    _save(POS, positions)
    _save(_path("daily", f"{today}.json"), evals)
    return True


# --- intraday mark ------------------------------------------------------------------------
def mark(now):
    """Mark open positions at live Kalshi mids (ZQ held at its last settlement)."""
    positions = _load(POS, [])
    if not any(p["status"] == "open" for p in positions):
        return False
    marked = []
    for p in positions:
        if p["status"] != "open":
            marked.append(p)
            continue
        pm = dict((p.get("mark") or {}).get("mids") or {})
        for lg in p["legs"]:
            m = yes_mid(S.kalshi_book(lg["ticker"]))
            if m is not None:
                pm[lg["ticker"]] = m
        zpx = (p.get("mark") or {}).get("zq_px")
        marked.append({**p, "mark": {"pnl": mark_position(p, pm, zpx)}})
    path = _path("intraday", f"{now.date()}.json")
    day = _load(path, {"date": now.date().isoformat(), "points": []})
    day["points"] = upsert_point(day["points"], equity_point(marked, now.replace(second=0, microsecond=0).isoformat()))
    _save(path, day)
    return True


# --- weekly report ------------------------------------------------------------------------
def report(now):
    from .report import write_report
    write_report(now)
    return True


def main(mode="auto"):
    now = _now()
    done = lambda kind: os.path.exists(_path(kind, f"{now.date()}.json"))
    if mode == "snapshot":
        return snapshot(now)
    if mode == "eod":
        return eod(now)
    if mode == "report":
        return report(now)
    if mode == "mark":
        return mark(now)
    hm = now.strftime("%H:%M")
    if now.weekday() == 5:
        return False if os.path.exists(os.path.join("reports", f"weekly_{now.date()}.md")) else report(now)
    if now.weekday() < 5:
        acted = False
        if C.SNAP_WINDOW[0] <= hm <= C.SNAP_WINDOW[1] and not done("snapshots"):
            acted = snapshot(now)
        elif hm >= C.EOD_AFTER and done("snapshots") and not done("daily"):
            acted = eod(now)
        if C.INTRADAY_MARKS and "09:30" <= hm <= "18:00":
            mark(now)
        return acted
    return False


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "auto")
