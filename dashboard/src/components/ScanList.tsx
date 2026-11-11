import { fmtDate } from '../lib/format';
import type { Evaluation } from '../lib/types';

export function ScanList({ scan, held }: { scan: Evaluation[]; held: Set<string> }) {
  if (!scan.length) return null;
  return (
    <section className="pt-6">
      <h2 className="px-4 text-[20px] font-semibold tracking-tight">Today’s scan</h2>
      <p className="px-4 pt-0.5 text-[12px] text-muted">Frozen rules applied to the 3pm ET snapshot · {fmtDate(scan[0].date)}</p>
      <ul className="mt-2">
        {scan.map((e) => {
          const best = e.direction ? (e.direction === 'L' ? e.L_top : e.H_top) : undefined;
          const status = !e.eligible ? 'Blocked' : e.trade ? (held.has(e.meeting) ? 'Signal · held' : 'Signal') : 'No edge';
          return (
            <li key={e.meeting} className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
              <div className="min-w-0">
                <div className="text-[15px] font-semibold">{fmtDate(e.meeting)}</div>
                <div className="truncate text-[12px] text-muted">
                  {e.eligible
                    ? `${e.direction === 'H' ? 'Strip rich' : 'Strip cheap'} · ${e.legs?.length ?? 0} active leg${e.legs?.length === 1 ? '' : 's'} · ZQ ${e.zq_settle?.toFixed(3) ?? '—'}`
                    : e.reason}
                </div>
              </div>
              <div className="shrink-0 text-right">
                <div className={`text-[13px] font-semibold ${status.startsWith('Signal') ? 'text-accent' : 'text-muted'}`}>{status}</div>
                {best && (
                  <div className="num text-[12px] text-muted">
                    gap {best.G.toFixed(2)} · sig {best.signal >= 0 ? '+' : ''}
                    {best.signal.toFixed(2)}
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
