import '@fontsource-variable/bricolage-grotesque/standard.css';
import './modules.css';
import { useState } from 'react';
import { adult, bike, company, local, representations } from '../../fixture';
import { href } from '../../shell/router';
import { byId, effectLabel, mods, runStates, type ModId } from './data';
import { Chapter, Tile } from './Mosaic';

export function Header({ here }: { here: 'landing' | 'app' | 'results' }) {
  return (
    <header className="md-head">
      <a className="md-wm" href={href('modules', 'landing')}>NUMEK</a>
      <nav aria-label="Primary">
        <a href={href('modules', 'landing')} aria-current={here === 'landing' ? 'page' : undefined}>Modules</a>
        <a href={href('modules', 'app')} aria-current={here === 'app' ? 'page' : undefined}>Runs</a>
        <a href={href('modules', 'results')} aria-current={here === 'results' ? 'page' : undefined}>Adult</a>
      </nav>
      <span className="md-head__r">DataTrust · runs on 127.0.0.1</span>
    </header>
  );
}

const adultOrder: ModId[] = ['score', 'imbalance', 'conflicts', 'outliers', 'leakage', 'gaps', 'dups', 'local', 'reports'];

export default function Landing() {
  const [open, setOpen] = useState<ModId | null>(null);
  const [origin, setOrigin] = useState('data-mod');
  const openFrom = (o: string) => (id: ModId) => { setOrigin(o); setOpen(id); };
  return (
    <div className="md md--landing">
      <Header here="landing" />

      <section className="md-hero">
        <h1>DataTrust, in fourteen parts.</h1>
        <div className="md-hero__r">
          <p>{company.productLine} Every tile is one thing it checks, drawn from a real local run. Open any of them.</p>
          <p className="md-key"><i className="md-key__ink" /> what the module found <i className="md-key__ghost" /> context</p>
        </div>
      </section>

      <section className="md-mosaic" aria-label="Modules">
        {mods.map((m, i) => (
          <div key={m.id} className="md-slot" style={{ gridArea: m.area, ['--d' as string]: i }}>
            <Tile m={m} onOpen={openFrom('data-mod')} />
          </div>
        ))}
      </section>

      <section className="md-read">
        <div className="md-read__h">
          <p className="md-eyebrow">One run, module by module</p>
          <h2>Adult, 48,842 rows. Four findings; one of them sets the score.</h2>
        </div>
        <ol className="md-ledger">
          {adultOrder.map((id) => {
            const m = byId[id]; const s = runStates.adult[id]!;
            return (
              <li key={id}>
                <button type="button" onClick={() => openFrom('data-mod-ledger')(id)} data-mod-ledger={id}>
                  <i style={{ background: m.bg }} className={m.light ? 'is-light' : ''}>{m.n}</i>
                  <b>{m.name}</b>
                  <span className={`md-ledger__s md-ledger__s--${s.tone}`}>{s.label}</span>
                  <span className="md-ledger__d">{s.detail}</span>
                  <span className="md-ledger__e">{effectLabel[m.effect]}</span>
                </button>
              </li>
            );
          })}
        </ol>
        <div className="md-sum">
          <div><span>Evidence</span><b>{adult.evidenceScore}</b></div>
          <div className="md-sum__arrow" aria-hidden="true">→</div>
          <div><span>Guardrail</span><b>cap 69</b><em>target balance {adult.subScores[2].value}</em></div>
          <div className="md-sum__arrow" aria-hidden="true">→</div>
          <div className="is-final"><span>Final</span><b>{adult.finalScore.toFixed(1)}</b><em>{adult.band}</em></div>
        </div>
        <p className="md-read__bike"><b>Bike sharing, hourly:</b> {bike.relationship} on all {bike.rows.toLocaleString()} rows, both parts declared unavailable at prediction time. Two High findings — and no score, because regression has no universal one.</p>
      </section>

      <section className="md-reps">
        <p className="md-eyebrow">Six kinds of data, each read by its own unit</p>
        <div className="md-reps__row">
          {representations.map((r, i) => (
            <article key={r.id} style={{ ['--bg' as string]: ['#1d2440', '#1f6f6a', '#f6c9c0', '#cfe0ea', '#dcd5c5', '#f5b83d'][i] }} className={i < 2 ? 'is-light' : ''}>
              <span className="md-reps__u">per {r.unit}</span>
              <h3>{r.name}</h3>
              <ul>{r.checks.map((c) => <li key={c}>{c}</li>)}</ul>
              <span className="md-reps__e">{r.example}</span>
            </article>
          ))}
        </div>
      </section>

      <section className="md-run">
        <div>
          <p className="md-eyebrow">Run it</p>
          <h2>On your machine, from one command.</h2>
        </div>
        <pre className="md-term"><span className="md-term__p">$</span> {local.commands[0]}{'\n'}{local.cliOutput.join('\n')}{'\n\n'}<span className="md-term__p">$</span> {local.commands[1]}{'\n'}<span className="md-term__c">→ http://127.0.0.1:8000/</span></pre>
      </section>

      <footer className="md-foot">
        <span className="md-wm md-wm--l">NUMEK</span>
        <p>{company.line}. DataTrust is the product. {company.direction}</p>
        <p className="md-foot__s">{adult.source} · sha256 {adult.sha256.slice(0, 12)}… · Findings support human review; they are not certification.</p>
      </footer>

      {open && <Chapter id={open} origin={origin} onClose={() => setOpen(null)} onNav={setOpen} />}
    </div>
  );
}
