import '@fontsource-variable/martian-mono';
import './resolution.css';
import { useState } from 'react';
import { runs, runFindings } from '../../fixture';
import { Header, Index, Sheet } from './Landing';
import { Wall } from './Wall';
import { runColour, tiles, type Tile } from './tiles';

export default function App() {
  const [run, setRun] = useState('adult');
  const [view, setView] = useState<'wall' | 'index'>('wall');
  const [open, setOpen] = useState<Tile | null>(null);
  const list = tiles.filter((t) => t.run === run);
  const r = runs.find((x) => x.id === run)!;
  return (
    <div className="rs rs--app" style={{ ['--accent' as string]: runColour[run] }}>
      <Header here="app" />
      <div className="rs-ws">
        <nav className="rs-runs" aria-label="Local runs">
          {runs.map((x) => (
            <button key={x.id} type="button" aria-pressed={x.id === run} style={{ ['--c' as string]: runColour[x.id] }} onClick={() => { setRun(x.id); setOpen(null); }}>
              <i /><b>{x.name}</b><span>{tiles.filter((t) => t.run === x.id).length} artefacts · {x.score == null ? 'no score' : x.score.toFixed(1)}</span>
            </button>
          ))}
        </nav>
        <section className="rs-hero rs-hero--app">
          <div className="rs-apphead"><h1>{r.name}</h1><span className="rs-k">{r.size} · {r.task} · {(runFindings[run] ?? []).length} findings</span>
            <div className="rs-pill" role="tablist" aria-label="View"><button type="button" role="tab" aria-selected={view === 'wall'} onClick={() => setView('wall')}>Wall</button><button type="button" role="tab" aria-selected={view === 'index'} onClick={() => setView('index')}>Index</button></div>
          </div>
          {view === 'wall' ? <Wall key={run} list={list} onOpen={setOpen} active={open?.id} /> : <Index list={list} onOpen={setOpen} />}
          {open && <Sheet t={open} onClose={() => setOpen(null)} />}
        </section>
      </div>
    </div>
  );
}
