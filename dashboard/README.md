# FedStrip dashboard

A mobile PWA for the Kalshi strip vs ZQ paper trader. It reads the files the paper trader commits to `data/` and shows:

- **Hero:** portfolio value ($10k notional), $ and % change for the selected timeframe, and cumulative P&L in $ and bp. Green `#00C805` when the timeframe is up, red `#FF5000` when it's down.
- **Chart:** monotone line, no gridlines, dotted baseline at the start of the window. Drag (touch) or hover (mouse) to scrub; the hero shows the scrubbed time and value.
- **Timeframes:** 1D · 1W · 1M · 3M · YTD · 1Y · ALL. 1D uses the intraday marks from the 15-minute Actions runs.
- **Fill model toggle:** Top of Book, Order Book Walk or Resting Limit. Drives the chart, hero and stats.
- **Positions feed:** Open/Settled/Expired badge, direction tag, gap, signal, ZQ entry → mark/final, active strikes, a P&L table for all three fill models, and leg detail.
- **Today's scan:** the frozen rules applied to the latest 3pm snapshot, for each upcoming meeting.

If live data can't be reached, the app falls back to built-in demo data and says so in the header.

Stack: Vite 6 + React 18 + TypeScript + Tailwind 3 + Recharts 3 + lucide-react. Plain service worker, no plugin.

## Run locally

```bash
cd dashboard
npm install
npm run dev          # http://localhost:5173 (demo data unless VITE_DATA_BASE is set)
npm run build        # production build to dist/
```

## Deploy free on Vercel (about 5 minutes, works with a private repo)

1. **Create a read-only token.** GitHub → Settings → Developer settings → Fine-grained tokens → Generate:
   - Repository access: only `arwat8/Kalshi-strat`
   - Permissions: Contents = Read-only
2. **Import the repo.** Go to vercel.com → Add New → Project → Import `arwat8/Kalshi-strat`.
3. **Set Root Directory to `dashboard`.** The framework is detected as Vite and build settings come from `vercel.json`.
4. **Add environment variables:**
   - `GITHUB_TOKEN` = the token from step 1
   - `GITHUB_REPO` = `arwat8/Kalshi-strat`
   - `GITHUB_BRANCH` = the branch the paper trader commits to (usually `main`)
5. **Deploy.** Open the URL on your phone:
   - iPhone (Safari): Share → Add to Home Screen
   - Android (Chrome): ⋮ → Install app

How it works: the browser calls `/api/data?f=positions.json`. That serverless function reads `data/` from GitHub with the token, so the token never reaches the phone. Responses are edge-cached for 60 seconds.

The data bot commits every 15 minutes. `vercel.json` has an `ignoreCommand` that skips rebuilds unless something under `dashboard/` changed. The data is fetched live, so a rebuild is never needed for new numbers.

## Alternative: GitHub Pages (public data only)

Pages is static, so it can't hold a token. Use it only if the data is public: either make the repo public, or push `data/` to a separate public repo.

1. Repo → Settings → Pages → Source: **GitHub Actions**.
2. Repo → Settings → Secrets and variables → Actions → Variables → add `VITE_DATA_BASE` = `https://raw.githubusercontent.com/arwat8/Kalshi-strat/main/data`.
3. Actions → **dashboard-pages** → Run workflow. The site goes live at `https://arwat8.github.io/Kalshi-strat/`.

Pages on a private repo needs a paid GitHub plan, and raw URLs for private repos don't work without auth. For a private repo, use Vercel.

## Data contract (written by `paper/run.py`)

| File | Used for |
| --- | --- |
| `data/positions.json` | Feed, stats; also the equity fallback (realized P&L stepped at `settled_on`) |
| `data/equity.json` | `{start_capital, updated, points:[{t, top, walk, rest, top_bp, …}]}`, the daily curve |
| `data/intraday/YYYY-MM-DD.json` | `{date, points:[…]}`, 1D marks (Kalshi mids live, ZQ held at last settle) |
| `data/signals.csv` | Finds the latest evaluation date |
| `data/daily/YYYY-MM-DD.json` | Today's scan (eligibility, reason, active legs, ZQ price, gap, signal) |

Marks are measurement only: nothing in `paper/marks.py` feeds back into the frozen rules.

## Env vars

| Name | Where | Purpose |
| --- | --- | --- |
| `VITE_DATA_BASE` | build time, public | Raw data base URL (public repos / Pages) |
| `VITE_FORCE_MOCK` | build time | `1` = always show demo data |
| `GITHUB_TOKEN`, `GITHUB_REPO`, `GITHUB_BRANCH` | Vercel server only | Private-repo proxy |
