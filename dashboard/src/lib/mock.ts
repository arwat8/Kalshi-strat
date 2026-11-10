// Deterministic demo data in exactly the shapes the paper trader writes.
// Used for the instant preview and whenever live data cannot be reached.
import type { Dataset, EquityPoint, Evaluation, Method, Position } from './types';

const DPB = 41.67; // $ per bp per ZQ contract

function rng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const rand = rng(20261110);
const gauss = () => {
  const u = Math.max(rand(), 1e-9);
  const v = rand();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
};

const iso = (d: Date) => d.toISOString().slice(0, 10);
const addDays = (s: string, n: number) => {
  const d = new Date(s + 'T12:00:00Z');
  d.setUTCDate(d.getUTCDate() + n);
  return iso(d);
};

interface Spec {
  meeting: string;
  opened: string;
  settled: string | null; // date the ZQ month settled (null = still open)
  dir: 'L' | 'H';
  wc: number;
  zq_month: string;
  zq: number;
  gap: number;
  signal: number;
  legs: { strike: number; px: number }[];
  bp: Record<Method, number | null>; // final (or current) bp per method; null = not filled
  rest: 'filled' | 'working' | 'expired';
  walk: 'filled' | 'unfillable';
  label: string; // ticker month code, e.g. 25OCT
}

const SPECS: Spec[] = [
  { meeting: '2025-10-29', opened: '2025-10-08', settled: '2025-12-01', dir: 'L', wc: 1.0, zq_month: '2025-11', zq: 96.115, gap: 4.6, signal: 2.31,
    legs: [{ strike: 3.75, px: 0.9 }, { strike: 4.0, px: 0.12 }], bp: { top: 3.9, walk: 3.2, rest: 4.4 }, rest: 'filled', walk: 'filled', label: '25OCT' },
  { meeting: '2025-12-10', opened: '2025-11-19', settled: '2026-01-02', dir: 'H', wc: 0.677, zq_month: '2025-12', zq: 96.31, gap: 5.1, signal: 2.74,
    legs: [{ strike: 3.5, px: 0.93 }, { strike: 3.75, px: 0.31 }], bp: { top: 4.8, walk: 3.9, rest: 5.3 }, rest: 'filled', walk: 'filled', label: '25DEC' },
  { meeting: '2026-03-18', opened: '2026-02-24', settled: '2026-04-01', dir: 'L', wc: 0.452, zq_month: '2026-03', zq: 96.395, gap: 3.4, signal: 1.12,
    legs: [{ strike: 3.5, px: 0.72 }], bp: { top: 2.6, walk: null, rest: null }, rest: 'expired', walk: 'unfillable', label: '26MAR' },
  { meeting: '2026-06-17', opened: '2026-05-27', settled: '2026-07-01', dir: 'L', wc: 0.433, zq_month: '2026-06', zq: 96.47, gap: 2.9, signal: 0.64,
    legs: [{ strike: 3.25, px: 0.95 }, { strike: 3.5, px: 0.41 }], bp: { top: -1.7, walk: -2.6, rest: null }, rest: 'expired', walk: 'filled', label: '26JUN' },
  { meeting: '2026-09-16', opened: '2026-08-25', settled: '2026-10-01', dir: 'H', wc: 0.467, zq_month: '2026-09', zq: 96.585, gap: 4.2, signal: 1.88,
    legs: [{ strike: 3.25, px: 0.58 }], bp: { top: 3.6, walk: 3.1, rest: 4.0 }, rest: 'filled', walk: 'filled', label: '26SEP' },
  { meeting: '2026-10-28', opened: '2026-10-06', settled: null, dir: 'L', wc: 1.0, zq_month: '2026-11', zq: 96.63, gap: 3.8, signal: 1.47,
    legs: [{ strike: 3.0, px: 0.96 }, { strike: 3.25, px: 0.27 }], bp: { top: 2.9, walk: 2.4, rest: 3.3 }, rest: 'filled', walk: 'filled', label: '26OCT' },
  { meeting: '2026-12-09', opened: '2026-11-04', settled: null, dir: 'L', wc: 0.71, zq_month: '2026-12', zq: 96.705, gap: 4.4, signal: 2.06,
    legs: [{ strike: 3.0, px: 0.965 }, { strike: 3.25, px: 0.71 }], bp: { top: -0.9, walk: -1.4, rest: null }, rest: 'working', walk: 'filled', label: '26DEC' },
];

