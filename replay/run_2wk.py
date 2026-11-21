"""Blind 2-week replay of the frozen paper-trading rules (v1.1), Nov 9-20, 2026.

Pre-registered in replay/PREREG_2WK.md. Uses the paper trader's own code (paper/strategy.py,
paper/broker.py, paper/marks.py) unchanged. Run once:  python replay/run_2wk.py
Env: RAW (input dir, default replay/raw), OUT (output dir, default replay/results).
"""
import csv
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paper import config as C                                         # noqa: E402
from paper.broker import open_position, update_resting                # noqa: E402
from paper.marks import mark_position                                 # noqa: E402
from paper.run import calendar_check                                  # noqa: E402
from paper.strategy import apply_gate, evaluate, record_only_reasons, zq_month_for   # noqa: E402
from paper.tradingdays import is_trading_day                          # noqa: E402

ET = ZoneInfo("America/New_York")
RAW = os.environ.get("RAW", "replay/raw")
OUT = os.environ.get("OUT", "replay/results")
START, END = dt.date(2026, 11, 9), dt.date(2026, 11, 20)
DAYS = [START + dt.timedelta(days=i) for i in range((END - START).days + 1)]
DAYS = [d for d in DAYS if is_trading_day(d)]
DEPTH = 1e9                     # candles carry no depth: top of book fills full size (backtest convention)
STALE_LOOKBACK_DAYS = 120
VARIANTS = ("strict", "proxy", "fresh60")


def t15(d):
    return dt.datetime.combine(d, dt.time(15, 0), ET)


def _f(x):
    try:
        return None if x in (None, "") else float(x)
    except ValueError:
        return None


# --- load ---------------------------------------------------------------------------------
def load():
    markets = json.load(open(f"{RAW}/kalshi_markets.json"))
    candles, trades = {}, {}
    for m in markets:
        t = m["ticker"]
        p = f"{RAW}/kalshi_candles/{t}.json"
        rows = []
        for c in (json.load(open(p)) if os.path.exists(p) else []):
            rows.append((int(c["end_period_ts"]), _f((c.get("yes_bid") or {}).get("close_dollars")),
                         _f((c.get("yes_ask") or {}).get("close_dollars"))))
        candles[t] = sorted(rows)
        p = f"{RAW}/kalshi_trades/{t}.json"
        tr = []
        for x in (json.load(open(p)) if os.path.exists(p) else []):
            tr.append({"id": x.get("trade_id"), "yes_price": _f(x.get("yes_price_dollars")) or 0.0,
                       "count": _f(x.get("count_fp")) or 0.0, "ts": x.get("created_time")})
        trades[t] = tr
    zq = json.load(open(f"{RAW}/zq.json"))
    eraw = json.load(open(f"{RAW}/effr.json"))
    effr, ub, esrc = {}, {}, None
    if eraw.get("nyfed"):
        for x in eraw["nyfed"]:
            if x.get("effectiveDate") and x.get("percentRate") is not None:
                effr[x["effectiveDate"]] = float(x["percentRate"])
            if x.get("effectiveDate") and x.get("targetRateTo") is not None:
                ub[x["effectiveDate"]] = float(x["targetRateTo"])
        esrc = "nyfed"
    if not effr and eraw.get("fred_effr") and eraw.get("fred_ub"):
        effr, ub, esrc = dict(eraw["fred_effr"]), dict(eraw["fred_ub"]), "fred"
    return markets, candles, trades, zq, effr, ub, esrc


# --- Kalshi quotes from candles -------------------------------------------------------------
def quote(candles, d):
    """Last candle on day d ending at or before 15:00 ET: (bid, ask, age_min) or None."""
    lo = int(dt.datetime.combine(d, dt.time(0, 0), ET).timestamp())
    hi = int(t15(d).timestamp())
    best = None
    for ts, b, a in candles:
        if lo < ts <= hi:
            best = (b, a, (hi - ts) / 60)
    return best


def stale_mid(candles, d):
    hi = int(t15(d).timestamp())
    lo = hi - STALE_LOOKBACK_DAYS * 86400
    mid = None
    for ts, b, a in candles:
        if lo < ts <= hi and b is not None and a is not None and 0 < b < a < 1:
            mid = round((b + a) / 2, 4)
    return mid


def book_from(q):
    if q is None:
        return {"yes_bids": [], "no_bids": []}
    b, a, _ = q
    return {"yes_bids": [(b, DEPTH)] if b is not None and b > 0 else [],
            "no_bids": [(round(1 - a, 4), DEPTH)] if a is not None and a < 1 else []}


def zq_price(zq, month, d, variant):
    ds = d.isoformat()
    px = (zq.get("cme") or {}).get(month, {}).get(ds)
    if px is not None:
        return px, "cme"
    px = (zq.get("yahoo") or {}).get(month, {}).get(ds)
    if px is not None:
        return px, "yahoo"
    return None, "missing"


