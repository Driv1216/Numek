// One drawing per module, bound to the run's canonical JSON. The approved rule holds: what the module
// found is drawn in full ink; context is a ghost. Where the JSON has nothing to draw, the tile keeps a
// static mark (marked schematic in the chapter), so no drawing implies data the report doesn't hold.
import type { ReactElement } from 'react';
import type { Analysis } from '../api';
import { governingCap, type TileRun } from './adapter';
import type { ModId } from './modules';

type P = { a: Analysis; t?: TileRun; big?: boolean };
const num = (v: unknown, d = 0) => (typeof v === 'number' && Number.isFinite(v) ? v : d);
const known = (v: unknown) => typeof v === 'number' && Number.isFinite(v);
/** Evidence the JSON does not hold is said to be unavailable, never drawn as zero. */
const Unavailable = ({ what }: { what: string }) => <svg viewBox="0 0 154 40" className="md-viz" preserveAspectRatio="xMidYMax meet"><text x={0} y={22} className="md-t md-t--s">{what} unavailable in this run</text></svg>;

function Score({ a, big }: P) {
  const v = a.scoring.status === 'computed' ? a.scoring.values : null;
  const s = v ? Object.entries(v.sub_scores) : ['completeness', 'uniqueness', 'target_balance', 'feature_usability', 'leakage_risk'].map((k) => [k, 0] as [string, number]);
  const cap = governingCap(v)?.cap;
  const W = 200, base = 112, bw = 30, gap = 9, x0 = 8;
  const short: Record<string, string> = { completeness: 'Compl.', uniqueness: 'Uniq.', target_balance: 'Balance', feature_usability: 'Usab.', leakage_risk: 'Leak.' };
  return (
    <svg viewBox={`0 0 ${W} 130`} className="md-viz" preserveAspectRatio="xMidYMax meet">
      <line x1={0} x2={W} y1={base} y2={base} className="md-ghost-l" />
      {s.map(([k, value], i) => {
        const x = x0 + i * (bw + gap), hh = v ? value : 6;
        return (
          <g key={k} className="md-grow" style={{ ['--i' as string]: i }}>
            <rect x={x} y={base - hh} width={bw} height={hh} className={v && value <= 50 ? 'md-hot' : 'md-ghost'} />
            {big && v && <text x={x + bw / 2} y={base - hh - 4} className="md-t md-t--c">{value}</text>}
            {big && <text x={x + bw / 2} y={base + 11} className="md-t md-t--c md-t--s">{short[k] ?? k}</text>}
          </g>
        );
      })}
      {cap != null && <line x1={0} x2={W} y1={base - cap} y2={base - cap} className="md-cap" />}
      {v && <line x1={0} x2={W} y1={base - 50} y2={base - 50} className="md-ghost-l" strokeDasharray="1 3" />}
      {big && cap != null && <text x={W} y={base - cap - 3} className="md-t md-t--r">cap {cap}</text>}
      {big && v && <text x={W} y={base - 53} className="md-t md-t--r md-t--s">critical ≤ 50</text>}
      {big && !v && <text x={W / 2} y={base - 30} className="md-t md-t--c">no score defined</text>}
    </svg>
  );
}

/** Each dot ≈ 1% of rows; rings are the share of rows with at least one missing feature. */
function Gaps({ a, big }: P) {
  if (!known(a.profile.missing_feature_row_rate)) return <Unavailable what="row missingness" />;
  const rate = num(a.profile.missing_feature_row_rate);
  const cols = 20, rr = 5, pitch = 6, total = cols * rr, hot = Math.round((rate / 100) * total);
  const step = hot ? total / hot : Infinity;
  return (
    <svg viewBox={`0 0 ${cols * pitch} ${rr * pitch + (big ? 9 : 0)}`} className="md-viz" preserveAspectRatio="xMidYMax meet">
      {Array.from({ length: total }, (_, i) => { const m = hot > 0 && Math.floor(i / step) !== Math.floor((i + 1) / step); return <circle key={i} cx={(i % cols) * pitch + 3} cy={Math.floor(i / cols) * pitch + 3} r={m ? 2.3 : 1.7} className={m ? 'md-ring' : 'md-ghost'} />; })}
      {big && <text x={0} y={rr * pitch + 8} className="md-t md-t--s">each dot ≈ 1% of rows · rings: {rate}% with a gap</text>}
    </svg>
  );
}

