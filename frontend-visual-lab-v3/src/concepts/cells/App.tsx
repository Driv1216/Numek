import '@fontsource-variable/space-grotesk';
import '@fontsource/space-mono/400.css';
import '@fontsource/space-mono/700.css';
import './cells.css';
import { useState } from 'react';
import { runFindings, runs, subScoresByRun } from '../../fixture';
import { href } from '../../shell/router';
import { Glyph, Header } from './Landing';

export default function App() {
  const [run, setRun] = useState('adult');
  const [sel, setSel] = useState<number | null>(null);
  const r = runs.find((x) => x.id === run)!;
  const f = runFindings[run] ?? [];
  const subs = subScoresByRun[run];
  return (
    <div className="ce ce--app">
      <Header here="app" />
      <div className="ce-ws">
        <nav className="ce-runs" aria-label="Local runs">
          <span className="ce-k">RUNS · {runs.length}</span>
          {runs.map((x, i) => (
            <button key={x.id} type="button" aria-pressed={x.id === run} className={x.id === run ? 'is-on' : ''} onClick={() => { setRun(x.id); setSel(null); }}>
              <span className="ce-k">{String(i + 1).padStart(2, '0')}</span><b>{x.name}</b><em>{x.score == null ? '—' : x.score.toFixed(1)}</em>
            </button>
          ))}
        </nav>
        <main className="ce-grid ce-grid--app">
          <div className="ce-c ce-c--w8 ce-c--title"><span className="ce-k">{r.file.toUpperCase()} · {r.task.toUpperCase()}</span><b>{r.name}</b></div>
          <div className="ce-c ce-c--w4"><Glyph id={r.rep} /><em>per {r.rep === 'tables' ? 'row' : r.rep === 'outcomes' ? 'value' : r.rep === 'text' ? 'sentence' : r.rep === 'images' ? 'image' : 'pair'}</em></div>
          <div className={`ce-c ce-c--w4 ${r.score != null ? 'ce-c--acc' : ''}`}><span className="ce-k">FINAL</span><b className="ce-xl">{r.score == null ? '—' : r.score.toFixed(1)}</b><em>{r.score == null ? 'no score defined, by design' : r.band}</em></div>
          <div className="ce-c ce-c--w4"><span className="ce-k">SIZE</span><b>{r.size}</b><em>{r.when}</em></div>
          <div className="ce-c ce-c--w4 ce-c--dark"><span className="ce-k">RUNTIME</span><b>{r.runtime}</b><em>local · 0 network calls</em></div>
          {subs ? subs.map((s) => <div key={s.label} className={`ce-c ce-c--w2 ${s.value <= 50 ? 'ce-c--acc2' : ''}`}><span className="ce-k">{s.label.toUpperCase()}</span><b>{s.value}</b></div>) : <div className="ce-c ce-c--w10"><span className="ce-k">SUB-SCORES</span><p>Not defined for {r.task.toLowerCase()}. Findings are reported as evidence.</p></div>}
          <div className="ce-c ce-c--w2 ce-c--dither" aria-hidden="true" />
          {f.length === 0 && <div className="ce-c ce-c--w12"><span className="ce-k">REPORTED</span><p>{r.lead}.</p></div>}
          {f.map((x, i) => (
            <button key={x.title} type="button" className={`ce-c ce-c--w${f.length === 4 ? 3 : f.length === 3 ? 4 : f.length === 2 ? 6 : 3} ce-f ${sel === i ? 'is-lit' : ''}`} aria-pressed={sel === i} onClick={() => setSel(sel === i ? null : i)}>
              <span className="ce-k">{String(i + 1).padStart(2, '0')} · {x.severity.toUpperCase()}</span><b>{x.title}</b><em>{x.effect === 'score' ? 'Changes a sub-score' : x.effect === 'evidence' ? 'Evidence only' : 'No score defined'}</em>
            </button>
          ))}
          {sel != null && f[sel] && <div className="ce-c ce-c--w12 ce-c--ev"><span className="ce-k">EVIDENCE · {f[sel].title.toUpperCase()}</span><p>{f[sel].evidence}</p>{run === 'adult' && <a href={href('cells', 'results')}>Open the Adult report in cells →</a>}</div>}
        </main>
      </div>
    </div>
  );
}
