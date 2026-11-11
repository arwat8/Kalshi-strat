import { memo, useCallback, useMemo, useRef } from 'react';
import { Line, LineChart, ReferenceDot, ReferenceLine, ResponsiveContainer, XAxis, YAxis } from 'recharts';
import type { ChartPoint } from '../lib/series';

interface Props {
  points: ChartPoint[];
  base: number;
  color: string;
  scrub: number | null;
  onScrub: (i: number | null) => void;
  animKey: string;
  height?: number;
}

const PAD_X = 6; // keeps the end dot from clipping; the pointer maths uses the same inset

function PriceChartImpl({ points, base, color, scrub, onScrub, animKey, height = 248 }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const n = points.length;
  const down = useRef(false);

  const data = useMemo(
    () => points.map((p) => ({ i: p.i, v: p.v, after: scrub != null && p.i >= scrub ? p.v : null })),
    [points, scrub],
  );

  const domain = useMemo(() => {
    let lo = base;
    let hi = base;
    for (const p of points) {
      if (p.v < lo) lo = p.v;
      if (p.v > hi) hi = p.v;
    }
    const pad = Math.max((hi - lo) * 0.1, 1);
    return [lo - pad, hi + pad] as [number, number];
  }, [points, base]);

  const indexAt = useCallback(
    (clientX: number) => {
      const el = ref.current;
      if (!el || n < 2) return null;
      const r = el.getBoundingClientRect();
      const f = (clientX - r.left - PAD_X) / Math.max(1, r.width - 2 * PAD_X);
      return Math.max(0, Math.min(n - 1, Math.round(f * (n - 1))));
    },
    [n],
  );

  const onDown = (e: React.PointerEvent) => {
    down.current = true;
    onScrub(indexAt(e.clientX));
  };
  const onMove = (e: React.PointerEvent) => {
    if (e.pointerType === 'mouse' || down.current) onScrub(indexAt(e.clientX));
  };
  const end = () => {
    down.current = false;
    onScrub(null);
  };

  const sp = scrub != null ? points[scrub] : null;

  return (
    <div
      ref={ref}
      className="chart-touch relative w-full"
      style={{ height }}
      onPointerDown={onDown}
      onPointerMove={onMove}
      onPointerUp={end}
      onPointerCancel={end}
      onPointerLeave={end}
      role="img"
      aria-label="Portfolio value chart. Drag to scrub."
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 12, right: PAD_X, bottom: 12, left: PAD_X }}>
          <XAxis dataKey="i" type="number" domain={[0, Math.max(1, n - 1)]} hide />
          <YAxis domain={domain} hide />
          <ReferenceLine y={base} stroke="var(--muted)" strokeOpacity={0.55} strokeDasharray="1 5" strokeLinecap="round" strokeWidth={1.5} ifOverflow="extendDomain" />
          <Line
            key={animKey}
            dataKey="v"
            type="monotone"
            stroke={color}
            strokeWidth={2}
            dot={false}
            activeDot={false}
            isAnimationActive
            animationDuration={650}
            animationEasing="ease-out"
            className="accent-transition"
          />
          {scrub != null && (
            <>
              {/* dim the part of the line to the right of the scrubber */}
              <Line dataKey="after" type="monotone" stroke="var(--bg)" strokeWidth={4} dot={false} activeDot={false} isAnimationActive={false} connectNulls={false} />
              <Line dataKey="after" type="monotone" stroke="var(--muted)" strokeOpacity={0.45} strokeWidth={2} dot={false} activeDot={false} isAnimationActive={false} connectNulls={false} />
              <ReferenceLine x={scrub} stroke="var(--muted)" strokeOpacity={0.6} strokeWidth={1} />
              {sp && <ReferenceDot x={scrub} y={sp.v} r={5} fill={color} stroke="var(--bg)" strokeWidth={2} />}
            </>
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export const PriceChart = memo(PriceChartImpl);