const TODAY = '2026-11-10';
const START = '2025-09-02';
const START_CAPITAL = 10_000;

function buildPosition(s: Spec): Position {
  const N = Math.round(1041.75 * s.wc);
  const side = s.dir === 'L' ? 'YES' : 'NO';
  const tick = 0.005;
  const zqFill = s.dir === 'L' ? s.zq + tick : s.zq - tick;
  const legs = s.legs.map((l) => {
    const top = s.dir === 'L' ? l.px : +(1 - l.px).toFixed(3);
    return {
      ticker: `KXFED-${s.label}-T${l.strike.toFixed(2)}`,
      strike: l.strike,
      side: side as 'YES' | 'NO',
      top_px: top,
      walk_px: s.walk === 'filled' ? +(top + 0.008).toFixed(4) : null,
      walk_filled: s.walk === 'filled' ? N : Math.round(N * 0.62),
      rest_limit: +(top - 0.01).toFixed(3),
      rest_filled: s.rest === 'filled' ? N : s.rest === 'working' ? Math.round(N * 0.35) : Math.round(N * 0.2),
    };
  });
  const pnl = Object.fromEntries(
    (['top', 'walk', 'rest'] as Method[]).map((m) => {
      const bp = s.bp[m];
      return [m, bp == null ? null : { usd: +(bp * DPB * s.wc).toFixed(2), bp }];
    }),
  ) as Record<Method, { usd: number; bp: number } | null>;
  const restDate = s.rest === 'filled' ? addDays(s.opened, 2) : null;
  const pos: Position = {
    id: `${s.meeting}_${s.opened}`,
    meeting: s.meeting,
    opened: s.opened,
    opened_at: `${s.opened}T17:41:00-04:00`,
    direction: s.dir,
    N,
    wc: s.wc,
    zq_month: s.zq_month,
    signal_bp: s.signal,
    gap_bp: s.gap,
    next_meeting_only: true,
    legs,
    fills: {
      top: { status: 'filled', zq_px: zqFill, date: s.opened },
      walk: { status: s.walk, zq_px: zqFill, date: s.opened },
      rest: {
        status: s.rest,
        zq_px: s.rest === 'filled' ? zqFill + (s.dir === 'L' ? 0.0025 : -0.0025) : null,
        date: restDate,
        days: s.rest === 'working' ? 4 : s.rest === 'expired' ? 5 : 2,
        placed: `${s.opened}T17:41:00-04:00`,
      },
    },
    status: s.settled ? 'settled' : 'open',
  };
  if (s.settled) {
    pos.settled_on = s.settled;
    pos.F_final = +(s.zq + (s.dir === 'L' ? 1 : -1) * 0.018).toFixed(4);
    pos.results = Object.fromEntries(legs.map((l, i) => [l.ticker, i === 0 ? 'yes' : 'no']));
    pos.pnl = pnl;
  } else {
    pos.mark = {
      date: TODAY,
      zq_px: +(s.zq + (s.dir === 'L' ? 0.012 : -0.012)).toFixed(4),
      pnl,
    };
  }
  return pos;
}

function weekdays(from: string, to: string): string[] {
  const out: string[] = [];
  for (let d = from; d <= to; d = addDays(d, 1)) {
    const wd = new Date(d + 'T12:00:00Z').getUTCDay();
    if (wd !== 0 && wd !== 6) out.push(d);
  }
  return out;
}

/** Path of one position's contribution: ~0 before open, a noisy bridge to its final P&L, flat after. */
function contribution(days: string[], s: Spec, m: Method, usd: number | null): number[] {
  const out = new Array(days.length).fill(0);
  if (usd == null) return out;
  const open = m === 'rest' && s.rest === 'filled' ? addDays(s.opened, 2) : s.opened;
  const end = s.settled ?? TODAY;
  const i0 = days.findIndex((d) => d >= open);
  let i1 = days.findIndex((d) => d >= end);
  if (i1 < 0) i1 = days.length - 1;
  if (i0 < 0) return out;
  const n = Math.max(1, i1 - i0);
  const scale = 0.55 * Math.abs(usd) + 12;
  let w = 0;
  const walk: number[] = [];
  for (let k = 0; k <= n; k++) {
    walk.push(w);
    w += gauss() * scale * 0.22;
  }
  const entry = -6 * s.wc; // fees hit on day one
  for (let k = 0; k <= n; k++) {
    const f = k / n;
    out[i0 + k] = entry + (usd - entry) * f + (walk[k] - walk[n] * f);
  }
  for (let i = i1 + 1; i < days.length; i++) out[i] = usd;
  return out;
}

