// Engineering line drawings for The Local Line. Every count and label is a real value.
import columnsAll from '../../fixture/columns.generated.json';
import { adult } from '../../fixture';

interface Col { name: string; target: boolean; missing: number; unique: number; kind: 'numeric' | 'categorical'; min?: number; max?: number; median?: number; bins?: number[]; values?: [string, number][] }
const fmt = (v?: number) => v == null ? '' : Math.abs(v) >= 10000 ? `${Math.round(v / 1000)}k` : String(v);
export const runCols = columnsAll as unknown as Record<string, { rows: number; columns: Col[] }>;

/** The file as a stack of hairlines: one line per ~407 rows of Adult. */
export function RowsStack({ rows = adult.rows }: { rows?: number }) {
  const n = 120, per = Math.round(rows / n);
  return (
    <svg viewBox="0 0 320 210" className="ln-draw" role="img" aria-label={`${rows.toLocaleString()} rows drawn as ${n} hairlines`}>
      {Array.from({ length: n }, (_, i) => <line key={i} x1={20 + i * 0.6} y1={20 + i * 1.4} x2={250 + i * 0.6} y2={20 + i * 1.4} className={i % 20 === 0 ? 'ln-l' : 'ln-l ln-l--dim'} />)}
      <line x1={286} y1={20} x2={286} y2={188} className="ln-dim" />
      <text x={292} y={24} className="ln-t">0</text>
      <text x={292} y={190} className="ln-t">{rows.toLocaleString()}</text>
      <text x={20} y={206} className="ln-t ln-t--dim">1 line ≈ {per} rows · {adult.columns} columns</text>
    </svg>
  );
}

/** Each column profiled: a glyph drawn from its real distribution. */
export function Columns({ run = 'adult', limit = 15 }: { run?: string; limit?: number }) {
  const cols = runCols[run].columns.slice(0, limit);
  const per = 5, cw = 76, ch = 58;
  return (
    <svg viewBox={`0 0 ${per * cw} ${Math.ceil(cols.length / per) * ch}`} className="ln-draw" role="img" aria-label={`${cols.length} columns profiled`}>
      {cols.map((c, i) => {
        const x = (i % per) * cw + 4, y = Math.floor(i / per) * ch + 4;
        const bins = c.kind === 'numeric' ? c.bins ?? [] : (c.values ?? []).map((v) => v[1]);
        const m = Math.max(1, ...bins), bw = 62 / Math.max(1, bins.length);
        return (
          <g key={c.name}>
            <rect x={x} y={y} width={66} height={30} className={c.target ? 'ln-box ln-box--amber' : 'ln-box'} />
            {bins.map((v, k) => <line key={k} x1={x + 2 + k * bw + bw / 2} x2={x + 2 + k * bw + bw / 2} y1={y + 29} y2={y + 29 - Math.sqrt(v / m) * 24} className="ln-l" />)}
            {c.missing > 0 && <rect x={x + 54} y={y + 2} width={10} height={6} className="ln-gap" />}
            <text x={x} y={y + 40} className="ln-t">{c.name.length > 14 ? c.name.slice(0, 13) + '…' : c.name}</text>
            <text x={x} y={y + 49} className="ln-t ln-t--dim">{c.kind === 'numeric' ? `${fmt(c.min)} – ${fmt(c.max)}` : `${c.unique} values`}</text>
          </g>
        );
      })}
    </svg>
  );
}

export const checks = [
  { k: 'Completeness', v: `${adult.missing.cells.toLocaleString()} empty cells`, sub: `${(adult.missing.rows.one + adult.missing.rows.two + adult.missing.rows.three_plus).toLocaleString()} rows · 3 columns`, dotted: false },
  { k: 'Uniqueness', v: `${adult.duplicates.repeated_rows} repeated rows`, sub: `${adult.duplicates.groups} groups · largest ${adult.duplicates.largest}`, dotted: false },
  { k: 'Target balance', v: `majority ${adult.majorityBaseline}%`, sub: `${adult.ratio} · balance ${adult.subScores[2].value} · critical`, dotted: false },
  { k: 'Conflicting labels', v: `${adult.conflicts.length} groups · 10 rows`, sub: '14 of 14 features equal · evidence only', dotted: false },
  { k: 'Outliers (1.5 × IQR)', v: `${adult.hours.outliers.toLocaleString()} outside ${adult.hours.lower} – ${adult.hours.upper}`, sub: 'hours_per_week · 27.63%', dotted: false },
  { k: 'Leakage', v: '1 review-only name', sub: 'marital_status · no cap', dotted: true },
];

