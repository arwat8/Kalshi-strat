// Data loader: live GitHub data first, demo data as the fallback.
//
// Sources, tried in order until positions.json loads:
//   1. VITE_DATA_BASE  e.g. https://raw.githubusercontent.com/arwat8/Kalshi-strat/main/data  (public repo)
//   2. ./api/data?f=   the Vercel serverless proxy (private repo; token stays on the server)
// If neither answers, the app shows the built-in demo data and says so in the header.
import { parseCsv } from './csv';
import { todayET } from './format';
import { mockDataset } from './mock';
import type { Dataset, EquityFile, EquityPoint, Evaluation, IntradayFile, Method, Position } from './types';

const env = import.meta.env;
const FORCE_MOCK = env.VITE_FORCE_MOCK === '1' || env.VITE_FORCE_MOCK === 'true';
const DEFAULT_CAPITAL = 10_000;

type Getter = (file: string) => Promise<Response>;

function makeGetter(base: string): Getter {
  const proxy = base.includes('?f=');
  return (file) => {
    const url = proxy ? base + encodeURIComponent(file) : `${base.replace(/\/$/, '')}/${file}`;
    const sep = url.includes('?') ? '&' : '?';
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), 8000);
    return fetch(`${url}${sep}t=${Math.floor(Date.now() / 60000)}`, { signal: ctl.signal, cache: 'no-store' }).finally(() =>
      clearTimeout(timer),
    );
  };
}

async function getJson<T>(get: Getter, file: string): Promise<T | null> {
  try {
    const r = await get(file);
    if (!r.ok) return null;
    const ct = r.headers.get('content-type') ?? '';
    if (ct.includes('text/html')) return null; // SPA fallback page, not data
    return (await r.json()) as T;
  } catch {
    return null;
  }
}

async function getText(get: Getter, file: string): Promise<string | null> {
  try {
    const r = await get(file);
    if (!r.ok) return null;
    if ((r.headers.get('content-type') ?? '').includes('text/html')) return null;
    return await r.text();
  } catch {
    return null;
  }
}

/** Equity curve from positions alone (realized P&L stepped at settlement + today's open marks). */
function equityFromPositions(positions: Position[]): EquityPoint[] {
  const events = new Map<string, Record<Method, number>>();
  const add = (t: string, m: Method, v: number) => {
    const e = events.get(t) ?? { top: 0, walk: 0, rest: 0 };
    e[m] += v;
    events.set(t, e);
  };
  for (const p of positions) {
    const methods: Method[] = ['top', 'walk', 'rest'];
    if (p.status === 'settled' && p.pnl) {
      const t = p.settled_on ?? p.meeting;
      methods.forEach((m) => p.pnl?.[m] && add(t, m, p.pnl[m]!.usd));
    } else if (p.mark?.pnl) {
      const t = p.mark.date ?? todayET();
      methods.forEach((m) => p.mark?.pnl[m] && add(t, m, p.mark.pnl[m]!.usd));
    }
  }
  const first = positions.map((p) => p.opened).sort()[0];
  const pts: EquityPoint[] = first ? [{ t: first, top: 0, walk: 0, rest: 0 }] : [];
  const acc = { top: 0, walk: 0, rest: 0 };
  [...events.keys()].sort().forEach((t) => {
    const e = events.get(t)!;
    acc.top += e.top;
    acc.walk += e.walk;
    acc.rest += e.rest;
    pts.push({ t, ...acc });
  });
  return pts;
}

async function loadFrom(get: Getter): Promise<Dataset | null> {
  const positions = await getJson<Position[]>(get, 'positions.json');
  if (!Array.isArray(positions)) return null;

  const [equity, signals] = await Promise.all([getJson<EquityFile>(get, 'equity.json'), getText(get, 'signals.csv')]);

  // latest evaluation day from signals.csv -> daily/{date}.json (has strikes and ZQ price)
  let scan: Evaluation[] = [];
  const rows = signals ? parseCsv(signals) : [];
  const lastDate = rows.length ? rows[rows.length - 1].date : undefined;
  if (lastDate) scan = (await getJson<Evaluation[]>(get, `daily/${lastDate}.json`)) ?? [];

  const daily = equity?.points?.length ? equity.points : equityFromPositions(positions);
  const today = todayET();
  const lastDaily = daily.length ? daily[daily.length - 1].t.slice(0, 10) : undefined;
  let intraday: EquityPoint[] = (await getJson<IntradayFile>(get, `intraday/${today}.json`))?.points ?? [];
  if (!intraday.length && lastDaily && lastDaily !== today)
    intraday = (await getJson<IntradayFile>(get, `intraday/${lastDaily}.json`))?.points ?? [];

  return {
    source: 'live',
    fetchedAt: Date.now(),
    startCapital: equity?.start_capital ?? DEFAULT_CAPITAL,
    daily,
    intraday,
    positions,
    scan,
    updated: equity?.updated,
  };
}

export async function loadDataset(): Promise<Dataset> {
  if (FORCE_MOCK) return mockDataset();
  const bases = [env.VITE_DATA_BASE as string | undefined, './api/data?f='].filter((b): b is string => !!b);
  for (const b of bases) {
    const ds = await loadFrom(makeGetter(b));
    if (ds) return ds;
  }
  return { ...mockDataset(), error: 'Live data unavailable. Showing demo data.' };
}
