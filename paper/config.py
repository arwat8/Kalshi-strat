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

# --- Dashboard (display only) ---------------------------------------------------------------
START_CAPITAL = 10_000              # notional account the dashboard shows P&L against (~1 unit, see capital notes)
INTRADAY_MARKS = True               # mark open positions on every weekday Actions run (data/intraday/)

# --- Schedule (America/New_York) ------------------------------------------------------------
SNAP_WINDOW = ("14:50", "15:45")    # Kalshi snapshot window around the 3pm ET reference time
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
