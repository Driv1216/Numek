// The instrument: a radial plot of a dataset. Each sector is a column; each ring is one bin of its
// real distribution (32 bins for numbers, top values for categories). Bins outside the 1.5 × IQR
// fences, missing values and the target's classes can be lit by a question.
import { useState } from 'react';
import columnsAll from '../../fixture/columns.generated.json';

export interface Col { name: string; target: boolean; missing: number; unique: number; kind: 'numeric' | 'categorical'; min?: number; max?: number; q1?: number; q3?: number; median?: number; bins?: number[]; values?: [string, number][] }
export const runCols = columnsAll as unknown as Record<string, { rows: number; columns: Col[] }>;

export type Mode = 'none' | 'target' | 'conflict' | 'outliers' | 'missing' | 'leak' | 'score' | 'relation';

/** Which bins of a numeric column lie outside DataTrust's 1.5 × IQR fences (none when IQR is 0). */
export function outsideBins(c: Col) {
  if (c.kind !== 'numeric' || !c.bins || c.q1 == null || c.q3 == null || c.min == null || c.max == null) return [];
  const iqr = c.q3 - c.q1; if (iqr <= 0) return c.bins.map(() => false);
  const lo = c.q1 - 1.5 * iqr, hi = c.q3 + 1.5 * iqr, step = (c.max - c.min) / c.bins.length;
  return c.bins.map((_, k) => { const v = c.min! + (k + 0.5) * step; return v < lo || v > hi; });
}

export const leakNames: Record<string, string[]> = {
  adult: ['marital_status'],
  german: ['checking_account_status', 'credit_history', 'credit_amount', 'savings_status', 'personal_status_sex'],
  bank: ['previous_campaign_outcome'],
  bike: ['casual', 'registered'],
};

export function Dial({ run, mode, onHover, hover, core = ['', ''] }: { run: string; mode: Mode; onHover?: (c: Col | null) => void; hover?: string | null; core?: [string, string] }) {
  const { columns: cols, rows } = runCols[run];
  const n = cols.length, cx = 260, cy = 260, r0 = 70, R = 236, rings = 16;
  const dr = (R - r0) / rings;
  const lit = (c: Col) => {
    if (mode === 'none' || mode === 'score') return true;
    if (mode === 'target' || mode === 'conflict') return c.target;
    if (mode === 'outliers') return outsideBins(c).some(Boolean);
    if (mode === 'missing') return c.missing > 0;
    if (mode === 'leak') return (leakNames[run] ?? []).includes(c.name);
    if (mode === 'relation') return ['casual', 'registered', 'cnt'].includes(c.name);
    return false;
  };
  const arc = (r: number, a0: number, a1: number) => `M${cx + r * Math.cos(a0)} ${cy + r * Math.sin(a0)} A${r} ${r} 0 0 1 ${cx + r * Math.cos(a1)} ${cy + r * Math.sin(a1)}`;
  return (
    <svg viewBox="0 0 520 520" className="in-dial" role="img" aria-label={`Instrument: ${n} columns of ${run}, rings from each column's distribution`}>
      <circle cx={cx} cy={cy} r={R + 8} className="in-bezel" />
      {Array.from({ length: 60 }, (_, k) => { const a = (k / 60) * Math.PI * 2; return <line key={k} x1={cx + (R + 8) * Math.cos(a)} y1={cy + (R + 8) * Math.sin(a)} x2={cx + (R + (k % 5 ? 12 : 16)) * Math.cos(a)} y2={cy + (R + (k % 5 ? 12 : 16)) * Math.sin(a)} className="in-tick" />; })}
      {cols.map((c, i) => {
        const a0 = (i / n) * Math.PI * 2 - Math.PI / 2 + 0.012, a1 = ((i + 1) / n) * Math.PI * 2 - Math.PI / 2 - 0.012;
        const raw = c.kind === 'numeric' ? c.bins ?? [] : (c.values ?? []).map((v) => v[1]);
        // Resample to the ring count so every sector has the same radial scale.
        const bins = Array.from({ length: rings }, (_, k) => raw.slice(Math.floor((k * raw.length) / rings), Math.max(Math.floor((k * raw.length) / rings) + 1, Math.floor(((k + 1) * raw.length) / rings))).reduce((a, b) => a + b, 0));
        const out = outsideBins(c);
        const outRing = Array.from({ length: rings }, (_, k) => out.slice(Math.floor((k * out.length) / rings), Math.max(Math.floor((k * out.length) / rings) + 1, Math.floor(((k + 1) * out.length) / rings))).some(Boolean));
        const m = Math.max(1, ...bins);
        const on = lit(c), hov = hover === c.name;
        const isTgt = c.target && (mode === 'target' || mode === 'conflict');
        const am = (a0 + a1) / 2;
        return (
          <g key={c.name} className={`in-sec ${on ? 'is-on' : 'is-off'} ${hov ? 'is-hover' : ''}`} onMouseEnter={() => onHover?.(c)} onMouseLeave={() => onHover?.(null)} onFocus={() => onHover?.(c)} onBlur={() => onHover?.(null)} tabIndex={onHover ? 0 : -1} aria-label={`${c.name}, ${c.kind}, ${c.unique} distinct values${c.missing ? `, ${c.missing} missing` : ''}`}>
            <path d={`M${cx} ${cy} L${cx + R * Math.cos(a0)} ${cy + R * Math.sin(a0)} A${R} ${R} 0 0 1 ${cx + R * Math.cos(a1)} ${cy + R * Math.sin(a1)} Z`} className="in-hit" />
            {bins.map((v, k) => {
              const r = r0 + (k + 0.5) * dr, w = v > 0 ? 0.8 + (v / m) * (dr - 2.2) : 0;
              if (!w) return null;
              const red = mode === 'outliers' && outRing[k];
              const cls = isTgt ? (k < rings / 2 ? 'in-arc in-arc--maj' : 'in-arc in-arc--min') : red ? 'in-arc in-arc--red' : 'in-arc';
              return <path key={k} d={arc(r, a0, a1)} strokeWidth={w.toFixed(2)} className={cls} />;
            })}
            {c.missing > 0 && <path d={arc(R + 2, a0, a0 + (a1 - a0) * Math.max(0.04, c.missing / rows))} className={`in-miss ${mode === 'missing' ? 'is-lit' : ''}`} />}
            <text x={cx + (r0 - 10) * Math.cos(am)} y={cy + (r0 - 10) * Math.sin(am)} className="in-num" textAnchor="middle" dominantBaseline="middle">{String(i + 1).padStart(2, '0')}</text>
          </g>
        );
      })}
      <circle cx={cx} cy={cy} r={r0 - 22} className="in-core" />
      <text x={cx} y={cy - 4} textAnchor="middle" className="in-core__v">{core[0]}</text>
      <text x={cx} y={cy + 14} textAnchor="middle" className="in-core__l">{core[1]}</text>
    </svg>
  );
}

