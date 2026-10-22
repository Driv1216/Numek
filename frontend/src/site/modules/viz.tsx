// One live drawing per module. A single rule runs through all of them:
// what the module found is drawn in full ink; context is drawn as a ghost.
import { useMemo, type ReactElement } from 'react';
import bikeHours from '../content/bike-hours.generated.json';
import { adult, decodeRows } from '../content';
import type { ModId } from './data';

type P = { big?: boolean };
let rowsCache: ReturnType<typeof decodeRows> | null = null;
const rows = () => (rowsCache ??= decodeRows());

function Score({ big }: P) {
  const s = adult.subScores;
  const W = 200, base = 112, bw = 30, gap = 9, x0 = 8;
  return (
    <svg viewBox={`0 0 ${W} 130`} className="md-viz" preserveAspectRatio="xMidYMax meet">
      <line x1={0} x2={W} y1={base} y2={base} className="md-ghost-l" />
      {s.map((d, i) => {
        const hh = d.value; const x = x0 + i * (bw + gap);
        return (
          <g key={d.key} className="md-grow" style={{ ['--i' as string]: i }}>
            <rect x={x} y={base - hh} width={bw} height={hh} className={'critical' in d && d.critical ? 'md-hot' : 'md-ghost'} />
            {big && <text x={x + bw / 2} y={base - hh - 4} className="md-t md-t--c">{d.value}</text>}
            {big && <text x={x + bw / 2} y={base + 11} className="md-t md-t--c md-t--s">{['Compl.', 'Uniq.', 'Balance', 'Usab.', 'Leak.'][i]}</text>}
          </g>
        );
      })}
      <line x1={0} x2={W} y1={base - 69} y2={base - 69} className="md-cap" />
      <line x1={0} x2={W} y1={base - 50} y2={base - 50} className="md-ghost-l" strokeDasharray="1 3" />
      {big && <text x={W} y={base - 72} className="md-t md-t--r">cap 69</text>}
      {big && <text x={W} y={base - 53} className="md-t md-t--r md-t--s">critical ≤ 50</text>}
    </svg>
  );
}

function Gaps({ big }: P) {
  const cols = big ? 64 : 34, rr = big ? 34 : 11, pitch = 6;
  const r = rows();
  const cells = useMemo(() => Array.from({ length: cols * rr }, (_, i) => r.miss[i]), [cols, rr, r]);
  return (
    <svg viewBox={`0 0 ${cols * pitch} ${rr * pitch}`} className="md-viz" preserveAspectRatio="xMidYMax meet">
      {cells.map((m, i) => (
        <circle key={i} cx={(i % cols) * pitch + 3} cy={Math.floor(i / cols) * pitch + 3} r={m ? 2.3 : 1.7} className={m ? 'md-ring' : 'md-ghost'} />
      ))}
    </svg>
  );
}

function Dups({ big }: P) {
  // 49 groups holding 101 rows with 52 repeats and a largest group of 3: 46 pairs and 3 triples.
  const groups = Array.from({ length: 49 }, (_, i) => (i % 16 === 5 ? 3 : 2));
  const cols = big ? 10 : 7, cw = 22, ch = 18;
  return (
    <svg viewBox={`0 0 ${cols * cw} ${Math.ceil(49 / cols) * ch}`} className="md-viz" preserveAspectRatio="xMidYMax meet">
      {groups.map((k, i) => (
        <g key={i} transform={`translate(${(i % cols) * cw + 2} ${Math.floor(i / cols) * ch + 2})`} className={k === 3 ? 'md-hotg' : ''}>
          {Array.from({ length: k }, (_, j) => <rect key={j} x={j * 3} y={j * 3} width={13} height={9} rx={1.5} className={j ? 'md-card' : 'md-card md-card--b'} />)}
        </g>
      ))}
    </svg>
  );
}

