import '@fontsource-variable/eb-garamond';
import '@fontsource-variable/eb-garamond/wght-italic.css';
import '@fontsource-variable/inter-tight';
import './provenance.css';
import { useState } from 'react';
import { runFindings, runs } from '../../fixture';
import { href } from '../../shell/router';
import { Header, RecordCard, rowA, rowB } from './trace';
import { traces } from './traces';

export default function App() {
  const [run, setRun] = useState('adult');
  const [sel, setSel] = useState(0);
  const r = runs.find((x) => x.id === run)!;
  const ts = traces[run];
  const fs = runFindings[run] ?? [];
  return (
    <div className="pv pv--app">
      <Header app />
      <div className="pv-ws">
        <nav className="pv-runs" aria-label="Runs">
          <p className="pv-kicker">Local runs</p>
          {runs.map((x) => (
            <button key={x.id} className={run === x.id ? 'is-on' : ''} onClick={() => { setRun(x.id); setSel(0); }}>
              <b>{x.name}</b><span>{x.task} · {x.when}</span>
            </button>
          ))}
        </nav>
        <main className="pv-list">
          <p className="pv-kicker">Traces · {r.file}</p>
          <h1>{r.name}</h1>
          <p className="pv-list__s">{r.size} · {r.score == null ? 'no score defined' : `${r.score.toFixed(1)} · ${r.band}`} · {r.runtime}</p>
          {ts ? ts.map((t, i) => (
            <div key={t.title} className={`pv-item ${sel === i ? 'is-on' : ''}`} onClick={() => setSel(i)} role="button" tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && setSel(i)}>
              <p className="pv-kicker">{t.severity} · {t.effect}</p>
              <h3>{t.title}</h3>
              <p className="pv-chain">{t.steps.map((s) => <span key={s.k}>{s.k}</span>)}</p>
            </div>
          )) : fs.length ? fs.map((f) => (
            <div key={f.title} className="pv-item"><p className="pv-kicker">{f.severity}</p><h3>{f.title}</h3><p className="pv-chain"><span>{f.evidence}</span></p></div>
          )) : <div className="pv-item"><h3>{r.lead}</h3><p className="pv-chain"><span>Open the report for the full evidence trail</span></p></div>}
          {run === 'adult' && <p style={{ marginTop: 30 }}><a className="pv-btn pv-btn--l" href={href('provenance', 'results')}>Open the Adult report, traced</a></p>}
        </main>
        <aside className="pv-side" aria-label="Selected evidence">
          {run === 'adult' && sel === 0 ? (
            <>
              <p>Evidence object · group 1 of 5</p>
              <RecordCard values={rowA} other={rowB} stage={4} />
              <RecordCard values={rowB} other={rowA} stage={4} label="Row 34,343" />
            </>
          ) : ts ? (
            <>
              <p>{ts[sel].title}</p>
              <ol className="pv-steps" style={{ width: '100%' }}>{ts[sel].steps.map((s) => <li key={s.k} className={s.o ? 'is-o' : ''}><b>{s.k}</b><span>{s.v}</span></li>)}</ol>
            </>
          ) : <p>Select a run with traces.</p>}
        </aside>
      </div>
    </div>
  );
}
