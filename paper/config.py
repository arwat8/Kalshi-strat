"""Frozen parameters for the paper trader.

These mirror the pre-registered strip-vs-ZQ rules (B1-B6, C1-C4) as frozen on 2026-11-03.
Do not change them during the paper-trading period. Any change is an amendment: log it in the
strategy doc with the date and the reason, before looking at paper results.
"""

# --- Rule parameters (frozen) -------------------------------------------------------------
ACTIVE_LO, ACTIVE_HI = 0.02, 0.98   # B1: legs with mid in this band are traded; C4 uses the same cutoffs
RESERVE_BP = 0.52                   # hedge reserve R-hat: last walk-forward value (bp)
BUFFER_BP = 0.5                     # buffer b: last walk-forward value (bp)
KALSHI_TAKER = 0.07                 # Kalshi taker fee: ceil(0.07 * C * P * (1 - P)) per order
KALSHI_MAKER = 0.0175               # Kalshi maker fee on KXFED (quadratic_with_maker_fees), resting orders
ZQ_FEE_USD = 2.00                   # B6: all-in ZQ cost per contract
ZQ_TICK = 0.005                     # ZQ tick outside the front month (price points)
ZQ_HALF_SPREAD_TICKS = 1            # settlement-based ZQ fill = settle +/- this many ticks
DOLLARS_PER_BP = 41.67              # one ZQ contract
CONTRACTS_PER_UNIT = 1041.75        # Kalshi contracts per leg for one ZQ, times (w + c)

# --- Paper-broker settings (measurement only, not strategy rules) --------------------------
REST_IMPROVE = 0.01                 # resting order sits 1c better than the price we would cross at
REST_MAX_DAYS = 5                   # cancel an unfilled resting order after this many trading days
MEETINGS_AHEAD = 3                  # how many upcoming meetings to snapshot and evaluate
STRIKE_STEP = 0.25                  # C1: Kalshi thresholds must run in unbroken steps of this size

# --- Data-quality gates (v1.1). These can only stop a trade, never create one. ----------------
SNAPSHOT_TARGET = "15:00"           # ZQ settles on 14:59-15:00 ET trades; the Kalshi snapshot aims here
MAX_SNAPSHOT_SKEW_MIN = 10          # snapshot further than this from 15:00 ET -> record only, no trade
TRUSTED_ZQ_SOURCES = ("cme",)       # a ZQ price from any other source -> record only, no trade

# --- Official FOMC calendar (decision days), federalreserve.gov ------------------------------
# 2027-2028 dates are the Fed's tentative schedule; each is confirmed at the meeting before it.
# Unscheduled (emergency) meetings are not listed: add them here by hand if one is called.
FOMC_DATES = [
    "2025-12-10",
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
    "2027-01-27", "2027-03-17", "2027-04-28", "2027-06-09",
    "2027-07-28", "2027-09-15", "2027-10-27", "2027-12-08",
    "2028-01-26",
]

# --- Days with no regular CME settlement (NYSE/CME holiday schedule). The bot skips them. ------
MARKET_HOLIDAYS = [
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19",
    "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
    "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31", "2027-06-18",
    "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24",
]

# --- Dashboard (display only) ---------------------------------------------------------------
START_CAPITAL = 10_000              # notional account the dashboard shows P&L against (~1 unit, see capital notes)
INTRADAY_MARKS = True               # mark open positions on every weekday Actions run (data/intraday/)

# --- Schedule (America/New_York) ------------------------------------------------------------
SNAP_WINDOW = ("14:40", "15:45")    # a run in this window takes the snapshot (waiting for 15:00 if early)
EOD_AFTER = "17:30"                 # CME settlements and EFFR are pulled after this time

# --- Data sources ---------------------------------------------------------------------------
KALSHI_API = "https://api.elections.kalshi.com/trade-api/v2"
KALSHI_SERIES = "KXFED"
# NY Fed EFFR history. Each row also carries the target range, so the upper bound comes from here.
NYFED_EFFR = "https://markets.newyorkfed.org/api/rates/unsecured/effr/last/{n}.json"
# CME daily settlements for 30-Day Fed Funds futures (product 305). Undocumented endpoint:
# confirm on the first live run (data/source_log.csv says which source worked each day).
CME_SETTLE = "https://www.cmegroup.com/CmeWS/mvc/Settlements/Futures/Settlements/305/FUT?tradeDate={d}"
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=1d"
# Last-resort manual ZQ prices: data/manual_zq.csv with columns date,zq_month,settle (e.g. 2027-01).
MANUAL_ZQ = "data/manual_zq.csv"
