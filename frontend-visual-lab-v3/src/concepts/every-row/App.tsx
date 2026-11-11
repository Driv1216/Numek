import '@fontsource-variable/schibsted-grotesk';
import '@fontsource-variable/source-serif-4';
import './every-row.css';
import { useEffect, useRef, useState } from 'react';
import { runFindings, runs } from '../../fixture';
import { fmt } from '../../shell/motion';
import { href } from '../../shell/router';
import { Wordmark } from './chrome';
import { UnitField, type Label, type Layout } from './field';
import { C, D } from './layouts';

// Units per run: rows, records, images or record+document pairs.
const units: Record<string, { n: number; unit: string }> = {
  adult: { n: 48842, unit: 'rows' }, bank: { n: 45211, unit: 'rows' }, german: { n: 1000, unit: 'rows' }, bike: { n: 17379, unit: 'hourly rows' },
  sms: { n: 5574, unit: 'records' }, coco: { n: 128, unit: 'images' }, finance: { n: 41, unit: 'records + documents' },
};
const order = ['adult', 'bank', 'bike', 'sms', 'german', 'coco', 'finance'];
const TOTAL = order.reduce((s, id) => s + units[id].n, 0);

const GAP = 26;
const BIG = ['adult', 'bank', 'bike', 'sms'];
const STACK = ['german', 'coco', 'finance'];
const STACK_W = 230;
/** Pitch 2 px, one mark per unit. Large runs are blocks; small runs stack in the last column. */
export function bandGeometry(w: number) {
  if (w < 700) {
    // Phones: blocks stack vertically at 1 px pitch, still one mark per unit.
    const cols = Math.floor(w - 32);
    const h = order.reduce((s, id) => s + Math.ceil(units[id].n / cols) + 44, 16);
    return { top: 16, left: 16, p: 1, rows: 0, cols, height: h + 20, narrow: true };
  }
  const top = 16, left = 24, right = 24, p = 2;
  const colsAvail = Math.floor((w - left - right - BIG.length * GAP - STACK_W) / p) - BIG.length;
  const rows = Math.max(110, Math.ceil(BIG.reduce((s, id) => s + units[id].n, 0) / Math.max(1, colsAvail)));
  return { top, left, p, rows, cols: 0, height: top + rows * p + 62, narrow: false };
}

function bandLayout(w: number, h: number, hot: string | null): Layout {
  const L: Layout = { pos: new Float32Array(TOTAL * 2), color: new Float32Array(TOTAL * 4), size: new Float32Array(TOTAL), labels: [] };
  const geo = bandGeometry(w);
  const { top, left, p, rows } = geo;
  void h;
  const start: Record<string, number> = {};
  order.reduce((k, id) => ((start[id] = k), k + units[id].n), 0);
  const colour = (id: string, j: number) => {
    if (hot && hot !== id) return C.ghost;
    if (id !== 'adult') return C.ink;
    return D.conflict[j] || D.dup[j] ? C.mag : D.miss[j] ? C.amber : D.hoursOut[j] ? C.violet : C.ink;
  };
  if (geo.narrow) {
    let y = top;
    for (const id of order) {
      const n = units[id].n, cc = n < 200 ? 30 : geo.cols, pitch = n < 200 ? 6 : 1, size = n < 200 ? 4 : 1;
      L.labels.push({ x: left, y: y + 12, text: runs.find((r) => r.id === id)!.name, sub: `${fmt(n)} ${units[id].unit}` });
      y += 34;
      for (let j = 0; j < n; j++) {
        const k = start[id] + j;
        L.pos[k * 2] = left + (j % cc) * pitch + pitch / 2; L.pos[k * 2 + 1] = y + Math.floor(j / cc) * pitch + pitch / 2;
        L.color.set(colour(id, j), k * 4); L.size[k] = size;
      }
      y += Math.ceil(n / cc) * pitch + 10;
    }
    return L;
  }
  let x = left;
  for (const id of BIG) {
    const n = units[id].n, cols = Math.ceil(n / rows);
    for (let j = 0; j < n; j++) {
      const k = start[id] + j;
      L.pos[k * 2] = x + Math.floor(j / rows) * p + p / 2; // column-major: blocks fill top to bottom
      L.pos[k * 2 + 1] = top + (j % rows) * p + p / 2;
      L.color.set(colour(id, j), k * 4); L.size[k] = p - 1;
    }
    L.labels.push({ x, y: top + rows * p + 22, text: runs.find((r) => r.id === id)!.name, sub: `${fmt(n)} ${units[id].unit}` });
    x += cols * p + GAP;
  }
  let y = top;
  for (const id of STACK) {
    const n = units[id].n;
    const pitch = n >= 200 ? p : 6, size = n >= 200 ? p - 1 : 4, cc = n >= 200 ? 40 : 14;
    for (let j = 0; j < n; j++) {
      const k = start[id] + j;
      L.pos[k * 2] = x + (j % cc) * pitch + pitch / 2;
      L.pos[k * 2 + 1] = y + Math.floor(j / cc) * pitch + pitch / 2;
      L.color.set(colour(id, j), k * 4); L.size[k] = size;
    }
    const bh = Math.ceil(n / cc) * pitch;
    L.labels.push({ x: x + 94, y: y + 2, text: runs.find((r) => r.id === id)!.name, sub: `${fmt(n)} ${units[id].unit}` });
    y += Math.max(bh, 34) + 16;
  }
  return L;
}