function Dups({ a, big }: P) {
  if (!known(a.profile.duplicate_group_count)) return <Unavailable what="duplicate evidence" />;
  const total = num(a.profile.duplicate_group_count), groups = Math.min(total, big ? 60 : 35), largest = num(a.profile.largest_duplicate_group_size, 2);
  const cols = big ? 10 : 7, cw = 22, ch = 18;
  if (!groups) return <svg viewBox="0 0 154 40" className="md-viz" preserveAspectRatio="xMidYMax meet"><rect x={2} y={14} width={13} height={9} rx={1.5} className="md-card" /><text x={22} y={22} className="md-t md-t--s">no repeated rows</text></svg>;
  return (
    <svg viewBox={`0 0 ${cols * cw} ${Math.ceil(groups / cols) * ch + (big ? 12 : 0)}`} className="md-viz" preserveAspectRatio="xMidYMax meet">
      {big && <text x={0} y={Math.ceil(groups / cols) * ch + 10} className="md-t md-t--s">{groups} of {total.toLocaleString('en-US')} groups drawn · first group shows the largest size</text>}
      {Array.from({ length: groups }, (_, i) => { const k = i === 0 ? Math.min(largest, 5) : 2; return (
        <g key={i} transform={`translate(${(i % cols) * cw + 2} ${Math.floor(i / cols) * ch + 2})`} className={i === 0 && largest > 2 ? 'md-hotg' : ''}>
          {Array.from({ length: k }, (_, j) => <rect key={j} x={j * 3} y={j * 3} width={13} height={9} rx={1.5} className={j ? 'md-card' : 'md-card md-card--b'} />)}
        </g>); })}
    </svg>
  );
}

function Conflicts() {
  return (
    <svg viewBox="0 0 120 150" className="md-viz" preserveAspectRatio="xMidYMax meet" role="img" aria-label="Schematic illustration, not data">
      <text x={118} y={148} className="md-t md-t--r md-t--s">schematic</text>
      {[0, 1].map((r) => (
        <g key={r} transform={`translate(${r * 62 + 4} 4)`}>
          {Array.from({ length: 14 }, (_, i) => <rect key={i} x={0} y={i * 8.6} width={50} height={6} rx={1.5} className="md-ghost" />)}
          <rect x={0} y={14 * 8.6 + 4} width={50} height={14} rx={2} className={r ? 'md-ring' : 'md-ink'} />
        </g>
      ))}
    </svg>
  );
}

function Imbalance({ a, big }: P) {
  const dist = (a.profile.target_distribution as { label: string; percentage: number }[] | undefined) ?? [];
  if (!dist.length) return <Unavailable what="class balance" />;
  // Each class gets its rounded share of 100 squares, in canonical order; the last class takes the remainder.
  const shares = dist.map((c) => Math.round(c.percentage)); shares[shares.length - 1] = Math.max(0, 100 - shares.slice(0, -1).reduce((x, y) => x + y, 0));
  const owner: number[] = shares.flatMap((k, i) => Array<number>(k).fill(i)).slice(0, 100);
  const cls = ['md-ink', 'md-ring', 'md-ghost', 'md-hot'];
  const cols = 10, s = 8;
  return (
    <svg viewBox={`0 0 ${cols * s} ${10 * s + (big ? 14 : 0)}`} className="md-viz" preserveAspectRatio="xMidYMax meet" role="img" aria-label={dist.map((c) => `${c.label} ${c.percentage}%`).join(', ')}>
      {owner.map((k, i) => <rect key={i} x={(i % cols) * s + 1} y={Math.floor(i / cols) * s + 1} width={s - 2} height={s - 2} rx={1} className={cls[Math.min(k, cls.length - 1)]} />)}
      {big && <text x={0} y={10 * s + 10} className="md-t md-t--s">each square ≈ 1% · {dist.slice(0, 3).map((c) => `${c.label} ${c.percentage}%`).join(' · ')}{dist.length > 3 ? ` · ${dist.length - 3} more` : ''}</text>}
    </svg>
  );
}

const names = (v: unknown) => new Set(Array.isArray(v) ? v.map((x) => (typeof x === 'string' ? x : (x as { name?: string })?.name ?? '')) : []);

function Leakage({ a, big }: P) {
  const cols = a.profile.columns.map((c) => c.name), target = String(a.profile.target ?? '');
  const review = names(a.profile.review_only_leakage_candidates), strong = names(a.profile.strong_leakage_candidates);
  const hot = (c: string) => review.has(c) || strong.has(c);
  if (big) {
    return (
      <ul className="md-leak">
        {cols.map((c) => <li key={c} className={hot(c) ? 'is-hot' : c === target ? 'is-target' : ''}><span>{c}</span>{strong.has(c) ? <em>strong</em> : review.has(c) ? <em>review only</em> : c === target ? <em>target</em> : null}</li>)}
      </ul>
    );
  }
  return (
    <svg viewBox={`0 0 120 ${Math.max(40, 8 + cols.length * 7.6)}`} className="md-viz" preserveAspectRatio="xMidYMax meet">
      {cols.map((c, i) => <rect key={c} x={4} y={4 + i * 7.6} width={Math.min(110, c.length * 4.2)} height={4.4} rx={1.5} className={hot(c) ? 'md-hot' : 'md-ghost'} />)}
    </svg>
  );
}