function Conflicts({ big }: P) {
  const g = adult.conflicts[0];
  if (big) {
    const keys = Object.keys(g.features);
    return (
      <div className="md-conf">
        <div className="md-conf__h"><span>row {g.rows[0].toLocaleString()}</span><span>row {g.rows[1].toLocaleString()}</span></div>
        {keys.map((k) => (
          <div key={k} className="md-conf__r"><span>{k}</span><b>{String(g.features[k])}</b><b>{String(g.features[k])}</b></div>
        ))}
        <div className="md-conf__r is-hot"><span>annual_income_over_50k</span><b>{g.labels[0]}</b><b>{g.labels[1]}</b></div>
      </div>
    );
  }
  return (
    <svg viewBox="0 0 120 150" className="md-viz" preserveAspectRatio="xMidYMax meet">
      {[0, 1].map((r) => (
        <g key={r} transform={`translate(${r * 62 + 4} 4)`}>
          {Array.from({ length: 14 }, (_, i) => <rect key={i} x={0} y={i * 8.6} width={50} height={6} rx={1.5} className="md-ghost" />)}
          <rect x={0} y={14 * 8.6 + 4} width={50} height={14} rx={2} className={r ? 'md-ring' : 'md-ink'} />
        </g>
      ))}
    </svg>
  );
}

function Imbalance({ big }: P) {
  const maj = Math.round(adult.majorityBaseline);
  const cols = 10, n = 100, s = 8;
  return (
    <svg viewBox={`0 0 ${cols * s} ${10 * s + (big ? 14 : 0)}`} className="md-viz" preserveAspectRatio="xMidYMax meet">
      {Array.from({ length: n }, (_, i) => (
        <rect key={i} x={(i % cols) * s + 1} y={Math.floor(i / cols) * s + 1} width={s - 2} height={s - 2} rx={1} className={i < maj ? 'md-ink' : 'md-ring'} />
      ))}
      {big && <text x={0} y={10 * s + 10} className="md-t md-t--s">each square ≈ 1% · filled ≤50K · open &gt;50K</text>}
    </svg>
  );
}

function Leakage({ big }: P) {
  const cols = adult.header;
  if (big) {
    return (
      <ul className="md-leak">
        {cols.map((c) => (
          <li key={c} className={c === 'marital_status' ? 'is-hot' : c === adult.target ? 'is-target' : ''}>
            <span>{c}</span>{c === 'marital_status' && <em>review only</em>}{c === adult.target && <em>target</em>}
          </li>
        ))}
      </ul>
    );
  }
  return (
    <svg viewBox="0 0 120 120" className="md-viz" preserveAspectRatio="xMidYMax meet">
      {cols.map((c, i) => (
        <rect key={c} x={4} y={4 + i * 7.6} width={c.length * 4.2} height={4.4} rx={1.5} className={c === 'marital_status' ? 'md-hot' : 'md-ghost'} />
      ))}
    </svg>
  );
}

function Outliers({ big }: P) {
  const h = adult.hours; const c = h.hist.counts; const max = Math.max(...c);
  const W = 196, H = big ? 120 : 110, bw = W / c.length;
  const xOf = (v: number) => (v - h.hist.start) * bw;
  return (
    <svg viewBox={`0 0 ${W} ${H + (big ? 14 : 2)}`} className="md-viz" preserveAspectRatio="xMidYMax meet">
      {c.map((v, i) => {
        const val = h.hist.start + i; const out = val < h.lower || val > h.upper;
        const hh = Math.max(0.6, Math.sqrt(v / max) * H);
        return <rect key={i} x={i * bw + 0.15} y={H - hh} width={bw - 0.3} height={hh} className={`md-grow ${out ? 'md-ink' : 'md-ghost'}`} style={{ ['--i' as string]: i / 8 }} />;
      })}
      <line x1={xOf(h.lower)} x2={xOf(h.lower)} y1={0} y2={H} className="md-cap" />
      <line x1={xOf(h.upper)} x2={xOf(h.upper)} y1={0} y2={H} className="md-cap" />
      {big && <>
        <text x={xOf(h.lower) - 3} y={10} className="md-t md-t--r">{h.lower}</text>
        <text x={xOf(h.upper) + 3} y={10} className="md-t">{h.upper}</text>
        {[1, 40, 99].map((v) => <text key={v} x={xOf(v) + bw / 2} y={H + 11} className="md-t md-t--c md-t--s">{v}h</text>)}
      </>}
    </svg>
  );
}