export default function App() {
  const canvas = useRef<HTMLCanvasElement>(null);
  const field = useRef<UnitField | null>(null);
  const [labels, setLabels] = useState<Label[]>([]);
  const [hot, setHot] = useState<string | null>(null);
  const [bandH, setBandH] = useState(420);

  useEffect(() => {
    const d = new Float32Array(TOTAL).map((_, i) => i / TOTAL);
    const f = new UnitField(canvas.current!, TOTAL, d);
    if (!f.ok) return;
    field.current = f;
    const apply = () => {
      const w = canvas.current!.getBoundingClientRect().width;
      const g = bandGeometry(w);
      canvas.current!.style.height = `${g.height}px`; setBandH(g.height);
      const r = f.resize(); const L = bandLayout(r.w, r.h, null); setLabels(L.labels); f.set(L, false);
    };
    apply();
    const ro = new ResizeObserver(apply); ro.observe(canvas.current!);
    return () => { ro.disconnect(); f.dispose(); };
  }, []);
  useEffect(() => {
    const f = field.current; if (!f) return;
    const r = canvas.current!.getBoundingClientRect();
    f.set(bandLayout(r.width, r.height, hot), true);
  }, [hot]);

  const open = (id: string) => { location.hash = id === 'adult' ? href('every-row', 'results') : href('every-row', 'app'); };
  const evidence = Object.entries(runFindings).flatMap(([id, fs]) => fs.filter((f) => f.severity !== 'Low').map((f) => ({ id, ...f }))).slice(0, 8);

  return (
    <div className="er er--app">
      <header className="er-appbar">
        <Wordmark />
        <nav aria-label="Workspace">
          <a aria-current="page" href={href('every-row', 'app')}>Runs</a>
          <a href={href('every-row', 'results')}>Adult</a>
          <a href={href('every-row', 'app')}>Methodology</a>
        </nav>
        <div className="er-appbar__r"><span><i className="er-dot" />Local · 127.0.0.1</span><a className="er-btn er-btn--s" href={href('every-row', 'results')}>New analysis</a></div>
      </header>
      <div className="er-band__head">
        <h1>{fmt(TOTAL)} units across 7 local runs</h1>
        <p>Every record, image and document analysed on this machine, one mark each. Coloured marks in Adult carry evidence; hover a run to isolate it.</p>
      </div>
      <section className="er-band" style={{ height: bandH }} onMouseLeave={() => setHot(null)}>
        <canvas ref={canvas} role="img" aria-label={`${TOTAL} units across seven runs, grouped by run.`} />
        <div className="er-band__keys">
          {labels.map((l) => (
            <div key={l.text} className="er-band__key" style={{ left: l.x, top: l.y - 10 }}><b>{l.text}</b><span>{l.sub}</span></div>
          ))}
        </div>
      </section>
      <div className="er-home">
        <section className="er-runs">
          <h2>Runs on this machine</h2>
          <table className="er-table">
            <thead><tr><th>Dataset</th><th>Task</th><th>Units</th><th>Result</th><th>Lead evidence</th><th>Run</th></tr></thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id} className={hot === r.id ? 'is-hot' : ''} onMouseEnter={() => setHot(r.id)} onFocus={() => setHot(r.id)} onClick={() => open(r.id)} tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && open(r.id)}>
                  <td className="name"><b>{r.name}</b><span>{r.file}</span></td>
                  <td>{r.task}</td>
                  <td>{fmt(units[r.id].n)}</td>
                  <td>{r.score == null ? <span className="er-score er-score--none">No score defined</span> : <span className="er-score">{r.score.toFixed(1)}<small>{r.band}</small></span>}</td>
                  <td className="lead">{r.lead}</td>
                  <td>{r.when}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
        <aside className="er-side">
          <h2>Evidence across runs</h2>
          <ul className="er-ev">
            {evidence.map((e, i) => (
              <li key={i}><i style={{ background: e.severity === 'High' ? 'var(--mag)' : 'var(--amber)' }} /><span>{e.title}<small>{runs.find((r) => r.id === e.id)!.name} · {e.severity} · {e.effect === 'none-defined' ? 'no score defined' : e.effect === 'evidence' ? 'evidence only' : 'affects score'}</small></span></li>
            ))}
          </ul>
          <div className="er-new"><b>Analyse a new dataset</b>CSV, JSONL, Parquet, image folders and record-document manifests are validated and previewed before anything runs. Nothing is uploaded.</div>
        </aside>
      </div>
    </div>
  );
}
