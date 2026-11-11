import '@fontsource-variable/anybody';
import '@fontsource-variable/jetbrains-mono';
import './slab.css';
import { useState } from 'react';
import { adult, runFindings, runs, subScoresByRun } from '../../fixture';
import { href } from '../../shell/router';
import { Header, adultCredits } from './Landing';
import { Credits, Shutter, SlabMark } from './slabs';

export default function App() {
  const [run, setRun] = useState('adult');
  const [open, setOpen] = useState<number | null>(null);
  const r = runs.find((x) => x.id === run)!;
  const subs = subScoresByRun[run];
  const f = runFindings[run] ?? [];
  const credits: [string, string][] = run === 'adult' ? adultCredits : [['File', r.file], ['Size', r.size], ['Task', r.task], ['Run', r.when], ['Runtime', r.runtime]];
  return (
    <div className="sl sl--app">
      <Header here="app" run={r.name} />
      <div className="sl-ws">
        <nav className="sl-index" aria-label="Runs">
          <span className="sl-k">RUN {String(runs.indexOf(r) + 1).padStart(2, '0')} / {String(runs.length).padStart(2, '0')}</span>
          {runs.map((x, k) => <button key={x.id} type="button" aria-pressed={x.id === run} className={x.id === run ? 'is-on' : ''} onClick={() => { setRun(x.id); setOpen(null); }}><span>{String(k + 1).padStart(2, '0')}</span>{x.name}</button>)}
        </nav>
        <main className="sl-main">
          <div className="sl-main__top">
            <div>
              <h1>{r.name}</h1>
              <p className="sl-final">{r.score == null ? 'No score defined' : <>Final <b className={r.band === 'Elevated' ? 'sl-red' : ''}>{r.score.toFixed(1)}</b> · {r.band}</>}</p>
              {subs ? <SlabMark key={run} values={subs} p={1} /> : <div className="sl-none"><p>No slabs: {r.task.toLowerCase()} has no universal score.</p></div>}
            </div>
            <Credits items={credits} />
          </div>
          <div className="sl-shutters">
            {f.length === 0 && <p className="sl-dim">{r.lead}.</p>}
            {f.map((x, i) => (
              <button key={x.title} type="button" className="sl-shutter-btn" aria-expanded={open === i} onClick={() => setOpen(open === i ? null : i)}>
                <Shutter open={open === i} label={x.title}>
                  <span className="sl-k">{String(i + 1).padStart(2, '0')} · {x.severity.toUpperCase()}</span>
                  <h3>{x.title}</h3>
                  <p>{x.evidence}</p>
                  {run === 'adult' && <p className="sl-dim">{adult.findings[i].review}</p>}
                </Shutter>
                <span className="sl-shutter-btn__lab">{open === i ? 'Close' : `${String(i + 1).padStart(2, '0')} · ${x.title}`}</span>
              </button>
            ))}
          </div>
          {run === 'adult' && <a className="sl-link" href={href('slab', 'results')}>Open the Adult result →</a>}
        </main>
      </div>
    </div>
  );
}
