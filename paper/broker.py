"""Paper broker and ledger: opens positions on signals, simulates three ways of filling them,
and books P&L when the meeting and the ZQ month have settled.

Fill methods, logged side by side for every position:
  top   - every Kalshi leg fills at the best quote for the full size (what the backtest assumed)
  walk  - every Kalshi leg fills by walking the live order book. If the book is too thin for the
          full size, the position is 'partial': the matched quantity q (smallest leg) is booked at
          the VWAP for q, with the ZQ hedge scaled by q/N.
  rest  - a resting limit order 1c better than 'top' on every leg; a leg fills only as Kalshi
          prints trade at or through the limit. ZQ is hedged on the day the fill is detected.
          Queue position is not modelled, so this is an optimistic upper bound for resting orders.
          After REST_MAX_DAYS trading days an unfilled order expires; a partly filled one becomes
          'partial' and is booked on the matched quantity.
ZQ always fills at the day's settlement +/- 1 tick, against us.

v1.1: resting fills are recounted from all trade prints since placement on every run (no double
counting, deduplicated by trade id), expiry counts trading days, partial fills are booked.
"""
import calendar
import datetime as dt
from zoneinfo import ZoneInfo

from . import config as C
from .strategy import kalshi_fee, walk
from .tradingdays import add_trading_days, trading_days_between

ET = ZoneInfo("America/New_York")
FILLED = ("filled", "partial")


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
    d, N = ev["direction"], ev["N"]
    legs = _leg_prices(ev, books)
    zq_px = ev["Fa"] if d == "L" else ev["Fb"]
    q = min(min(lg["walk_filled"], N) for lg in legs)          # matched strip size the book allows
    if q >= N:
        walk_status = "filled"
    elif q > 0:
        walk_status = "partial"
        side = "YES" if d == "L" else "NO"
        for lg in legs:                                        # VWAP for the matched quantity only
            lg["walk_px"] = walk(books[lg["ticker"]], side, q)[0]
    else:
        walk_status = "unfillable"
    return {
        "id": f"{ev['meeting']}_{ev['date']}", "meeting": ev["meeting"], "opened": ev["date"],
        "opened_at": now_iso, "direction": d, "N": N, "wc": ev["w"] + ev["c"],
        "zq_month": ev["zq_month"], "signal_bp": ev[f"{d}_top"]["signal"], "gap_bp": ev[f"{d}_top"]["G"],
        "next_meeting_only": ev["next_meeting_only"], "legs": legs,
        "fills": {
            "top": {"status": "filled", "qty": N, "zq_px": zq_px, "date": ev["date"]},
            "walk": {"status": walk_status, "qty": q if q > 0 else 0, "zq_px": zq_px if q > 0 else None,
                     "date": ev["date"] if q > 0 else None},
            "rest": {"status": "working", "qty": 0, "zq_px": None, "date": None, "days": 0, "placed": now_iso},
        },
        "status": "open",
    }


def _ts(s):
    """Kalshi ISO timestamp -> aware datetime, or None."""
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None


def update_resting(pos, trades_by_ticker, today, zq_px_today, zq_source=None):
    """Recompute a working resting order from ALL trade prints since it was placed.

    trades_by_ticker: every Kalshi trade on each leg since placement (the caller fetches from the
    placement time each run). Fills are recounted from scratch, so running this twice, or after a
    missed day, gives the same answer. Prints after the expiry day do not count.
    """
    f = pos["fills"]["rest"]
    if f["status"] != "working":
        return
    N = pos["N"]
    placed = _ts(f["placed"])
    placed_day = placed.astimezone(ET).date() if placed else dt.date.fromisoformat(pos["opened"])
    expiry_day = add_trading_days(placed_day, C.REST_MAX_DAYS)
    cutoff = dt.datetime.combine(expiry_day, dt.time(23, 59, 59), ET)
    for lg in pos["legs"]:
        seen, filled = set(), 0.0
        for i, t in enumerate(trades_by_ticker.get(lg["ticker"], [])):
            key = t.get("id") or f"noid-{i}"
            if key in seen:
                continue
            seen.add(key)
            ts = _ts(t.get("ts"))
            if ts is not None and ((placed and ts < placed) or ts > cutoff):
                continue
            hit = (t["yes_price"] <= lg["rest_limit"] + 1e-9) if lg["side"] == "YES" \
                else (t["yes_price"] >= 1 - lg["rest_limit"] - 1e-9)
            if hit:
                filled += t["count"]
        lg["rest_filled"] = min(N, filled)
    f["days"] = trading_days_between(placed_day, today)
    q = min(lg["rest_filled"] for lg in pos["legs"])
    tick = C.ZQ_TICK * C.ZQ_HALF_SPREAD_TICKS
    done_full = q >= N
    expired = today >= expiry_day
    if (done_full or (expired and q > 0)) and zq_px_today is not None:
        f.update(status="filled" if done_full else "partial", qty=N if done_full else q, date=today.isoformat(),
                 zq_px=zq_px_today + tick if pos["direction"] == "L" else zq_px_today - tick)
        if zq_source is not None and zq_source not in C.TRUSTED_ZQ_SOURCES:
            f["zq_source"], f["unverified"] = zq_source, True
    elif expired and q <= 0:
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
    """Book P&L for every filled or partly filled method. results: {ticker: 'yes'|'no'} from Kalshi."""
    N, d = pos["N"], pos["direction"]
    pnl = {}
    for method, f in pos["fills"].items():
        if f["status"] not in FILLED:
            pnl[method] = None
            continue
        q = f.get("qty") or N
        scale = q / N
        k_usd = 0.0
        for lg in pos["legs"]:
            px = {"top": lg["top_px"], "walk": lg["walk_px"], "rest": lg["rest_limit"]}[method]
            fee = kalshi_fee(q, px, C.KALSHI_MAKER if method == "rest" else C.KALSHI_TAKER)
            won = (results[lg["ticker"]] == "yes") if lg["side"] == "YES" else (results[lg["ticker"]] == "no")
            k_usd += q * ((1.0 if won else 0.0) - px - fee)
        z = (F_final - f["zq_px"]) if d == "L" else (f["zq_px"] - F_final)
        usd = k_usd + scale * (z * 100 * C.DOLLARS_PER_BP - C.ZQ_FEE_USD)
        per_bp = C.DOLLARS_PER_BP * pos["wc"] * scale
        pnl[method] = {"usd": round(usd, 2), "bp": round(usd / per_bp, 3), "qty": q}
    pos.update(status="settled", F_final=F_final, results=results, pnl=pnl)
    return pos