# --- replay ---------------------------------------------------------------------------------
def replay(variant, markets, candles, trades, zq, effr, ub):
    cal = sorted(dt.date.fromisoformat(x) for x in C.FOMC_DATES)
    events = {}
    for m in markets:
        events.setdefault(m["event_ticker"], []).append(m)
    meet = {e: dt.datetime.fromisoformat(ms[0]["close_time"].replace("Z", "+00:00")).astimezone(ET).date()
            for e, ms in events.items()}
    positions, rows, ages = [], [], {}
    for d in DAYS:
        cut = t15(d)
        listed = [e for e in events if meet[e] > d and any(
            dt.datetime.fromisoformat(m["open_time"].replace("Z", "+00:00")) <= cut for m in events[e])]
        cal_ok = calendar_check([meet[e] for e in listed], d)["ok"]
        for e in sorted(listed, key=lambda e: meet[e])[: C.MEETINGS_AHEAD]:
            ladder, books, qage = [], {}, {}
            for m in sorted(events[e], key=lambda m: m.get("floor_strike") or 0):
                if dt.datetime.fromisoformat(m["open_time"].replace("Z", "+00:00")) > cut:
                    continue
                q = quote(candles[m["ticker"]], d)
                bk = book_from(q)
                books[m["ticker"]] = bk
                qage[m["ticker"]] = None if q is None else q[2]
                ladder.append({"ticker": m["ticker"], "strike": m["floor_strike"], "book": bk,
                               "stale_mid": stale_mid(candles[m["ticker"]], d)})
            y, mo = zq_month_for(meet[e], cal)
            px, src = zq_price(zq, f"{y}-{mo:02d}", d, variant)
            ev = evaluate(d, meet[e], cal, ladder, px, effr, ub)
            gate_src = src if px is not None else None
            if variant in ("proxy", "fresh60") and src == "yahoo":
                gate_src = "cme"                         # these variants accept Yahoo when CME is missing
            reasons = record_only_reasons(gate_src, 0.0, cal_ok)
            if variant == "fresh60" and ev.get("eligible"):
                old = [lg["ticker"] for lg in ev.get("legs", []) if (qage.get(lg["ticker"]) or 1e9) > 60]
                if old:
                    reasons.append(f"active-leg quote older than 60 min: {', '.join(old)}")
            apply_gate(ev, reasons)
            for lg in ev.get("legs", []):
                ages.setdefault(lg["ticker"], []).append(qage.get(lg["ticker"]))
            d_best = ev.get("direction")
            rows.append({
                "variant": variant, "date": d.isoformat(), "meeting": meet[e].isoformat(), "zq_month": f"{y}-{mo:02d}",
                "zq_source": src, "eligible": ev.get("eligible"), "reason": ev.get("reason") or "",
                "direction": d_best or "", "N": ev.get("N"),
                "L_gap_bp": (ev.get("L_top") or {}).get("G"), "L_signal_bp": (ev.get("L_top") or {}).get("signal"),
                "H_gap_bp": (ev.get("H_top") or {}).get("G"), "H_signal_bp": (ev.get("H_top") or {}).get("signal"),
                "trade": ev.get("trade"), "trade_if_allowed": ev.get("trade_if_allowed"),
                "record_only": " | ".join(ev.get("record_only", [])),
                "active_legs": ";".join(lg["ticker"] for lg in ev.get("legs", [])),
                "active_leg_quote_age_min": ";".join(
                    "" if qage.get(lg["ticker"]) is None else f"{qage[lg['ticker']]:.0f}" for lg in ev.get("legs", [])),
            })
            if ev.get("trade") and not any(p["meeting"] == ev["meeting"] for p in positions):
                pos = open_position(ev, books, f"{d.isoformat()}T17:45:00-05:00")
                pos["fills"]["walk"] = {"status": "not_reproducible", "qty": 0, "zq_px": None, "date": None}
                pos["zq_source"] = src
                positions.append(pos)
        # end of day: advance resting orders with prints up to the end of day d
        eod_cut = dt.datetime.combine(d, dt.time(23, 59, 59), ET)
        for p in positions:
            if p["fills"]["rest"]["status"] != "working":
                continue
            tr = {lg["ticker"]: [t for t in trades.get(lg["ticker"], [])
                                 if t["ts"] and dt.datetime.fromisoformat(t["ts"].replace("Z", "+00:00")) <= eod_cut]
                  for lg in p["legs"]}
            zpx, zsrc = zq_price(zq, p["zq_month"], d, variant)
            update_resting(p, tr, d, zpx, zsrc if zpx is not None else None)

    # daily marks and final valuation (nothing settles inside the window)
    marks = []
    for d in DAYS:
        for p in positions:
            if dt.date.fromisoformat(p["opened"]) > d:
                continue
            mids = {}
            for lg in p["legs"]:
                q = quote(candles[lg["ticker"]], d)
                if q and q[0] is not None and q[1] is not None and 0 < q[0] < q[1] < 1:
                    mids[lg["ticker"]] = (q[0] + q[1]) / 2
                else:
                    mids[lg["ticker"]] = stale_mid(candles[lg["ticker"]], d)
            zpx, _ = zq_price(zq, p["zq_month"], d, variant)
            pn = mark_position(p, mids, zpx)
            marks.append({"variant": variant, "date": d.isoformat(), "position": p["id"],
                          **{f"{k}_usd": (v or {}).get("usd") for k, v in pn.items()},
                          **{f"{k}_bp": (v or {}).get("bp") for k, v in pn.items()}})
            if d == DAYS[-1]:
                p["mark_final"] = {"date": d.isoformat(), "zq_px": zpx, "mids": mids, "pnl": pn}
    return rows, positions, marks, ages


