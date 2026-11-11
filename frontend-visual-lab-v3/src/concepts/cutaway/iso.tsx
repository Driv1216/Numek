// The dataset drawn as an isometric engineering cutaway. Every dimension is a real value:
// strip height = log of the column's distinct values, notch = the column's missing share,
// target split = class shares, lifted rows = the first conflicting-label pair, section = the real
// hours_per_week histogram with its 1.5 × IQR fences.
import type React from 'react';
import type { ReactNode } from 'react';
import columnsAll from '../../fixture/columns.generated.json';
import { adult } from '../../fixture';

export interface Col { name: string; target: boolean; missing: number; unique: number; kind: 'numeric' | 'categorical'; bins?: number[]; values?: [string, number][] }
export const runCols = columnsAll as unknown as Record<string, { rows: number; columns: Col[] }>;

/** Majority share of the target where DataTrust reports one (classification runs only). */
export const targetSplit: Record<string, number> = { adult: adult.majorityBaseline / 100, german: 0.7, bank: 0.883 };

const W = 14, G = 7, D = 96;
/** The hours_per_week section stands well in front of the slab so it reads as pulled out. */
const SY = D + 150;
export const COS = Math.cos(Math.PI / 6), SIN = 0.5;
export const iso = (x: number, y: number, z: number) => [(x - y) * COS, (x + y) * SIN - z] as const;
const pt = (x: number, y: number, z: number) => iso(x, y, z).map((v) => v.toFixed(1)).join(' ');
export const colX = (i: number) => i * (W + G);
export const colH = (c: Col) => 22 + Math.log10(Math.max(2, c.unique)) * 30;

function Prism({ x, y, z = 0, w, d, h, cls = '' }: { x: number; y: number; z?: number; w: number; d: number; h: number; cls?: string }) {
  const top = `M${pt(x, y, z + h)} L${pt(x + w, y, z + h)} L${pt(x + w, y + d, z + h)} L${pt(x, y + d, z + h)} Z`;
  const right = `M${pt(x + w, y, z)} L${pt(x + w, y + d, z)} L${pt(x + w, y + d, z + h)} L${pt(x + w, y, z + h)} Z`;
  const front = `M${pt(x, y + d, z)} L${pt(x + w, y + d, z)} L${pt(x + w, y + d, z + h)} L${pt(x, y + d, z + h)} Z`;
  return <g className={`cw-prism ${cls}`}><path d={right} className="cw-f2" /><path d={front} className="cw-f1" /><path d={top} className="cw-f0" /></g>;
}

/** A mono label on a leader line, anchored at an isometric point. */
function Label({ at, dy = -34, children, cls = '' }: { at: readonly [number, number]; dy?: number; children: ReactNode; cls?: string }) {
  const [x, y] = at;
  return (
    <g className={`cw-label ${cls}`}>
      <line x1={x} y1={y} x2={x} y2={y + dy} />
      <circle cx={x} cy={y} r={1.6} />
      <text x={x + 3} y={y + dy - 3}>{children}</text>
    </g>
  );
}

export type Part = 'all' | 'target' | 'lift' | 'section' | 'leak' | 'gaps' | 'relation' | 'cap';

