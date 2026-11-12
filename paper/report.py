"""Weekly report: what the recorder saw, what traded, and P&L by fill method."""
import csv
import json
import os
from collections import Counter


def _rows(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def write_report(now):
    sig = _rows("data/signals.csv")
    src = _rows("data/source_log.csv")
    pos = json.load(open("data/positions.json")) if os.path.exists("data/positions.json") else []
    days = sorted({r["date"] for r in sig})
    elig = [r for r in sig if r["eligible"] == "True"]
    reasons = Counter(r["reason"] for r in sig if r["eligible"] != "True")
    gaps = []
    for r in elig:
        for d in ("L", "H"):
            g = _f(r.get(f"{d}_top_gap_bp"))
            if g is not None:
                gaps.append((g, d, r["date"], r["event"]))
    gaps.sort(reverse=True)

    L = [f"# Paper trading report, {now.date()}", "",
         f"- Days recorded: {len(days)} ({days[0] if days else '-'} to {days[-1] if days else '-'})",
         f"- Meeting-days evaluated: {len(sig)}; eligible under the rules: {len(elig)}",
         f"- Signals (trade = True): {sum(r['trade'] == 'True' for r in sig)}",
         f"- Signals blocked by the data-quality gate (record only): {sum(r.get('trade_if_allowed') == 'True' for r in sig)}",
         f"- Meeting-days recorded as record-only: {sum(bool(r.get('record_only')) for r in sig)}", ""]
    L += ["## Why days were not eligible", "", "| Reason | Count |", "| --- | --- |"]
    L += [f"| {k} | {v} |" for k, v in reasons.most_common()] or ["| none | 0 |"]
    L += ["", "## Largest executable gaps seen (top of book, before costs)", "",
          "| Date | Meeting | Direction | Gap (bp) |", "| --- | --- | --- | --- |"]
    L += [f"| {d} | {e} | {di} | {g:.2f} |" for g, di, d, e in gaps[:10]] or ["| - | - | - | - |"]
    L += ["", "## Positions", "",
          "| Meeting | Opened | Dir | Next-meeting only | Signal (bp) | Status | Top P&L | Walk P&L | Rest P&L |",
          "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    tot = Counter()
    for p in pos:
        pn = p.get("pnl") or {}
        cell = lambda m: ((f"${pn[m]['usd']:,.0f} ({pn[m]['bp']:+.2f}bp)" + (" partial" if p["fills"][m]["status"] == "partial" else ""))
                          if pn.get(m) else p["fills"][m]["status"])
        for m in ("top", "walk", "rest"):
            if pn.get(m):
                tot[m] += pn[m]["usd"]
        L.append(f"| {p['meeting']} | {p['opened']} | {p['direction']} | {p['next_meeting_only']} | "
                 f"{p['signal_bp']:.2f} | {p['status']} | {cell('top')} | {cell('walk')} | {cell('rest')} |")
    if not pos:
        L.append("| - | - | - | - | - | - | - | - | - |")
    L += ["", f"**Settled P&L per unit:** top ${tot['top']:,.0f} · walk ${tot['walk']:,.0f} · rest ${tot['rest']:,.0f}", ""]
    fails = [r for r in src if r.get("ok") == "0"]
    L += ["## Data sources", "", f"- Fetches logged: {len(src)}; failures: {len(fails)}"]
    zq_src = Counter(r["note"] for r in src if r["source"].startswith("zq") and r.get("ok") == "1")
    L += [f"- ZQ source used: {dict(zq_src) or 'none yet'}"]
    L += [f"- Last failure: {fails[-1]['time']} {fails[-1]['source']}: {fails[-1]['note'][:120]}"] if fails else []
    ro = Counter(x for r in sig for x in (r.get("record_only") or "").split(" | ") if x)
    if ro:
        L += ["", "## Record-only reasons (data-quality gate)", "", "| Reason | Count |", "| --- | --- |"]
        L += [f"| {k} | {v} |" for k, v in ro.most_common()]
    os.makedirs("reports", exist_ok=True)
    with open(os.path.join("reports", f"weekly_{now.date()}.md"), "w") as f:
        f.write("\n".join(L) + "\n")
