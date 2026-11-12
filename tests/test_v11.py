"""Tests for the v1.1 fixes (no network). Run: python -m unittest discover tests

1 resting fills recounted, not added (no double counting); duplicates by trade id ignored
2 snapshot timing gate (record only when > 10 min from 15:00 ET)
3 official FOMC calendar check
4 partial fills booked on the matched quantity
5 C1: a hole in the strike ladder blocks the day
6 ZQ from a fallback source -> record only
7 resting-order expiry counts trading days (weekends and holidays skipped)
"""
import datetime as dt
import unittest

from paper import config as C
from paper import strategy as St
from paper.broker import open_position, settle, update_resting
from paper.run import calendar_check
from paper.tradingdays import add_trading_days, is_trading_day, trading_days_between

D = dt.date.fromisoformat


def book(bid, ask, size=50000):
    return {"yes_bids": [(bid, size)], "no_bids": [(round(1 - ask, 4), size)]}


class Base(unittest.TestCase):
    def setUp(self):
        self.today = D("2027-01-04")
        self.meeting = D("2027-01-27")
        self.cal = [self.meeting, D("2027-03-17")]
        days = [self.today - dt.timedelta(days=i) for i in range(60)]
        self.effr = {d.isoformat(): 3.63 for d in days}
        self.ub = {d.isoformat(): 3.75 for d in days}
        self.ladder = [{"ticker": "T3.25", "strike": 3.25, "book": book(0.98, 0.99)},
                       {"ticker": "T3.50", "strike": 3.50, "book": book(0.74, 0.75)},
                       {"ticker": "T3.75", "strike": 3.75, "book": book(0.09, 0.10)},
                       {"ticker": "T4.00", "strike": 4.00, "book": book(0.005, 0.015)}]
        self.zq = 100 - (3.75 - 0.12)

    def ev(self, ladder=None):
        return St.evaluate(self.today, self.meeting, self.cal, ladder or self.ladder, self.zq, self.effr, self.ub)

    def position(self, books=None):
        ev = self.ev()
        books = books or {x["ticker"]: x["book"] for x in self.ladder}
        return ev, open_position(ev, books, "2027-01-04T17:40:00-05:00")


# --- 1. resting fills -------------------------------------------------------------------------
class RestingRecount(Base):
    def tape(self, pos, specs):
        """specs: list of (id, iso_ts, count) printed at the limit on every leg."""
        return {lg["ticker"]: [{"id": f"{lg['ticker']}-{i}", "ts": ts, "count": n,
                                "yes_price": lg["rest_limit"] if lg["side"] == "YES" else 1 - lg["rest_limit"]}
                               for i, ts, n in specs] for lg in pos["legs"]}

    def test_rerun_does_not_double(self):
        _, pos = self.position()
        t = self.tape(pos, [("a", "2027-01-05T15:00:00Z", 300)])
        update_resting(pos, t, D("2027-01-05"), self.zq)
        update_resting(pos, t, D("2027-01-05"), self.zq)          # same trades again (duplicate run)
        self.assertTrue(all(lg["rest_filled"] == 300 for lg in pos["legs"]))

    def test_second_day_counts_new_prints_once(self):
        _, pos = self.position()
        update_resting(pos, self.tape(pos, [("a", "2027-01-05T15:00:00Z", 300)]), D("2027-01-05"), self.zq)
        day2 = self.tape(pos, [("a", "2027-01-05T15:00:00Z", 300), ("b", "2027-01-06T15:00:00Z", 200)])
        update_resting(pos, day2, D("2027-01-06"), self.zq)       # v1 would have counted 300 + 500 = 800
        self.assertTrue(all(lg["rest_filled"] == 500 for lg in pos["legs"]))
        self.assertEqual(pos["fills"]["rest"]["status"], "working")

    def test_duplicate_ids_ignored(self):
        _, pos = self.position()
        t = self.tape(pos, [("a", "2027-01-05T15:00:00Z", 300), ("a", "2027-01-05T15:00:00Z", 300)])
        update_resting(pos, t, D("2027-01-05"), self.zq)
        self.assertTrue(all(lg["rest_filled"] == 300 for lg in pos["legs"]))

    def test_prints_before_placement_or_after_expiry_ignored(self):
        _, pos = self.position()
        expiry = add_trading_days(D("2027-01-04"), C.REST_MAX_DAYS)
        t = self.tape(pos, [("early", "2027-01-04T20:00:00Z", 400),                  # before 17:40 ET placement
                            ("late", f"{expiry + dt.timedelta(days=1)}T15:00:00Z", 400)])
        update_resting(pos, t, expiry + dt.timedelta(days=1), self.zq)
        self.assertTrue(all(lg["rest_filled"] == 0 for lg in pos["legs"]))
        self.assertEqual(pos["fills"]["rest"]["status"], "expired")


# --- 2/6. data-quality gate -------------------------------------------------------------------
class Gate(Base):
    def test_clean_day_unchanged(self):
        ev = self.ev()
        before = ev["trade"]
        St.apply_gate(ev, St.record_only_reasons("cme", 3.0, True))
        self.assertEqual(ev["trade"], before)
        self.assertNotIn("record_only", ev)

    def test_fallback_source_blocks(self):
        ev = self.ev()
        self.assertTrue(ev["trade"])
        St.apply_gate(ev, St.record_only_reasons("yahoo", 3.0, True))
        self.assertFalse(ev["trade"])
        self.assertTrue(ev["trade_if_allowed"])
        self.assertIn("yahoo", ev["record_only"][0])

    def test_off_time_snapshot_blocks(self):
        for skew in (10.5, 45, None):
            ev = self.ev()
            St.apply_gate(ev, St.record_only_reasons("cme", skew, True))
            self.assertFalse(ev["trade"], skew)

    def test_skew_at_limit_allowed(self):
        self.assertEqual(St.record_only_reasons("cme", 10.0, True), [])

    def test_calendar_mismatch_blocks(self):
        ev = self.ev()
        St.apply_gate(ev, St.record_only_reasons("cme", 1.0, False))
        self.assertFalse(ev["trade"])

    def test_gate_never_creates_a_trade(self):
        ev = self.ev()
        ev["trade"] = False
        St.apply_gate(ev, St.record_only_reasons("yahoo", 30, False))
        self.assertFalse(ev["trade"])
        self.assertFalse(ev["trade_if_allowed"])