/** Share of finite values outside the 1.5 × IQR fences, per numeric column; ink from 5%. */
function Outliers({ a, big }: P) {
  const zero = (c: { numeric_summary?: unknown }) => { const q = c.numeric_summary as { q1?: number; q3?: number } | undefined; return typeof q?.q1 === 'number' && q.q1 === q.q3; };
  const all = a.profile.columns.filter((c) => c.is_numeric !== false && c.role !== 'target' && (typeof c.outlier_rate === 'number' || zero(c as { numeric_summary?: unknown })));
  const cols = [...all].sort((x, y) => (y.outlier_rate ?? -1) - (x.outlier_rate ?? -1)).slice(0, big ? 16 : 12);
  const legacy = a.methodology_id === 'classification_legacy_2026_08_13';
  const max = Math.max(5, ...cols.map((c) => c.outlier_rate ?? 0));
  const W = 196, H = big ? 120 : 110, bw = W / Math.max(cols.length, 1);
  return (
    <svg viewBox={`0 0 ${W} ${H + (big ? 26 : 2)}`} className="md-viz" preserveAspectRatio="xMidYMax meet">
      <line x1={0} x2={W} y1={H - (5 / max) * H} y2={H - (5 / max) * H} className="md-ghost-l" strokeDasharray="1 3" />
      {cols.map((c, i) => { const undefinedFences = zero(c as { numeric_summary?: unknown }); const hh = Math.max(0.8, ((c.outlier_rate ?? 0) / max) * H); return (
        <g key={c.name}>
          {undefinedFences
            ? <><rect x={i * bw + 1.5} y={H * 0.35} width={bw - 3} height={H * 0.65} className="md-ghost-l" strokeDasharray="2 2" fill="none" />{big && <text x={i * bw + bw / 2} y={H * 0.33} className="md-t md-t--c md-t--s">IQR 0</text>}</>
            : <rect x={i * bw + 1} y={H - hh} width={bw - 2} height={hh} className={`md-grow ${(c.outlier_rate ?? 0) >= 5 ? 'md-ink' : 'md-ghost'}`} style={{ ['--i' as string]: i }} />}
          {big && <text x={i * bw + bw / 2} y={H + 10} className="md-t md-t--c md-t--s">{c.name.length > 7 ? `${c.name.slice(0, 6)}…` : c.name}</text>}
        </g>); })}
      {big && <text x={W} y={H - (5 / max) * H - 3} className="md-t md-t--r md-t--s">5%</text>}
      {big && <text x={0} y={H + 24} className="md-t md-t--s">{legacy ? 'share of all rows' : 'share of finite values'} outside 1.5 × IQR · dashed: IQR 0, fences undefined{all.length > cols.length ? ` · ${cols.length} of ${all.length} columns drawn` : ''}</text>}
    </svg>
  );
}

function Relations({ t, big }: P) {
  const found = !!t?.findings.length;
  return (
    <svg viewBox="0 0 196 120" className="md-viz" preserveAspectRatio="xMidYMax meet" role="img" aria-label="Schematic illustration, not data">
      {!big && <text x={194} y={10} className="md-t md-t--r md-t--s">schematic</text>}
      {Array.from({ length: 24 }, (_, i) => { const r = 30 + ((i * 37) % 50), c = 10 + ((i * 23) % 30); return (
        <g key={i}><rect x={i * 8 + 1} y={110 - r} width={6} height={r} className="md-ghost" /><rect x={i * 8 + 1} y={110 - r - c} width={6} height={c} className={found ? 'md-ink' : 'md-ghost'} /></g>); })}
      {big && <text x={0} y={119} className="md-t md-t--s">schematic · component + component = target</text>}
    </svg>
  );
}

function Time({ big }: { big?: boolean }) {
  const ev = [12, 34, 52, 71, 96, 118, 140, 166], cut = 104;
  return (
    <svg viewBox="0 0 180 90" className="md-viz" preserveAspectRatio="xMidYMax meet">
      <line x1={4} x2={176} y1={60} y2={60} className="md-ghost-l" />
      {ev.map((x) => <circle key={x} cx={x} cy={60} r={4} className={x < cut ? 'md-ink' : 'md-ring'} />)}
      <line x1={cut} x2={cut} y1={14} y2={76} className="md-cap" />
      <text x={cut + 4} y={22} className="md-t">{big ? 'prediction time' : 't₀'}</text>
      {big && <text x={4} y={84} className="md-t md-t--s">schematic · declared availability per feature</text>}
    </svg>
  );
}

