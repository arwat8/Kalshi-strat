import { useCallback, useMemo, useState } from 'react';
import { Header } from './components/Header';
import { Hero } from './components/Hero';
import { MethodToggle } from './components/MethodToggle';
import { Pills } from './components/Pills';
import { PositionCard } from './components/PositionCard';
import { PriceChart } from './components/PriceChart';
import { ScanList } from './components/ScanList';
import { StatsRow } from './components/StatsRow';
import { useDataset } from './hooks/useDataset';
import { useTheme } from './hooks/useTheme';
import { fmtStamp } from './lib/format';
import { buildSeries, stats } from './lib/series';
import type { Method, Position, Timeframe } from './lib/types';

function sortFeed(ps: Position[]) {
  const open = ps.filter((p) => p.status === 'open').sort((a, b) => a.meeting.localeCompare(b.meeting));
  const done = ps.filter((p) => p.status !== 'open').sort((a, b) => b.meeting.localeCompare(a.meeting));
  return [...open, ...done];
}

export default function App() {
  const { data, loading, refresh } = useDataset();
  const { theme, toggle } = useTheme();
  const [tf, setTf] = useState<Timeframe>('1M');
  const [method, setMethod] = useState<Method>('top');
  const [scrub, setScrub] = useState<number | null>(null);

  const series = useMemo(() => (data ? buildSeries(data, method, tf) : null), [data, method, tf]);
  const feed = useMemo(() => (data ? sortFeed(data.positions) : []), [data]);
  const st = useMemo(() => (data ? stats(data.positions, method) : null), [data, method]);
  const onScrub = useCallback((i: number | null) => setScrub(i), []);
  const changeTf = (t: Timeframe) => {
    setScrub(null);
    setTf(t);
  };

  const up = (series?.delta ?? 0) >= 0;
  const accent = up ? 'var(--up)' : 'var(--down)';

  return (
    <div className="mx-auto min-h-screen max-w-[480px]" style={{ ['--accent' as string]: accent }}>
      <Header source={data?.source} loading={loading} theme={theme} onRefresh={refresh} onTheme={toggle} />

      {!data || !series || !st ? (
        <Skeleton />
      ) : (
        <main className="safe-bottom">
          <Hero series={series} scrub={scrub} tf={tf} method={method} startCapital={data.startCapital} />
          <PriceChart points={series.points} base={series.base} color={accent} scrub={scrub} onScrub={onScrub} animKey={`${tf}-${method}-${data.fetchedAt}`} />
          <Pills value={tf} onChange={changeTf} />
          <MethodToggle value={method} onChange={setMethod} />
          <StatsRow s={st} />

          <section className="pt-6">
            <h2 className="px-4 text-[20px] font-semibold tracking-tight">Positions</h2>
            <p className="px-4 pt-0.5 text-[12px] text-muted">One trade per meeting, held to settlement. P&amp;L for all three fill models.</p>
            {feed.length ? feed.map((p) => <PositionCard key={p.id} p={p} method={method} />) : (
              <p className="px-4 py-8 text-[15px] text-muted">No positions yet. The first one opens on the first qualifying signal.</p>
            )}
          </section>

          <ScanList scan={data.scan} held={new Set(data.positions.map((p) => p.meeting))} />

          <footer className="px-4 pt-8 text-[11px] leading-relaxed text-muted">
            {data.error && <div className="mb-1">{data.error}</div>}
            {data.source === 'live' ? 'Live from the paper-trader repo' : 'Demo data (realistic, not real fills)'}
            {data.updated ? ` · updated ${fmtStamp(data.updated)}` : ''}
            <br />
            Paper trading only: simulated fills, no real orders. Kalshi strip vs CME 30-Day Fed Funds (ZQ).
          </footer>
        </main>
      )}
    </div>
  );
}

function Skeleton() {
  return (
    <div className="animate-pulse px-4 pt-4">
      <div className="h-3 w-40 rounded bg-surface" />
      <div className="mt-3 h-10 w-56 rounded bg-surface" />
      <div className="mt-3 h-4 w-44 rounded bg-surface" />
      <div className="mt-6 h-[248px] rounded-xl bg-surface" />
    </div>
  );
}