/** Screen-space rectangles for the camera to frame, per part, in the slab's own SVG coordinates. */
export function partBox(run: string, part: Part): [number, number, number, number] {
  const cols = runCols[run].columns;
  const n = cols.length, X = colX(n);
  const find = (name: string) => cols.findIndex((c) => c.name === name);
  // Frame a strip with generous context: ~360 × 270 around its centre.
  const around = (i: number, extra = 0) => {
    const [cx, cy] = iso(colX(i) + W / 2, D / 2, colH(cols[i]) / 2);
    const w = 380 + extra * 2, h = w * 0.68;
    return [cx - w / 2, cy - h * 0.55, w, h] as [number, number, number, number];
  };
  if (part === 'target') return around(cols.findIndex((c) => c.target), 20);
  if (part === 'leak') return around(find(run === 'bike' ? 'casual' : run === 'bank' ? 'previous_campaign_outcome' : 'marital_status'));
  if (part === 'gaps') return around(Math.max(0, cols.findIndex((c) => c.missing > 0)), 40);
  if (part === 'section') { const [sx, sy] = iso(colX(find('hours_per_week')), SY, 60); return [sx - 230, sy - 170, 460, 313]; }
  if (part === 'lift') { const [a] = iso(-20, D * 0.7, 0); const [b] = iso(X, 0, 0); const [, top] = iso(X / 2, D * 0.35, 230); const [, bot] = iso(X, D, 0); return [a - 120, top - 50, b - a + 170, bot - top + 80]; }
  if (part === 'relation') return around(find('casual'), 60);
  const [l] = iso(0, D + 10, 0), [r] = iso(X + 10, 0, 0), [, t] = iso(0, 0, 180), [, b] = iso(X, D, 0);
  return [l - 40, t - 40, r - l + 80, b - t + 90];
}