function Relations({ big }: P) {
  const hs = bikeHours.hours as { t: string; casual: number; registered: number; cnt: number }[];
  const max = Math.max(...hs.map((d) => d.cnt));
  const W = 196, H = big ? 120 : 110, bw = W / hs.length;
  return (
    <svg viewBox={`0 0 ${W} ${H + (big ? 14 : 2)}`} className="md-viz" preserveAspectRatio="xMidYMax meet">
      {hs.map((d, i) => {
        const rh = (d.registered / max) * H, ch = (d.casual / max) * H;
        return (
          <g key={d.t} className="md-grow" style={{ ['--i' as string]: i / 6 }}>
            <rect x={i * bw + 0.5} y={H - rh} width={bw - 1} height={rh} className="md-ghost" />
            <rect x={i * bw + 0.5} y={H - rh - ch} width={bw - 1} height={ch} className="md-ink" />
          </g>
        );
      })}
      {big && <>
        <text x={0} y={H + 11} className="md-t md-t--s">{hs[0].t.slice(0, 10)}</text>
        <text x={W} y={H + 11} className="md-t md-t--r md-t--s">{hs[hs.length - 1].t.slice(0, 10)}</text>
      </>}
    </svg>
  );
}

function Time({ big }: P) {
  const ev = [12, 34, 52, 71, 96, 118, 140, 166];
  const cut = 104;
  return (
    <svg viewBox="0 0 180 90" className="md-viz" preserveAspectRatio="xMidYMax meet">
      <line x1={4} x2={176} y1={60} y2={60} className="md-ghost-l" />
      {ev.map((x, i) => <circle key={x} cx={x} cy={60} r={4} className={x < cut ? 'md-ink' : 'md-ring'} style={{ ['--i' as string]: i }} />)}
      <line x1={cut} x2={cut} y1={14} y2={76} className="md-cap" />
      <text x={cut + 4} y={22} className="md-t">{big ? 'prediction time' : 't₀'}</text>
      {big && <text x={4} y={84} className="md-t md-t--s">schematic · declared availability per feature</text>}
    </svg>
  );
}

function Text({ big }: P) {
  const w = [150, 118, 136, 92, 160, 104, 136, 128, 70];
  return (
    <svg viewBox="0 0 180 120" className="md-viz" preserveAspectRatio="xMidYMax meet">
      {w.map((ww, i) => <rect key={i} x={14} y={6 + i * 12.4} width={ww} height={6} rx={3} className={i === 2 || i === 6 ? 'md-ink' : 'md-ghost'} />)}
      <path d={`M10 9 h-5 v${4 * 12.4} h5`} className="md-brk" transform="translate(0 24.8)" />
      {big && <text x={176} y={118} className="md-t md-t--r md-t--s">schematic · not SMS content</text>}
    </svg>
  );
}

function Images({ big }: P) {
  const cols = 16, s = big ? 10 : 6;
  return (
    <svg viewBox={`0 0 ${cols * s} ${Math.ceil(128 / cols) * s}`} className="md-viz" preserveAspectRatio="xMidYMax meet">
      {Array.from({ length: 128 }, (_, i) => (
        <rect key={i} x={(i % cols) * s + 0.8} y={Math.floor(i / cols) * s + 0.8} width={s - 1.6} height={s - 1.6} rx={0.8} className={i < 61 ? 'md-ring' : 'md-ghost'} />
      ))}
    </svg>
  );
}