/** The checks branch from one node and rejoin at the score. */
export function Branches({ active = -1, items = checks }: { active?: number; items?: { k: string; v: string; sub: string; dotted: boolean }[] }) {
  return (
    <svg viewBox="0 0 520 270" className="ln-draw" role="img" aria-label="Six checks branching from the profile and rejoining at the score">
      <circle cx={18} cy={135} r={4} className="ln-node" />
      <circle cx={500} cy={135} r={4} className="ln-node" />
      {items.map((c, i) => {
        const y = 135 + (i - (items.length - 1) / 2) * Math.min(48, 230 / Math.max(1, items.length - 1));
        return (
          <g key={c.k} className={active === -1 || active === i ? '' : 'ln-faint'}>
            <path d={`M18 135 C70 135 70 ${y} 120 ${y} H400 C450 ${y} 450 135 500 135`} className={c.dotted ? 'ln-l ln-l--dot' : 'ln-l'} />
            <text x={128} y={y - 6} className="ln-t ln-t--b">{c.k}</text>
            <text x={396} y={y - 6} className="ln-t ln-t--amber" textAnchor="end">{c.v}</text>
            <text x={128} y={y + 12} className="ln-t ln-t--dim">{c.sub}</text>
          </g>
        );
      })}
    </svg>
  );
}

/** Five sub-scores join into the mean; the cap line holds the result at 69. */
export function ScoreJoin({ subs = adult.subScores.map((s) => ({ label: s.label, value: s.value })), final = adult.finalScore, evidence = adult.evidenceScore }: { subs?: { label: string; value: number }[]; final?: number | null; evidence?: number }) {
  const capped = subs.some((s) => s.value <= 50);
  const X = (v: number) => 140 + v * 3.2;
  return (
    <svg viewBox="0 0 520 230" className="ln-draw" role="img" aria-label={`Five sub-scores, evidence ${evidence}, final ${final}`}>
      {subs.map((s, i) => {
        const y = 20 + i * 30;
        return (
          <g key={s.label}>
            <text x={0} y={y + 4} className="ln-t">{s.label}</text>
            <line x1={140} y1={y} x2={X(s.value)} y2={y} className={s.value <= 50 ? 'ln-l ln-l--red' : 'ln-l'} />
            <text x={X(s.value) + 6} y={y + 4} className={s.value <= 50 ? 'ln-t ln-t--red' : 'ln-t'}>{s.value}</text>
            <path d={`M${X(s.value) + 34} ${y} C${X(100) + 50} ${y} ${X(100) + 30} 196 ${X(100) + 60} 196`} className="ln-l ln-l--dim" />
          </g>
        );
      })}
      <line x1={X(50)} y1={8} x2={X(50)} y2={160} className="ln-dash" />
      <text x={X(50) + 3} y={172} className="ln-t ln-t--dim">critical ≤ 50</text>
      {capped && <><line x1={X(69)} y1={8} x2={X(69)} y2={160} className="ln-l--red ln-l" /><text x={X(69) + 3} y={186} className="ln-t ln-t--red">cap 69</text></>}
      <text x={X(100) + 64} y={192} className="ln-t ln-t--dim">evidence {evidence}</text>
      <text x={X(100) + 64} y={214} className="ln-big">{final == null ? 'no score' : final.toFixed(1)}</text>
    </svg>
  );
}

/** The three outputs as an exploded isometric stack. */
export function ReportStack() {
  const layers = [['JSON', 'strict · every computed value'], ['PDF', 'decision pages + landscape appendix'], ['HTML', 'canonical · eight topics']];
  return (
    <svg viewBox="0 0 420 230" className="ln-draw" role="img" aria-label="Exploded stack of the HTML, PDF and JSON reports">
      {layers.map(([k, d], i) => {
        const y = 30 + i * 62;
        return (
          <g key={k}>
            <path d={`M60 ${y + 30} L160 ${y} L280 ${y + 30} L180 ${y + 60} Z`} className="ln-plate" />
            {Array.from({ length: 5 }, (_, j) => <line key={j} x1={110 + j * 8} y1={y + 22 + j * 4} x2={180 + j * 8} y2={y + 40 + j * 4 - 18} className="ln-l ln-l--dim" />)}
            <line x1={280} y1={y + 30} x2={310} y2={y + 30} className="ln-dim" />
            <text x={316} y={y + 28} className="ln-t ln-t--b">{k}</text>
            <text x={316} y={y + 40} className="ln-t ln-t--dim">{d}</text>
          </g>
        );
      })}
    </svg>
  );
}

/** Loopback: the line leaves the analysis and returns to the same address. */
export function Loopback() {
  return (
    <svg viewBox="0 0 260 120" className="ln-draw" role="img" aria-label="Loopback to 127.0.0.1: nothing leaves the machine">
      <rect x={10} y={20} width={240} height={80} className="ln-box" />
      <path d="M40 60 H170 C215 60 215 30 185 30 C160 30 160 60 185 60" className="ln-l" />
      <circle cx={40} cy={60} r={3} className="ln-node" />
      <text x={20} y={14} className="ln-t ln-t--dim">this machine</text>
      <text x={20} y={90} className="ln-t ln-t--amber">127.0.0.1 → 127.0.0.1 · 0 network calls</text>
    </svg>
  );
}
