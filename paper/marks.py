"""Mark-to-market for the dashboard. Measurement only: nothing here feeds back into the rules.

equity.json      one point per trading day: cumulative P&L per fill method (realized + open marks)
intraday/D.json  one point per Actions run on day D while a position is open (Kalshi mids live,
                 ZQ held at the last settlement, so intraday moves are Kalshi-side only)
"""
from . import config as C
from .strategy import kalshi_fee

METHODS = ("top", "walk", "rest")


def yes_mid(book):
    """Two-sided YES mid from a Kalshi book, or None."""
    if not book:
        return None
    yb = book["yes_bids"][0][0] if book.get("yes_bids") else None
    ya = 1 - book["no_bids"][0][0] if book.get("no_bids") else None
    if yb is None or ya is None:
        return None
    return (yb + ya) / 2


def mark_position(pos, mids, zq_now):
    """Unrealized P&L per fill method for an open position.

    mids: {ticker: YES mid (or 1.0/0.0 once the contract has resolved)}. A leg with no mid is
    held at its entry price (zero mark). zq_now: latest ZQ price, or None to hold ZQ at entry.
    """
    N, d = pos["N"], pos["direction"]
    out = {}
    for method in METHODS:
        f = pos["fills"][method]
        if f["status"] not in ("filled", "partial"):
            out[method] = None
            continue
        q = f.get("qty") or N                       # partial fills are marked on the matched quantity
        scale = q / N
        usd = 0.0
        for lg in pos["legs"]:
            px = {"top": lg["top_px"], "walk": lg["walk_px"], "rest": lg["rest_limit"]}[method]
            m = mids.get(lg["ticker"])
            val = px if m is None else (m if lg["side"] == "YES" else 1 - m)
            fee = kalshi_fee(q, px, C.KALSHI_MAKER if method == "rest" else C.KALSHI_TAKER)
            usd += q * (val - px - fee)
        if zq_now is not None and f.get("zq_px") is not None:
            z = (zq_now - f["zq_px"]) if d == "L" else (f["zq_px"] - zq_now)
            usd += scale * z * 100 * C.DOLLARS_PER_BP
        usd -= scale * C.ZQ_FEE_USD
        per_bp = C.DOLLARS_PER_BP * pos["wc"] * scale
        out[method] = {"usd": round(usd, 2), "bp": round(usd / per_bp, 3)}
    return out


def equity_point(positions, t):
    """Cumulative P&L per method: settled P&L plus the latest mark of every open position."""
    usd = {k: 0.0 for k in METHODS}
    bp = {k: 0.0 for k in METHODS}
    for p in positions:
        src = p.get("pnl") if p["status"] == "settled" else (p.get("mark") or {}).get("pnl")
        for k in METHODS:
            v = (src or {}).get(k)
            if v:
                usd[k] += v["usd"]
                bp[k] += v["bp"]
    pt = {"t": t}
    for k in METHODS:
        pt[k] = round(usd[k], 2)
        pt[f"{k}_bp"] = round(bp[k], 3)
    return pt


def upsert_point(points, pt):
    """Replace the point with the same timestamp, else append (kept sorted by time)."""
    points = [x for x in points if x["t"] != pt["t"]] + [pt]
    return sorted(points, key=lambda x: x["t"])