def main():
    os.makedirs(OUT, exist_ok=True)
    markets, candles, trades, zq, effr, ub, esrc = load()
    need = set()
    cal = sorted(dt.date.fromisoformat(x) for x in C.FOMC_DATES)
    for d in DAYS:
        for mdate in [x for x in cal if x > d][:3]:
            y, mo = zq_month_for(mdate, cal)
            need.add((f"{y}-{mo:02d}", d.isoformat()))
    cme_have = sum(1 for m, d in need if (zq.get("cme") or {}).get(m, {}).get(d) is not None)
    yah_have = sum(1 for m, d in need if (zq.get("yahoo") or {}).get(m, {}).get(d) is not None)
    both = [(m, d) for m, d in need if (zq.get("cme") or {}).get(m, {}).get(d) is not None
            and (zq.get("yahoo") or {}).get(m, {}).get(d) is not None]
    diffs = [abs(zq["cme"][m][d] - zq["yahoo"][m][d]) for m, d in both]
    headline = "strict" if need and cme_have / len(need) >= 0.8 else "proxy"
    coverage = {"days": [d.isoformat() for d in DAYS], "zq_needed": len(need), "zq_cme": cme_have, "zq_yahoo": yah_have,
                "cme_vs_yahoo_pairs": len(both), "cme_vs_yahoo_max_abs_diff": max(diffs) if diffs else None,
                "effr_source": esrc, "effr_days": len(effr), "headline_variant": headline}

    all_rows, all_pos, all_marks, ages_h = [], {}, [], {}
    for v in VARIANTS:
        rows, pos, marks, ages = replay(v, markets, candles, trades, zq, effr, ub)
        all_rows += rows
        all_pos[v] = pos
        all_marks += marks
        if v == headline:
            ages_h = ages
    with open(f"{OUT}/evaluations.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(all_rows[0]))
        w.writeheader()
        w.writerows(all_rows)
    if all_marks:
        keys = sorted({k for r in all_marks for k in r}, key=lambda k: (k not in ("variant", "date", "position"), k))
        with open(f"{OUT}/marks.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(all_marks)
    json.dump(all_pos, open(f"{OUT}/positions.json", "w"), indent=1, default=str)
    json.dump(coverage, open(f"{OUT}/coverage.json", "w"), indent=1)

    # human summary
    L = [f"# Blind 2-week replay, {DAYS[0]} to {DAYS[-1]} ({len(DAYS)} trading days)", "",
         f"Headline variant: **{headline}** (pre-registered rule: strict if CME covers >= 80% of needed ZQ prices).", "",
         "## Data coverage", "", "```", json.dumps(coverage, indent=1), "```", ""]
    for v in VARIANTS:
        rs = [r for r in all_rows if r["variant"] == v]
        L += [f"## Variant: {v}", "", "| Date | Meeting | Eligible | Reason / gate | Dir | L gap | L signal | H gap | H signal | Trade |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        fmt = lambda x: "" if x is None else f"{x:.2f}"
        for r in rs:
            why = r["reason"] or r["record_only"]
            L.append(f"| {r['date']} | {r['meeting']} | {r['eligible']} | {why} | {r['direction']} | {fmt(r['L_gap_bp'])} | "
                     f"{fmt(r['L_signal_bp'])} | {fmt(r['H_gap_bp'])} | {fmt(r['H_signal_bp'])} | {r['trade']} |")
        L += ["", "Positions:", ""]
        if not all_pos[v]:
            L.append("- none")
        for p in all_pos[v]:
            mf = p.get("mark_final", {}).get("pnl", {})
            cell = lambda m: "—" if not mf.get(m) else f"${mf[m]['usd']:,.2f} ({mf[m]['bp']:+.2f}bp)"
            L.append(f"- {p['meeting']} meeting, opened {p['opened']}, {p['direction']}, N={p['N']}, signal {p['signal_bp']:.2f}bp; "
                     f"rest fill: {p['fills']['rest']['status']}; mark at {DAYS[-1]}: top {cell('top')}, rest {cell('rest')}")
        L.append("")
    if ages_h:
        L += ["## Active-leg quote age at 15:00 (headline variant, minutes since last candle)", ""]
        for t, a in sorted(ages_h.items()):
            a = [x for x in a if x is not None]
            L.append(f"- {t}: n={len(a)}, median {sorted(a)[len(a)//2]:.0f}" if a else f"- {t}: no same-day quote")
    open(f"{OUT}/summary.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
