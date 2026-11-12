// Shapes written by the paper trader (paper/run.py, paper/broker.py, paper/marks.py).

export type Method = 'top' | 'walk' | 'rest';
export const METHODS: Method[] = ['top', 'walk', 'rest'];
export const METHOD_LABEL: Record<Method, string> = {
  top: 'Top of Book',
  walk: 'Order Book Walk',
  rest: 'Resting Limit',
};
export const METHOD_SHORT: Record<Method, string> = { top: 'Top', walk: 'Walk', rest: 'Rest' };

export type Direction = 'L' | 'H';
export type FillStatus = 'filled' | 'partial' | 'working' | 'expired' | 'unfillable';

export interface Leg {
  ticker: string;
  strike: number;
  side: 'YES' | 'NO';
  top_px: number;
  walk_px: number | null;
  walk_filled: number;
  rest_limit: number;
  rest_filled: number;
}

export interface Fill {
  status: FillStatus;
  qty?: number; // contracts per leg actually filled (partial fills)
  unverified?: boolean; // ZQ hedge priced from a fallback source
  zq_px: number | null;
  date: string | null;
  days?: number;
  placed?: string;
}

export interface PnL {
  usd: number;
  bp: number;
  qty?: number;
}

export interface Position {
  id: string;
  meeting: string; // YYYY-MM-DD decision day
  opened: string;
  opened_at: string;
  direction: Direction;
  N: number;
  wc: number;
  zq_month: string; // YYYY-MM
  signal_bp: number;
  gap_bp: number;
  next_meeting_only: boolean;
  legs: Leg[];
  fills: Record<Method, Fill>;
  status: 'open' | 'settled';
  settled_on?: string;
  F_final?: number;
  results?: Record<string, 'yes' | 'no'>;
  pnl?: Record<Method, PnL | null>;
  mark?: { date?: string; zq_px?: number | null; mids?: Record<string, number | null>; pnl: Record<Method, PnL | null> };
}

/** Cumulative P&L (USD and summed bp) per fill method at time t. */
export interface EquityPoint {
  t: string; // YYYY-MM-DD (daily) or ISO datetime (intraday)
  top: number;
  walk: number;
  rest: number;
  top_bp?: number;
  walk_bp?: number;
  rest_bp?: number;
}

export interface EquityFile {
  start_capital: number;
  updated?: string;
  points: EquityPoint[];
}

export interface IntradayFile {
  date: string;
  points: EquityPoint[];
}

/** One row of data/daily/{date}.json: the rule evaluation for one meeting. */
export interface Evaluation {
  date: string;
  meeting: string;
  zq_month: string;
  eligible: boolean;
  reason?: string;
  next_meeting_only?: boolean;
  direction?: Direction;
  trade?: boolean;
  N?: number;
  zq_settle?: number;
  legs?: { ticker: string; strike: number; bid: number; ask: number }[];
  record_only?: string[]; // data-quality gate: evaluated and logged, but no position allowed
  trade_if_allowed?: boolean;
  zq_source?: string | null;
  L_top?: { G: number; signal: number };
  H_top?: { G: number; signal: number };
}

export type Source = 'live' | 'mock';

export interface Dataset {
  source: Source;
  fetchedAt: number;
  startCapital: number;
  daily: EquityPoint[];
  intraday: EquityPoint[];
  positions: Position[];
  scan: Evaluation[];
  updated?: string;
  error?: string;
}

export type Timeframe = '1D' | '1W' | '1M' | '3M' | 'YTD' | '1Y' | 'ALL';
export const TIMEFRAMES: Timeframe[] = ['1D', '1W', '1M', '3M', 'YTD', '1Y', 'ALL'];
