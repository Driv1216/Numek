import '@fontsource/ibm-plex-sans/300.css';
import '@fontsource/ibm-plex-sans/400.css';
import '@fontsource/ibm-plex-sans/500.css';
import '@fontsource/ibm-plex-mono/400.css';
import './cutaway.css';
import { useState } from 'react';
import { adult } from '../../fixture';
import { Header } from './Landing';
import { Slab, partBox, type Part } from './iso';

const parts: Part[] = ['lift', 'target', 'section', 'leak'];
const box = (b: number[]) => b.map((v) => v.toFixed(1)).join(' ');

export default function Results() {
  const [sel, setSel] = useState(-1);
  // Frame the slab, the lifted rows and the section together.
  const bs = (['all', 'lift', 'section'] as Part[]).map((p) => partBox('adult', p));
  const x0 = Math.min(...bs.map((b) => b[0])), y0 = Math.min(...bs.map((b) => b[1]));
  const view = [x0, y0, Math.max(...bs.map((b) => b[0] + b[2])) - x0, Math.max(...bs.map((b) => b[1] + b[3])) - y0];
  return (
    <div className="cw cw--results">
      <Header here="results" />
      <div className="cw-res">
        <section className="cw-res__draw" aria-label="Adult cutaway">
          <span>{adult.file} · {adult.task} · {adult.generatedAt} · sha256 {adult.sha256.slice(0, 12)}…</span>
          <h1>Adult, cut open.</h1>
          <svg className="cw-svg" viewBox={box(view)} role="img" aria-label="Full cutaway of Adult with the lifted conflicting rows and the hours_per_week section">
            <Slab run="adult" focus={sel >= 0 ? parts[sel] : 'all'} lift section />
          </svg>
        </section>
        <aside className="cw-side" aria-label="Findings and score">
          <h2>FINDINGS · {adult.findings.length}</h2>
          {adult.findings.map((f, i) => (
            <button key={f.code} type="button" className={`cw-fnd ${i === sel ? 'is-on' : ''}`} aria-pressed={i === sel} onClick={() => setSel(i === sel ? -1 : i)}>
              <span>{f.severity} · {f.scoreEffect.startsWith('Evidence only') ? 'evidence only' : 'changes the score'}</span>
              <b>{f.title}</b>
              <p>{f.finding} {f.evidence}</p>
              {i === sel && <p><i>Review:</i> {f.review}</p>}
            </button>
          ))}
          <h2 style={{ marginTop: 14 }}>SCORE · AS CALCULATED</h2>
          <div className="cw-calc">
            {adult.subScores.map((s) => <div key={s.key}><span>{s.label}</span><span className={s.value <= 50 ? 'is-red' : ''}>{s.value}</span></div>)}
            <div><span>Evidence = mean of five</span><span>{adult.evidenceScore}</span></div>
            <div><span>Guardrail · target balance ≤ 50</span><span className="is-red">cap 69</span></div>
            <div><span>Final</span><span className="is-blue">{adult.finalScore.toFixed(1)} · {adult.band}</span></div>
          </div>
          <p className="cw-dim" style={{ fontSize: 12.5, lineHeight: 1.5 }}>{adult.limits}</p>
        </aside>
      </div>
    </div>
  );
}
