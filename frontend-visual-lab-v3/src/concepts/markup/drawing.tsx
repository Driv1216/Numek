import { useEffect, useRef, useState, type ReactNode } from 'react';
import { adult } from '../../fixture';
import { reducedMotion } from '../../shell/motion';

// Column widths (drawing units) for the Adult elevation, in source order.
const W = [34, 86, 64, 78, 34, 124, 106, 92, 66, 46, 50, 50, 44, 94, 64];
export const COLS = adult.header;
const X: number[] = W.map((_, i) => W.slice(0, i).reduce((s, v) => s + v, 0));
export const TABLE_W = X[14] + W[14];
const HEAD = 146;
const ROW = 19;

const conflict = adult.conflicts[0];
const conflictRows = conflict.rows.map((_, i) => [
  ...COLS.slice(0, 14).map((c) => String(conflict.features[c] ?? '?')),
  conflict.labels[i],
]);

export type MarkId = 1 | 2 | 3 | 4;
export const marks: { id: MarkId; tone: 'v' | 'b'; code: string; short: string; line: string }[] = [
  { id: 1, tone: 'v', code: 'conflicting_target_labels', short: 'Labels disagree', line: '5 feature-identical groups · 10 rows · evidence only' },
  { id: 2, tone: 'v', code: 'numeric_outlier_concentration', short: 'hours_per_week', line: '13,496 rows (27.63%) outside IQR fences 32.5 – 52.5' },
  { id: 3, tone: 'b', code: 'leakage_review_prompts', short: 'marital_status', line: 'Review only · name prompt · no score effect' },
  { id: 4, tone: 'v', code: 'target_imbalance', short: 'Target', line: 'Majority baseline 76.07% · ratio 3.18 : 1' },
];

/** Starts the draw-on sequence when the drawing enters the viewport. */
export function useDrawn<T extends Element>() {
  const ref = useRef<T>(null);
  const [on, setOn] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (reducedMotion()) { setOn(true); return; }
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setOn(true); io.disconnect(); } }, { threshold: 0.2 });
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return [ref, on] as const;
}

const trunc = (s: string, w: number) => {
  const max = Math.max(2, Math.floor((w - 8) / 5.6));
  return s.length > max ? s.slice(0, max - 1) + '…' : s;
};

/**
 * The real Adult table, drawn as an elevation: column titles set vertically,
 * sample rows in mono, a break for the undrawn rows, then one real conflicting group.
 */
