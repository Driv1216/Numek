import '@fontsource-variable/newsreader/opsz.css';
import '@fontsource-variable/newsreader/opsz-italic.css';
import '@fontsource-variable/familjen-grotesk';
import './issue.css';
import { useEffect, useState } from 'react';
import { adult } from '../../fixture';
import { fmt } from '../../shell/motion';
import { Masthead } from './parts';

const ids = ['decision', 'actions', 'overview', 'target', 'missing', 'duplicates', 'method', 'appendix'];
const notes: Record<string, { k: string; t: string }> = {
  n1: { k: 'Note 1 · Guardrail', t: 'A guardrail caps the overall score when any sub-score is critical. Here target balance is 47.86, so the 89.15 evidence score is held at 69.0.' },
  n2: { k: 'Note 2 · Baseline', t: 'The majority baseline is the accuracy of always predicting the largest class. It is context, not a model-quality result.' },
  n3: { k: 'Note 3 · Conflicting labels', t: 'A conflicting-label group has identical recorded feature values but more than one non-missing label. It needs context review and is not automatically treated as a labeling error.' },
  n4: { k: 'Note 4 · Leakage names', t: 'Name-based prompts are review-only unless the name is strongly outcome-like. marital_status changes no score; confirm when its value becomes available.' },
};

