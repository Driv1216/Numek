import '@fontsource-variable/newsreader/opsz.css';
import '@fontsource-variable/newsreader/opsz-italic.css';
import '@fontsource-variable/familjen-grotesk';
import './issue.css';
import { adult, local, runs } from '../../fixture';
import { useCount, useInView, useScrollProgress } from '../../shell/motion';
import { href } from '../../shell/router';
import { Cover, Masthead } from './parts';

const pages = ['01', '02', '03', '04', '05', '06', '07', '08'];
const topicNotes = [
  'Score, assessment, principal evidence, next action',
  'Four findings in severity order, each with its score effect',
  '48,842 rows, 15 columns, 14 features',
  'Two classes and a 76.07% majority baseline',
  '6,465 missing cells across three columns',
  '49 duplicate groups, 5 that disagree on the label',
  'Five sub-scores, one guardrail, and what is not covered',
  'Complete evidence for every column',
];

export default function Landing() {
  const [coverRef, p] = useScrollProgress<HTMLDivElement>('pinned');
  const [scoreRef, seen] = useInView<HTMLDivElement>();
  const score = useCount(69, seen, 1400, 1);
  return (
    <div className="is is--landing">
      <Masthead />
      <div className="is-coverwrap" ref={coverRef}>
        <section className="is-hero" style={{ transform: `scale(${1 - p * 0.08}) translateY(${p * -4}vh)`, borderRadius: p * 18, opacity: 1 - p * 0.35 }}>
          <div className="is-hero__top">
            <span>Issue 01</span><span>The Adult dataset</span><span>48,842 rows × 15 columns</span><span>13 August 2026</span>
          </div>
          <div className="is-hero__grid" ref={scoreRef}>
            <div className="is-hero__score">
              <span className="is-hero__num" aria-label="69.0">{score}</span>
              <span className="is-hero__band"><em>Elevated</em> — held there by one weak measure.</span>
            </div>
            <ol className="is-coverlines">
              <li><b>Ten rows, five identical pairs, two answers.</b><span>Conflicting labels · p. 06</span></li>
              <li><b>Why a 76% baseline holds the score at 69.0.</b><span>Target evidence · p. 04</span></li>
              <li><b>hours_per_week, outside the fences.</b><span>Priority actions · p. 02</span></li>
              <li><b>marital_status: a question, not a penalty.</b><span>Leakage review · p. 06</span></li>
            </ol>
          </div>
          <p className="is-hero__foot">DataTrust is NUMEK’s evidence-based reliability analysis for the datasets behind ML and AI. Every issue is computed and printed on your own machine — this one in 0.18 seconds.</p>
        </section>
      </div>

      <section className="is-contents" aria-labelledby="contents-h">
        <div className="is-contents__head">
          <h2 id="contents-h">In this issue</h2>
          <p>Every DataTrust report has the same eight chapters, so a CTO, a risk reviewer and the engineer who ran it can find the same thing on the same page.</p>
        </div>
        <ol className="is-toc">
          {adult.topics.map((t, i) => (
            <li key={t}>
              <a href={href('issue', 'results')}>
                <span className="is-toc__n">{String(i + 1).padStart(2, '0')}</span>
                <span className="is-toc__t">{t}<small>{topicNotes[i]}</small></span>
                <span className="is-toc__lead" aria-hidden="true" />
                <span className="is-toc__p">{pages[i]}</span>
              </a>
            </li>
          ))}
        </ol>
      </section>

      <section className="is-chapter is-chapter--decision">
        <div className="is-chapter__head">
          <span className="is-chapter__no">01</span>
          <h2>The decision</h2>
          <div className="is-chapter__intro">
            <p>{adult.narrative}</p>
          </div>
          <div className="is-inthis">
            <p>In this chapter</p>
            <ul><li>The final score and band</li><li>Why the evidence score was capped</li><li>Principal evidence</li><li>The recommended next action</li></ul>
          </div>
        </div>
        <figure className="is-path">
          <div><span>Evidence score</span><b>89.15</b></div>
          <div className="is-path__arrow" aria-hidden="true"><i /><span>Guardrail · critical sub-score<br />Target balance 47.86</span></div>
          <div><span>Final score</span><b>69.0</b><em>Elevated</em></div>
          <figcaption>Score path. Five transparent sub-scores feed the evidence score; an explained guardrail caps it, so a severe weakness cannot hide behind healthy averages.</figcaption>
        </figure>
      </section>

      <section className="is-chapter is-chapter--evidence">
        <div className="is-chapter__head">
          <span className="is-chapter__no">02</span>
          <h2>Priority actions</h2>
          <div className="is-chapter__intro"><p>Four findings, ordered by severity. Each says what was found, what it may do to a model, what to review — and whether it changed the score.</p></div>
        </div>
        <div className="is-articles">
          {adult.findings.map((f, i) => (
            <article key={f.code}>
              <span className="is-art__k">{String(i + 1).padStart(2, '0')} · {f.severity}</span>
              <h3>{f.title}</h3>
              <p className="is-art__stand">{f.finding}</p>
              <p><b>Evidence.</b> {f.evidence}</p>
              <p><b>Review.</b> {f.review}</p>
              <p className="is-art__eff">{f.scoreEffect}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="is-chapter is-chapter--method">
        <div className="is-chapter__head">
          <span className="is-chapter__no">07</span>
          <h2>What the score is, and is not</h2>
          <div className="is-chapter__intro"><p>Classification issues carry five sub-scores and explained guardrails. Regression, text, image and connected-document issues carry evidence without a universal score — by design, not omission.</p></div>
        </div>
        <div className="is-method">
          <table className="is-subs">
            <caption>Sub-scores · Issue 01</caption>
            <tbody>
              {adult.subScores.map((s) => (
                <tr key={s.key} className={s.critical ? 'is-crit' : ''}><th>{s.label}</th><td><i style={{ width: `${s.value}%` }} /></td><td>{s.value.toFixed(2)}</td></tr>
              ))}
            </tbody>
          </table>
          <blockquote className="is-pull">
            “Findings support human review; they do not prove causation or prescribe automatic cleaning.”
            <cite>From the methodology chapter of every issue</cite>
          </blockquote>
        </div>
        <p className="is-notincl"><b>Not included</b> label-noise estimation · drift · fairness · calibration · semantic date validation · fuzzy category normalization · feature correlation · compliance · certification</p>
      </section>

      <section className="is-print">
        <div className="is-print__head">
          <h2>The printed issue</h2>
          <p>HTML is canonical. The PDF opens with portrait decision pages and closes with a landscape technical appendix. Strict JSON carries every computed value.</p>
        </div>
        <Spread />
      </section>

      <section className="is-back">
        <div className="is-back__head">
          <h2>Back issues</h2>
          <p>Tables, outcomes, text, images and connected documents. Only classification issues carry a score; the others say so on the cover.</p>
        </div>
        <div className="is-back__grid">
          {runs.slice(1).map((r, i) => <Cover key={r.id} run={r} no={i + 2} size="s" />)}
        </div>
      </section>

      <section className="is-colophon" id="colophon">
        <h2>Colophon</h2>
        <dl>
          <div><dt>Printed on</dt><dd>Your machine. The browser interface binds to {local.host}; nothing is uploaded.</dd></div>
          <div><dt>Source</dt><dd>{adult.file} · sha256 {adult.sha256.slice(0, 16)}…</dd></div>
          <div><dt>Method</dt><dd>DataTrust classification methodology · eight-topic canonical report</dd></div>
          <div><dt>Models</dt><dd>None for this issue. Optional local models are pinned files you provision; nothing is downloaded at run time.</dd></div>
          <div><dt>Formats</dt><dd>HTML · PDF · JSON</dd></div>
          <div><dt>Publisher</dt><dd>NUMEK, AI reliability verification. Model confidence and LLM grounding are research directions, not products.</dd></div>
        </dl>
      </section>

      <footer className="is-foot">
        <h2>Read your own<br /><em>first issue.</em></h2>
        <code>$ {local.commands[1]}</code>
        <a className="is-btn" href={href('issue', 'app')}>Open DataTrust</a>
      </footer>
    </div>
  );
}

function Spread() {
  const [ref, seen] = useInView<HTMLDivElement>();
  return (
    <div className={`is-spread ${seen ? 'is-in' : ''}`} ref={ref}>
      <div className="is-page is-page--p" style={{ ['--i' as string]: 0 }}>
        <span className="is-page__run">Adult · DataTrust Reliability Report · 1</span>
        <span className="is-page__h">1. Decision Summary</span>
        <span className="is-page__score">69.0</span>
        <span className="is-page__band">Elevated Risk</span>
        <span className="is-page__txt">Evidence score 89.15 → final score 69.0 after applied guardrails.</span>
        {adult.findings.slice(0, 3).map((f) => <span key={f.code} className="is-page__item"><b>{f.title}</b> ({f.severity})</span>)}
      </div>
      <div className="is-page is-page--p" style={{ ['--i' as string]: 1 }}>
        <span className="is-page__run">Adult · DataTrust Reliability Report · 2</span>
        <span className="is-page__h">2. Priority Actions</span>
        {adult.findings.map((f) => <span key={f.code} className="is-page__item is-page__item--b"><b>{f.title}</b>{f.evidence}</span>)}
      </div>
      <div className="is-page is-page--l" style={{ ['--i' as string]: 2 }}>
        <span className="is-page__run">Adult · Technical Appendix · 9</span>
        <span className="is-page__h">8. Technical Appendix</span>
        <table className="is-page__tbl">
          <thead><tr><th>Column</th><th>Type</th><th>Missing</th><th>Unique</th><th>Outliers</th></tr></thead>
          <tbody>{adult.columnEvidence.slice(0, 9).map((c) => <tr key={c.name}><td>{c.name}</td><td>{c.type}</td><td>{c.missing}</td><td>{c.unique}</td><td>{c.outliers}</td></tr>)}</tbody>
        </table>
      </div>
    </div>
  );
}
