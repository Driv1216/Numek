import './line.css';
import { useState } from 'react';
import { adult } from '../../fixture';
import { Branches, Columns, ReportStack, RowsStack, ScoreJoin } from './draw';
import { Header } from './Landing';

/** Which finding each check branch opens. */
const branchFinding = [-1, -1, 1, 0, 2, 3];

export default function Results() {
  const [b, setB] = useState(3);
  const fi = branchFinding[b];
  const f = fi >= 0 ? adult.findings[fi] : null;
  return (
    <div className="ln ln--results">
      <Header here="results" />
      <section className="ln-res-h">
        <span className="ln-mono ln-amber">{adult.file} · {adult.generatedAt} · sha256 {adult.sha256.slice(0, 12)}…</span>
        <h1>The Adult line, end to end.</h1>
        <p className="ln-dim">Scroll sideways along the line. Select a check to open its evidence.</p>
      </section>
      <div className="ln-strip" tabIndex={0} aria-label="The Adult pipeline, scrollable horizontally">
        {[['01 Read', <RowsStack key="r" />], ['02 Profile', <Columns key="p" />], ['03 Check', <Branches key="c" active={b} />], ['04 Score', <ScoreJoin key="s" />], ['05 Report', <ReportStack key="o" />]].map(([k, d]) => (
          <figure key={k as string} className="ln-strip__s"><figcaption className="ln-mono ln-amber">{k as string}</figcaption>{d}</figure>
        ))}
      </div>
      <section className="ln-ev">
        <div className="ln-seg" role="radiogroup" aria-label="Checks">
          {['Completeness', 'Uniqueness', 'Target balance', 'Conflicting labels', 'Outliers', 'Leakage'].map((k, i) => <button key={k} type="button" role="radio" aria-checked={i === b} onClick={() => setB(i)}>{k}</button>)}
        </div>
        {f ? (
          <div className="ln-ev__b">
            <span className="ln-mono ln-amber">{f.severity} · {f.scoreEffect.startsWith('Evidence only') ? 'evidence only' : 'changes the score'}</span>
            <h2>{f.title}</h2>
            <p>{f.finding} {f.evidence}</p>
            <p className="ln-dim">{f.impact}</p>
            <p><b>Review.</b> {f.review}</p>
            <p className="ln-mono ln-dim">{f.scoreEffect}</p>
          </div>
        ) : (
          <div className="ln-ev__b">
            <span className="ln-mono ln-amber">No finding · recorded as evidence</span>
            <h2>{b === 0 ? 'Completeness 99.12' : 'Uniqueness 99.89'}</h2>
            <p>{b === 0 ? `${adult.missing.cells.toLocaleString()} empty cells in workclass (${adult.missing.byColumn.workclass.toLocaleString()}), occupation (${adult.missing.byColumn.occupation.toLocaleString()}) and native_country (${adult.missing.byColumn.native_country}); ${(adult.missing.rows.one + adult.missing.rows.two + adult.missing.rows.three_plus).toLocaleString()} rows touched.` : `${adult.duplicates.groups} groups of exact duplicates, ${adult.duplicates.repeated_rows} repeated rows, the largest group has ${adult.duplicates.largest} copies.`}</p>
            <p className="ln-dim">Feeds the sub-score without raising a finding.</p>
          </div>
        )}
      </section>
    </div>
  );
}