export function Slab({ run, focus = 'all', lift = false, section = false, split, labels = true }: { run: string; focus?: Part; lift?: boolean; section?: boolean; split?: number; labels?: boolean }) {
  const { columns: cols, rows } = runCols[run];
  const n = cols.length, X = colX(n);
  const sp = split ?? targetSplit[run];
  const hi = (name: string) => {
    if (focus === 'all') return false;
    if (focus === 'target') return cols.find((c) => c.name === name)?.target;
    if (focus === 'leak') return run === 'bike' ? ['casual', 'registered'].includes(name) : run === 'bank' ? name === 'previous_campaign_outcome' : run === 'german' ? ['checking_account_status', 'credit_history', 'credit_amount', 'savings_status', 'personal_status_sex'].includes(name) : name === 'marital_status';
    if (focus === 'gaps') return (cols.find((c) => c.name === name)?.missing ?? 0) > 0;
    if (focus === 'section') return name === 'hours_per_week';
    if (focus === 'relation') return ['casual', 'registered', 'cnt'].includes(name);
    return false;
  };
  const dim = focus !== 'all' && focus !== 'lift' && focus !== 'cap';
  const ti = cols.findIndex((c) => c.target);
  const g = adult.conflicts[0];
  return (
    <g className={`cw-slab ${dim ? 'is-focus' : ''}`}>
      <Prism x={-10} y={-10} w={X + 13} d={D + 20} h={6} z={-6} cls="cw-base" />
      {cols.map((c, i) => {
        const x = colX(i), h = colH(c);
        const m = c.missing / rows;
        const on = hi(c.name);
        if (c.target && sp) {
          const d1 = D * sp;
          return (
            <g key={c.name} className={`cw-col ${on ? 'is-on' : ''}`} style={{ ['--d' as string]: i * 55 } as React.CSSProperties}>
              <Prism x={x} y={0} w={W} d={d1 - 2} h={h} cls="cw-maj" />
              <Prism x={x} y={d1 + 2} w={W} d={D - d1 - 2} h={h} cls="cw-min" />
            </g>
          );
        }
        if (m > 0) {
          const dm = Math.max(3, D * m);
          return (
            <g key={c.name} className={`cw-col ${on ? 'is-on' : ''}`} style={{ ['--d' as string]: i * 55 } as React.CSSProperties}>
              <Prism x={x} y={0} w={W} d={D - dm - 1.5} h={h} />
              <Prism x={x} y={D - dm} w={W} d={dm} h={h} cls="cw-hollow" />
            </g>
          );
        }
        return <g key={c.name} className={`cw-col ${on ? 'is-on' : ''} ${c.target ? 'is-target' : ''}`} style={{ ['--d' as string]: i * 55 } as React.CSSProperties}><Prism x={x} y={0} w={W} d={D} h={h} cls={c.target ? 'cw-tgt' : ''} /></g>;
      })}
      {run === 'bike' && (() => {
        const a = cols.findIndex((c) => c.name === 'casual'), b = cols.findIndex((c) => c.name === 'registered');
        const [ax, ay] = iso(colX(a) + W / 2, 0, colH(cols[a]) + 12), [bx, by] = iso(colX(b) + W / 2, 0, colH(cols[b]) + 12), [tx, ty] = iso(colX(ti) + W / 2, 0, colH(cols[ti]) + 12);
        return <g className={`cw-rel ${focus === 'relation' || focus === 'all' ? 'is-on' : ''}`}><path d={`M${ax} ${ay} L${ax} ${ay - 18} L${tx} ${ty - 18} L${tx} ${ty} M${bx} ${by} L${bx} ${by - 18}`} /><text x={(ax + tx) / 2} y={Math.min(ay, ty) - 24}>cnt = casual + registered · 17,379 / 17,379 rows</text></g>;
      })()}
      {lift && run === 'adult' && g.rows.map((r, k) => {
        const y = D * (r / rows), z = 150 + k * 30;
        return (
          <g key={r} className="cw-lift">
            <Prism x={0} y={y} w={X - G} d={3} h={6} z={z} cls="cw-row" />
            <Prism x={colX(ti)} y={y} w={W} d={3} h={6} z={z} cls={k === 0 ? 'cw-min' : 'cw-maj'} />
            <line {...{ x1: iso(X / 2, y, 0)[0], y1: iso(X / 2, y, 0)[1], x2: iso(X / 2, y, z)[0], y2: iso(X / 2, y, z)[1] }} className="cw-tie" />
            <text {...(() => { const [lx, ly] = iso(-6, y + 3, z + 4); return { x: lx - 4, y: ly + 2 }; })()} className="cw-rowlab" textAnchor="end">row {r.toLocaleString()} · {g.labels[k]}</text>
          </g>
        );
      })}
      {section && run === 'adult' && <Section x={colX(cols.findIndex((c) => c.name === 'hours_per_week'))} />}
      {labels && (() => {
        const L: ReactNode[] = [];
        const top = (i: number, dz = 0) => iso(colX(i) + W / 2, D / 2, colH(cols[i]) + dz);
        if (ti >= 0) L.push(<Label key="t" at={top(ti)} dy={-46} cls={focus === 'target' ? 'is-on' : ''}>{sp ? `TARGET ${(sp * 100).toFixed(2)} / ${(100 - sp * 100).toFixed(2)}` : 'TARGET · REGRESSION'}</Label>);
        const gi = cols.findIndex((c) => c.missing > 0);
        if (gi >= 0) L.push(<Label key="g" at={iso(colX(gi) + W / 2, D, colH(cols[gi]))} dy={-58} cls={focus === 'gaps' ? 'is-on' : ''}>{`GAPS · ${cols.filter((c) => c.missing).length} COLUMNS`}</Label>);
        if (run === 'adult') {
          const hi2 = cols.findIndex((c) => c.name === 'hours_per_week');
          L.push(<Label key="o" at={top(hi2)} dy={-30} cls={focus === 'section' ? 'is-on' : ''}>OUTLIERS 27.63%</Label>);
          const li = cols.findIndex((c) => c.name === 'marital_status');
          L.push(<Label key="l" at={top(li)} dy={-40} cls={focus === 'leak' ? 'is-on' : ''}>REVIEW ONLY</Label>);
        }
        return <g>{L}</g>;
      })()}
    </g>
  );
}

