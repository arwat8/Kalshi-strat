# Kalshi-strat: paper trader for the Kalshi strip vs. fed funds futures trade

Runs the frozen strip-vs-ZQ rules on live data every trading day, logs paper trades three ways, and
books P&L at settlement. No local Python needed: everything runs on GitHub Actions and the results
are committed back to this repo.

## What happens each trading day

| Time (ET) | Step | Output |
| --- | --- | --- |
| 2:50–3:45pm | **Snapshot**: full Kalshi order book for every contract on the next 3 Fed meetings | `data/snapshots/YYYY-MM-DD.json` |
| after 5:30pm | **End of day**: EFFR and upper bound (NY Fed), ZQ settlement (CME, then Yahoo, then `data/manual_zq.csv`), apply the rules, open/advance/settle paper positions | `data/signals.csv`, `data/daily/`, `data/positions.json`, `data/source_log.csv` |
| Saturday | **Weekly report** | `reports/weekly_YYYY-MM-DD.md` |

Each paper position is filled three ways, side by side:

- **top**: every Kalshi leg at the best quote (what the backtest assumed)
- **walk**: the full size walked through the live order book (real slippage)
- **rest**: a resting limit 1c better than top, filled only as Kalshi trades print through it
  (queue position not modelled, so this is an upper bound); maker fee applied

ZQ always fills at the day's settlement ± 1 tick.

## Files

| File | What it does |
| --- | --- |
| `paper/config.py` | Frozen parameters (do not change during the paper period) |
| `paper/data_sources.py` | Kalshi, NY Fed, CME, Yahoo and manual fetchers; never crash on a dead source |
| `paper/strategy.py` | The rules: month map, shares, fed funds gap, C2(b)/C3/C4, gaps, costs, signal |
| `paper/broker.py` | Paper fills (top/walk/rest), resting-order updates, ZQ final, settlement P&L |
| `paper/run.py` | Orchestrator (`python -m paper.run auto|snapshot|eod|report`) |
| `paper/report.py` | Weekly markdown report |
| `.github/workflows/paper.yml` | Schedule (every 15 min, 18:00–23:45 UTC weekdays; Saturday report) |
| `tests/test_offline.py` | Offline checks on synthetic data: `python -m unittest discover tests` |

## Setup (one time)

1. Settings → Actions → General: allow actions, and set workflow permissions to **Read and write**.
2. Actions tab → **paper-trader** → **Run workflow** with mode `snapshot`, then `eod`, to test.
3. Check `data/source_log.csv`: confirm which ZQ source worked. If CME and Yahoo both fail from
   GitHub's servers, add daily rows to `data/manual_zq.csv` (`date,zq_month,settle`).

## Known limitations

- ZQ uses the daily settlement price, not a live quote. Settlement is set at 2:59–3:00pm ET, close to
  the Kalshi snapshot, but it is not an executable bid/ask.
- GitHub's schedule can run late or skip a slot. The snapshot window is 55 minutes wide and every
  snapshot records its actual time.
- The CME endpoint is undocumented and may change or block automated requests.
- Resting-order fills ignore queue position, so treat `rest` P&L as optimistic.
- Rules are frozen as of 2026-11-03. The "next meeting only" flag is recorded for analysis only and
  is not a trading rule.

## Dashboard

`dashboard/` is a mobile PWA (Vite + React + TS) that reads `data/` and shows the equity curve, positions and today's scan. Deploy steps are in [dashboard/README.md](dashboard/README.md). Use Vercel with a read-only token for a private repo.

The paper trader also writes `data/equity.json` (daily marks) and `data/intraday/` (15-minute marks while a position is open) for the dashboard. These are measurement only.