/** The row range of the file, with marks at the rows a question points to. */
export function RowRange({ rows, marks = [], range, onRange }: { rows: number; marks?: number[]; range: [number, number]; onRange: (r: [number, number]) => void }) {
  const [drag, setDrag] = useState<0 | 1 | null>(null);
  const pct = (v: number) => (v / rows) * 100;
  const fromX = (e: React.PointerEvent<HTMLDivElement>) => { const b = e.currentTarget.getBoundingClientRect(); return Math.round(Math.min(1, Math.max(0, (e.clientX - b.left) / b.width)) * rows); };
  return (
    <div className="in-range">
      <div className="in-range__track" onPointerDown={(e) => { const v = fromX(e); const h = Math.abs(v - range[0]) < Math.abs(v - range[1]) ? 0 : 1; setDrag(h); e.currentTarget.setPointerCapture(e.pointerId); onRange(h === 0 ? [Math.min(v, range[1]), range[1]] : [range[0], Math.max(v, range[0])]); }}
        onPointerMove={(e) => { if (drag == null) return; const v = fromX(e); onRange(drag === 0 ? [Math.min(v, range[1]), range[1]] : [range[0], Math.max(v, range[0])]); }} onPointerUp={() => setDrag(null)}>
        <i className="in-range__sel" style={{ left: `${pct(range[0])}%`, width: `${pct(range[1] - range[0])}%` }} />
        {marks.map((m) => <b key={m} className={m >= range[0] && m <= range[1] ? 'is-in' : ''} style={{ left: `${pct(m)}%` }} />)}
      </div>
      <div className="in-range__lab"><span>row {range[0].toLocaleString()}</span><span>rows in range · {(range[1] - range[0]).toLocaleString()}</span><span>row {range[1].toLocaleString()}</span></div>
      <div className="in-range__keys">
        <label>From <input type="number" min={0} max={range[1]} value={range[0]} onChange={(e) => onRange([Math.max(0, Math.min(range[1], +e.target.value)), range[1]])} /></label>
        <label>To <input type="number" min={range[0]} max={rows} value={range[1]} onChange={(e) => onRange([range[0], Math.min(rows, Math.max(range[0], +e.target.value))])} /></label>
      </div>
    </div>
  );
}