/** hours_per_week pulled out of its strip as a section, drawn in the x–z plane in front of the slab. */
function Section({ x }: { x: number }) {
  const h = adult.hours, c = h.hist.counts, m = Math.max(...c);
  const y = SY, x0 = x - 74, span = 160, bw = span / c.length;
  const xOf = (v: number) => x0 + (v - h.hist.start) * bw;
  const bars = c.map((v, i) => {
    const val = h.hist.start + i, hh = Math.max(0.8, Math.sqrt(v / m) * 92);
    const out = val < h.lower || val > h.upper;
    const xx = x0 + i * bw;
    return <path key={i} d={`M${pt(xx, y, 0)} L${pt(xx + bw * 0.8, y, 0)} L${pt(xx + bw * 0.8, y, hh)} L${pt(xx, y, hh)} Z`} className={out ? 'cw-out' : 'cw-in'} />;
  });
  const fence = (v: number, label: string) => {
    const [a, b] = iso(xOf(v), y, 0), [, t] = iso(xOf(v), y, 108);
    return <g className="cw-fence"><line x1={a} y1={b} x2={a} y2={t} /><text x={a + 3} y={t + 8}>{label}</text></g>;
  };
  const [lx, ly] = iso(x0, y, -14);
  const [ax, ay] = iso(x + W / 2, D, 0), [bx, by] = iso(x + W / 2, y, 0);
  return (
    <g className="cw-section">
      <line x1={ax} y1={ay} x2={bx} y2={by} className="cw-tie" />
      <path d={`M${pt(x0 - 6, y, 0)} L${pt(x0 + span + 6, y, 0)} L${pt(x0 + span + 6, y, 112)} L${pt(x0 - 6, y, 112)} Z`} className="cw-plate" />
      {bars}
      {fence(h.lower, String(h.lower))}
      {fence(h.upper, String(h.upper))}
      <text x={lx} y={ly + 4} className="cw-rowlab">SECTION · hours_per_week · 1 – 99 h · {h.outliers.toLocaleString()} outside</text>
    </g>
  );
}

/** Non-tabular runs are drawn as their own units: records, images, records↔pages. */
export function Units({ run }: { run: string }) {
  const cells: ReactNode[] = [];
  if (run === 'coco') {
    for (let i = 0; i < 128; i++) { const x = (i % 16) * 9, y = Math.floor(i / 16) * 9; cells.push(<Prism key={i} x={x} y={y} w={7} d={7} h={i < 61 ? 3 : 10} cls={i < 61 ? 'cw-hollow' : ''} />); }
    return <g className="cw-slab">{cells}<Label at={iso(0, 0, 10)} dy={-30}>128 IMAGES · 875 OBJECTS · 61 ICC-BEARING EXCLUDED FROM DEFAULT METHODS</Label></g>;
  }
  if (run === 'finance') {
    for (let i = 0; i < 20; i++) cells.push(<Prism key={`r${i}`} x={0} y={i * 7} w={30} d={4} h={8} cls={i === 6 || i === 13 ? 'cw-min' : ''} />);
    for (let i = 0; i < 21; i++) cells.push(<Prism key={`d${i}`} x={70} y={i * 6.6} w={22} d={4} h={20} cls={i === 6 || i === 13 || i === 14 ? 'cw-min' : 'cw-doc'} />);
    return <g className="cw-slab">{cells}<Label at={iso(0, 0, 8)} dy={-30}>20 RECORDS</Label><Label at={iso(70, 0, 20)} dy={-30}>21 PDFs · 18 AGREE · 1 DISCREPANCY · 1 CONFLICT</Label></g>;
  }
  // text: 5,574 records drawn as 60 rows of lines (1 line ≈ 93 records)
  for (let i = 0; i < 60; i++) cells.push(<Prism key={i} x={0} y={i * 3} w={60 + ((i * 37) % 70)} d={1.6} h={2} />);
  return <g className="cw-slab">{cells}<Label at={iso(0, 0, 2)} dy={-30}>5,574 RECORDS · NEAR-DUPLICATE CANDIDATES (MINHASH)</Label></g>;
}

export function slabBounds(run: string) { return partBox(run, 'all'); }
