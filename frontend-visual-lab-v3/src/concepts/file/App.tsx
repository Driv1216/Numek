import '@fontsource/dm-serif-display/400.css';
import '@fontsource/dm-serif-display/400-italic.css';
import '@fontsource-variable/dm-sans';
import './file.css';
import { useState } from 'react';
import { runFindings, runs } from '../../fixture';
import { href } from '../../shell/router';
import { Header } from './Landing';
import { Stack, states, type State } from './stack';

export default function App() {
  const [run, setRun] = useState('adult');
  const [st, setSt] = useState<State>('read');
  const r = runs.find((x) => x.id === run)!;
  const f = runFindings[run] ?? [];
  const isAdult = run === 'adult';
  return (
    <div className="fl fl--app">
      <Header here="app" />
      <div className="fl-ws">
        <nav className="fl-books" aria-label="Files">
          {runs.map((x) => (
            <button key={x.id} type="button" aria-pressed={x.id === run} className={x.id === run ? 'is-on' : ''} onClick={() => { setRun(x.id); setSt('read'); }}>
              <span className="fl-books__spine">{x.file}</span><b>{x.name}</b><em>{x.score == null ? 'no score' : x.score.toFixed(1)}</em>
            </button>
          ))}
        </nav>
        <main className={`fl-desk f-${isAdult ? st : 'read'}`}>
          {isAdult && (
            <div className="fl-tabs" role="tablist" aria-label="States">
              {states.slice(1).map((s) => <button key={s.id} type="button" role="tab" aria-selected={st === s.id} onClick={() => setSt(s.id)}>{s.k.split(' · ')[1]}</button>)}
            </div>
          )}
          <div className="fl-desk__obj"><Stack state={isAdult ? st : 'read'} label={r.file} /></div>
          <aside className="fl-desk__t">
            <span className="fl-k">{r.task}</span>
            <h1>{r.name}</h1>
            <p className="fl-figline">{r.size} · {r.when} · {r.runtime}</p>
            {isAdult ? (
              <><p>{states.find((s) => s.id === st)?.caption}</p><b className="fl-figsm">{states.find((s) => s.id === st)?.figure}</b><a href={href('file', 'results')}>See the file in its final state →</a></>
            ) : (
              <><p>{r.lead}.</p><p className="fl-dim">{r.score == null ? 'No universal score is defined for this kind of data.' : `${r.score.toFixed(1)} · ${r.band}`}</p></>
            )}
            {f.length > 0 && <ul className="fl-flist">{f.map((x) => <li key={x.title}><b>{x.title}</b><span>{x.severity} · {x.evidence}</span></li>)}</ul>}
          </aside>
        </main>
      </div>
    </div>
  );
}
