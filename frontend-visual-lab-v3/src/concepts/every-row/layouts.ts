import { adult, decodeRows } from '../../fixture';
import { fmt } from '../../shell/motion';
import type { Layout } from './field';

export const D = decodeRows();
export const N = D.n;

const hex = (h: string, a = 1): [number, number, number, number] => [parseInt(h.slice(1, 3), 16) / 255, parseInt(h.slice(3, 5), 16) / 255, parseInt(h.slice(5, 7), 16) / 255, a];
export const C = {
  ink: hex('#1A1A1A', 0.82), slate: hex('#8F98A1'), teal: hex('#0F7C74'), mag: hex('#C2185B'), amber: hex('#D98E04'), violet: hex('#5B4BC4'),
  fade: hex('#8F98A1', 0.22), ghost: hex('#8F98A1', 0.2), slateSoft: hex('#8F98A1', 0.38), tealSoft: hex('#0F7C74', 0.32),
};

export type Arrangement = 'population' | 'target' | 'missing' | 'duplicates' | 'conflicts' | 'outliers' | 'accounted';
export const arrangements: { id: Arrangement; label: string; count: string }[] = [
  { id: 'population', label: 'Population', count: fmt(N) },
  { id: 'target', label: 'Target', count: '76.07%' },
  { id: 'missing', label: 'Missingness', count: '3,620' },
  { id: 'duplicates', label: 'Duplicates', count: '49' },
  { id: 'conflicts', label: 'Conflicts', count: '5' },
  { id: 'outliers', label: 'Outliers', count: '13,496' },
  { id: 'accounted', label: 'All evidence', count: '' },
];

export interface Rect { x: number; y: number; w: number; h: number }

/** Stable, deterministic stagger: sweep in source order with a little jitter. */
export function delays() {
  const d = new Float32Array(N);
  let s = 7;
  for (let i = 0; i < N; i++) { s = (s * 16807) % 2147483647; d[i] = (i / N) * 0.78 + (s / 2147483647) * 0.22; }
  return d;
}

function blank(): Layout {
  return { pos: new Float32Array(N * 2), color: new Float32Array(N * 4), size: new Float32Array(N), labels: [] };
}
const put = (L: Layout, i: number, x: number, y: number, c: number[], s: number) => {
  L.pos[i * 2] = x; L.pos[i * 2 + 1] = y;
  L.color[i * 4] = c[0]; L.color[i * 4 + 1] = c[1]; L.color[i * 4 + 2] = c[2]; L.color[i * 4 + 3] = c[3];
  L.size[i] = s;
};

// Integer pitch keeps every mark on the pixel grid (no moiré at small sizes).
const pitchFor = (n: number, r: Rect, fill = 0.92) => Math.max(2, Math.floor(Math.sqrt((r.w * r.h * fill) / n)));
const markSize = (p: number) => (p <= 3 ? p - 1 : Math.round(p * 0.78));

/** Row-major waffle: returns the block's bottom edge. */
function waffle(L: Layout, idx: ArrayLike<number>, x: number, y: number, cols: number, p: number, color: (i: number) => number[], size: number) {
  for (let k = 0; k < idx.length; k++) {
    const i = idx[k];
    put(L, i, Math.round(x) + (k % cols) * p + p / 2, Math.round(y) + Math.floor(k / cols) * p + p / 2, color(i), size);
  }
  return y + Math.ceil(idx.length / cols) * p;
}

const range = (pred: (i: number) => boolean) => { const a: number[] = []; for (let i = 0; i < N; i++) if (pred(i)) a.push(i); return a; };
const ALL = range(() => true);

function population(r: Rect, color: (i: number) => number[]) {
  const L = blank();
  const p = pitchFor(N, r);
  const cols = Math.floor(r.w / p);
  const rows = Math.ceil(N / cols);
  const y0 = r.y + (r.h - rows * p) / 2;
  const x0 = r.x + (r.w - cols * p) / 2;
  waffle(L, ALL, x0, y0, cols, p, color, markSize(p));
  return { L, p, x0, y0, cols, rows };
}

/** Lay several groups side by side as blocks of equal height (a stacked waffle). */
function blocks(L: Layout, groups: { idx: number[]; color: (i: number) => number[]; label: string; sub: string; tone?: string }[], r: Rect, gapCols = 6) {
  const total = groups.reduce((s, g) => s + g.idx.length, 0);
  const p = pitchFor(total, { ...r, w: r.w - gapCols * (groups.length - 1) * 3 }, 0.86);
  const usable = Math.floor(r.w / p) - gapCols * (groups.length - 1);
  const rows = Math.ceil(total / usable);
  const y0 = r.y + Math.max(28, (r.h - rows * p) / 2);
  let x = r.x;
  const widths = groups.map((g) => Math.max(1, Math.ceil(g.idx.length / rows)));
  const usedW = (widths.reduce((s, w) => s + w, 0) + gapCols * (groups.length - 1)) * p;
  x += (r.w - usedW) / 2;
  groups.forEach((g, k) => {
    waffle(L, g.idx, x, y0, widths[k], p, g.color, markSize(p));
    L.labels.push({ x, y: y0 - 10, text: g.label, sub: g.sub, tone: g.tone });
    x += (widths[k] + gapCols) * p;
  });
  return p;
}

const byClass = (i: number) => (D.cls[i] ? C.teal : C.slate);

