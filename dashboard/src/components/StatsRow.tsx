import type { Stats } from '../lib/series';

export function StatsRow({ s }: { s: Stats }) {
  const items = [
    { k: 'Positions', v: String(s.trades) },
    { k: 'Open', v: String(s.open) },
    { k: 'Win rate', v: s.settled ? `${Math.round((s.wins / s.settled) * 100)}%` : '—' },
    { k: 'Avg / trade', v: s.avgBp == null ? '—' : `${s.avgBp >= 0 ? '+' : '−'}${Math.abs(s.avgBp).toFixed(2)}bp` },
  ];
  return (
    <div className="grid grid-cols-4 gap-2 px-4 pt-5">
      {items.map((it) => (
        <div key={it.k}>
          <div className="text-[11px] font-medium uppercase tracking-wide text-muted">{it.k}</div>
          <div className="num mt-0.5 text-[17px] font-semibold">{it.v}</div>
        </div>
      ))}
    </div>
  );
}