export default function Results() {
  const [on, setOn] = useState('decision');
  const [hl, setHl] = useState<string | null>(null);
  useEffect(() => {
    const io = new IntersectionObserver((es) => es.forEach((e) => e.isIntersecting && setOn(e.target.id)), { rootMargin: '-30% 0px -60% 0px' });
    ids.forEach((id) => { const el = document.getElementById(id); if (el) io.observe(el); });
    return () => io.disconnect();
  }, []);
  const Fn = ({ n }: { n: string }) => <button className="is-fn" onClick={() => { setHl(n); document.getElementById(n)?.scrollIntoView({ behavior: 'smooth', block: 'center' }); }} aria-label={`Show ${notes[n].k}`}>{n.slice(1)}</button>;
  const groups = adult.conflicts;

  return (
    <div className="is is--read">
      <Masthead compact />
      <div className="is-room">
        <nav className="is-rail" aria-label="Chapters">
          <p className="is-rail__issue">Issue 01 · Adult · {adult.generatedAt.slice(0, 10)}</p>
          <ol>
            {adult.topics.map((t, i) => (
              <li key={t}><a href={`#${ids[i]}`} className={on === ids[i] ? 'is-on' : ''} onClick={(e) => { e.preventDefault(); document.getElementById(ids[i])?.scrollIntoView({ behavior: 'smooth' }); }}><span>{String(i + 1).padStart(2, '0')}</span>{t}</a></li>
            ))}
          </ol>
          <div className="is-rail__tools">
            <button>Download PDF</button>
            <button>Open canonical HTML</button>
            <button>Export strict JSON</button>
          </div>
        </nav>

        <article className="is-measure">
          <section id="decision">
            <p className="is-sec-k">01 · Decision summary</p>
            <div className="is-decision"><b>69.0</b><em>Elevated</em><small>Final reliability score under the current DataTrust methodology. Evidence score 89.15 before guardrails.<Fn n="n1" /></small></div>
            <p className="is-dropcap">The final reliability score is 69.0 — elevated risk — held there by one weak measure rather than many. The target is dominated by one class: the majority baseline is 76.07%<Fn n="n2" />, and the target-balance sub-score of 47.86 is critical enough to cap everything else.</p>
            <p>The principal evidence is quieter. Five groups of rows are identical in every recorded feature and still disagree on the label<Fn n="n3" />. That changes no score, but it is the first thing a reviewer should read.</p>
            <p><i>Recommended next action:</i> {adult.nextAction}</p>
          </section>
          <section id="actions">
            <p className="is-sec-k">02 · Priority actions</p>
            <h2>Four findings, in order</h2>
            {adult.findings.map((f, i) => (
              <div key={f.code} className="is-art">
                <span className="is-art__k" style={{ fontFamily: 'var(--sans)', fontSize: 12.5, letterSpacing: '.12em', textTransform: 'uppercase' }}>{String(i + 1).padStart(2, '0')} · {f.severity}</span>
                <h3>{f.title}{f.code === 'leakage_review_prompts' && <Fn n="n4" />}</h3>
                <dl>
                  <dt>Finding</dt><dd>{f.finding}</dd>
                  <dt>Evidence</dt><dd>{f.evidence}</dd>
                  <dt>Modelling impact</dt><dd>{f.impact}</dd>
                  <dt>Review</dt><dd>{f.review}</dd>
                  <dt>Score effect</dt><dd>{f.scoreEffect}</dd>
                </dl>
              </div>
            ))}
          </section>
          <section id="overview">
            <p className="is-sec-k">03 · Dataset overview</p>
            <h2>48,842 rows, 15 columns</h2>
            <p>Fourteen features — six numeric, eight non-numeric — and one target, {adult.target}. Missing cells are 0.88% of the table; repeated rows 0.11%.</p>
          </section>
          <section id="target">
            <p className="is-sec-k">04 · Target and label evidence</p>
            <h2>Two classes, one dominant</h2>
            <figure className="is-fig">
              <div className="is-bars">
                <div className="is-ox"><span>≤50K</span><i style={{ width: '76.07%' }} /><span>{fmt(adult.classes.le50k)} · 76.07%</span></div>
                <div><span>&gt;50K</span><i style={{ width: '23.93%' }} /><span>{fmt(adult.classes.gt50k)} · 23.93%</span></div>
              </div>
              <figcaption>Figure 4.1 · Target distribution. Class calculations exclude 0 rows without target labels. Majority : minority 3.18 : 1.</figcaption>
            </figure>
          </section>
          <section id="missing">
            <p className="is-sec-k">05 · Missingness evidence</p>
            <h2>Minimal, and in three places</h2>
            <p>6,465 of 683,788 feature cells (0.95%) are missing, affecting 7.41% of rows. No feature column is severe.</p>
            <figure className="is-fig">
              <div className="is-bars">
                {Object.entries(adult.missing.byColumn).sort((a, b) => b[1] - a[1]).map(([c, n]) => (
                  <div key={c}><span>{c}</span><i style={{ width: `${(n / 2809) * 100}%` }} /><span>{fmt(n)} · {((n / adult.rows) * 100).toFixed(2)}%</span></div>
                ))}
              </div>
              <figcaption>Figure 5.1 · Missing values by feature. Rows missing one feature: 821; two: 2,753; three or more: 46.</figcaption>
            </figure>
          </section>
          <section id="duplicates">
            <p className="is-sec-k">06 · Duplicate and feature evidence</p>
            <h2>Five groups that disagree</h2>
            <p>52 repeated rows across 49 exact duplicate groups; the largest has three rows. Five feature-identical groups carry conflicting labels:</p>
            <figure className="is-fig">
              <table className="is-gtable">
                <thead><tr><th>Group</th><th>Rows</th><th>age</th><th>education</th><th>occupation</th><th>hours</th><th>Labels</th></tr></thead>
                <tbody>{groups.map((g) => <tr key={g.id}><td>{g.id}</td><td>{g.rows.join(', ')}</td><td>{String(g.features.age)}</td><td>{String(g.features.education)}</td><td>{String(g.features.occupation ?? '—')}</td><td>{String(g.features.hours_per_week)}</td><td className="lbl">{g.labels.join(' / ')}</td></tr>)}</tbody>
              </table>
              <figcaption>Figure 6.1 · Feature-identical groups with conflicting non-missing target labels. All 14 features match within each group; four of the fourteen are shown here.</figcaption>
            </figure>
          </section>
          <section id="method">
            <p className="is-sec-k">07 · Scoring, methodology and limitations</p>
            <h2>What this issue does not say</h2>
            <p>{adult.limits}</p>
          </section>
          <section id="appendix">
            <p className="is-sec-k">08 · Technical appendix</p>
            <h2>Every column</h2>
            <table className="is-gtable">
              <thead><tr><th>Column</th><th>Type</th><th>Missing</th><th>Unique</th><th>Top share</th><th>Outliers</th></tr></thead>
              <tbody>{adult.columnEvidence.map((c) => <tr key={c.name}><td>{c.name}</td><td>{c.type}</td><td>{c.missing}</td><td>{c.unique}</td><td>{c.top_share}</td><td>{c.outliers}</td></tr>)}</tbody>
            </table>
          </section>
        </article>

        <aside className="is-margin" aria-label="Notes">
          {Object.entries(notes).map(([id, n]) => (
            <div key={id} id={id} className={`is-note ${hl === id ? 'is-hl' : ''}`}><b>{n.k}</b>{n.t}</div>
          ))}
          <div className="is-note"><b>Source</b>{adult.file} · sha256 {adult.sha256.slice(0, 20)}… · {adult.source}</div>
          <div className="is-note"><b>Printed</b>Locally in {adult.runtimeSeconds.toFixed(2)} s · HTML canonical · PDF and JSON from the same completed result.</div>
        </aside>
      </div>
    </div>
  );
}
