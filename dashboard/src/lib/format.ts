const ET = 'America/New_York';

const usdFmt = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const usd = (v: number) => usdFmt.format(v);
export const signedUsd = (v: number) => (v > 0 ? '+' : v < 0 ? '−' : '') + usdFmt.format(Math.abs(v));
export const signedPct = (v: number) => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(2) + '%';
export const signedBp = (v: number, d = 2) => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(d) + ' bp';
export const bp = (v: number, d = 2) => v.toFixed(d) + ' bp';
export const cents = (p: number) => (p * 100).toFixed(1).replace(/\.0$/, '') + '¢';

const isDateOnly = (s: string) => /^\d{4}-\d{2}-\d{2}$/.test(s);

/** ms timestamp. Date-only strings are pinned to 4pm ET-ish (21:00 UTC) so ordering with intraday works. */
export const toMs = (s: string) => (isDateOnly(s) ? Date.parse(s + 'T21:00:00Z') : Date.parse(s));

export function fmtDate(s: string, withYear = true) {
  const d = isDateOnly(s) ? new Date(s + 'T12:00:00Z') : new Date(s);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', ...(withYear ? { year: 'numeric' } : {}), timeZone: isDateOnly(s) ? 'UTC' : ET });
}

export function fmtTime(s: string) {
  return new Date(s).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', timeZone: ET }) + ' ET';
}

/** Scrubber label: time for intraday points, date otherwise. */
export function fmtStamp(s: string) {
  return isDateOnly(s) ? fmtDate(s) : `${fmtDate(s, false)}, ${fmtTime(s)}`;
}

export function fmtMonth(ym: string) {
  const [y, m] = ym.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, 15)).toLocaleDateString('en-US', { month: 'short', timeZone: 'UTC' }) + ` ’${String(y).slice(2)}`;
}

export function todayET() {
  return new Intl.DateTimeFormat('en-CA', { timeZone: ET, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
}
