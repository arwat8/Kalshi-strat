import { toMs } from './format';
import type { Dataset, EquityPoint, Method, Position, Timeframe } from './types';

export interface ChartPoint {
  i: number;
  t: string;
  ms: number;
  v: number; // portfolio value
  pnl: number; // cumulative P&L (USD)
  bp: number; // cumulative summed bp
}

export interface Series {
  points: ChartPoint[];
  base: number; // value at the start of the window
  end: number;
  delta: number;
  pct: number;
  intraday: boolean;
}

const DAY = 86_400_000;

function toPoint(p: EquityPoint, i: number, m: Method, cap: number): ChartPoint {
  const pnl = p[m] ?? 0;
  return { i, t: p.t, ms: toMs(p.t), v: cap + pnl, pnl, bp: (p[`${m}_bp` as const] as number | undefined) ?? 0 };
}

export function buildSeries(ds: Dataset, m: Method, tf: Timeframe): Series {
  const cap = ds.startCapital;
  let daily = ds.daily;
  const intra = ds.intraday;
  // today's intraday marks arrive before the end-of-day point: extend the daily curve with the latest one
  if (intra.length && daily.length) {
    const li = intra[intra.length - 1];
    const lastDay = daily[daily.length - 1].t.slice(0, 10);
    if (li.t.slice(0, 10) > lastDay) daily = [...daily, { ...li, t: li.t.slice(0, 10) }];
  }

  let raw: EquityPoint[];
  let base: number;
  let isIntra = false;

  if (tf === '1D') {
    if (intra.length >= 2) {
      const day = intra[0].t.slice(0, 10);
      const prev = [...daily].reverse().find((p) => p.t.slice(0, 10) < day);
      raw = intra;
      base = cap + (prev ? prev[m] : intra[0][m]);
      isIntra = true;
    } else {
      raw = daily.slice(-2);
      base = cap + (raw[0]?.[m] ?? 0);
    }
  } else {
    const last = daily.length ? toMs(daily[daily.length - 1].t) : Date.now();
    const lastDate = new Date(last);
    const cutoff =
      tf === '1W' ? last - 7 * DAY
      : tf === '1M' ? new Date(lastDate).setUTCMonth(lastDate.getUTCMonth() - 1)
      : tf === '3M' ? new Date(lastDate).setUTCMonth(lastDate.getUTCMonth() - 3)
      : tf === 'YTD' ? Date.UTC(lastDate.getUTCFullYear(), 0, 1) - 1
      : tf === '1Y' ? new Date(lastDate).setUTCFullYear(lastDate.getUTCFullYear() - 1)
      : -Infinity;
    let start = 0;
    for (let i = 0; i < daily.length; i++) if (toMs(daily[i].t) <= cutoff) start = i;
    raw = daily.slice(start);
    base = cap + (raw[0]?.[m] ?? 0);
  }

  let points = raw.map((p, i) => toPoint(p, i, m, cap));
  if (points.length === 1) points = [points[0], { ...points[0], i: 1 }];
  if (!points.length) points = [0, 1].map((i) => ({ i, t: '', ms: 0, v: cap, pnl: 0, bp: 0 }));
  const end = points[points.length - 1].v;
  const delta = end - base;
  return { points, base, end, delta, pct: base ? (delta / base) * 100 : 0, intraday: isIntra };
}

export const TF_LABEL: Record<Timeframe, string> = {
  '1D': 'Today',
  '1W': 'Past week',
  '1M': 'Past month',
  '3M': 'Past 3 months',
  YTD: 'Year to date',
  '1Y': 'Past year',
  ALL: 'All time',
};

/** Fill status of a position for one method, folded into the badge the feed shows. */
export function positionBadge(p: Position, m: Method): 'Open' | 'Settled' | 'Expired' {
  const s = p.fills[m]?.status;
  if (s === 'expired' || s === 'unfillable') return 'Expired';
  return p.status === 'settled' ? 'Settled' : 'Open';
}

export function positionPnl(p: Position, m: Method) {
  return (p.status === 'settled' ? p.pnl?.[m] : p.mark?.pnl?.[m]) ?? null;
}

export interface Stats {
  trades: number;
  open: number;
  wins: number;
  settled: number;
  avgBp: number | null;
}

export function stats(positions: Position[], m: Method): Stats {
  const settled = positions.filter((p) => p.status === 'settled' && p.pnl?.[m]);
  const wins = settled.filter((p) => (p.pnl![m]!.usd ?? 0) > 0).length;
  const avg = settled.length ? settled.reduce((a, p) => a + p.pnl![m]!.bp, 0) / settled.length : null;
  return {
    trades: positions.length,
    open: positions.filter((p) => p.status === 'open').length,
    wins,
    settled: settled.length,
    avgBp: avg,
  };
}
