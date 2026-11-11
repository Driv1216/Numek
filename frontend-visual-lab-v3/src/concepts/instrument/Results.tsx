import '@fontsource-variable/instrument-sans';
import '@fontsource/instrument-serif/400.css';
import '@fontsource/instrument-serif/400-italic.css';
import '@fontsource-variable/jetbrains-mono';
import './instrument.css';
import { adult } from '../../fixture';
import { Header } from './Landing';
import { Instrument } from './Instrument';

export default function Results() {
  return (
    <div className="in in--results">
      <Header here="results" />
      <div className="in-apphead">
        <div><span className="in-kicker">{adult.file} · {adult.task} · {adult.generatedAt} · sha256 {adult.sha256.slice(0, 12)}…</span><h1><em>Adult, measured.</em></h1></div>
        <dl className="in-score">
          <div><dt>evidence</dt><dd>{adult.evidenceScore}</dd></div>
          <div><dt>guardrail</dt><dd>critical sub-score · cap 69</dd></div>
          <div className="is-final"><dt>final</dt><dd>{adult.finalScore.toFixed(1)} · {adult.band}</dd></div>
        </dl>
      </div>
      <Instrument run="adult" initial={5} />
      <section className="in-findings">
        <h2><em>The four findings, in full</em></h2>
        <ol>
          {adult.findings.map((f) => (
            <li key={f.code}>
              <span className="in-kicker">{f.severity} · {f.code}</span>
              <h3>{f.title}</h3>
              <p>{f.finding} {f.evidence}</p>
              <p className="in-dim">{f.impact}</p>
              <p><b>Review</b> {f.review}</p>
              <p className="in-mono">{f.scoreEffect}</p>
            </li>
          ))}
        </ol>
        <p className="in-dim in-limits">{adult.limits}</p>
      </section>
    </div>
  );
}
