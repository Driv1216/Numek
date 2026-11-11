import '@fontsource-variable/schibsted-grotesk';
import '@fontsource-variable/source-serif-4';
import './every-row.css';
import { useState, type ReactNode } from 'react';
import { adult } from '../../fixture';
import { href } from '../../shell/router';
import { Wordmark } from './chrome';
import { FieldView } from './FieldView';
import { arrangements, type Arrangement } from './layouts';

const findingArr: Record<string, Arrangement> = {
  conflicting_target_labels: 'conflicts', target_imbalance: 'target', numeric_outlier_concentration: 'outliers', leakage_review_prompts: 'accounted',
};
const tone: Record<Arrangement, string> = { population: 'var(--ink)', target: 'var(--teal)', missing: 'var(--amber)', duplicates: 'var(--mag)', conflicts: 'var(--mag)', outliers: 'var(--violet)', accounted: 'var(--ink)' };

export default function Results() {
  const [a, setA] = useState<Arrangement>('conflicts');
  const [open, setOpen] = useState<string | null>('conflicting_target_labels');
  const L = ({ to, children }: { to: Arrangement; children: ReactNode }) => (
    <button className={`er-link ${a === to ? 'is-on' : ''}`} style={{ ['--c' as string]: tone[to] }} onClick={() => setA(to)}>{children}</button>
  );

  return (
    <div className="er er--results">
      <header className="er-appbar">
        <Wordmark />
        <nav aria-label="Workspace">
          <a href={href('every-row', 'app')}>Runs</a>
          <a aria-current="page" href={href('every-row', 'results')}>Adult</a>
          <a href={href('every-row', 'results')}>Methodology</a>
        </nav>
        <div className="er-appbar__r"><span><i className="er-dot" />Generated {adult.generatedAt} · local</span><a className="er-btn er-btn--s er-btn--ghost" href={href('every-row', 'results')}>Export HTML · PDF · JSON</a></div>
      </header>
      <div className="er-res">
        <article className="er-narr">
          <h1>Adult</h1>
          <p className="er-narr__meta">{adult.file} · {adult.task} · target {adult.target} · 48,842 × 15</p>
          <div className="er-verdict"><b>69.0</b><span>Elevated</span><small>Evidence score 89.15, capped at 69.0 by the critical-sub-score guardrail.</small></div>
          <p>Of <L to="population">48,842 rows</L>, <L to="target">76.07% fall in one class</L>: the majority baseline, and the reason target balance scores 47.86 — low enough to hold the overall score at 69.0.</p>
          <p><L to="conflicts">Five feature-identical groups</L> disagree on the label. Ten rows; evidence only, no score effect. Review whether they are label errors, repeated people over time, target updates, or omitted features.</p>
          <p><L to="outliers">hours_per_week</L> has 13,496 rows outside the IQR fences. <L to="missing">3,620 rows</L> have a missing feature, and <L to="duplicates">52 repeat</L> exactly. marital_status is a review-only name prompt.</p>
          <p style={{ fontSize: 15, color: 'var(--ink-2)' }}>{adult.nextAction}</p>
          <div className="er-findings">
            {adult.findings.map((f) => (
              <div key={f.code} className="er-finding">
                <button aria-expanded={open === f.code} onClick={() => { setOpen(open === f.code ? null : f.code); setA(findingArr[f.code]); }}>
                  <i style={{ background: tone[findingArr[f.code]] }} />{f.title}<span>{f.severity}</span>
                </button>
                {open === f.code && (
                  <dl>
                    <div><dt>Finding</dt><dd>{f.finding}</dd></div>
                    <div><dt>Evidence</dt><dd>{f.evidence}</dd></div>
                    <div><dt>Possible modelling impact</dt><dd>{f.impact}</dd></div>
                    <div><dt>Review</dt><dd>{f.review}</dd></div>
                    <div><dt>Score effect</dt><dd>{f.scoreEffect}</dd></div>
                  </dl>
                )}
              </div>
            ))}
          </div>
          <p style={{ fontSize: 13.5, color: 'var(--mute)', marginTop: 24 }}>{adult.limits}</p>
        </article>
        <section className="er-canvaswrap" aria-label="All rows">
          <div className="er-tabs" role="toolbar" aria-label="Arrange rows by">
            {arrangements.map((x) => (
              <button key={x.id} aria-pressed={a === x.id} onClick={() => setA(x.id)}>{x.label}{x.count && <small>{x.count}</small>}</button>
            ))}
          </div>
          <div className="er-stage">
            <FieldView arrangement={a} area={(w, h) => ({ x: 28, y: 56, w: w - 56, h: h - 80 })} />
          </div>
          <div className="er-legend">
            <span><i style={{ background: 'var(--slate)' }} />≤50K</span>
            <span><i style={{ background: 'var(--teal)' }} />&gt;50K</span>
            <span><i style={{ background: 'var(--amber)' }} />Missing feature</span>
            <span><i style={{ background: 'var(--mag)' }} />Duplicate or conflicting label</span>
            <span><i style={{ background: 'var(--violet)' }} />hours_per_week outside fences</span>
            <span style={{ marginLeft: 'auto' }}>One square per row · hover for values</span>
          </div>
        </section>
      </div>
    </div>
  );
}
