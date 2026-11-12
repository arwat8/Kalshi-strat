"""End-to-end day with fake data sources (no network): snapshot -> eod -> duplicate trigger.

Checks the 15:00 wait, the official-calendar check, the data-quality gate, the daily checks log,
and that running a step twice changes nothing.
"""
import datetime as dt
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock
from zoneinfo import ZoneInfo

from paper import data_sources as S
from paper import run as R

ET = ZoneInfo("America/New_York")
TODAY = dt.date(2026, 11, 13)


def _book(bid, ask, q=5000):
    return {"yes_bids": [(bid, q)], "no_bids": [(round(1 - ask, 4), q)]}


DEC = {2.75: (0.995, 0.999), 3.00: (0.99, 0.995), 3.25: (0.985, 0.99), 3.50: (0.60, 0.61),
       3.75: (0.004, 0.01), 4.00: (0.001, 0.005)}
OTHER = {3.00: (0.99, 0.995), 3.25: (0.97, 0.98), 3.50: (0.50, 0.52), 3.75: (0.004, 0.01), 4.00: (0.001, 0.005)}


def _markets(skip_jan=False):
    out = []
    for ev, date, ladder in (("KXFED-26DEC", "2026-12-09", DEC), ("KXFED-27JAN", "2027-01-27", OTHER),
                             ("KXFED-27MAR", "2027-03-17", OTHER)):
        if skip_jan and ev == "KXFED-27JAN":
            continue
        for k in ladder:
            out.append({"event_ticker": ev, "close_time": f"{date}T18:55:00Z", "ticker": f"{ev}-T{k:.2f}",
                        "floor_strike": k, "last_price_dollars": ""})
    return out


def _book_for(ticker):
    ev, k = ticker.rsplit("-T", 1)
    lad = DEC if ev == "KXFED-26DEC" else OTHER
    return _book(*lad[float(k)])


def _effr(n=90):
    days = [(TODAY - dt.timedelta(days=i)).isoformat() for i in range(1, n)]
    return {d: 3.63 for d in days}, {d: 3.75 for d in days}, None


class Clock:
    def __init__(self, t):
        self.t = t

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += dt.timedelta(seconds=s)


class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.old = os.getcwd()
        self.dir = tempfile.mkdtemp()
        os.chdir(self.dir)

    def tearDown(self):
        os.chdir(self.old)
        shutil.rmtree(self.dir)

    def day(self, zq_src="cme", start=(14, 52), skip_jan=False):
        clock = Clock(dt.datetime(2026, 11, 13, *start, tzinfo=ET))
        zq = {(2026, 12): 96.4125}
        with mock.patch.object(R, "_now", clock.now), mock.patch.object(R.time, "sleep", clock.sleep), \
             mock.patch.object(S, "kalshi_open_markets", lambda: (_markets(skip_jan), None)), \
             mock.patch.object(S, "kalshi_book", _book_for), \
             mock.patch.object(S, "effr_history", _effr), \
             mock.patch.object(S, "zq_settlement",
                               lambda y, m, d: (zq[(y, m)], zq_src) if (y, m) in zq else (None, "cme: month not found")), \
             mock.patch.object(S, "kalshi_trades", lambda t, s: []), \
             mock.patch.object(S, "kalshi_market", lambda t: {}):
            self.assertTrue(R.snapshot(clock.now()))
            snap = json.load(open(f"data/snapshots/{TODAY}.json"))
            clock.t = dt.datetime(2026, 11, 13, 17, 45, tzinfo=ET)
            self.assertTrue(R.eod(clock.now()))
            first = json.load(open("data/positions.json"))
            self.assertFalse(R.main("eod"))                       # duplicate trigger: nothing happens
            self.assertFalse(R.main("snapshot"))
            self.assertEqual(json.load(open("data/positions.json")), first)
            checks = json.load(open(f"data/checks/{TODAY}.json"))
        return snap, first, checks

    def test_clean_day_trades_once_at_1500(self):
        snap, pos, checks = self.day()
        self.assertTrue(snap["time"].startswith("2026-11-13T15:00"))      # waited for 15:00 ET
        self.assertLessEqual(snap["skew_min"], 1)
        self.assertTrue(snap["calendar_check"]["ok"])
        self.assertEqual(len(pos), 1)
        self.assertEqual(pos[0]["meeting"], "2026-12-09")
        self.assertEqual(checks["zq_sources"]["2026-12"], "cme")
        with open("data/signals.csv") as f:
            self.assertEqual(sum(1 for _ in f) - 1, 3)                  # one row per meeting, no duplicates

    def test_yahoo_price_records_but_does_not_trade(self):
        _, pos, checks = self.day(zq_src="yahoo")
        self.assertEqual(pos, [])
        dec = next(m for m in checks["meetings"] if m["meeting"] == "2026-12-09")
        self.assertTrue(dec["trade_if_allowed"])
        self.assertIn("yahoo", dec["record_only"][0])

    def test_late_snapshot_records_but_does_not_trade(self):
        snap, pos, _ = self.day(start=(15, 25))
        self.assertGreater(snap["skew_min"], 10)
        self.assertEqual(pos, [])

    def test_calendar_mismatch_blocks(self):
        snap, pos, _ = self.day(skip_jan=True)
        self.assertFalse(snap["calendar_check"]["ok"])
        self.assertEqual(snap["calendar_check"]["official_missing_on_kalshi"], ["2027-01-27"])
        self.assertEqual(pos, [])


if __name__ == "__main__":
    unittest.main()
