"""The frozen strip-vs-ZQ rules, applied to one live snapshot.

Pure functions only: give it a ladder (with order books), a ZQ price, EFFR and the upper bound,
and it returns the gap, costs and signal. No network calls here, so the same code can be checked
against historical data.
"""
import calendar
import datetime as dt
import math

from . import config as C


# --- Calendar helpers ----------------------------------------------------------------------
def _carry(by_date, d):
    """Value in force on date d from {date_str: value}, carrying the last value over gaps."""
    best = None
    for k in sorted(by_date):
        if dt.date.fromisoformat(k) <= d:
            best = by_date[k]
    return best


def month_shares(meeting, next_meeting, year, month):
    """a, w, c: shares of the ZQ month before this meeting takes effect, until the next one, after."""
    E = meeting + dt.timedelta(days=1)
    E2 = (next_meeting + dt.timedelta(days=1)) if next_meeting else dt.date(2100, 1, 1)
    n = calendar.monthrange(year, month)[1]
    days = [dt.date(year, month, i + 1) for i in range(n)]
    a = sum(d < E for d in days) / n
    w = sum(E <= d < E2 for d in days) / n
    return a, w, 1 - a - w


def zq_month_for(meeting, all_meetings):
    """Same month map as the backtest: of the meeting month and the next month, take the one with
    the highest (share of the month after the decision) - 2 x (share decided by a later meeting)."""
    best = None
    for k in (0, 1):
        y, m = meeting.year + (meeting.month + k - 1) // 12, (meeting.month + k - 1) % 12 + 1
        n = calendar.monthrange(y, m)[1]
        first, last = dt.date(y, m, 1), dt.date(y, m, n)
        start = max(first, meeting + dt.timedelta(days=1))
        later = [x for x in all_meetings if x > meeting and first <= x <= last]
        end = min(later) if later else last + dt.timedelta(days=1)
        w = max((end - start).days, 0) / n
        contam = ((last - min(later)).days / n) if later else 0.0
        score = w - 2 * contam
        if best is None or score > best[0]:
            best = (score, y, m)
    return best[1], best[2]


def fed_funds_gap(today, effr_by_date, ub_by_date):
    """g(t): mean of (upper bound - EFFR) over the 30 calendar days before today."""
    vals = []
    for i in range(30, 0, -1):
        d = today - dt.timedelta(days=i)
        e, u = _carry(effr_by_date, d), _carry(ub_by_date, d)
        if e is None or u is None:
            return None
        vals.append(u - e)
    return sum(vals) / len(vals)


# --- Order-book helpers --------------------------------------------------------------------
def top(book):
    """Best YES bid and ask, Kalshi convention: no bid = 0, no offer = 1 (a NO bid at p is a YES
    offer at 1 - p). Returns (bid, ask, fresh) where fresh = the book has at least one order."""
    if not book or (not book["yes_bids"] and not book["no_bids"]):
        return 0.0, 1.0, False
    yb = book["yes_bids"][0][0] if book["yes_bids"] else 0.0
    ya = round(1 - book["no_bids"][0][0], 4) if book["no_bids"] else 1.0
    return yb, ya, True


def walk(book, side, n):
    """Average price paid to buy n contracts. side 'YES' lifts the YES offers (NO bids);
    side 'NO' lifts the NO offers (YES bids). Returns (vwap of the contract bought, filled)."""
    levels = ([(1 - p, q) for p, q in book["no_bids"]] if side == "YES"
              else [(1 - p, q) for p, q in book["yes_bids"]])
    levels.sort()
    got, cost = 0.0, 0.0
    for p, q in levels:
        take = min(q, n - got)
        cost += take * p
        got += take
        if got >= n:
            break
    return (cost / got if got else None), got


def kalshi_fee(n, p, rate=None):
    """Per-contract Kalshi fee for an order of n contracts at price p (rounded up to the cent per order)."""
    rate = C.KALSHI_TAKER if rate is None else rate
    return math.ceil(round(rate * n * p * (1 - p) * 100, 6)) / 100 / n


