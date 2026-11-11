import '@fontsource-variable/hanken-grotesk';
import '@fontsource-variable/azeret-mono';
import './passage.css';
import { useState } from 'react';
import { representations, runs } from '../../fixture';
import { href } from '../../shell/router';
import { repColour, repInk } from './artefacts';
import { Header } from './chrome';
import { Miller } from './miller';

export default function App() {
  const [path, setPath] = useState<string[]>(['adult']);
  return (
    <div className="ps ps--app">
      <Header app />
      <section className="ps-doors" aria-label="Representations">
        {representations.map((r, i) => {
          const n = runs.filter((x) => x.rep === r.id).length;
          return (
            <a key={r.id} className="ps-door" href={href('passage', 'app')} style={{ background: repColour[r.id], color: repInk[r.id] }} onClick={(e) => { e.preventDefault(); const run = runs.find((x) => x.rep === r.id); if (run) setPath([run.id]); }}>
              <span className="ps-mono">{i + 1}/6</span>
              <b>{r.name}</b>
              <span>{n ? `${n} run${n > 1 ? 's' : ''}` : 'No runs yet'}</span>
            </a>
          );
        })}
      </section>
      <div className="ps-trail">
        <span className="ps-mono">Path</span>
        {path.map((p, i) => <button key={i} onClick={() => setPath(path.slice(0, i + 1))}>{p.replace(/_/g, ' ')}</button>)}
        <a className="ps-btn ps-btn--s" style={{ marginLeft: 'auto' }} href={href('passage', 'results')}>Follow the conflicting labels</a>
      </div>
      <Miller path={path} setPath={setPath} />
    </div>
  );
}
