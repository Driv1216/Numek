import '@fontsource-variable/recursive/full.css';
import './two-readings.css';
import { useEffect, useRef, useState } from 'react';
import { runFindings, runs } from '../../fixture';
import { href } from '../../shell/router';
import { Json, Wordmark, axes } from './shared';

export function CommandBar({ onOpen }: { onOpen: () => void }) {
  return (
    <header className="tr-bar">
      <Wordmark />
      <button className="tr-cmdk" onClick={onOpen} style={axes(1)}><span>Run a command, open a run, find a column…</span><kbd>⌘K</kbd></button>
      <span className="tr-bar__local" style={axes(1)}><i />local · 127.0.0.1:8000</span>
    </header>
  );
}

export function Palette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [q, setQ] = useState('');
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => { if (open) setTimeout(() => input.current?.focus(), 10); }, [open]);
  if (!open) return null;
  const items = [
    ...runs.map((r) => ({ k: `open ${r.file}`, d: `${r.name} · ${r.task}`, go: r.id === 'adult' ? href('two-readings', 'results') : href('two-readings', 'app') })),
    { k: 'audit <file> --target <column>', d: 'Start a new local analysis', go: href('two-readings', 'app') },
    { k: 'export adult --format pdf', d: 'Portrait decision pages + landscape appendix', go: href('two-readings', 'results') },
    { k: 'reading human', d: 'Switch every pane to the human reading', go: href('two-readings', 'results') },
  ].filter((x) => !q || `${x.k} ${x.d}`.toLowerCase().includes(q.toLowerCase()));
  return (
    <div className="tr-pal" role="dialog" aria-label="Command palette" onClick={onClose}>
      <div className="tr-pal__box" onClick={(e) => e.stopPropagation()}>
        <input ref={input} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Type a command or a run…" style={axes(1)} onKeyDown={(e) => e.key === 'Escape' && onClose()} />
        <ul>{items.map((x) => <li key={x.k}><a href={x.go} onClick={onClose}><b style={axes(1)}>{x.k}</b><span>{x.d}</span></a></li>)}</ul>
      </div>
    </div>
  );
}

export function usePalette() {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const on = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setOpen((o) => !o); } };
    addEventListener('keydown', on); return () => removeEventListener('keydown', on);
  }, []);
  return [open, setOpen] as const;
}

/** Drag the divider to shift between the machine and the human reading. */
export function useSplit(initial = 0.42) {
  const [split, setSplit] = useState(initial);
  const drag = (e: React.PointerEvent<HTMLDivElement>) => {
    const box = (e.currentTarget.parentElement as HTMLElement).getBoundingClientRect();
    const move = (ev: PointerEvent) => setSplit(Math.min(0.85, Math.max(0.15, (ev.clientX - box.left) / box.width)));
    const up = () => { removeEventListener('pointermove', move); removeEventListener('pointerup', up); };
    addEventListener('pointermove', move); addEventListener('pointerup', up);
  };
  const key = (e: React.KeyboardEvent) => { if (e.key === 'ArrowLeft') setSplit((s) => Math.max(0.15, s - 0.05)); if (e.key === 'ArrowRight') setSplit((s) => Math.min(0.85, s + 0.05)); };
  return { split, drag, key };
}

export default function App() {
  const [open, setOpen] = usePalette();
  const [sel, setSel] = useState('adult');
  const { split, drag, key } = useSplit();
  const run = runs.find((r) => r.id === sel)!;
  const fs = runFindings[sel] ?? [];
  const machine = { dataset: run.file, task: run.task, size: run.size, overall: run.score, risk_level: run.band, findings: fs.map((f) => ({ title: f.title, severity: f.severity, evidence: f.evidence })) };
  return (
    <div className="tr tr--app">
      <CommandBar onOpen={() => setOpen(true)} />
      <div className="tr-work">
        <nav className="tr-timeline" aria-label="Session timeline">
          <p className="tr-tl__h" style={axes(1)}>~/datasets · session</p>
          <ol>
            {runs.map((r) => (
              <li key={r.id}>
                <button className={sel === r.id ? 'is-on' : ''} onClick={() => setSel(r.id)} onDoubleClick={() => { if (r.id === 'adult') location.hash = href('two-readings', 'results'); }}>
                  <span className="tr-tl__t" style={axes(1)}>{r.when}</span>
                  <span className="tr-tl__c" style={axes(1)}>$ audit {r.file}</span>
                  <span className="tr-tl__r" style={axes(0)}>{r.score != null ? <><b>{r.score.toFixed(1)}</b> {r.band}</> : <>no score defined</>}</span>
                </button>
              </li>
            ))}
          </ol>
          <a className="tr-btn tr-btn--s tr-tl__new" href={href('two-readings', 'results')} style={axes(1)}>$ audit … <kbd>N</kbd></a>
        </nav>
        <div className="tr-split" style={{ gridTemplateColumns: `${split}fr 10px ${1 - split}fr` }}>
          <section className="tr-pane tr-pane--m" aria-label="Machine reading">
            <p className="tr-pane__h" style={axes(1)}>machine · {run.file.replace(/\.\w+$/, '')}.json</p>
            <Json value={machine} />
          </section>
          <div className="tr-divider" role="separator" aria-orientation="vertical" aria-valuenow={Math.round(split * 100)} tabIndex={0} onPointerDown={drag} onKeyDown={key}><i /></div>
          <section className="tr-pane tr-pane--h" aria-label="Human reading" style={axes(0, 0.15)}>
            <p className="tr-pane__h" style={axes(1)}>human · summary</p>
            <h1>{run.name}</h1>
            <p className="tr-pane__meta">{run.task} · {run.size} · {run.when}</p>
            {run.score != null
              ? <p className="tr-big"><b>{run.score.toFixed(1)}</b> <span>{run.band}</span></p>
              : <p className="tr-big tr-big--none"><b>—</b> <span>No score is defined for this task family; the evidence below stands on its own.</span></p>}
            <p className="tr-lead">{run.lead}.</p>
            <ul className="tr-hfind">
              {fs.map((f) => <li key={f.title}><span className={`tr-sev tr-sev--${f.severity.toLowerCase()}`}>{f.severity}</span><b>{f.title}</b><p>{f.evidence}</p></li>)}
              {!fs.length && <li><p>Open the full report for this run’s findings.</p></li>}
            </ul>
            {sel === 'adult' && <a className="tr-btn" href={href('two-readings', 'results')}>Open the Adult result</a>}
          </section>
        </div>
      </div>
      <Palette open={open} onClose={() => setOpen(false)} />
    </div>
  );
}
