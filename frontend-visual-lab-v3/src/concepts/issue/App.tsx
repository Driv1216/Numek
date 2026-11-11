import '@fontsource-variable/newsreader/opsz.css';
import '@fontsource-variable/newsreader/opsz-italic.css';
import '@fontsource-variable/familjen-grotesk';
import './issue.css';
import { useState } from 'react';
import { runFindings, runs } from '../../fixture';
import { href } from '../../shell/router';
import { Cover, Masthead } from './parts';

const filters = [['all', 'All issues'], ['scored', 'Scored'], ['unscored', 'No score defined'], ['tables', 'Tables'], ['text', 'Text'], ['images', 'Images'], ['connected', 'Connected']] as const;

export default function App() {
  const [f, setF] = useState<string>('all');
  const [q, setQ] = useState('');
  const shown = runs.filter((r) =>
    (f === 'all' || (f === 'scored' && r.score != null) || (f === 'unscored' && r.score == null) || r.rep === f) &&
    (!q || `${r.name} ${r.task} ${r.lead}`.toLowerCase().includes(q.toLowerCase())));
  const briefs = Object.entries(runFindings).flatMap(([id, fs]) => fs.slice(0, 1).map((x) => ({ id, ...x })));
  return (
    <div className="is is--app">
      <Masthead compact />
      <main className="is-desk">
        <div className="is-desk__bar">
          <h1>Issues<em>seven, all printed on this machine</em></h1>
          <div className="is-filters" role="group" aria-label="Filter issues">
            {filters.map(([k, l]) => <button key={k} aria-pressed={f === k} onClick={() => setF(k)}>{l}</button>)}
          </div>
          <input className="is-search" placeholder="Search issues, findings, columns" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search issues" />
        </div>
        <div className="is-newsstand">
          {shown.map((r) => <Cover key={r.id} run={r} no={runs.indexOf(r) + 1} />)}
          {!shown.length && <p style={{ fontSize: 20 }}>No issue matches. Try another filter.</p>}
        </div>
        <aside className="is-sidebar">
          <h2>Leading findings</h2>
          <ul className="is-brief">
            {briefs.map((b) => (
              <li key={b.id}><b>{b.title}</b><span>{runs.find((r) => r.id === b.id)!.name} · {b.severity} · {b.effect === 'none-defined' ? 'no score defined' : b.effect === 'evidence' ? 'evidence only' : 'affects the score'}</span></li>
            ))}
          </ul>
          <div className="is-newissue">
            <h3>Begin a new issue</h3>
            <p>Choose a table, text corpus, image folder or records-and-documents manifest. DataTrust validates and previews it before anything runs, and nothing leaves this machine.</p>
            <a className="is-btn is-btn--s" href={href('issue', 'results')}>Read Issue 01 first</a>
          </div>
        </aside>
      </main>
    </div>
  );
}
