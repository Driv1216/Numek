import '@fontsource-variable/albert-sans';
import '@fontsource/red-hat-mono/400.css';
import '@fontsource/red-hat-mono/500.css';
import './findings.css';
import { useMemo, useState } from 'react';
import { runs, type Severity } from '../../fixture';
import { effectLabel, rows, sevRank, type Effect } from './data';
import { Header } from './Landing';

export default function App() {
  const [run, setRun] = useState<string>('all');
  const [sev, setSev] = useState<Severity | 'all'>('all');
  const [eff, setEff] = useState<Effect | 'all'>('all');
  const [sel, setSel] = useState(rows[0].id);
  const [tab, setTab] = useState<'evidence' | 'raw'>('evidence');
  const list = useMemo(() => rows.filter((r) => (run === 'all' || r.run === run) && (sev === 'all' || r.severity === sev) && (eff === 'all' || r.effect === eff)).sort((a, b) => sevRank[a.severity] - sevRank[b.severity]), [run, sev, eff]);
  const cur = rows.find((r) => r.id === sel);
  const r = runs.find((x) => x.id === cur?.run);
  const count = (pred: (x: (typeof rows)[number]) => boolean) => rows.filter(pred).length;
  return (
    <div className="fd fd--app">
      <Header here="app" />
      <div className="fd-ws">
        <aside className="fd-filters" aria-label="Filters">
          <fieldset><legend>Run</legend>
            {[['all', 'All runs'] as const, ...runs.map((x) => [x.id, x.name] as const)].map(([id, n]) => <label key={id}><input type="radio" name="run" checked={run === id} onChange={() => setRun(id)} /><span>{n}</span><em>{id === 'all' ? rows.length : count((x) => x.run === id)}</em></label>)}
          </fieldset>
          <fieldset><legend>Severity</legend>
            {(['all', 'High', 'Moderate', 'Low'] as const).map((s) => <label key={s}><input type="radio" name="sev" checked={sev === s} onChange={() => setSev(s)} /><span>{s === 'all' ? 'Any' : s}</span><em>{s === 'all' ? rows.length : count((x) => x.severity === s)}</em></label>)}
          </fieldset>
          <fieldset><legend>Effect</legend>
            {(['all', 'score', 'evidence', 'none-defined'] as const).map((e) => <label key={e}><input type="radio" name="eff" checked={eff === e} onChange={() => setEff(e)} /><span>{e === 'all' ? 'Any' : effectLabel[e]}</span><em>{e === 'all' ? rows.length : count((x) => x.effect === e)}</em></label>)}
          </fieldset>
        </aside>
        <main className="fd-main">
          <div className="fd-main__h"><h1>Findings</h1><span className="fd-mono">{list.length} shown · sorted by severity</span></div>
          <div className="fd-table fd-table--app" aria-label="Findings">
            <div className="fd-table__h" aria-hidden="true"><span>Finding</span><span>Run</span><span>Severity</span><span>Effect</span></div>
            {list.map((x) => (
              <button key={x.id} type="button" className={`fd-arow ${x.id === sel ? 'is-on' : ''}`} aria-pressed={x.id === sel} onClick={() => setSel(x.id)}>
                <span className="fd-row__t"><b>{x.title}</b><small>{x.evidence}</small></span><span>{x.runName}</span><span className={`fd-sev fd-sev--${x.severity.toLowerCase()}`}>{x.severity}</span><span className={`fd-eff fd-eff--${x.effect}`}>{effectLabel[x.effect]}</span>
              </button>
            ))}
            {list.length === 0 && <p className="fd-empty">No findings match these filters.</p>}
          </div>
        </main>
        <aside className="fd-detail" aria-label="Finding detail">
          {cur && r && (
            <>
              <span className="fd-tag">{r.name} · {r.task}</span>
              <h2>{cur.title}</h2>
              <div className="fd-tabs" role="tablist"><button type="button" role="tab" aria-selected={tab === 'evidence'} onClick={() => setTab('evidence')}>Evidence</button><button type="button" role="tab" aria-selected={tab === 'raw'} onClick={() => setTab('raw')}>Fields</button></div>
              {tab === 'evidence' ? (
                <div className="fd-detail__b">
                  <p>{cur.raw ? cur.raw.finding : cur.evidence}</p>
                  {cur.raw && <><p className="fd-dimp">{cur.raw.impact}</p><p><b>Review.</b> {cur.raw.review}</p></>}
                  <dl className="fd-kv"><div><dt>Severity</dt><dd>{cur.severity}</dd></div><div><dt>Effect</dt><dd>{effectLabel[cur.effect]}</dd></div><div><dt>Run score</dt><dd>{r.score == null ? 'none defined' : `${r.score.toFixed(1)} · ${r.band}`}</dd></div><div><dt>Runtime</dt><dd>{r.runtime}</dd></div></dl>
                </div>
              ) : (
                <pre className="fd-raw">{cur.raw ? Object.entries({ code: cur.raw.code, severity: cur.raw.severity, evidence: cur.raw.evidence, scoreEffect: cur.raw.scoreEffect, columns: cur.raw.locus.columns.join(', ') }).map(([k, v]) => `${k.padEnd(12)} ${v}`).join('\n') : `run          ${cur.runName}\nseverity     ${cur.severity}\nevidence     ${cur.evidence}`}</pre>
              )}
            </>
          )}
        </aside>
      </div>
    </div>
  );
}