# --- 3. calendar --------------------------------------------------------------------------------
class Calendar(unittest.TestCase):
    def test_match(self):
        k = [D("2026-12-09"), D("2027-01-27"), D("2027-03-17"), D("2027-04-28")]
        self.assertTrue(calendar_check(k, D("2026-11-13"))["ok"])

    def test_kalshi_missing_a_meeting(self):
        k = [D("2026-12-09"), D("2027-03-17"), D("2027-04-28")]
        r = calendar_check(k, D("2026-11-13"))
        self.assertFalse(r["ok"])
        self.assertEqual(r["official_missing_on_kalshi"], ["2027-01-27"])

    def test_kalshi_date_not_official(self):
        k = [D("2026-12-10"), D("2027-01-27"), D("2027-03-17")]
        self.assertFalse(calendar_check(k, D("2026-11-13"))["ok"])

    def test_config_has_next_year(self):
        self.assertIn("2027-06-09", C.FOMC_DATES)        # June 2027 is unusually early (8-9 June)


# --- 4. partial fills ---------------------------------------------------------------------------
class Partial(Base):
    def test_walk_partial_books_matched_quantity(self):
        thin = {x["ticker"]: x["book"] for x in self.ladder}
        thin["T3.50"] = {"yes_bids": [(0.74, 50000)], "no_bids": [(0.25, 200), (0.24, 300)]}   # 500 YES offered
        ev, pos = self.position(thin)
        self.assertEqual(ev["direction"], "L")
        w = pos["fills"]["walk"]
        self.assertEqual(w["status"], "partial")
        self.assertEqual(w["qty"], 500)
        leg = next(lg for lg in pos["legs"] if lg["ticker"] == "T3.50")
        self.assertAlmostEqual(leg["walk_px"], (200 * 0.75 + 300 * 0.76) / 500)
        settle(pos, {"T3.50": "yes", "T3.75": "no"}, self.zq)
        self.assertEqual(pos["pnl"]["walk"]["qty"], 500)
        self.assertIsNotNone(pos["pnl"]["walk"]["usd"])
        self.assertEqual(pos["pnl"]["top"]["qty"], pos["N"])

    def test_rest_partial_at_expiry(self):
        _, pos = self.position()
        legs = pos["legs"]
        t = {lg["ticker"]: [{"id": f"x{lg['ticker']}", "ts": "2027-01-05T15:00:00Z", "count": 100 if i == 0 else 400,
                             "yes_price": lg["rest_limit"] if lg["side"] == "YES" else 1 - lg["rest_limit"]}]
             for i, lg in enumerate(legs)}
        expiry = add_trading_days(D("2027-01-04"), C.REST_MAX_DAYS)
        update_resting(pos, t, expiry, self.zq, "cme")
        f = pos["fills"]["rest"]
        self.assertEqual(f["status"], "partial")
        self.assertEqual(f["qty"], 100)                    # matched strip = the smallest leg
        settle(pos, {lg["ticker"]: "yes" for lg in legs} | {"T3.75": "no"}, self.zq)
        self.assertEqual(pos["pnl"]["rest"]["qty"], 100)

    def test_unverified_zq_on_rest_fill_flagged(self):
        _, pos = self.position()
        t = {lg["ticker"]: [{"id": "z", "ts": "2027-01-05T15:00:00Z", "count": pos["N"],
                             "yes_price": lg["rest_limit"] if lg["side"] == "YES" else 1 - lg["rest_limit"]}]
             for lg in pos["legs"]}
        update_resting(pos, t, D("2027-01-05"), self.zq, "yahoo")
        self.assertEqual(pos["fills"]["rest"]["status"], "filled")
        self.assertTrue(pos["fills"]["rest"]["unverified"])


# --- 5. ladder holes ------------------------------------------------------------------------------
class LadderC1(Base):
    def test_hole_blocks(self):
        holed = [x for x in self.ladder if x["strike"] != 3.50]
        ev = self.ev(holed)
        self.assertFalse(ev["eligible"])
        self.assertEqual(ev["reason"], "C1: gap in ladder")

    def test_full_ladder_passes(self):
        self.assertTrue(self.ev()["eligible"])


# --- 7. trading days ------------------------------------------------------------------------------
class TradingDays(unittest.TestCase):
    def test_holiday_and_weekend(self):
        self.assertFalse(is_trading_day(D("2026-11-26")))          # Thanksgiving
        self.assertFalse(is_trading_day(D("2026-11-28")))          # Saturday
        self.assertTrue(is_trading_day(D("2026-11-27")))

    def test_expiry_skips_thanksgiving(self):
        # placed Wed 25 Nov 2026: Fri 27, Mon 30, Tue 1, Wed 2, Thu 3 -> 5th trading day = 3 Dec
        self.assertEqual(add_trading_days(D("2026-11-25"), 5), D("2026-12-03"))
        self.assertEqual(trading_days_between(D("2026-11-25"), D("2026-12-03")), 5)


if __name__ == "__main__":
    unittest.main()