# --- The rules ----------------------------------------------------------------------------
def evaluate(today, meeting, all_meetings, ladder, zq_settle, effr_by_date, ub_by_date):
    """Apply the frozen rules to today's snapshot for one meeting.

    ladder: every open contract for the meeting, [{ticker, strike, book}].
    Returns a dict with the decision and diagnostics. 'eligible' False means a rule blocked the day.
    """
    future = sorted(x for x in all_meetings if x > meeting)
    next_meeting = future[0] if future else None
    y, m = zq_month_for(meeting, all_meetings)
    a, w, c = month_shares(meeting, next_meeting, y, m)
    wc = w + c
    between = [x for x in all_meetings if today < x < meeting]
    out = {"date": today.isoformat(), "meeting": meeting.isoformat(), "zq_month": f"{y}-{m:02d}",
           "a": round(a, 4), "w": round(w, 4), "c": round(c, 4), "next_meeting_only": not between}

    if a > 0 and between:
        return {**out, "eligible": False, "reason": "C3: meeting in between and a > 0"}
    g = fed_funds_gap(today, effr_by_date, ub_by_date)
    U0 = _carry(ub_by_date, today)
    if g is None or U0 is None:
        return {**out, "eligible": False, "reason": "missing EFFR / upper bound history"}
    if zq_settle is None:
        return {**out, "eligible": False, "reason": "missing ZQ price"}
    ladder = sorted(ladder, key=lambda x: x["strike"])
    if not ladder:
        return {**out, "eligible": False, "reason": "empty ladder"}
    tops, mids, fresh = [], [], []
    for x in ladder:
        b, a_, fr = top(x["book"])
        md = (b + a_) / 2
        if not fr:                                   # empty book: C2(b) - a stale price may only
            md = x.get("stale_mid")                  # classify the contract as settled (<2c / >98c)
            if md is None:
                return {**out, "eligible": False, "reason": "empty book and no earlier price (cannot classify)"}
        tops.append((b, a_)); mids.append(md); fresh.append(fr)
    if not (mids[0] >= C.ACTIVE_HI and mids[-1] <= C.ACTIVE_LO):
        return {**out, "eligible": False, "reason": "C4: ladder does not cover both tails"}
    act = [C.ACTIVE_LO <= md <= C.ACTIVE_HI for md in mids]
    if not any(act):
        return {**out, "eligible": False, "reason": "no active threshold"}
    for (b, a_), is_act, fr in zip(tops, act, fresh):
        if is_act and not fr:
            return {**out, "eligible": False, "reason": "C2(b): active leg has no live quote"}
        if is_act and not (b > 0 and a_ < 1 and a_ > b):
            return {**out, "eligible": False, "reason": "active leg fails bid > 0, ask < 1, ask > bid"}

    N = round(C.CONTRACTS_PER_UNIT * wc)
    X1 = ladder[0]["strike"]
    tick = C.ZQ_TICK * C.ZQ_HALF_SPREAD_TICKS
    Fa, Fb = zq_settle + tick, zq_settle - tick                     # settlement-based ZQ fill
    UF = lambda F: ((100 - F) + g - a * U0) / wc
    fixed = [1.0 if md > C.ACTIVE_HI else 0.0 for md in mids]
    dK = (meeting - today).days
    r = _carry(effr_by_date, today - dt.timedelta(days=1)) / 100

    res = {}
    for d in ("L", "H"):
        # L buys YES on active legs (Kalshi implies the lower rate); H buys NO (Kalshi higher)
        p_top, p_walk, filled = [], [], []
        for x, (b, a_), is_act, fx in zip(ladder, tops, act, fixed):
            if not is_act:
                p_top.append(fx); p_walk.append(fx); filled.append(None)
                continue
            vw, got = walk(x["book"], "YES" if d == "L" else "NO", N)
            if d == "L":
                p_top.append(a_); p_walk.append(vw if vw is not None else 1.0)
            else:
                p_top.append(b); p_walk.append(1 - vw if vw is not None else 0.0)   # YES-equivalent
            filled.append(got)
        for mode, prices in (("top", p_top), ("walk", p_walk)):
            UK = X1 + 0.25 * sum(prices)
            G = (UF(Fa) - UK) * 100 if d == "L" else (UK - UF(Fb)) * 100
            paid = [(p if d == "L" else 1 - p) for p, ia in zip(prices, act) if ia]
            kf = 25 * sum(kalshi_fee(N, p) for p in paid)
            zf = C.ZQ_FEE_USD / (C.DOLLARS_PER_BP * wc)
            fund = 25 * sum(paid) * r * dK / 360
            Z = G - kf - zf - fund
            res[f"{d}_{mode}"] = dict(G=round(G, 4), Z=round(Z, 4), kalshi_fee_bp=round(kf, 4),
                                      zq_fee_bp=round(zf, 4), funding_bp=round(fund, 4),
                                      signal=round(Z - C.RESERVE_BP - C.BUFFER_BP, 4))
        res[f"{d}_full_fill"] = all(f is None or f >= N for f in filled)

    best = "H" if res["H_top"]["Z"] > res["L_top"]["Z"] else "L"
    legs = [{"ticker": x["ticker"], "strike": x["strike"], "bid": b, "ask": a_}
            for x, (b, a_), ia in zip(ladder, tops, act) if ia]
    out.update(eligible=True, N=N, g=round(g, 4), U0=U0, zq_settle=zq_settle, Fa=Fa, Fb=Fb,
               X1=X1, fixed_prices=[f for f, ia in zip(fixed, act) if not ia], legs=legs,
               direction=best, **res)
    out["trade"] = res[f"{best}_top"]["signal"] > 0
    return out
