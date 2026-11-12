"""Daily orchestrator. Run with:  python -m paper.run [auto|snapshot|eod|report|mark]

auto (called by the external scheduler at ~2:50pm and ~5:45pm ET, with GitHub's own schedule as backup):
  - between 14:40 and 15:45 ET, if today has no snapshot yet: wait until 15:00:00 ET, then save
    the Kalshi snapshot
  - after 17:30 ET, if today has a snapshot but no end-of-day run: run eod
  - while a position is open: intraday mark for the dashboard
  - on Saturdays: write the weekly report
  - market holidays are skipped
Every step checks whether it already ran today, so duplicate triggers do nothing.

snapshot: full order book for every contract on the next few Fed meetings, timestamped.
eod:      pull EFFR and ZQ settlements, apply the frozen rules to today's snapshot, apply the
          data-quality gate, open paper positions, advance resting orders, settle finished
          positions, write the equity mark and the daily checks log.
mark:     intraday mark of open positions for the dashboard.
Set FORCE=1 to re-run snapshot or eod on a day that already has one.
"""
import csv
import datetime as dt
import json
import os
import sys
import time
from zoneinfo import ZoneInfo

from . import config as C
from . import data_sources as S
from .broker import open_position, settle, update_resting, zq_final
from .marks import equity_point, mark_position, upsert_point, yes_mid
from .strategy import apply_gate, evaluate, record_only_reasons, zq_month_for
from .tradingdays import is_trading_day

ET = ZoneInfo("America/New_York")
DATA = "data"
POS = os.path.join(DATA, "positions.json")
FORCE = os.environ.get("FORCE") == "1"


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
    if not new:                                   # keep one header; add new columns at the end
        with open(path) as f:
            head = next(csv.reader(f), [])
        if any(k not in head for k in row):
            with open(path) as f:
                old = list(csv.DictReader(f))
            head = head + [k for k in row if k not in head]
            with open(path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=head)
                w.writeheader()
                w.writerows(old)
        fields = head
    else:
        fields = list(row)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new:
            w.writeheader()
        w.writerow(row)


def _meeting_date(close_time):
    return dt.datetime.fromisoformat(close_time.replace("Z", "+00:00")).astimezone(ET).date()


def _target(day):
    h, m = map(int, C.SNAPSHOT_TARGET.split(":"))
    return dt.datetime.combine(day, dt.time(h, m), ET)


def _official_calendar():
    return sorted(dt.date.fromisoformat(d) for d in C.FOMC_DATES)


def calendar_check(kalshi_dates, today):
    """Compare Kalshi's listed meeting dates with the official FOMC calendar for the next few meetings."""
    official = _official_calendar()
    k_next = sorted(d for d in set(kalshi_dates) if d > today)[: C.MEETINGS_AHEAD]
    off_next = [d for d in official if d > today][: C.MEETINGS_AHEAD]
    not_official = [d.isoformat() for d in k_next if d not in official]
    missing = [d.isoformat() for d in off_next if d not in set(kalshi_dates)]
    return {"ok": not not_official and not missing, "kalshi_next": [d.isoformat() for d in k_next],
            "official_next": [d.isoformat() for d in off_next], "kalshi_not_official": not_official,
            "official_missing_on_kalshi": missing}


