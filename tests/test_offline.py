"""Offline checks of the frozen rules and the paper broker on synthetic data (no network).
Run: python -m unittest discover tests"""
import datetime as dt
import unittest

from paper import strategy as St
from paper.broker import open_position, settle, update_resting, zq_final


def book(bid, ask, size=50000):
    return {"yes_bids": [(bid, size)], "no_bids": [(round(1 - ask, 4), size)]}


class Rules(unittest.TestCase):
    def setUp(self):
        self.today = dt.date(2027, 1, 4)
        self.meeting = dt.date(2027, 1, 27)
        self.cal = [self.meeting, dt.date(2027, 3, 17)]
        days = [self.today - dt.timedelta(days=i) for i in range(60)]
        self.effr = {d.isoformat(): 3.63 for d in days}          # gap = 3.75 - 3.63 = 12bp
        self.ub = {d.isoformat(): 3.75 for d in days}
        # ladder: 3.25 at 99c, 3.50 at 0.75, 3.75 at 0.10, 4.00 at 1c  -> Kalshi implied UB
        self.ladder = [{"ticker": "T3.25", "strike": 3.25, "book": book(0.98, 0.99)},
                       {"ticker": "T3.50", "strike": 3.50, "book": book(0.74, 0.75)},
                       {"ticker": "T3.75", "strike": 3.75, "book": book(0.09, 0.10)},
                       {"ticker": "T4.00", "strike": 4.00, "book": book(0.00 + 0.005, 0.015)}]

    def test_month_map_matches_backtest(self):
        self.assertEqual(St.zq_month_for(dt.date(2022, 3, 16), [dt.date(2022, 3, 16), dt.date(2022, 5, 4)]), (2022, 4))
        self.assertEqual(St.zq_month_for(dt.date(2022, 5, 4), [dt.date(2022, 5, 4), dt.date(2022, 6, 15)]), (2022, 5))
        self.assertEqual(St.zq_month_for(dt.date(2022, 6, 15), [dt.date(2022, 6, 15), dt.date(2022, 7, 27)]), (2022, 7))

    def test_gap_sign(self):
        # Kalshi top-of-book (H uses bids): 3.25 + 0.25*(1 + 0.74 + 0.09 + 0) = 3.7075 ; ZQ priced for UB 3.75
        zq = 100 - (3.75 - 0.12)      # February is fully after the meeting: a = 0
        ev = St.evaluate(self.today, self.meeting, self.cal, self.ladder, zq, self.effr, self.ub)
        self.assertTrue(ev["eligible"], ev.get("reason"))
        self.assertEqual(ev["zq_month"], "2027-02")
        self.assertEqual(ev["direction"], "L")          # Kalshi implies a LOWER rate than ZQ -> buy the strip
        self.assertGreater(ev["L_top"]["G"], 0)

    def test_c4_blocks_short_ladder(self):
        short = self.ladder[1:]                          # lowest leg now at 0.745 -> tails not covered
        ev = St.evaluate(self.today, self.meeting, self.cal, short, 96.37, self.effr, self.ub)
        self.assertFalse(ev["eligible"])
        self.assertIn("C4", ev["reason"])

    def test_broker_roundtrip(self):
        zq = 100 - (3.75 - 0.12)
        ev = St.evaluate(self.today, self.meeting, self.cal, self.ladder, zq, self.effr, self.ub)
        books = {x["ticker"]: x["book"] for x in self.ladder}
        pos = open_position(ev, books, "2027-01-04T15:00:00-05:00")
        self.assertEqual(pos["fills"]["walk"]["status"], "filled")
        trades = {lg["ticker"]: [{"yes_price": lg["rest_limit"], "count": 5000}] for lg in pos["legs"]}
        update_resting(pos, trades, self.today, zq)
        self.assertEqual(pos["fills"]["rest"]["status"], "filled")
        results = {"T3.50": "yes", "T3.75": "no"}      # Fed holds at 3.75
        F = 100 - (3.75 - 0.12)
        settle(pos, results, F)
        self.assertIsNotNone(pos["pnl"]["top"])

    def test_zq_final(self):
        effr = {dt.date(2027, 2, d).isoformat(): 3.63 for d in range(1, 29)}
        self.assertAlmostEqual(zq_final("2027-02", effr), 96.37)
        self.assertIsNone(zq_final("2027-03", effr))


if __name__ == "__main__":
    unittest.main()
