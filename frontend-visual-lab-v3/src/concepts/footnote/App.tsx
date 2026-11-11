import '@fontsource-variable/newsreader';
import '@fontsource-variable/newsreader/wght-italic.css';
import '@fontsource-variable/hanken-grotesk';
import '@fontsource/red-hat-mono/400.css';
import './footnote.css';
import { useState } from 'react';
import { adult, runFindings, runs, subScoresByRun } from '../../fixture';
import { href } from '../../shell/router';
import { Header } from './Landing';
import { Token } from './inserts';

const lower = (s: string) => s.charAt(0).toLowerCase() + s.slice(1);

export default function App() {
  const [run, setRun] = useState('adult');
  const [claim, setClaim] = useState(0);
  const r = runs.find((x) => x.id === run)!;
  const f = runFindings[run] ?? [];
  const subs = subScoresByRun[run];
  const sel = f[claim];
  const raw = run === 'adult' ? adult.findings[claim] : null;
  return (
    <div className="fn fn--app">
      <Header here="app" />
      <div className="fn-ws">
        <nav className="fn-runs" aria-label="Local runs">
          <p className="fn-paren">(Runs)</p>
          {runs.map((x) => (
            <button key={x.id} type="button" aria-pressed={x.id === run} className={x.id === run ? 'is-on' : ''} onClick={() => { setRun(x.id); setClaim(0); }}>
              <span>{x.name}</span><em>{x.score == null ? 'no score' : x.score.toFixed(1)}</em>
            </button>
          ))}
        </nav>
        <main className="fn-main">
          <p className="fn-paren">({r.file} · {r.task} · {r.when})</p>
          <p className="fn-claim">
            {r.name}, {r.size}, {r.score == null ? <>has no score, because none is defined for {lower(r.task)}.</> : <>scored <Token value={r.score.toFixed(1)} label="final score" lines={[...(subs ?? []).map((s) => [s.label, String(s.value)] as [string, string]), ['Final', `${r.score.toFixed(1)} · ${r.band}`]]} />, {r.band}.</>}{' '}
            {f.length ? <>It has {f.length === 1 ? 'one finding' : `${f.length} findings`}: {f.map((x, i) => (
              <span key={x.title}>{i > 0 && (i === f.length - 1 ? ' and ' : ', ')}<button type="button" className={`fn-claimref ${i === claim ? 'is-on' : ''}`} aria-pressed={i === claim} onClick={() => setClaim(i)}>{lower(x.title)}<sup>{i + 1}</sup></button></span>
            ))}.</> : <>{r.lead}.</>}
          </p>
          {sel && (
            <section className="fn-ev" aria-live="polite">
              <p className="fn-paren"><sup>{claim + 1}</sup>({sel.title})</p>
              <p className="fn-big fn-big--s">{raw ? raw.finding : sel.evidence}</p>
              {raw && <><p className="fn-small">{raw.evidence} {raw.impact}</p><p className="fn-small"><b>Review.</b> {raw.review}</p></>}
              {run === 'adult' && <a className="fn-more" href={href('footnote', 'results')}>Read the whole Adult result →</a>}
            </section>
          )}
        </main>
        <aside className="fn-spec" aria-label="Claim facts">
          {sel ? (
            <dl>
              <div><dt>Claim</dt><dd>{claim + 1} of {f.length}</dd></div>
              <div><dt>Severity</dt><dd>{sel.severity}</dd></div>
              <div><dt>Effect</dt><dd>{sel.effect === 'score' ? 'Changes the score' : sel.effect === 'evidence' ? 'Evidence only' : 'No score defined'}</dd></div>
              <div><dt>Evidence</dt><dd>{sel.evidence}</dd></div>
              <div><dt>Run</dt><dd>{r.name} · {r.runtime}</dd></div>
            </dl>
          ) : <p className="fn-small">No findings are listed for this run in the lab’s evidence. DataTrust reports it by its own units.</p>}
        </aside>
      </div>
    </div>
  );
}
