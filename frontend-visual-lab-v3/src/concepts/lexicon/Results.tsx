import '@fontsource-variable/fraunces/full.css';
import '@fontsource-variable/fraunces/full-italic.css';
import '@fontsource-variable/work-sans';
import '@fontsource/dm-mono/400.css';
import './lexicon.css';
import { adult } from '../../fixture';
import { entries } from './entries';
import { Header } from './parts';

const E = Object.fromEntries(entries.map((e) => [e.id, e]));
const senses: { id: string; tags: string[]; score?: boolean; quote?: string; note?: string }[] = [
  { id: 'imbalance', tags: ['Moderate', 'Target balance 47.86 · critical', 'Caps the score at 69'], score: true },
  { id: 'excess', tags: ['Moderate', 'hours_per_week', 'Feature usability 98.86'], score: true },
  { id: 'ambiguity', tags: ['Moderate', 'Evidence only'], quote: E.ambiguity.frags[0].t + '\n' + E.ambiguity.frags[1].t },
  { id: 'hindsight', tags: ['Low', 'marital_status', 'Review only · leakage risk 100'] },
  { id: 'absence', tags: ['No finding', 'Completeness 99.12'], note: 'workclass 2,799 · occupation 2,809 · native_country 857' },
  { id: 'repetition', tags: ['No finding', 'Uniqueness 99.89'] },
  { id: 'constancy', tags: ['Near-constant', 'capital_loss · 95.33%'] },
];

export default function Results() {
  return (
    <div className="lx lx--results">
      <Header here="results" />
      <article className="lx-page">
        <div className="lx-running"><span>Adult — {adult.file}</span><span>{adult.generatedAt}</span></div>
        <header className="lx-head-word">
          <div>
            <h1>Adult<i>n.</i></h1>
            <p>{adult.source}. {adult.rows.toLocaleString()} rows, {adult.columns} columns; target {adult.target}. {adult.task}. Read locally in {adult.runtimeSeconds.toFixed(2)} s.</p>
          </div>
          <div className="lx-score"><b>{adult.finalScore.toFixed(1)}</b><span>{adult.band} · evidence {adult.evidenceScore}</span></div>
        </header>
        <div className="lx-cols">
          {senses.map((s, i) => {
            const e = E[s.id];
            const hit = e.in.find((x) => x.run === 'Adult')!;
            return (
              <section key={s.id} className={`lx-sense ${s.tags[0] === 'No finding' ? 'lx-sense--none' : ''}`}>
                <h2>{i + 1}. {e.word}<small>{e.sense}</small></h2>
                <p>{hit.line}</p>
                {s.quote && <p className="lx-quote" style={{ whiteSpace: 'pre-wrap' }}>{s.quote}</p>}
                {s.note && <p className="lx-dim" style={{ fontSize: 13 }}>{s.note}</p>}
                <p>{e.effect}</p>
                <div className="lx-tags">{s.tags.map((t) => <span key={t} className={s.score && t.includes('score') ? 'is-score' : ''}>{t}</span>)}</div>
              </section>
            );
          })}
          <section className="lx-sense">
            <h2>Reliability<small>how the number was made</small></h2>
            <div className="lx-subs">
              {adult.subScores.map((s) => (
                <div key={s.key} className={'critical' in s && s.critical ? 'is-crit' : ''}><span>{s.label}</span><i style={{ ['--w' as string]: `${s.value}%` }} /><b>{s.value}</b></div>
              ))}
            </div>
            <p>{adult.guardrail.explanation} Evidence {adult.evidenceScore} → final {adult.finalScore.toFixed(1)}, {adult.band}.</p>
            <p className="lx-dim" style={{ fontSize: 13 }}>{adult.limits}</p>
          </section>
        </div>
      </article>
    </div>
  );
}