export function build(a: Arrangement, r: Rect): Layout {
  if (a === 'population') return population(r, () => C.ink).L;
  if (a === 'accounted') {
    const { L, p } = population(r, (i) => (D.conflict[i] ? C.mag : D.dup[i] ? C.mag : D.miss[i] ? C.amber : D.hoursOut[i] ? C.violet : D.cls[i] ? C.tealSoft : C.slateSoft));
    for (let i = 0; i < N; i++) if (D.conflict[i] || D.dup[i]) L.size[i] = Math.max(4, p * 2);
    return L;
  }
  if (a === 'target') {
    const L = blank();
    blocks(L, [
      { idx: range((i) => !D.cls[i]), color: () => C.slate, label: '≤50K', sub: `${fmt(adult.classes.le50k)} rows · 76.07% · the majority baseline` },
      { idx: range((i) => !!D.cls[i]), color: () => C.teal, label: '>50K', sub: `${fmt(adult.classes.gt50k)} rows · 23.93%`, tone: 'teal' },
    ], r, 5);
    return L;
  }
  if (a === 'missing') {
    const L = blank();
    const p = pitchFor(N, r, 0.9);
    const left: Rect = { x: r.x, y: r.y + 30, w: r.w * 0.6, h: r.h - 30 };
    const lc = Math.floor(left.w / p);
    waffle(L, range((i) => !D.miss[i]), left.x, left.y, lc, p, () => C.fade, markSize(p));
    L.labels.push({ x: left.x, y: left.y - 8, text: 'Complete rows', sub: `${fmt(N - 3620)}` });
    const rx = r.x + r.w * 0.66, rc = Math.floor((r.w * 0.34) / p);
    let y = left.y;
    ([[1, '1 missing feature', '821 rows'], [2, '2 missing features', '2,753 rows'], [3, '3 or more', '46 rows']] as const).forEach(([m, t, sub]) => {
      L.labels.push({ x: rx, y: y + 30, text: t, sub, tone: 'amber' });
      y = waffle(L, range((i) => D.miss[i] === m), rx, y + 36, rc, p, () => C.amber, markSize(p)) + 30;
    });
    return L;
  }
  if (a === 'outliers') {
    const L = blank();
    blocks(L, [
      { idx: range((i) => D.hours[i] < adult.hours.lower), color: () => C.violet, label: '< 32.5 h', sub: `${fmt(adult.hours.below)} rows`, tone: 'violet' },
      { idx: range((i) => D.hours[i] >= adult.hours.lower && D.hours[i] <= adult.hours.upper), color: () => C.fade, label: '32.5 – 52.5 h · inside the IQR fences', sub: `${fmt(N - adult.hours.outliers)} rows` },
      { idx: range((i) => D.hours[i] > adult.hours.upper), color: () => C.violet, label: '> 52.5 h', sub: `${fmt(adult.hours.above)} rows`, tone: 'violet' },
    ], r, 4);
    return L;
  }
  // duplicates and conflicts keep everyone else in place as context
  // Narrow screens stack the context above the evidence instead of beside it.
  const narrow = r.w < 600;
  const { L, p, x0, y0, cols, rows } = population(narrow ? { ...r, y: r.y + 24, h: r.h * 0.34 } : { ...r, w: r.w * 0.58 }, () => C.ghost);
  const right: Rect = narrow ? { x: r.x, y: r.y + r.h * 0.4, w: r.w, h: r.h * 0.6 } : { x: r.x + r.w * 0.62, y: r.y, w: r.w * 0.38, h: r.h };
  if (a === 'duplicates') {
    const groups = new Map<number, number[]>();
    for (let i = 0; i < N; i++) if (D.dupGroup[i]) groups.set(D.dupGroup[i], [...(groups.get(D.dupGroup[i]) ?? []), i]);
    const per = 7;
    const cell = Math.min(right.w / per, (right.h - 60) / 7);
    const s = Math.max(4, cell / 4.2);
    [...groups.values()].forEach((g, k) => {
      const cx = right.x + (k % per) * cell + cell * 0.2, cy = right.y + 40 + Math.floor(k / per) * cell + cell * 0.25;
      g.forEach((i, j) => put(L, i, cx + j * s * 1.25, cy, C.mag, s));
    });
    L.labels.push({ x: right.x, y: right.y + 18, text: '49 exact duplicate groups', sub: '101 rows · 52 repeated · largest group 3', tone: 'mag' });
    L.labels.push({ x: x0, y: y0 - 10, text: 'Every other row, in place', sub: `${fmt(N - 101)} rows` });
    void rows; void cols; void p;
    return L;
  }
  // conflicts: five pairs, enlarged, coloured by their disagreeing labels
  const s = Math.min(34, right.w / 9);
  adult.conflicts.forEach((g, k) => {
    const y = right.y + 60 + k * (s * 2.2 + 16);
    g.rows.forEach((row, j) => {
      const i = row - 1;
      put(L, i, right.x + s / 2 + j * (s + 6), y + s / 2, D.cls[i] ? C.teal : C.slate, s);
    });
    L.labels.push({ x: right.x + 2 * s + 22, y: y + s * 0.35, text: `Group ${g.id} · rows ${g.rows.join(' & ')}`, sub: `age ${g.features.age} · ${g.features.education} · ${g.features.occupation ?? '?'}`, tone: 'mag' });
  });
  L.labels.push({ x: right.x, y: right.y + 26, text: '5 groups whose labels disagree', sub: 'identical in all 14 features · 10 rows', tone: 'mag' });
  L.labels.push({ x: x0, y: y0 - 10, text: 'The other 48,832 rows', sub: 'shown as context' });
  return L;
}

export { byClass };
