import type { Method } from '../lib/types';
import { METHODS, METHOD_SHORT } from '../lib/types';

export function MethodToggle({ value, onChange }: { value: Method; onChange: (m: Method) => void }) {
  return (
    <div className="px-4 pt-4">
      <div className="mb-2 text-[13px] font-medium text-muted">Fill model</div>
      <div className="grid grid-cols-3 rounded-full bg-surface p-1" role="radiogroup" aria-label="Fill model">
        {METHODS.map((m) => {
          const on = m === value;
          return (
            <button
              key={m}
              role="radio"
              aria-checked={on}
              onClick={() => onChange(m)}
              className={`rounded-full py-1.5 text-[13px] font-semibold transition-colors ${on ? 'bg-bg text-fg shadow-sm' : 'text-muted'}`}
            >
              {METHOD_SHORT[m]}
            </button>
          );
        })}
      </div>
    </div>
  );
}
