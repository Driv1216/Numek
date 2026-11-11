import { useId } from 'react';
import columnsAll from '../../fixture/columns.generated.json';

export interface Col { name: string; target: boolean; missing: number; unique: number; kind: 'numeric' | 'categorical'; min?: number; max?: number; median?: number; mean?: number; q1?: number; q3?: number; bins?: number[]; zero_share?: number; values?: [string, number][] }
export const runsCols = columnsAll as unknown as Record<string, { rows: number; columns: Col[] }>;
export const code = (i: number) => `C_${String(i + 1).padStart(2, '0')}`;
export const num = (i: number) => String(i + 1).padStart(3, '0');

/** A numeric column as a turned vessel: its histogram, mirrored. Bins outside the 1.5 × IQR fences are darker. */
function Vessel({ c, h = 260, w = 160 }: { c: Col; h?: number; w?: number }) {
  const id = useId().replace(/:/g, '');
  const bins = c.bins!;
  const max = Math.max(...bins);
  const n = bins.length;
  const bh = h / n;
  const half = (v: number) => 3 + Math.sqrt(v / max) * (w / 2 - 6);
  const cx = w / 2;
  // Smooth silhouette: a Catmull-Rom spline through each bin's half-width, mirrored.
  const pts: [number, number][] = [[half(bins[0]) * 0.92, h]];
  bins.forEach((v, i) => pts.push([half(v), h - (i + 0.5) * bh]));
  pts.push([Math.max(2, half(bins[n - 1]) * 0.6), 0]);
  const spline = (P: [number, number][], side: 1 | -1) => {
    let d = '';
    for (let i = 0; i < P.length - 1; i++) {
      const p0 = P[Math.max(0, i - 1)], p1 = P[i], p2 = P[i + 1], p3 = P[Math.min(P.length - 1, i + 2)];
      const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6], c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
      d += ` C${cx + side * c1[0]} ${c1[1]} ${cx + side * c2[0]} ${c2[1]} ${cx + side * p2[0]} ${p2[1]}`;
    }
    return d;
  };
  const rev = [...pts].reverse();
  const path = `M${cx - pts[0][0]} ${h} L${cx + pts[0][0]} ${h}${spline(pts, 1)} L${cx - rev[0][0]} 0${spline(rev, -1)} Z`;
  const iqr = (c.q3 ?? 0) - (c.q1 ?? 0);
  const lo = (c.q1 ?? 0) - 1.5 * iqr, hi = (c.q3 ?? 0) + 1.5 * iqr;
  const span = (c.max! - c.min!) || 1;
  const yOf = (v: number) => h - ((v - c.min!) / span) * h;
  return (
    <svg viewBox={`-10 -10 ${w + 20} ${h + 40}`} className="co-obj" aria-hidden="true">
      <defs>
        <linearGradient id={`m${id}`} x1="0" x2="1">
          <stop offset="0" stopColor="#b9ad97" /><stop offset=".32" stopColor="#efe8db" /><stop offset=".55" stopColor="#e2d8c6" /><stop offset="1" stopColor="#a39780" />
        </linearGradient>
        <filter id={`n${id}`}><feTurbulence type="fractalNoise" baseFrequency="1.4" numOctaves="2" result="t" /><feColorMatrix in="t" type="saturate" values="0" /><feComponentTransfer><feFuncA type="table" tableValues="0 .09" /></feComponentTransfer><feComposite in2="SourceGraphic" operator="in" /></filter>
        <clipPath id={`c${id}`}><path d={path} /></clipPath>
      </defs>
      <ellipse cx={cx} cy={h + 8} rx={w * 0.42} ry={7} className="co-shadow" />
      <path d={path} fill={`url(#m${id})`} />
      {iqr > 0 && (
        <g clipPath={`url(#c${id})`}>
          <rect x={0} y={0} width={w} height={Math.max(0, yOf(hi))} className="co-out" />
          <rect x={0} y={Math.min(h, yOf(lo))} width={w} height={Math.max(0, h - yOf(lo))} className="co-out" />
        </g>
      )}
      <path d={path} fill="#000" filter={`url(#n${id})`} opacity=".9" />
      <path d={path} className="co-edge" />
    </svg>
  );
}

const STONES = ['#57544f', '#6b6863', '#47443f', '#7c7872', '#3c3a36', '#625f5a'];

/** A categorical column as a totem: one block per category, height by share; missing values a hollow block. */
function Totem({ c, h = 260, w = 160 }: { c: Col; h?: number; w?: number }) {
  const vals = c.values!;
  const total = vals.reduce((s, [, n]) => s + n, 0) + c.missing;
  const gap = 3;
  const usable = h - gap * (vals.length + (c.missing ? 1 : 0));
  let y = h;
  const blocks: { y: number; hh: number; ww: number; fill: string; label: string; hollow?: boolean }[] = [];
  if (c.missing) { const hh = Math.max(5, (c.missing / total) * usable); y -= hh; blocks.push({ y, hh, ww: w * 0.9, fill: 'none', label: 'missing', hollow: true }); y -= gap; }
  vals.forEach(([k, n], i) => {
    const hh = Math.max(4, (n / total) * usable);
    y -= hh;
    const ww = w * (0.94 - Math.min(0.5, i * 0.045));
    const fill = c.target ? (i === 0 ? '#e9e1d3' : '#6e4b34') : STONES[i % STONES.length];
    blocks.push({ y, hh, ww, fill, label: k });
    y -= gap;
  });
  return (
    <svg viewBox={`-10 -10 ${w + 20} ${h + 40}`} className="co-obj" aria-hidden="true">
      <ellipse cx={w / 2} cy={h + 8} rx={w * 0.42} ry={7} className="co-shadow" />
      {blocks.map((b, i) => (
        <rect key={i} x={(w - b.ww) / 2} y={Math.max(0, b.y)} width={b.ww} height={b.hh} rx={Math.min(6, b.hh / 2)} fill={b.fill} className={b.hollow ? 'co-hollow' : 'co-block'} />
      ))}
    </svg>
  );
}

export function ColumnObject({ c, h, w }: { c: Col; h?: number; w?: number }) {
  return c.kind === 'numeric' ? <Vessel c={c} h={h} w={w} /> : <Totem c={c} h={h} w={w} />;
}

export function describe(c: Col, rows: number) {
  if (c.kind === 'numeric') return `${c.min} – ${c.max} · median ${c.median}${c.zero_share && c.zero_share > 50 ? ` · ${c.zero_share}% zero` : ''}`;
  const top = c.values![0];
  return `${c.unique} values · top “${top[0]}” ${((top[1] / rows) * 100).toFixed(1)}%${c.missing ? ` · ${((c.missing / rows) * 100).toFixed(2)}% missing` : ''}`;
}