# --- snapshot -----------------------------------------------------------------------------
def snapshot(now):
    target = _target(now.date())
    if now < target and (target - now).total_seconds() <= 25 * 60:
        time.sleep((target - now).total_seconds())          # line up with the 14:59-15:00 ZQ settlement
    t0 = _now()
    markets, err = S.kalshi_open_markets()
    if markets is None:
        _append_csv("source_log.csv", {"time": t0.isoformat(), "step": "snapshot", "source": "kalshi", "ok": 0, "note": err})
        return False
    events = {}
    for m in markets:
        events.setdefault(m["event_ticker"], []).append(m)
    date_of = {e: _meeting_date(ms[0]["close_time"]) for e, ms in events.items()}
    upcoming = sorted((e for e in events if date_of[e] > t0.date()), key=lambda e: date_of[e])[: C.MEETINGS_AHEAD]
    cal_check = calendar_check(list(date_of.values()), t0.date())

    # the official FOMC calendar drives the rules; Kalshi's listings only have to agree with it
    out = {"time": t0.isoformat(), "calendar": [d.isoformat() for d in _official_calendar()],
           "calendar_check": cal_check, "events": {}}
    last = _load(_path("last_quotes.json"), {})          # last two-sided mid seen for each contract
    for e in upcoming:
        ladder = []
        for m in sorted(events[e], key=lambda m: m.get("floor_strike") or 0):
            bk = S.kalshi_book(m["ticker"])
            yb = bk["yes_bids"][0][0] if bk and bk["yes_bids"] else None
            ya = 1 - bk["no_bids"][0][0] if bk and bk["no_bids"] else None
            if yb is not None and ya is not None:
                last[m["ticker"]] = {"mid": round((yb + ya) / 2, 4), "date": t0.date().isoformat()}
            stale = last.get(m["ticker"], {}).get("mid")
            if stale is None and m.get("last_price_dollars") not in (None, ""):
                stale = float(m["last_price_dollars"])     # Kalshi's last traded price as a fallback
            ladder.append({"ticker": m["ticker"], "strike": m.get("floor_strike"), "book": bk, "stale_mid": stale})
        out["events"][e] = {"meeting": date_of[e].isoformat(), "ladder": ladder}
    t1 = _now()
    tgt = _target(t0.date())
    out["time_end"] = t1.isoformat()
    out["skew_min"] = round(max(abs((t0 - tgt).total_seconds()), abs((t1 - tgt).total_seconds())) / 60, 2)
    _save(_path("snapshots", f"{t0.date()}.json"), out)
    _save(_path("last_quotes.json"), last)
    _append_csv("source_log.csv", {"time": t0.isoformat(), "step": "snapshot", "source": "kalshi", "ok": 1,
                                   "note": f"{len(upcoming)} meetings; skew {out['skew_min']} min; calendar ok={cal_check['ok']}"})
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
    cal_ok = bool((snap.get("calendar_check") or {}).get("ok"))
    skew = snap.get("skew_min")
    positions = _load(POS, [])
    zq_cache, evals, checks = {}, [], []

    def zq(y, m):
        if (y, m) not in zq_cache:
            zq_cache[(y, m)] = S.zq_settlement(y, m, today)
            px, src = zq_cache[(y, m)]
            _append_csv("source_log.csv", {"time": now.isoformat(), "step": "eod", "source": f"zq {y}-{m:02d}",
                                           "ok": int(px is not None), "note": src})
        return zq_cache[(y, m)]

    for e, info in snap["events"].items():
        meeting = dt.date.fromisoformat(info["meeting"])
        y, m = zq_month_for(meeting, cal)
        px, src = zq(y, m)
        ev = evaluate(today, meeting, cal, info["ladder"], px, effr or {}, ub or {})
        apply_gate(ev, record_only_reasons(src if px is not None else None, skew, cal_ok))
        ev["event"], ev["snapshot_time"], ev["zq_source"] = e, snap["time"], src if px is not None else None
        evals.append(ev)
        row = {k: ev.get(k) for k in ("date", "event", "meeting", "zq_month", "eligible", "reason",
                                      "next_meeting_only", "direction", "N", "g", "zq_settle", "trade")}
        for d in ("L", "H"):
            for mode in ("top", "walk"):
                r = ev.get(f"{d}_{mode}") or {}
                row[f"{d}_{mode}_gap_bp"], row[f"{d}_{mode}_signal_bp"] = r.get("G"), r.get("signal")
        row["zq_source"], row["snapshot_skew_min"] = ev["zq_source"], skew
        row["record_only"] = " | ".join(ev.get("record_only", []))
        row["trade_if_allowed"] = ev.get("trade_if_allowed")
        _append_csv("signals.csv", row)
        checks.append({"event": e, "meeting": info["meeting"], "ladder_strikes": len(info["ladder"]),
                       "eligible": ev.get("eligible"), "reason": ev.get("reason"), "trade": ev.get("trade"),
                       "trade_if_allowed": ev.get("trade_if_allowed"), "record_only": ev.get("record_only", []),
                       "zq_month": ev.get("zq_month"), "zq_source": ev["zq_source"]})
        if ev.get("trade") and not any(p["meeting"] == ev["meeting"] for p in positions):
            books = {x["ticker"]: x["book"] for x in info["ladder"]}
            pos = open_position(ev, books, now.isoformat())
            pos["zq_source"] = src
            positions.append(pos)

    # advance resting orders and settle what has finished
    for p in positions:
        if p["status"] != "open":
            continue
        y, m = map(int, p["zq_month"].split("-"))
        if p["fills"]["rest"]["status"] == "working":
            since = dt.datetime.fromisoformat(p["fills"]["rest"]["placed"]).timestamp()
            trades = {lg["ticker"]: S.kalshi_trades(lg["ticker"], since) for lg in p["legs"]}
            zpx, zsrc = zq(y, m)
            update_resting(p, trades, today, zpx, zsrc if zpx is not None else None)
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
        zpx = zq(y, m)[0]
        p["mark"] = {"date": today.isoformat(), "zq_px": zpx, "mids": pm, "pnl": mark_position(p, pm, zpx)}
    eq = _load(_path("equity.json"), {"start_capital": C.START_CAPITAL, "points": []})
    eq["start_capital"], eq["updated"] = C.START_CAPITAL, now.isoformat()
    eq["points"] = upsert_point(eq["points"], equity_point(positions, today.isoformat()))
    _save(_path("equity.json"), eq)

    _save(POS, positions)
    _save(_path("daily", f"{today}.json"), evals)
    _save(_path("checks", f"{today}.json"), {
        "date": today.isoformat(), "snapshot_time": snap["time"], "snapshot_skew_min": skew,
        "snapshot_skew_limit_min": C.MAX_SNAPSHOT_SKEW_MIN, "calendar_check": snap.get("calendar_check"),
        "effr_ok": effr is not None, "zq_sources": {f"{y}-{m:02d}": v[1] for (y, m), v in zq_cache.items()},
        "meetings": checks, "open_positions": sum(p["status"] == "open" for p in positions),
    })
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
        return snapshot(now) if (FORCE or not done("snapshots")) else False
    if mode == "eod":
        return eod(now) if (FORCE or not done("daily")) else False
    if mode == "report":
        return report(now)
    if mode == "mark":
        return mark(now)
    hm = now.strftime("%H:%M")
    if now.weekday() == 5:
        return False if os.path.exists(os.path.join("reports", f"weekly_{now.date()}.md")) else report(now)
    if not is_trading_day(now.date()):
        return False
    acted = False
    if C.SNAP_WINDOW[0] <= hm <= C.SNAP_WINDOW[1] and not done("snapshots"):
        acted = snapshot(now)
    elif hm >= C.EOD_AFTER and done("snapshots") and not done("daily"):
        acted = eod(now)
    if C.INTRADAY_MARKS and "09:30" <= _now().strftime("%H:%M") <= "18:00":
        mark(_now())
    return acted


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "auto")
