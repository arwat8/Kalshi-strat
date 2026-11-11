"""Paper broker and ledger: opens positions on signals, simulates three ways of filling them,
and books P&L when the meeting and the ZQ month have settled.

Fill methods, logged side by side for every position:
  top   - every Kalshi leg fills at the best quote (what the backtest assumed)
  walk  - every Kalshi leg fills by walking the live order book for the full size
  rest  - a resting limit order 1c better than 'top' on every leg; a leg fills only as Kalshi
          prints trade at or through the limit. ZQ is hedged on the day the last leg fills.
          Queue position is not modelled, so this is an optimistic upper bound for resting orders.
ZQ always fills at the day's settlement +/- 1 tick (conservative).
"""
import calendar
import datetime as dt

from . import config as C
from .strategy import kalshi_fee, walk


def _leg_prices(ev, books):
    """Per active leg: contract bought, price at top, VWAP to fill N, filled size, resting limit."""
    d, N = ev["direction"], ev["N"]
    legs = []
    for lg in ev["legs"]:
        book = books[lg["ticker"]]
        bid, ask = lg["bid"], lg["ask"]
        if d == "L":                                 # buy YES
            top_px = ask
            limit = max(bid, round(ask - C.REST_IMPROVE, 4))
            vw, got = walk(book, "YES", N)
        else:                                        # buy NO
            top_px = round(1 - bid, 4)
            limit = max(round(1 - ask, 4), round(top_px - C.REST_IMPROVE, 4))
            vw, got = walk(book, "NO", N)
        legs.append({"ticker": lg["ticker"], "strike": lg["strike"], "side": "YES" if d == "L" else "NO",
                     "top_px": top_px, "walk_px": vw, "walk_filled": got,
                     "rest_limit": limit, "rest_filled": 0.0})
    return legs


def open_position(ev, books, now_iso):
    d = ev["direction"]
    legs = _leg_prices(ev, books)
    zq_px = ev["Fa"] if d == "L" else ev["Fb"]
    walk_ok = all(lg["walk_filled"] >= ev["N"] for lg in legs)
    return {
        "id": f"{ev['meeting']}_{ev['date']}", "meeting": ev["meeting"], "opened": ev["date"],
        "opened_at": now_iso, "direction": d, "N": ev["N"], "wc": ev["w"] + ev["c"],
        "zq_month": ev["zq_month"], "signal_bp": ev[f"{d}_top"]["signal"], "gap_bp": ev[f"{d}_top"]["G"],
        "next_meeting_only": ev["next_meeting_only"], "legs": legs,
        "fills": {
            "top": {"status": "filled", "zq_px": zq_px, "date": ev["date"]},
            "walk": {"status": "filled" if walk_ok else "unfillable", "zq_px": zq_px, "date": ev["date"]},
            "rest": {"status": "working", "zq_px": None, "date": None, "days": 0, "placed": now_iso},
        },
        "status": "open",
    }


def update_resting(pos, trades_by_ticker, today, zq_px_today):
    """Advance a working resting order with the trades printed since it was placed."""
    f = pos["fills"]["rest"]
    if f["status"] != "working":
        return
    for lg in pos["legs"]:
        for t in trades_by_ticker.get(lg["ticker"], []):
            hit = (t["yes_price"] <= lg["rest_limit"] + 1e-9) if lg["side"] == "YES" \
                else (t["yes_price"] >= 1 - lg["rest_limit"] - 1e-9)
            if hit:
                lg["rest_filled"] = min(pos["N"], lg["rest_filled"] + t["count"])
    f["days"] += 1
    if all(lg["rest_filled"] >= pos["N"] for lg in pos["legs"]):
        if zq_px_today is not None:
            tick = C.ZQ_TICK * C.ZQ_HALF_SPREAD_TICKS
            f.update(status="filled", date=today.isoformat(),
                     zq_px=zq_px_today + tick if pos["direction"] == "L" else zq_px_today - tick)
    elif f["days"] >= C.REST_MAX_DAYS:
        f["status"] = "expired"


def zq_final(zq_month, effr_by_date):
    """ZQ final settlement = 100 - calendar-day average EFFR over the month (None until complete)."""
    y, m = map(int, zq_month.split("-"))
    n = calendar.monthrange(y, m)[1]
    days = [dt.date(y, m, i + 1) for i in range(n)]
    known = sorted(effr_by_date)
    if not known or dt.date.fromisoformat(known[-1]) < days[-1]:
        return None
    vals, last = [], None
    for d in days:
        for k in known:
            if dt.date.fromisoformat(k) <= d:
                last = effr_by_date[k]
        if last is None:
            return None
        vals.append(last)
    return 100 - sum(vals) / len(vals)


def settle(pos, results, F_final):
    """Book P&L for every filled method. results: {ticker: 'yes'|'no'} from Kalshi."""
    N, d = pos["N"], pos["direction"]
    per_bp = C.DOLLARS_PER_BP * pos["wc"]
    pnl = {}
    for method, f in pos["fills"].items():
        if f["status"] != "filled":
            pnl[method] = None
            continue
        k_usd = 0.0
        for lg in pos["legs"]:
            px = {"top": lg["top_px"], "walk": lg["walk_px"], "rest": lg["rest_limit"]}[method]
            fee = kalshi_fee(N, px, C.KALSHI_MAKER if method == "rest" else C.KALSHI_TAKER)
            won = (results[lg["ticker"]] == "yes") if lg["side"] == "YES" else (results[lg["ticker"]] == "no")
            k_usd += N * ((1.0 if won else 0.0) - px - fee)
        z = (F_final - f["zq_px"]) if d == "L" else (f["zq_px"] - F_final)
        usd = k_usd + z * 100 * C.DOLLARS_PER_BP - C.ZQ_FEE_USD
        pnl[method] = {"usd": round(usd, 2), "bp": round(usd / per_bp, 3)}
    pos.update(status="settled", F_final=F_final, results=results, pnl=pnl)
    return pos
