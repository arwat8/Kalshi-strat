import { useAnimatedNumber } from '../hooks/useAnimatedNumber';
import { fmtStamp, signedBp, signedPct, signedUsd, usd } from '../lib/format';
import type { Series } from '../lib/series';
import { TF_LABEL } from '../lib/series';
import type { Method, Timeframe } from '../lib/types';
import { METHOD_LABEL } from '../lib/types';

interface Props {
  series: Series;
  scrub: number | null;
  tf: Timeframe;
  method: Method;
  startCapital: number;
}

export function Hero({ series, scrub, tf, method, startCapital }: Props) {
  const sp = scrub != null ? series.points[scrub] : null;
  const value = sp ? sp.v : series.end;
  const delta = value - series.base;
  const pct = series.base ? (delta / series.base) * 100 : 0;
  const last = sp ?? series.points[series.points.length - 1];
  const animate = scrub == null;
  const v = useAnimatedNumber(value, animate);
  const d = useAnimatedNumber(delta, animate);
  const p = useAnimatedNumber(pct, animate);
  const up = delta >= 0;

  return (
    <section className="px-4 pb-2 pt-3">
      <div className="text-[13px] font-medium text-muted">Paper portfolio · {METHOD_LABEL[method]}</div>
      <div className="num mt-1 text-[40px] font-semibold leading-[1.05] tracking-tight">{usd(v)}</div>
      <div className={`num mt-1.5 flex flex-wrap items-baseline gap-x-1.5 text-[15px] font-medium ${up ? 'text-up' : 'text-down'}`}>
        <span>{signedUsd(d)}</span>
        <span>({signedPct(p)})</span>
        <span className="text-fg font-normal">{sp ? fmtStamp(sp.t) : TF_LABEL[tf]}</span>
      </div>
      <div className="num mt-1 text-[13px] text-muted">
        Cumulative P&amp;L {signedUsd(last.pnl)} · {signedBp(last.bp)} on {usd(startCapital).replace('.00', '')}
      </div>
    </section>
  );
}
