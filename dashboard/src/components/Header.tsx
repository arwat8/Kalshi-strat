import { Moon, RefreshCw, Sun } from 'lucide-react';
import type { Source } from '../lib/types';

interface Props {
  source?: Source;
  loading: boolean;
  theme: 'dark' | 'light';
  onRefresh: () => void;
  onTheme: () => void;
}

export function Header({ source, loading, theme, onRefresh, onTheme }: Props) {
  return (
    <header className="safe-top sticky top-0 z-20 bg-bg">
      <div className="flex h-12 items-center justify-between px-4">
        <div className="flex items-center gap-2">
          <span className="text-[17px] font-semibold tracking-tight">FedStrip</span>
          {source && (
            <span className="flex items-center gap-1.5 rounded-full border border-line px-2 py-0.5 text-[11px] font-medium text-muted">
              <span className={`h-1.5 w-1.5 rounded-full ${source === 'live' ? 'bg-up animate-pulse' : 'bg-muted'}`} />
              {source === 'live' ? 'Live' : 'Demo data'}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button onClick={onRefresh} aria-label="Refresh" className="grid h-9 w-9 place-items-center rounded-full text-fg active:bg-surface">
            <RefreshCw size={18} strokeWidth={2} className={loading ? 'animate-spin' : ''} />
          </button>
          <button onClick={onTheme} aria-label="Toggle theme" className="grid h-9 w-9 place-items-center rounded-full text-fg active:bg-surface">
            {theme === 'dark' ? <Sun size={18} strokeWidth={2} /> : <Moon size={18} strokeWidth={2} />}
          </button>
        </div>
      </div>
    </header>
  );
}
