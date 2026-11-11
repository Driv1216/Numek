import '@fontsource-variable/newsreader';
import '@fontsource-variable/newsreader/wght-italic.css';
import '@fontsource-variable/hanken-grotesk';
import '@fontsource/red-hat-mono/400.css';
import './footnote.css';
import { useState } from 'react';
import { adult } from '../../fixture';
import { Header } from './Landing';
import { RowChip, Token } from './inserts';

const notes: { n: number; title: string; body: string }[] = [
  { n: 1, title: 'Final score', body: `${adult.finalScore.toFixed(1)}, ${adult.band}. Bands: 85 and above Low, 70–84 Moderate, 50–69 Elevated, below 50 High.` },
  { n: 2, title: 'Evidence score', body: `The mean of five sub-scores: ${adult.subScores.map((s) => `${s.label.toLowerCase()} ${s.value}`).join(', ')}.` },
  { n: 3, title: 'Guardrail', body: `${adult.guardrail.label}: ${adult.guardrail.explanation} Any sub-score at or below 50 caps the final score at ${adult.guardrail.cap}.` },
  { n: 4, title: 'Conflicting labels', body: `${adult.findings[0].finding} ${adult.findings[0].evidence} ${adult.findings[0].scoreEffect}` },
  { n: 5, title: 'Target imbalance', body: `${adult.findings[1].evidence} ${adult.findings[1].scoreEffect}` },
  { n: 6, title: 'Outliers', body: `${adult.findings[2].evidence} 13,496 rows outside 32.5 – 52.5 hours. ${adult.findings[2].scoreEffect}` },
  { n: 7, title: 'Leakage review', body: `${adult.findings[3].evidence} ${adult.findings[3].scoreEffect}` },
];

export default function Results() {
  const [hl, setHl] = useState<number | null>(null);
  const Ref = ({ n }: { n: number }) => <a href={`#note-${n}`} className={`fn-sup ${hl === n ? 'is-on' : ''}`} onMouseEnter={() => setHl(n)} onMouseLeave={() => setHl(null)} onFocus={() => setHl(n)} onBlur={() => setHl(null)}><sup>{n}</sup></a>;
  return (
    <div className="fn fn--results">
      <Header here="results" />
      <div className="fn-res">
        <article className="fn-res__text">
          <p className="fn-paren">({adult.file} · {adult.task} · {adult.generatedAt} · sha256 {adult.sha256.slice(0, 12)}…)</p>
          <p className="fn-claim">The final reliability score is <Token value={adult.finalScore.toFixed(1)} label="final score" lines={[['Evidence', String(adult.evidenceScore)], ['Cap', '69'], ['Final', adult.finalScore.toFixed(1)]]} /><Ref n={1} /> — Elevated Risk under the current DataTrust methodology. Evidence score <Token value={String(adult.evidenceScore)} label="evidence score" lines={adult.subScores.map((s) => [s.label, String(s.value)] as [string, string])} /><Ref n={2} /> became the final score after an applied guardrail<Ref n={3} />: the target balance sub-score is 47.86, a critical weakness.</p>
          <p className="fn-claim">Five feature-identical groups contain more than one label<Ref n={4} /> <RowChip />; the majority class is 76.07%<Ref n={5} />; hours_per_week has 27.63% of values beyond its fences<Ref n={6} />; and marital_status is a review-only name<Ref n={7} />.</p>
          <p className="fn-claim fn-claim--next"><span className="fn-hl">Next:</span> {adult.nextAction}</p>
          <p className="fn-small">{adult.limits}</p>
          <p className="fn-paren">(The report’s eight topics)</p>
          <ol className="fn-topics">{adult.topics.map((t) => <li key={t}>{t}</li>)}</ol>
        </article>
        <aside className="fn-res__notes" aria-label="Footnotes">
          <p className="fn-paren">(Notes)</p>
          <ol>{notes.map((x) => <li key={x.n} id={`note-${x.n}`} className={hl === x.n ? 'is-on' : ''}><sup>{x.n}</sup><b>{x.title}</b><p>{x.body}</p></li>)}</ol>
        </aside>
      </div>
    </div>
  );
}