function buildDaily(positions: Position[]): EquityPoint[] {
  const days = weekdays(START, TODAY);
  const tot: Record<Method, number[]> = {
    top: new Array(days.length).fill(0),
    walk: new Array(days.length).fill(0),
    rest: new Array(days.length).fill(0),
  };
  SPECS.forEach((s, idx) => {
    const p = positions[idx];
    const src = p.pnl ?? p.mark?.pnl;
    (['top', 'walk', 'rest'] as Method[]).forEach((m) => {
      const c = contribution(days, s, m, src?.[m]?.usd ?? null);
      c.forEach((v, i) => (tot[m][i] += v));
    });
  });
  // summed bp of settled trades (stepped at settlement)
  return days.map((t, i) => {
    const bp = (m: Method) =>
      SPECS.reduce((a, s, j) => {
        const p = positions[j];
        const done = s.settled ? t >= s.settled : t === TODAY;
        const v = (p.pnl ?? p.mark?.pnl)?.[m]?.bp;
        return a + (done && v != null ? v : 0);
      }, 0);
    return {
      t,
      top: +tot.top[i].toFixed(2),
      walk: +tot.walk[i].toFixed(2),
      rest: +tot.rest[i].toFixed(2),
      top_bp: +bp('top').toFixed(3),
      walk_bp: +bp('walk').toFixed(3),
      rest_bp: +bp('rest').toFixed(3),
    };
  });
}

/** 15-minute marks for today (the Actions cron cadence), ending at today's daily value. */
function buildIntraday(daily: EquityPoint[]): EquityPoint[] {
  const prev = daily[daily.length - 2];
  const last = daily[daily.length - 1];
  const times: string[] = [];
  for (let h = 13; h <= 18; h++) for (const mm of [0, 15, 30, 45]) if (!(h === 18 && mm > 0)) times.push(`${TODAY}T${String(h).padStart(2, '0')}:${String(mm).padStart(2, '0')}:00-05:00`);
  const n = times.length - 1;
  const paths = (['top', 'walk', 'rest'] as Method[]).map((m) => {
    let w = 0;
    const r: number[] = [];
    for (let k = 0; k <= n; k++) {
      r.push(w);
      w += gauss() * 4.2;
    }
    return r.map((x, k) => prev[m] + (last[m] - prev[m]) * (k / n) + (x - r[n] * (k / n)));
  });
  return times.map((t, k) => ({
    t,
    top: +paths[0][k].toFixed(2),
    walk: +paths[1][k].toFixed(2),
    rest: +paths[2][k].toFixed(2),
    top_bp: last.top_bp,
    walk_bp: last.walk_bp,
    rest_bp: last.rest_bp,
  }));
}

const SCAN: Evaluation[] = [
  {
    date: TODAY, meeting: '2026-12-09', zq_month: '2026-12', eligible: true, next_meeting_only: true, direction: 'L', trade: true, N: 740, zq_settle: 96.715,
    legs: [{ ticker: 'KXFED-26DEC-T3.00', strike: 3.0, bid: 0.96, ask: 0.97 }, { ticker: 'KXFED-26DEC-T3.25', strike: 3.25, bid: 0.72, ask: 0.73 }],
    L_top: { G: 3.62, signal: 1.21 }, H_top: { G: -4.05, signal: -6.41 },
  },
  { date: TODAY, meeting: '2027-01-27', zq_month: '2027-02', eligible: false, reason: 'C4: ladder does not cover both tails', next_meeting_only: false },
  { date: TODAY, meeting: '2027-03-17', zq_month: '2027-03', eligible: false, reason: 'C3: meeting in between and a > 0', next_meeting_only: false },
];

let cached: Dataset | null = null;

export function mockDataset(): Dataset {
  if (cached) return { ...cached, fetchedAt: Date.now() };
  const positions = SPECS.map(buildPosition);
  const daily = buildDaily(positions);
  const intraday = buildIntraday(daily);
  cached = {
    source: 'mock',
    fetchedAt: Date.now(),
    startCapital: START_CAPITAL,
    daily,
    intraday,
    positions,
    scan: SCAN,
    updated: `${TODAY}T18:00:00-05:00`,
  };
  return cached;
}
