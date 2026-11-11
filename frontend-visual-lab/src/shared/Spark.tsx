import type { ColDist } from './distributions';

/** Real per-column distribution as a tiny bar chart. Styling comes from the caller. */
export function Spark({
  d,
  width = 120,
  height = 28,
  gap = 1,
  className,
  hot,
}: {
  d: ColDist;
  width?: number;
  height?: number;
  gap?: number;
  className?: string;
  /** index range of numeric bins to emphasise */
  hot?: (lo: number, hi: number) => boolean;
}) {
  if (d.kind === 'numeric') {
    const max = Math.max(...d.bins);
    const bw = width / d.bins.length;
    return (
      <svg viewBox={`0 0 ${width} ${height}`} className={className} preserveAspectRatio="none" aria-label={`${d.name} distribution`}>
        {d.bins.map((c, i) => {
          const h = c ? Math.max(1, (c / max) * height) : 0;
          const isHot = hot?.(d.edges[i], d.edges[i + 1]);
          return <rect key={i} x={i * bw + gap / 2} y={height - h} width={Math.max(0.5, bw - gap)} height={h} className={isHot ? 'hot' : ''} />;
        })}
      </svg>
    );
  }
  const vals = [...d.top.map((t) => t[1]), d.other].filter((v) => v > 0);
  const total = vals.reduce((a, b) => a + b, 0);
  let x = 0;
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className={className} preserveAspectRatio="none" aria-label={`${d.name} categories`}>
      {vals.map((v, i) => {
        const w = (v / total) * width;
        const r = <rect key={i} x={x + gap / 2} y={height * 0.25} width={Math.max(0.5, w - gap)} height={height * 0.5} opacity={1 - i * 0.09} />;
        x += w;
        return r;
      })}
    </svg>
  );
}
