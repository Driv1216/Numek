import '@fontsource/ibm-plex-sans/300.css';
import '@fontsource/ibm-plex-sans/400.css';
import '@fontsource/ibm-plex-sans/500.css';
import '@fontsource/ibm-plex-mono/400.css';
import './cutaway.css';
import { useEffect, useRef, useState } from 'react';
import { reducedMotion } from '../../shell/motion';
import { href } from '../../shell/router';
import { Header } from './Landing';
import { Slab, Units, partBox, type Part } from './iso';
import { runFindings, runs, subScoresByRun, tabular } from './model';

/** Which part of the drawing each finding points at. */
const partOf = (title: string): Part =>
  /imbalance/i.test(title) ? 'target' : /conflicting/i.test(title) ? 'lift' : /outlier|IQR/i.test(title) ? 'section'
    : /leakage|unavailable/i.test(title) ? 'leak' : /relationship/i.test(title) ? 'relation' : 'all';

const fmtBox = (b: number[]) => b.map((v) => v.toFixed(1)).join(' ');

export default function App() {
  const [run, setRun] = useState('adult');
  const [sel, setSel] = useState(-1);
  const r = runs.find((x) => x.id === run)!;
  const f = runFindings[run] ?? [];
  const isTab = tabular.includes(run);
  const part = sel >= 0 ? partOf(f[sel].title) : 'all';
  const target = isTab ? partBox(run, run === 'adult' ? part : part === 'section' || part === 'lift' ? 'all' : part) : [-90, -100, 340, 240];

  // The view box eases to the part in focus; dragging pans it, the buttons zoom it.
  const svg = useRef<SVGSVGElement>(null);
  const view = useRef<number[]>(target);
  useEffect(() => {
    const from = [...view.current], to = target;
    if (reducedMotion()) { view.current = to; svg.current?.setAttribute('viewBox', fmtBox(to)); return; }
    const t0 = performance.now(); let raf = 0;
    const tick = (t: number) => {
      const k = Math.min(1, (t - t0) / 650), e = 1 - Math.pow(1 - k, 3);
      view.current = from.map((v, i) => v + (to[i] - v) * e);
      svg.current?.setAttribute('viewBox', fmtBox(view.current));
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run, sel]);

  const drag = useRef<{ x: number; y: number; v: number[] } | null>(null);
  const onDown = (e: React.PointerEvent) => { (e.target as Element).setPointerCapture?.(e.pointerId); drag.current = { x: e.clientX, y: e.clientY, v: [...view.current] }; };
  const onMove = (e: React.PointerEvent) => {
    const d = drag.current, s = svg.current; if (!d || !s) return;
    const scale = d.v[2] / s.clientWidth;
    view.current = [d.v[0] - (e.clientX - d.x) * scale, d.v[1] - (e.clientY - d.y) * scale, d.v[2], d.v[3]];
    s.setAttribute('viewBox', fmtBox(view.current));
  };
  const zoom = (k: number) => {
    const [x, y, w, h] = view.current;
    view.current = [x + (w - w * k) / 2, y + (h - h * k) / 2, w * k, h * k];
    svg.current?.setAttribute('viewBox', fmtBox(view.current));
  };
  const subs = subScoresByRun[run];

  return (
    <div className="cw cw--app">
      <Header here="app" />
      <div className="cw-ws">
        <nav className="cw-runs" aria-label="Local runs">
          <p>LOCAL RUNS · {runs.length}</p>
          {runs.map((x) => (
            <button key={x.id} type="button" className={x.id === run ? 'is-on' : ''} aria-pressed={x.id === run} onClick={() => { setRun(x.id); setSel(-1); }}>
              <b>{x.name}</b>
              <span>{x.size}</span>
              <span>{x.score == null ? 'no score defined' : `${x.score.toFixed(1)} · ${x.band}`}</span>
            </button>
          ))}
        </nav>
        <div className="cw-canvas" onPointerDown={onDown} onPointerMove={onMove} onPointerUp={() => (drag.current = null)} onPointerCancel={() => (drag.current = null)}>
          <div className="cw-canvas__h"><h1>{r.name}</h1><span>{r.file} · {r.task} · drag to pan</span></div>
          <svg ref={svg} viewBox={fmtBox(target)} role="img" aria-label={`Cutaway of ${r.name}`}>
            {isTab ? <Slab run={run} focus={part} lift={run === 'adult' && part === 'lift'} section={run === 'adult' && part === 'section'} /> : <Units run={run} />}
          </svg>
          <div className="cw-canvas__ctl"><button type="button" aria-label="Zoom in" onClick={() => zoom(0.8)}>+</button><button type="button" aria-label="Zoom out" onClick={() => zoom(1.25)}>−</button><button type="button" aria-label="Reset view" onClick={() => setSel((s) => (s === -1 ? -2 : -1))}>⟲</button></div>
        </div>
        <aside className="cw-side" aria-label="Findings">
          <h2>FINDINGS · {f.length || '—'}</h2>
          {f.length === 0 && <p className="cw-dim">{r.lead}. DataTrust reports this run by its own units; no universal score is defined.</p>}
          {f.map((x, i) => (
            <button key={x.title} type="button" className={`cw-fnd ${i === sel ? 'is-on' : ''}`} aria-pressed={i === sel} onClick={() => setSel(i === sel ? -1 : i)}>
              <span className={x.severity === 'High' ? 'is-red' : ''}>{x.severity} · {x.effect === 'score' ? 'changes a sub-score' : x.effect === 'evidence' ? 'evidence only' : 'no score defined'}</span>
              <b>{x.title}</b>
              <p>{x.evidence}</p>
            </button>
          ))}
          {subs && (
            <div className="cw-calc" aria-label="Score calculation">
              {subs.map((s) => <div key={s.label}><span>{s.label}</span><span className={s.value <= 50 ? 'is-red' : ''}>{s.value}</span></div>)}
              <div><span>Evidence (mean)</span><span>{(subs.reduce((a, s) => a + s.value, 0) / subs.length).toFixed(2)}</span></div>
              <div><span>Final</span><span className="is-blue">{r.score?.toFixed(1)} · {r.band}{subs.some((s) => s.value <= 50) ? ' · capped at 69' : ''}</span></div>
            </div>
          )}
          {run === 'adult' && <a className="cw-btn" href={href('cutaway', 'results')}>Open the full Adult cutaway</a>}
        </aside>
      </div>
    </div>
  );
}
