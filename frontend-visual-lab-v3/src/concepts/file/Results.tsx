import '@fontsource/dm-serif-display/400.css';
import '@fontsource/dm-serif-display/400-italic.css';
import '@fontsource-variable/dm-sans';
import './file.css';
import { useState } from 'react';
import { adult } from '../../fixture';
import { Header } from './Landing';
import { Stack, states, type State } from './stack';

const evidenceFor: Partial<Record<State, number>> = { split: 1, disagree: 0, fences: 2 };

export default function Results() {
  const [st, setSt] = useState<State>('score');
  const s = states.find((x) => x.id === st)!;
  const fi = evidenceFor[st];
  return (
    <div className="fl fl--results">
      <Header here="results" />
      <div className={`fl-res f-${st}`}>
        <div className="fl-res__obj"><Stack state={st} /></div>
        <aside className="fl-res__t">
          <span className="fl-k">{adult.file} · {adult.generatedAt}</span>
          <h1>adult.csv, <em>{adult.finalScore.toFixed(1)}</em></h1>
          <p>{adult.band}. Evidence {adult.evidenceScore}, held at the cap by a target balance of 47.86.</p>
          <ol className="fl-steps">
            {states.slice(1).map((x) => <li key={x.id}><button type="button" aria-pressed={st === x.id} onClick={() => setSt(x.id)}><span>{x.k}</span><b>{x.figure}</b></button></li>)}
          </ol>
          <div className="fl-ev" aria-live="polite">
            <h2>{s.title}</h2>
            <p>{s.caption}</p>
            {fi != null && <><p className="fl-dim">{adult.findings[fi].impact}</p><p><b>Review.</b> {adult.findings[fi].review}</p><p className="fl-dim">{adult.findings[fi].scoreEffect}</p></>}
            {st === 'score' && <dl className="fl-dl">{adult.subScores.map((x) => <div key={x.key}><dt>{x.label}</dt><dd className={x.value <= 50 ? 'is-red' : ''}>{x.value}</dd></div>)}</dl>}
          </div>
          <p className="fl-dim fl-limits">{adult.limits}</p>
        </aside>
      </div>
    </div>
  );
}
