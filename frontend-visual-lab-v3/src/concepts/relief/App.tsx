import '@fontsource-variable/cormorant';
import '@fontsource-variable/cormorant/wght-italic.css';
import '@fontsource-variable/figtree';
import './relief.css';
import { useState } from 'react';
import { adult, runFindings, runs } from '../../fixture';
import { href } from '../../shell/router';
import { Header, fences } from './Landing';
import { Relief, adultGrid, bikeGrid } from './surface';

export default function App() {
  const [run, setRun] = useState('adult');
  const [sel, setSel] = useState(0);
  const r = runs.find((x) => x.id === run)!;
  const f = runFindings[run] ?? [];
  const grid = run === 'adult' ? adultGrid : run === 'bike' ? bikeGrid : null;
  return (
    <div className="rl rl--app">
      <Header here="app" />
      <div className="rl-ws">
        <nav className="rl-runs" aria-label="Local runs">
          {runs.map((x) => <button key={x.id} type="button" aria-pressed={x.id === run} onClick={() => { setRun(x.id); setSel(0); }}><b>{x.name}</b><span>{x.score == null ? 'no score defined' : `${x.score.toFixed(1)} · ${x.band}`}</span></button>)}
        </nav>
        <main className="rl-main">
          <div className="rl-band">
            {grid ? <Relief key={run} grid={grid} label={`${r.name} surface`} lines={run === 'adult' ? fences : []} className="rl-canvas--band" /> : <div className="rl-flat"><span>{r.name} is not a table; it has no surface. DataTrust reads it by its own units — {r.lead.toLowerCase()}.</span></div>}
            <div className="rl-band__t"><span className="rl-kicker">{r.file} · {r.task}</span><h1>{r.name}</h1><span>{r.size} · {r.when} · {r.runtime}</span></div>
          </div>
          <div className="rl-wins">
            {f.length === 0 && <p className="rl-cap">No findings are listed for this run in the lab’s evidence.</p>}
            {f.map((x, i) => (
              <button key={x.title} type="button" className={`rl-win rl-win--${x.severity === 'High' ? 'rust' : i % 2 ? 'rust' : 'teal'} ${i === sel ? 'is-on' : ''}`} aria-pressed={i === sel} onClick={() => setSel(i)}>
                <span className="rl-win__k">{x.severity} · {x.effect === 'score' ? 'changes a sub-score' : x.effect === 'evidence' ? 'evidence only' : 'no score defined'}</span>
                <b className="rl-win__t">{x.title}</b>
              </button>
            ))}
          </div>
          {f[sel] && (
            <section className="rl-ev" aria-live="polite">
              <h2><em>{f[sel].title}</em></h2>
              <p>{run === 'adult' ? `${adult.findings[sel].finding} ${adult.findings[sel].evidence}` : f[sel].evidence}</p>
              {run === 'adult' && <p className="rl-dim">{adult.findings[sel].review}</p>}
              {run === 'adult' && <a href={href('relief', 'results')}>Open the Adult relief →</a>}
            </section>
          )}
        </main>
      </div>
    </div>
  );
}
