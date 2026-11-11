import '@fontsource-variable/hanken-grotesk';
import '@fontsource-variable/azeret-mono';
import './passage.css';
import { useState } from 'react';
import { adult } from '../../fixture';
import { href } from '../../shell/router';
import { Header } from './chrome';
import { Miller } from './miller';

export default function Results() {
  const [path, setPath] = useState<string[]>(['adult', 'duplicates', 'conflicting_target_labels', 'g1']);
  return (
    <div className="ps ps--app ps--results">
      <Header app />
      <section className="ps-runhead" style={{ ['--run' as string]: '#B4633B' }}>
        <div>
          <p className="ps-mono">1/6 Tables · {adult.file} · {adult.task}</p>
          <h1>Adult</h1>
        </div>
        <dl>
          <div><dt>Final</dt><dd>69.0<small>Elevated</small></dd></div>
          <div><dt>Evidence</dt><dd>89.15</dd></div>
          <div><dt>Guardrail</dt><dd>47.86<small>target balance</small></dd></div>
          <div><dt>Rows</dt><dd>48,842</dd></div>
        </dl>
        <a className="ps-btn ps-btn--line" href={href('passage', 'app')}>All runs</a>
      </section>
      <div className="ps-trail">
        <span className="ps-mono">Path</span>
        {path.map((p, i) => <button key={i} onClick={() => setPath(path.slice(0, i + 1))}>{p.replace(/_/g, ' ')}</button>)}
      </div>
      <Miller path={path} setPath={setPath} />
    </div>
  );
}
