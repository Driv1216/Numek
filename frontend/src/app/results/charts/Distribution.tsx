// Recorded distributions: a histogram of the bins the analysis recorded (method and denominator stated), and a quantile
// strip of recorded quantiles with the recorded IQR fences. Nothing is re-binned or re-estimated here.

export interface Bin { lower: number; upper: number; count: number }
const fmt = (v: number) => (Math.abs(v) >= 1000 || Number.isInteger(v) ? v.toLocaleString('en-US', { maximumFractionDigits: 0 }) : v.toLocaleString('en-US', { maximumSignificantDigits: 4 }));

export function Histogram({ bins, denominator, method, caption, unit }: { bins: Bin[] | null | undefined; denominator: number | null | undefined; method?: string; caption: string; unit?: string | null }) {
  if (!bins?.length || !denominator) return <p className="ap-chart__na">{caption}: no recorded histogram in this result</p>;
  const top = Math.max(...bins.map((b) => b.count), 1);
  const lo = bins[0].lower, hi = bins[bins.length - 1].upper;
  return (
    <figure className="ap-chart ap-hist">
      <div className="ap-hist__bars" role="img" aria-label={`${caption}: ${bins.length} bins from ${fmt(lo)} to ${fmt(hi)}, tallest bin ${top.toLocaleString('en-US')} of ${denominator.toLocaleString('en-US')}`}>
        {bins.map((b, i) => <i key={i} style={{ height: `${Math.max(1.5, (b.count / top) * 100)}%` }} title={`${fmt(b.lower)}–${fmt(b.upper)}: ${b.count.toLocaleString('en-US')}`} />)}
      </div>
      <div className="ap-hist__axis"><span>{fmt(lo)}</span><span>{unit ?? ''}</span><span>{fmt(hi)}</span></div>
      <figcaption>{caption} · {bins.length} bins{method ? ` (${method.replace(/_/g, ' ')})` : ''} · denominator {denominator.toLocaleString('en-US')} finite values</figcaption>
    </figure>
  );
}

export function QuantileStrip({ quantiles, fences, min, max, caption }: {
  quantiles: Record<string, number> | null | undefined; fences?: { lower?: number | null; upper?: number | null; count?: number | null; denominator?: number | null } | null;
  min?: number | null; max?: number | null; caption: string;
}) {
  const order = ['p1', 'p5', 'q1', 'median', 'q3', 'p95', 'p99'].filter((k) => typeof quantiles?.[k] === 'number');
  if (!order.length || typeof min !== 'number' || typeof max !== 'number' || max === min) return <p className="ap-chart__na">{caption}: no recorded quantiles in this result</p>;
  const lo = Math.min(min, fences?.lower ?? min), hi = Math.max(max, fences?.upper ?? max);
  const x = (v: number) => `${((v - lo) / (hi - lo)) * 100}%`;
  const q = quantiles!;
  return (
    <figure className="ap-chart ap-qs">
      <div className="ap-qs__t" role="img" aria-label={`${caption}: ${order.map((k) => `${k} ${fmt(q[k])}`).join(', ')}; observed ${fmt(min)} to ${fmt(max)}`}>
        <span className="ap-qs__range" style={{ left: x(min), width: `calc(${x(max)} - ${x(min)})` }} />
        {typeof q.q1 === 'number' && typeof q.q3 === 'number' && <span className="ap-qs__box" style={{ left: x(q.q1), width: `calc(${x(q.q3)} - ${x(q.q1)})` }} />}
        {order.map((k) => <span key={k} className={`ap-qs__m ${k === 'median' ? 'is-med' : ''}`} style={{ left: x(q[k]) }} />)}
        {typeof fences?.lower === 'number' && fences.lower >= lo && <span className="ap-qs__f" style={{ left: x(fences.lower) }} />}
        {typeof fences?.upper === 'number' && fences.upper <= hi && <span className="ap-qs__f" style={{ left: x(fences.upper) }} />}
      </div>
      <div className="ap-hist__axis"><span>{fmt(lo)}</span><span>median {fmt(q.median)}</span><span>{fmt(hi)}</span></div>
      <figcaption>{caption} · bar: observed range; box: q1–q3; ticks: p1, p5, p95, p99{fences ? ` · dashed: 1.5 × IQR fences${fences.count != null && fences.denominator ? `, ${fences.count.toLocaleString('en-US')} of ${fences.denominator.toLocaleString('en-US')} outside` : ''}` : ''}</figcaption>
    </figure>
  );
}