export function TableDrawing({ rows = 12, active, onMark, drawn = true, showCallouts = true }: {
  rows?: number; active?: MarkId | null; onMark?: (m: MarkId) => void; drawn?: boolean; showCallouts?: boolean;
}) {
  const body = adult.sampleRows.slice(0, rows);
  const breakY = HEAD + rows * ROW;
  const confY = breakY + 46;
  const H = confY + 2 * ROW;
  const PAD_T = showCallouts ? 150 : 44;
  const PAD_R = showCallouts ? 290 : 34;
  const vbW = TABLE_W + PAD_R + 40;
  const vbH = H + PAD_T + 30;
  const tx = (i: number) => X[i] + W[i] / 2;
  const isOn = (m: MarkId) => !active || active === m;
  const click = (m: MarkId) => onMark && (() => onMark(m));

  return (
    <svg className={`mk-draw ${drawn ? 'is-drawn' : ''} ${active ? 'has-active' : ''}`} viewBox={`-50 ${-PAD_T} ${vbW + 30} ${vbH}`} role="img"
      aria-label={`Drawing of adult.csv: ${rows} sample rows of 48,842 and one conflicting-label group, with four marks.`}>
      <g className="mk-draw__table">
        <rect className="ln ln--frame" x={0} y={0} width={TABLE_W} height={H} pathLength={1} />
        <line className="ln" x1={0} x2={TABLE_W} y1={HEAD} y2={HEAD} pathLength={1} />
        {X.slice(1).map((x, i) => <line key={i} className="ln ln--col" style={{ ['--d' as string]: `${i * 28}ms` }} x1={x} x2={x} y1={0} y2={H} pathLength={1} />)}
        {COLS.map((c, i) => (
          <text key={c} className={`hd ${c === 'annual_income_over_50k' ? 'hd--target' : ''}`} transform={`translate(${tx(i) + 3} ${HEAD - 8}) rotate(-90)`}>{c}</text>
        ))}
        {body.map((r, ri) => (
          <g key={ri} className="row" style={{ ['--d' as string]: `${300 + ri * 35}ms` }}>
            {ri > 0 && <line className="ln ln--row" x1={0} x2={TABLE_W} y1={HEAD + ri * ROW} y2={HEAD + ri * ROW} pathLength={1} />}
            {r.map((v, ci) => <text key={ci} className="cell" x={X[ci] + 4} y={HEAD + ri * ROW + 13}>{trunc(v, W[ci])}</text>)}
          </g>
        ))}
        <g className="brk">
          <line className="ln" x1={0} x2={TABLE_W} y1={breakY} y2={breakY} pathLength={1} />
          <path className="ln ln--break" d={`M0 ${breakY + 23} ${Array.from({ length: 44 }, (_, i) => `L${(i + 1) * (TABLE_W / 44)} ${breakY + 23 + (i % 2 ? -5 : 5)}`).join(' ')}`} pathLength={1} />
          <rect x={TABLE_W / 2 - 150} y={breakY + 14} width={300} height={18} className="brk__bg" />
          <text className="brk__t" x={TABLE_W / 2} y={breakY + 27} textAnchor="middle">{`${(adult.rows - rows - 2).toLocaleString('en-US')} ROWS NOT DRAWN · ROWS ${conflict.rows.join(' & ')} SHOWN`}</text>
          <line className="ln" x1={0} x2={TABLE_W} y1={confY} y2={confY} pathLength={1} />
        </g>
        {conflictRows.map((r, ri) => (
          <g key={ri} className="row row--conf">
            {ri > 0 && <line className="ln ln--row" x1={0} x2={TABLE_W} y1={confY + ri * ROW} y2={confY + ri * ROW} pathLength={1} />}
            <text className="rowno" x={-6} y={confY + ri * ROW + 13} textAnchor="end">{conflict.rows[ri]}</text>
            {r.map((v, ci) => <text key={ci} className={`cell ${ci === 14 ? 'cell--diff' : ''}`} x={X[ci] + 4} y={confY + ri * ROW + 13}>{trunc(v, W[ci])}</text>)}
          </g>
        ))}
        {/* hours_per_week column shading: the column the outlier mark concerns */}
        <rect className={`col-tint ${isOn(2) ? '' : 'is-dim'}`} x={X[12]} y={HEAD} width={W[12]} height={H - HEAD} />
      </g>

      {/* ① conflicting labels: ring on the disagreeing target cells */}
      <g className={`mark mark--v ${isOn(1) ? '' : 'is-dim'}`} onClick={click(1)} style={{ ['--d' as string]: '1400ms' }}>
        <rect className="ring" x={X[14] + 1} y={confY + 1} width={W[14] - 2} height={2 * ROW - 2} rx={2} pathLength={1} />
        {showCallouts && <>
          <path className="leader" d={`M${TABLE_W} ${confY + ROW} H${TABLE_W + 40} V${confY - 40}`} pathLength={1} />
          <Callout x={TABLE_W + 40} y={confY - 118} n={1} title="LABELS DISAGREE" lines={['5 feature-identical groups', '10 labeled rows', 'Evidence only · no score effect']} />
        </>}
      </g>
      {/* ② hours_per_week: bracket over the column */}
      <g className={`mark mark--v ${isOn(2) ? '' : 'is-dim'}`} onClick={click(2)} style={{ ['--d' as string]: '1700ms' }}>
        <path className="ring" d={`M${X[12] + 2} -6 V-14 H${X[12] + W[12] - 2} V-6`} pathLength={1} />
        {showCallouts && <>
          <path className="leader" d={`M${tx(12)} -14 V-60 H${tx(12) + 30}`} pathLength={1} />
          <Callout x={tx(12) + 34} y={-118} n={2} title="HOURS_PER_WEEK" lines={['13,496 rows · 27.63%', 'outside IQR fences 32.5 – 52.5', 'Reduces feature usability']} />
        </>}
      </g>
      {/* ③ marital_status: blue-pencil review prompt */}
      <g className={`mark mark--b ${isOn(3) ? '' : 'is-dim'}`} onClick={click(3)} style={{ ['--d' as string]: '2000ms' }}>
        <rect className="ring" x={X[5] + 3} y={4} width={W[5] - 6} height={HEAD - 8} rx={8} pathLength={1} />
        {showCallouts && <>
          <path className="leader" d={`M${tx(5)} 4 V-60 H${tx(5) - 26}`} pathLength={1} />
          <Callout x={tx(5) - 240} y={-118} n={3} title="MARITAL_STATUS" lines={['Review only · name-based prompt', 'Confirm when the value is available', 'No score or guardrail effect']} tone="b" />
        </>}
      </g>
      {/* ④ target: majority baseline */}
      <g className={`mark mark--v ${isOn(4) ? '' : 'is-dim'}`} onClick={click(4)} style={{ ['--d' as string]: '2300ms' }}>
        <path className="ring" d={`M${X[14] + 2} -6 V-14 H${X[14] + W[14] - 2} V-6`} pathLength={1} />
        {showCallouts && <>
          <path className="leader" d={`M${tx(14)} -14 V-30 H${TABLE_W + 26} V${HEAD / 2 + 11} H${TABLE_W + 40}`} pathLength={1} />
          <Callout x={TABLE_W + 44} y={HEAD / 2} n={4} title="TARGET IMBALANCE" lines={['Majority baseline 76.07%', '37,155 : 11,687 · ratio 3.18 : 1', 'Lowers target balance to 47.86']} />
        </>}
      </g>
      {!showCallouts && ([
        [1, X[14] + W[14] + 16, confY + ROW, 'v'], [2, tx(12), -28, 'v'], [3, tx(5), -28, 'b'], [4, tx(14), -28, 'v'],
      ] as [MarkId, number, number, string][]).map(([n, x, y, t]) => (
        <g key={n} className={`pin pin--${t} ${isOn(n) ? '' : 'is-dim'}`} onClick={click(n)} role="button" aria-label={`Mark ${n}`}>
          <circle cx={x} cy={y} r={10} /><text x={x} y={y + 4} textAnchor="middle">{n}</text>
        </g>
      ))}
    </svg>
  );
}

