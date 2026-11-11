import '@fontsource-variable/geist';
import '@fontsource-variable/geist-mono';
import './camera.css';
import { local, runs } from '../../fixture';
import { href } from '../../shell/router';
import { Icon, Sidebar } from './ui';

const repIcon = { tables: Icon.table, outcomes: Icon.outcomes, text: Icon.text, images: Icon.images, connected: Icon.connected, time: Icon.time };
const totalFindings = runs.reduce((s, r) => s + (r.findings ?? 0), 0);

export default function App() {
  return (
    <div className="cm cm--app">
      <div className="cm-app">
        <Sidebar active="" link />
        <div className="cm-main">
          <header className="cm-top">
            <div className="cm-crumbs"><span>Runs</span></div>
            <div className="cm-top__r"><span className="cm-kbd">{local.host}:8000</span><a className="cm-btn" href="#cm-new">New run</a></div>
          </header>
          <div className="cm-home">
            <div className="cm-home__h">
              <div><h1>Local runs</h1><p>{runs.length} runs on this machine. Nothing is uploaded; nothing is fetched during analysis.</p></div>
            </div>
            <div className="cm-stats">
              <div className="cm-card"><span>Runs</span><b>{runs.length}</b><span>6 kinds of data</span></div>
              <div className="cm-card"><span>Scored</span><b>{runs.filter((r) => r.score != null).length}</b><span>classification tables only</span></div>
              <div className="cm-card"><span>Findings</span><b>{totalFindings}</b><span>across {runs.filter((r) => r.findings).length} runs</span></div>
              <div className="cm-card"><span>Adult audit</span><b>0.18 s</b><span>48,842 rows · recorded locally</span></div>
            </div>
            <section className="cm-card">
              <div className="cm-card__h"><span>All runs</span><span className="cm-muted">Oldest first</span></div>
              <div className="cm-runtbl" role="table" aria-label="Runs">
                <div role="row" className="cm-tbl__h"><span /><span>Name</span><span>Task</span><span>Size</span><span>Score</span><span>Findings</span><span>Lead</span><span>Date</span></div>
                {runs.map((r) => {
                  const cells = (<>
                    <span className="cm-runs__i">{repIcon[r.rep]}</span>
                    <span><b style={{ fontWeight: 550 }}>{r.name}</b><br /><small className="cm-mono">{r.file}</small></span>
                    <span>{r.task}</span>
                    <span className="cm-mono" style={{ fontSize: 12 }}>{r.size}</span>
                    <span>{r.score == null ? <small>No score defined</small> : <span className={`cm-badge ${r.band === 'Low' ? 'is-ok' : 'is-mod'}`}>{r.score.toFixed(1)} · {r.band}</span>}</span>
                    <span className="cm-mono">{r.findings ?? '—'}</span>
                    <small>{r.lead}</small>
                    <small>{r.when}</small>
                  </>);
                  return r.id === 'adult'
                    ? <a key={r.id} role="row" href={href('camera', 'results')}>{cells}</a>
                    : <div key={r.id} role="row">{cells}</div>;
                })}
              </div>
            </section>
            <section className="cm-card" id="cm-new">
              <div className="cm-card__h"><span>New run</span><span className="cm-muted">Upload limit {local.uploadLimit} · stays on this machine</span></div>
              <div className="cm-new">
                <div className="cm-drop"><b>Drop a dataset file</b><span>or choose one from disk</span></div>
                <div style={{ display: 'grid', gap: 12 }}>
                  <label className="cm-field">Target column<span className="cm-in">annual_income_over_50k</span></label>
                  <label className="cm-field">Reports<span className="cm-in">HTML · PDF · JSON</span></label>
                  <label className="cm-field">Same run from the terminal<span className="cm-in" style={{ color: 'var(--muted)', lineHeight: 1.5 }}>$ {local.commands[0]}</span></label>
                </div>
              </div>
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}