function Text({ big }: { big?: boolean }) {
  const w = [150, 118, 136, 92, 160, 104, 136, 128, 70];
  return (
    <svg viewBox="0 0 180 120" className="md-viz" preserveAspectRatio="xMidYMax meet">
      {w.map((ww, i) => <rect key={i} x={14} y={6 + i * 12.4} width={ww} height={6} rx={3} className={i === 2 || i === 6 ? 'md-ink' : 'md-ghost'} />)}
      <path d={`M10 9 h-5 v${4 * 12.4} h5`} className="md-brk" transform="translate(0 24.8)" />
      {big && <text x={176} y={118} className="md-t md-t--r md-t--s">schematic</text>}
    </svg>
  );
}

function Images({ big }: { big?: boolean }) {
  const cols = 16, s = big ? 10 : 6;
  return (
    <svg viewBox={`0 0 ${cols * s} ${6 * s + (big ? 10 : 0)}`} className="md-viz" preserveAspectRatio="xMidYMax meet" role="img" aria-label="Schematic illustration, not data">
      {big && <text x={cols * s} y={6 * s + 9} className="md-t md-t--r md-t--s">schematic</text>}
      {Array.from({ length: 96 }, (_, i) => <rect key={i} x={(i % cols) * s + 0.8} y={Math.floor(i / cols) * s + 0.8} width={s - 1.6} height={s - 1.6} rx={0.8} className={i % 9 === 4 ? 'md-ring' : 'md-ghost'} />)}
    </svg>
  );
}

function Docs({ big }: { big?: boolean }) {
  const cols = big ? 4 : 10, cw = big ? 48 : 30, ch = big ? 30 : 22;
  return (
    <svg viewBox={`0 0 ${cols * cw} ${Math.ceil(20 / cols) * ch + (big ? 10 : 0)}`} className="md-viz" preserveAspectRatio="xMidYMax meet" role="img" aria-label="Schematic illustration, not data">
      {big && <text x={cols * cw} y={Math.ceil(20 / cols) * ch + 9} className="md-t md-t--r md-t--s">schematic</text>}
      {Array.from({ length: 20 }, (_, i) => { const x = (i % cols) * cw + 4, y = Math.floor(i / cols) * ch + ch / 2, hot = i === 6; return (
        <g key={i}><circle cx={x + 3} cy={y} r={3} className={hot ? 'md-ink' : 'md-ghost'} /><line x1={x + 6} x2={x + 15} y1={y} y2={y} className={hot ? 'md-cap' : 'md-ghost-l'} /><rect x={x + 15} y={y - 3.5} width={7} height={7} rx={1} className={hot ? 'md-ring' : 'md-ghost'} /></g>); })}
    </svg>
  );
}

function Local({ big }: { big?: boolean }) {
  return (
    <svg viewBox="0 0 120 120" className="md-viz" preserveAspectRatio="xMidYMax meet">
      <circle cx={60} cy={62} r={34} className="md-ghost-l md-spin" strokeDasharray="4 5" />
      <circle cx={60} cy={62} r={6} className="md-ink" />
      <path d="M60 28 a34 34 0 0 1 29 17" className="md-arc" />
      <path d="M86 40 l3 6 l-6 0" className="md-ink" />
      {big && <text x={60} y={112} className="md-t md-t--c">{location.hostname} → {location.hostname}</text>}
    </svg>
  );
}

function Reports({ big }: { big?: boolean }) {
  return (
    <svg viewBox="0 0 180 110" className="md-viz" preserveAspectRatio="xMidYMax meet">
      {['HTML', 'PDF', 'JSON'].map((x, i) => (
        <g key={x} transform={`translate(${8 + i * 58} ${8 + i * 4})`} className="md-grow" style={{ ['--i' as string]: i }}>
          <rect x={4} y={4} width={46} height={64} rx={2} className="md-ghost" />
          <rect x={0} y={0} width={46} height={64} rx={2} className="md-page" />
          {Array.from({ length: 7 }, (_, j) => <rect key={j} x={6} y={10 + j * 7} width={j % 3 === 2 ? 22 : 34} height={2.6} rx={1} className="md-ghost" />)}
          <text x={0} y={80} className="md-t">{x}</text>
        </g>
      ))}
      {big && <text x={8} y={106} className="md-t md-t--s">one evidence model · canonical HTML</text>}
    </svg>
  );
}

const table: Record<ModId, (p: P) => ReactElement> = {
  score: Score, gaps: Gaps, dups: Dups, conflicts: Conflicts, imbalance: Imbalance, leakage: Leakage, outliers: Outliers,
  relations: Relations, time: Time, text: Text, images: Images, docs: Docs, local: Local, reports: Reports,
};

export function Viz({ id, a, t, big }: { id: ModId; a: Analysis; t?: TileRun; big?: boolean }) {
  const C = table[id];
  return <C a={a} t={t} big={big} />;
}