function Callout({ x, y, n, title, lines, tone = 'v' }: { x: number; y: number; n: number; title: string; lines: string[]; tone?: 'v' | 'b' }) {
  return (
    <g className={`callout callout--${tone}`} transform={`translate(${x} ${y})`}>
      <circle cx={11} cy={11} r={10} className="callout__dot" />
      <text x={11} y={15.5} textAnchor="middle" className="callout__n">{n}</text>
      <text x={28} y={16} className="callout__t">{title}</text>
      {lines.map((l, i) => <text key={i} x={28} y={34 + i * 14} className="callout__l">{l}</text>)}
    </g>
  );
}

/** Registration crosshair used at sheet corners and section joints. */
export const Cross = ({ className = '' }: { className?: string }) => (
  <svg className={`mk-cross ${className}`} viewBox="0 0 20 20" aria-hidden="true"><path d="M10 0V20M0 10H20" /><circle cx="10" cy="10" r="4" /></svg>
);

export function TitleBlock({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="mk-tb">
      {rows.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}
    </dl>
  );
}

export function Wordmark({ small = false }: { small?: boolean }) {
  return (
    <a className={`mk-wm ${small ? 'mk-wm--s' : ''}`} href="#/markup/landing" aria-label="NUMEK home">
      <svg viewBox="0 0 22 22" aria-hidden="true"><rect x="1" y="1" width="20" height="20" /><path d="M1 21 21 1" /><circle cx="15.5" cy="6.5" r="3.4" /></svg>
      <span>NUMEK</span>
    </a>
  );
}

/** Histogram drawn as a stepped elevation with IQR fences (Detail views). */
export function HoursDetail({ width = 520, height = 200 }: { width?: number; height?: number }) {
  const { counts, start } = adult.hours.hist;
  const max = Math.max(...counts);
  const sx = (v: number) => ((v - start) / counts.length) * width;
  const sy = (c: number) => height - Math.sqrt(c / max) * (height - 16);
  let d = `M0 ${height}`;
  counts.forEach((c, i) => { d += ` L${sx(start + i)} ${sy(c)} L${sx(start + i + 1)} ${sy(c)}`; });
  d += ` L${width} ${height}`;
  const lo = sx(adult.hours.lower), hi = sx(adult.hours.upper);
  return (
    <svg className="mk-detail" viewBox={`-30 -20 ${width + 50} ${height + 56}`} role="img" aria-label="hours_per_week distribution, square-root scale, with IQR fences at 32.5 and 52.5">
      <defs>
        <pattern id="mk-hatch" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="5" className="hatch" /></pattern>
      </defs>
      <rect x={0} y={0} width={lo} height={height} fill="url(#mk-hatch)" className="out" />
      <rect x={hi} y={0} width={width - hi} height={height} fill="url(#mk-hatch)" className="out" />
      <path d={d} className="hist" />
      <line x1={lo} x2={lo} y1={-10} y2={height} className="fence" />
      <line x1={hi} x2={hi} y1={-10} y2={height} className="fence" />
      <text x={lo} y={-12} textAnchor="middle" className="lab lab--v">32.5</text>
      <text x={hi} y={-12} textAnchor="middle" className="lab lab--v">52.5</text>
      <line x1={0} x2={width} y1={height} y2={height} className="axis" />
      {[1, 20, 40, 60, 80, 99].map((v) => <g key={v}><line x1={sx(v)} x2={sx(v)} y1={height} y2={height + 5} className="axis" /><text x={sx(v)} y={height + 17} textAnchor="middle" className="lab">{v}</text></g>)}
      <text x={sx(40.5)} y={sy(counts[39]) - 6} textAnchor="middle" className="lab">40 h · 46.69%</text>
      <text x={0} y={height + 34} className="lab">HOURS PER WEEK · SQRT COUNT · HATCHED = OUTSIDE FENCES (13,496 ROWS)</text>
    </svg>
  );
}
