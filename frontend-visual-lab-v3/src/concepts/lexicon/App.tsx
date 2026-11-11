import '@fontsource-variable/fraunces/full.css';
import '@fontsource-variable/fraunces/full-italic.css';
import '@fontsource-variable/work-sans';
import '@fontsource/dm-mono/400.css';
import './lexicon.css';
import { useState } from 'react';
import { runs } from '../../fixture';
import { href } from '../../shell/router';
import { entries } from './entries';
import { Fragments, Header } from './parts';

const lineFor = (entryRun: string, runName: string) => runName.startsWith(entryRun) || entryRun.startsWith(runName);

export default function App() {
  const [run, setRun] = useState('adult');
  const r = runs.find((x) => x.id === run)!;
  const rows = entries.map((e) => ({ e, hit: e.in.find((x) => lineFor(x.run, r.name)) }));
  const present = rows.filter((x) => x.hit);
  const [sel, setSel] = useState<string>('imbalance');
  const cur = rows.find((x) => x.e.id === sel && x.hit) ?? present[0];

  return (
    <div className="lx lx--app">
      <Header here="app" />
      <div className="lx-conc">
        <nav className="lx-runs" aria-label="Local runs">
          <p>Runs · {runs.length}</p>
          {runs.map((x) => (
            <button key={x.id} type="button" className={x.id === run ? 'is-on' : ''} aria-pressed={x.id === run} onClick={() => setRun(x.id)}>
              <b>{x.name}</b>
              <span>{x.score == null ? 'no score defined' : `${x.score.toFixed(1)} · ${x.band}`}</span>
            </button>
          ))}
        </nav>
        <section className="lx-words" aria-label={`Words found in ${r.name}`}>
          <h1>{r.name}</h1>
          <p>{r.file} · {r.task} · {present.length} of {entries.length} words have an example here</p>
          <ol>
            {rows.map(({ e, hit }, i) => (
              <li key={e.id} className={hit ? '' : 'is-absent'}>
                <button type="button" className={cur && cur.e.id === e.id ? 'is-on' : ''} disabled={!hit} onClick={() => setSel(e.id)}>
                  <span>{String(i + 1).padStart(2, '0')}</span>
                  <b>{e.word}</b>
                  <em>{hit ? e.sense : '—'}</em>
                </button>
              </li>
            ))}
          </ol>
        </section>
        <aside className="lx-panel" aria-live="polite">
          {cur ? (
            <>
              <Fragments frags={cur.e.frags.slice(0, 6)} seed={2} />
              <h2>{cur.e.word}</h2>
              <div className="lx-def">
                <p className="lx-def__pos"><i>{cur.e.pos}</i> {cur.e.sense}</p>
                <p className="lx-def__d">{cur.e.def}</p>
                <dl><div><dt>In {r.name}</dt><dd>{cur.hit!.line}</dd></div></dl>
                <p className="lx-def__fx">{cur.e.effect}</p>
                {run === 'adult' && <a className="lx-link" href={href('lexicon', 'results')}>Read the full Adult entry →</a>}
              </div>
            </>
          ) : (
            <>
              <h2><i>{r.name}</i></h2>
              <div className="lx-def">
                <p className="lx-def__d">None of the nine words is illustrated from this run. DataTrust reads {r.rep} by its own units.</p>
                <dl><div><dt>What it reported</dt><dd>{r.lead}.</dd></div></dl>
                <p className="lx-def__fx">{r.task} · {r.size} · no score defined.</p>
              </div>
            </>
          )}
        </aside>
      </div>
    </div>
  );
}
