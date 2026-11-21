# Blind 2-week replay: results (Nov 9–20, 2026)

Run once, after pre-registration (commit b596a9d) and with all 10 script fingerprints verified.
Headline variant = **proxy**: CME blocked every request (HTTP 403), so ZQ prices are Yahoo daily
closes. That headline rule was fixed in advance.

## Result
**No trades in any variant (strict, proxy, fresh60).** P&L = $0.

| Meeting | Days eligible (of 10) | Why the other days were blocked | Best signal on an eligible day |
|---|---|---|---|
| Dec 9, 2026 | 3 (Nov 16, 19, 20) | C4 (4 days), far-tail contract has no price to classify (3 days) | −0.77bp (L, Nov 19); trade needs > 0 |
| Jan 27, 2027 | 0 | C4 (8), C2(b) (1), no valid active quote (1) | — |
| Mar 17, 2027 | 0 | C4 (10) | — |

On the eligible Dec days, Kalshi and ZQ agreed to within −2.4bp to +0.5bp before costs. After
fees, the 0.52bp reserve and the 0.5bp buffer, every signal was negative.

## Post-run diagnostics (do not change the result)
- **The Dec blocks are mostly a candle artifact.** The 5.25% contract almost never trades, so on
  most days it has no hourly candle. The replay then falls back to its last two-sided quote
  (2–3¢, which fails C4) or finds none within 120 days (cannot classify). A live order book would
  show it at about 0/1¢, which passes.
- **Exploratory, not counted:** treating no-candle tail contracts as settled makes the Dec meeting
  eligible on all 10 days. One marginal L signal appears (Nov 12, +0.23bp), smaller than one ZQ
  tick of price uncertainty (about 0.7bp).
- **Jan and Mar 2027 ladders run 0–6% and are illiquid at the tails.** C4 blocks them, as the Nov 9
  order-book check had already found.

## Data caveats
- ZQ = Yahoo daily close, unverified against CME settlement (CME blocks GitHub's servers). One
  tick = 0.005, about 0.7bp on the Dec gap.
- Kalshi = hourly candle quotes, not true 3pm order books, with no depth.
- EFFR = NY Fed (complete).
