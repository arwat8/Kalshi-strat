import { ChevronDown } from 'lucide-react';
import { useState } from 'react';
import { cents, fmtDate, fmtMonth, signedBp, signedUsd } from '../lib/format';
import { positionBadge, positionPnl } from '../lib/series';
import type { FillStatus, Method, Position } from '../lib/types';
import { METHODS, METHOD_LABEL } from '../lib/types';

const DIR_LABEL = { H: 'Kalshi Strip Rich (H)', L: 'Kalshi Strip Cheap (L)' } as const;

function Badge({ kind }: { kind: 'Open' | 'Settled' | 'Expired' }) {
  const cls =
    kind === 'Open'
      ? 'border-accent text-accent'
      : kind === 'Settled'
        ? 'border-line bg-surface text-fg'
        : 'border-line text-muted line-through decoration-1';
  return (
    <span className={`accent-transition inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold ${cls}`}>
      {kind === 'Open' && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />}
      {kind}
    </span>
  );
}

const FILL_TEXT: Record<FillStatus, string> = { filled: 'Filled', working: 'Working', expired: 'Expired', unfillable: 'Unfillable' };

function Money({ v, bpv }: { v: number | null; bpv: number | null }) {
  if (v == null) return <><td className="py-2 text-right text-muted">—</td><td className="py-2 text-right text-muted">—</td></>;
  const c = v > 0 ? 'text-up' : v < 0 ? 'text-down' : 'text-fg';
  return (
    <>
      <td className={`num py-2 text-right font-semibold ${c}`}>{signedUsd(v)}</td>
      <td className={`num py-2 text-right ${c}`}>{bpv == null ? '—' : signedBp(bpv)}</td>
    </>
  );
}

export function PositionCard({ p, method }: { p: Position; method: Method }) {
  const [open, setOpen] = useState(false);
  const badge = positionBadge(p, method);
  const zqEntry = p.fills.top.zq_px;
  const zqNow = p.status === 'settled' ? p.F_final : p.mark?.zq_px;
  const live = p.status === 'open';

  return (
    <article className="border-b border-line px-4 py-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[17px] font-semibold tracking-tight">{fmtDate(p.meeting)} FOMC</div>
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            <span className="rounded-md bg-surface px-1.5 py-0.5 text-[12px] font-semibold">{DIR_LABEL[p.direction]}</span>
            <span className="text-[12px] text-muted">Opened {fmtDate(p.opened, false)}</span>
          </div>
        </div>
        <Badge kind={badge} />
      </div>

      <div className="num mt-3 grid grid-cols-3 gap-2 text-[13px]">
        <div>
          <div className="text-muted">Gap</div>
          <div className="font-semibold">{p.gap_bp.toFixed(2)} bp</div>
        </div>
        <div>
          <div className="text-muted">Signal</div>
          <div className="font-semibold">{p.signal_bp.toFixed(2)} bp</div>
        </div>
        <div>
          <div className="text-muted">ZQ {fmtMonth(p.zq_month)}</div>
          <div className="font-semibold">
            {zqEntry?.toFixed(3) ?? '—'}
            {zqNow != null && <span className="font-normal text-muted"> → {zqNow.toFixed(3)}</span>}
          </div>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {p.legs.map((l) => (
          <span key={l.ticker} className="num rounded-full border border-line px-2 py-0.5 text-[12px]">
            &gt;{l.strike.toFixed(2)}% <span className="font-semibold">{l.side}</span> @ {cents(l.top_px)}
          </span>
        ))}
      </div>

      <table className="num mt-3 w-full text-[13px]">
        <thead>
          <tr className="text-[11px] uppercase tracking-wide text-muted">
            <th className="pb-1 text-left font-medium">Fill model</th>
            <th className="pb-1 text-left font-medium">Status</th>
            <th className="pb-1 text-right font-medium">{live ? 'Mark' : 'P&L'}</th>
            <th className="pb-1 text-right font-medium">bp</th>
          </tr>
        </thead>
        <tbody>
          {METHODS.map((m) => {
            const pl = positionPnl(p, m);
            const f = p.fills[m];
            const sel = m === method;
            return (
              <tr key={m} className={`border-t border-line ${sel ? '' : 'opacity-70'}`}>
                <td className={`py-2 ${sel ? 'font-semibold' : ''}`}>{METHOD_LABEL[m]}</td>
                <td className="py-2 text-muted">
                  {FILL_TEXT[f.status]}
                  {m === 'rest' && f.status === 'working' && f.days != null ? ` · d${f.days}` : ''}
                </td>
                <Money v={pl?.usd ?? null} bpv={pl?.bp ?? null} />
              </tr>
            );
          })}
        </tbody>
      </table>

      <button onClick={() => setOpen((o) => !o)} className="mt-2 flex items-center gap-1 text-[12px] font-medium text-muted" aria-expanded={open}>
        Leg detail <ChevronDown size={14} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="num mt-2 space-y-1.5 rounded-xl bg-surface p-3 text-[12px]">
          <div className="flex justify-between text-muted">
            <span>{p.N.toLocaleString()} contracts / leg · w+c {p.wc.toFixed(3)}</span>
            <span>{p.next_meeting_only ? 'Next meeting' : 'Further out'}</span>
          </div>
          {p.legs.map((l) => (
            <div key={l.ticker} className="grid grid-cols-4 gap-1">
              <span className="col-span-4 font-semibold">{l.ticker}</span>
              <span className="text-muted">Top {cents(l.top_px)}</span>
              <span className="text-muted">Walk {l.walk_px == null ? '—' : cents(l.walk_px)}</span>
              <span className="text-muted">Limit {cents(l.rest_limit)}</span>
              <span className="text-right text-muted">
                {Math.round((l.rest_filled / p.N) * 100)}% rested
              </span>
              {p.results?.[l.ticker] && <span className="col-span-4 text-muted">Resolved {p.results[l.ticker].toUpperCase()}</span>}
            </div>
          ))}
        </div>
      )}
    </article>
  );
}