function Docs({ big }: P) {
  // 20 records, each joined to its document(s): 18 agree, record 7 disagrees, record 14 has two documents that conflict.
  const cols = big ? 4 : 10, cw = big ? 48 : 30, ch = big ? 30 : 22;
  return (
    <svg viewBox={`0 0 ${cols * cw} ${Math.ceil(20 / cols) * ch}`} className="md-viz" preserveAspectRatio="xMidYMax meet">
      {Array.from({ length: 20 }, (_, i) => {
        const k = i === 6 ? 'diff' : i === 13 ? 'conf' : 'ok';
        const x = (i % cols) * cw + 4, y = Math.floor(i / cols) * ch + ch / 2;
        const cls = k === 'ok' ? 'md-ghost' : 'md-ink';
        return (
          <g key={i}>
            <circle cx={x + 3} cy={y} r={3} className={cls} />
            {k === 'conf' ? <>
              <path d={`M${x + 6} ${y} C${x + 11} ${y} ${x + 11} ${y - 5} ${x + 15} ${y - 5} M${x + 6} ${y} C${x + 11} ${y} ${x + 11} ${y + 5} ${x + 15} ${y + 5}`} className="md-arc" style={{ strokeWidth: 1.1 }} />
              <rect x={x + 15} y={y - 8} width={7} height={5} rx={1} className="md-ink" />
              <rect x={x + 15} y={y + 3} width={7} height={5} rx={1} className="md-ring" />
            </> : <>
              <line x1={x + 6} x2={x + 15} y1={y} y2={y} className={k === 'ok' ? 'md-ghost-l' : 'md-cap'} />
              <rect x={x + 15} y={y - 3.5} width={7} height={7} rx={1} className={k === 'ok' ? 'md-ghost' : 'md-ring'} />
            </>}
            {big && k !== 'ok' && <text x={x + 25} y={y + 2.5} className="md-t md-t--s">{k === 'diff' ? '≠ discrepancy' : 'conflict'}</text>}
          </g>
        );
      })}
    </svg>
  );
}

function Local({ big }: P) {
  return (
    <svg viewBox="0 0 120 120" className="md-viz" preserveAspectRatio="xMidYMax meet">
      <circle cx={60} cy={62} r={34} className="md-ghost-l md-spin" strokeDasharray="4 5" />
      <circle cx={60} cy={62} r={6} className="md-ink" />
      <path d="M60 28 a34 34 0 0 1 29 17" className="md-arc" />
      <path d="M86 40 l3 6 l-6 0" className="md-ink" />
      {big && <text x={60} y={112} className="md-t md-t--c">127.0.0.1 → 127.0.0.1</text>}
    </svg>
  );
}

function Reports({ big }: P) {
  const names = ['HTML', 'PDF', 'JSON'];
  return (
    <svg viewBox="0 0 180 110" className="md-viz" preserveAspectRatio="xMidYMax meet">
      {names.map((n, i) => (
        <g key={n} transform={`translate(${8 + i * 58} ${8 + i * 4})`} className="md-grow" style={{ ['--i' as string]: i }}>
          <rect x={4} y={4} width={46} height={64} rx={2} className="md-ghost" />
          <rect x={0} y={0} width={46} height={64} rx={2} className="md-page" />
          {Array.from({ length: 7 }, (_, j) => <rect key={j} x={6} y={10 + j * 7} width={j % 3 === 2 ? 22 : 34} height={2.6} rx={1} className="md-ghost" />)}
          <text x={0} y={80} className="md-t">{n}</text>
        </g>
      ))}
      {big && <text x={8} y={106} className="md-t md-t--s">one evidence model · eight topics</text>}
    </svg>
  );
}

const table: Record<ModId, (p: P) => ReactElement> = {
  score: Score, gaps: Gaps, dups: Dups, conflicts: Conflicts, imbalance: Imbalance, leakage: Leakage, outliers: Outliers,
  relations: Relations, time: Time, text: Text, images: Images, docs: Docs, local: Local, reports: Reports,
};

export function Viz({ id, big }: { id: ModId; big?: boolean }) {
  const C = table[id];
  return <C big={big} />;
}
