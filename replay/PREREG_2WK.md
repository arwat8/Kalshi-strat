# Pre-registration: blind 2-week replay of the frozen paper rules (v1.1)

Written and committed **before any data for the test window was fetched or viewed**. The commit
timestamp of this file is the proof of order. Anything changed after the data arrives is logged
below as a deviation, and both versions are reported.

## Why a replay
The live paper trader recorded nothing from Nov 9 to Nov 20: GitHub's scheduler never fired
inside the 14:40–15:45 ET window and the external trigger was not yet set up. This replay
reconstructs what the frozen rules would have done on those days from historical data.

## Window and question
- Trading days 2026-11-09 to 2026-11-20 (10 days), evaluated at 15:00 ET.
- Meetings: the next 3 official FOMC meetings each day (Dec 9 2026, Jan 27 2027, Mar 17 2027).
- Question: which days were eligible, which signals fired, which paper positions would have
  opened, and their mark-to-market P&L at 15:00 ET on Nov 20. **Nothing can settle in the
  window** (the Dec meeting is Dec 9; the Dec ZQ final is early January), so P&L is unrealized.

## Rules (unchanged)
`paper/strategy.evaluate`, `paper/broker`, `paper/marks` and `paper/config` exactly as on
main (v1.1). No parameter is touched.

## Data, decided in advance
- **Kalshi quotes:** hourly candles. Each contract's quote = the yes_bid / yes_ask close of the
  last candle on day d ending at or before 15:00 ET (same convention as the validated backtest).
  No same-day candle = empty book. stale_mid (C2(b) classification only) = the last two-sided
  candle mid within 120 days before 15:00 ET on d. Ladder = the event's markets whose open_time
  is at or before 15:00 ET on d.
- **Depth:** candles carry none. Top-of-book fills full size (backtest convention). The order-book
  walk model cannot be reproduced and is reported as N/A.
- **Resting orders:** placed at 17:45 ET on the entry day. Filled from Kalshi's historical
  trade prints using the frozen broker (trade-id de-duplication, 5 trading-day expiry).
- **ZQ:** CME official daily settlement for the mapped month and day. If CME is missing, the
  Yahoo daily close is recorded as a labelled proxy. Where both exist, the gap between them is
  reported.
- **EFFR and upper bound:** NY Fed refRates. FRED (EFFR, DFEDTARU) only if NY Fed fails.
- **Gate inputs:** snapshot skew = 0 (15:00 candle convention). Calendar check = Kalshi event
  dates vs the official FOMC calendar.

## Variants (all reported)
1. **strict**: the live v1.1 gate exactly. A non-CME ZQ price means record only, no trade.
2. **proxy**: as strict, but a Yahoo price is accepted when CME is missing.
3. **fresh60**: as proxy, plus every active leg's quote must be from a candle 60 min or less
   before 15:00. This tests the quote-age risk of the candle convention.

**Headline:** strict if CME covers at least 80% of the ZQ prices the window needs; otherwise
proxy. The rule depends on coverage only, never on results.

## Process
1. This file and the scripts are committed. Fingerprints below.
2. Kalshi data is fetched by `replay/fetch_kalshi.py`, and ZQ and EFFR by
   `replay/fetch_external.py` on GitHub Actions. Both print coverage counts only, never prices.
3. Raw files are not opened before step 4.
4. `replay/run_2wk.py` runs once and writes `replay/results/`. The results are reported as they are.

## Fingerprints (sha256) at registration
```
e422c0a7b5746816066e1081cdf652b1ce8025917d481a6fed7b7c79e77a4804  replay/run_2wk.py
145531c6d4ccd701b7101d42b96bbde90d754ebac0c059f9634684444b52c271  replay/fetch_kalshi.py
27a089e2d45d8c95ca2670e84dd46d48df78f4907475662e54ea141fd1d0687d  replay/fetch_external.py
829c870327297a77914a63e7104f1f8e9e3ff2e36d6e0c665dabe7fb3ae0606d  paper/strategy.py
b2ee4acfd76361497b849f9cb286cb95241573da0132d458bf79b383a0437626  paper/broker.py
c97874ea4b2c0363193bd720577cc29a9dd18851a55ee1b69d58aa753354afcc  paper/marks.py
b58cffa20347f619fd16735545f2e3a16911b5b4d5f82b654664c1f34b7aa8b9  paper/config.py
f58b3b5c9f363dea6216adf3508189969c7401ad5166c499adfec817c0fcc37a  paper/run.py
93fbd37b2c0fa8bdccc504ef57fb65c2dc6edd85794a79cad3b33432c180032e  paper/tradingdays.py
17651b4a3ba1cf759688721da3f037fbe4894daa0bfbb464817bdd27a73cc735  .github/workflows/replay-fetch.yml
```

## Deviations after data arrived
None. The replay ran once with all fingerprints matching. CME returned HTTP 403 for every date, so the pre-registered headline rule selected the proxy variant. Post-run diagnostics, labelled as such, are in RESULTS_2WK.md.
