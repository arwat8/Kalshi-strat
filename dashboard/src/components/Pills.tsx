import type { Timeframe } from '../lib/types';
import { TIMEFRAMES } from '../lib/types';

export function Pills({ value, onChange }: { value: Timeframe; onChange: (t: Timeframe) => void }) {
  return (
    <div className="flex items-center justify-between border-b border-line px-3 pb-3 pt-2" role="tablist" aria-label="Timeframe">
      {TIMEFRAMES.map((t) => {
        const on = t === value;
        return (
          <button
            key={t}
            role="tab"
            aria-selected={on}
            onClick={() => onChange(t)}
            className={`accent-transition num rounded-full px-2.5 py-1.5 text-[13px] font-semibold ${on ? 'text-accent' : 'text-fg'}`}
            style={on ? { backgroundColor: 'color-mix(in srgb, var(--accent) 16%, transparent)' } : undefined}
          >
            {t}
          </button>
        );
      })}
    </div>
  );
}
