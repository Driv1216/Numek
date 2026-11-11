import '@fontsource-variable/eb-garamond';
import '@fontsource-variable/eb-garamond/wght-italic.css';
import '@fontsource-variable/inter-tight';
import './provenance.css';
import { adult, bike, finance, local } from '../../fixture';
import { href } from '../../shell/router';
import { Header, RecordCard, Thread, csvLine, g, rowA, rowB, stages, useStage } from './trace';

const others = [
  { title: 'An unusual distribution', chain: ['hours_per_week', 'quartiles 40 · 45', 'fences 32.5 – 52.5', '13,496 rows outside', 'review, not deletion'] },
  { title: 'A score held at a cap', chain: ['annual_income_over_50k', 'majority 76.07%', 'target balance 47.86', '≤ 50: critical', 'final 69.0'] },
  { title: 'A sum inside the features', chain: ['bike_hour.csv', bike.relationship, 'holds on 17,379 of 17,379 rows', 'declared unavailable', 'no score defined'] },
  { title: 'A record that disagrees with its document', chain: ['records.csv', 'statement PDF', 'page · table · row', `${finance.discrepancies} discrepancy, ${finance.conflicts} conflict`, 'both kept'] },
];

export default function Landing() {
  const [ref, p, step] = useStage(stages.length);
  return (
    <div className="pv pv--landing">
      <Header />
      <section className="pv-hero">
        <h1 className="pv-hero__w"><span>Tracing</span><Thread /><span>Evidence</span></h1>
        <p className="pv-hero__k">DataTrust by NUMEK · AI reliability verification</p>
      </section>

      <section className="pv-intro">
        <p className="pv-kicker">Every finding · one way back</p>
        <h2>Here is how one finding was made — from a single line of a public dataset to page six of a report.</h2>
        <span className="pv-pill">Scroll down</span>
      </section>

      <section className="pv-trace" ref={ref} aria-label="One finding, traced">
        <div className="pv-trace__stage">
          <div className={`pv-obj pv-obj--s${step}`}>
            {step === 0 && (
              <figure className="pv-slip">
                <span className="pv-slip__n">16,685</span>
                <code>{csvLine}</code>
              </figure>
            )}
            {step >= 1 && step <= 4 && (
              <div className="pv-pair">
                <RecordCard values={rowA} other={step >= 3 ? rowB : undefined} stage={step} />
                {step >= 3 && (
                  <>
                    <div className="pv-eq" aria-hidden="true"><b>14</b><span>of 14 features equal</span>{step >= 4 && <em>label differs</em>}</div>
                    <RecordCard values={rowB} other={rowA} stage={step} label="Row 34,343" className="pv-rec--b" />
                  </>
                )}
              </div>
            )}
            {step === 5 && (
              <article className="pv-finding">
                <p className="pv-kicker">Finding · Moderate</p>
                <h3>Potentially conflicting target labels</h3>
                <p>{adult.findings[0].finding}</p>
                <dl>
                  <div><dt>Evidence</dt><dd>{adult.findings[0].evidence}</dd></div>
                  <div><dt>Review</dt><dd>{adult.findings[0].review}</dd></div>
                  <div><dt>Score effect</dt><dd>{adult.findings[0].scoreEffect}</dd></div>
                </dl>
              </article>
            )}
            {step === 6 && (
              <div className="pv-pages">
                <div className="pv-page"><span>2 · Priority Actions</span><b>1 · Potentially conflicting target labels</b><i /><i /><i className="s" /><b className="m">2 · Target imbalance</b><i /><i className="s" /></div>
                <div className="pv-page pv-page--hi"><span>6 · Duplicate and Feature Evidence</span><i /><i className="s" /><b>Conflicting-label groups · 5</b><i /><i /><i className="s" /></div>
                <div className="pv-page pv-page--json"><span>adult.json</span><code>{'"findings": [\n  { "code": "conflicting_target_labels",\n    "severity": "Moderate", … }'}</code></div>
              </div>
            )}
          </div>
          <p className="pv-caption">{step === 0 ? 'adult.csv · data row 16,684' : step < 3 ? 'Row 16,684 · UCI Adult · prepared validation corpus' : step < 5 ? `Rows ${g.rows.join(' and ')} · group 1 of 5` : step === 5 ? 'conflicting_target_labels' : 'DataTrust reliability report · Adult'}</p>
          <div className="pv-sentence" key={step}>
            <p className="pv-sentence__t">{stages[step].t}</p>
            <p className="pv-sentence__s">{stages[step].s}</p>
          </div>
          <ol className="pv-scrub" aria-label="Trace stages">
            <i className="pv-scrub__bar" style={{ width: `${p * 100}%` }} />
            {stages.map((s, i) => <li key={s.k} className={i === step ? 'is-on' : i < step ? 'is-past' : ''}>{s.k}</li>)}
          </ol>
        </div>
      </section>

      <section className="pv-more">
        <p className="pv-kicker">Other traces</p>
        <h2>Every finding keeps its way back.</h2>
        <ol>
          {others.map((o, i) => (
            <li key={o.title}>
              <span className="pv-more__n">{String(i + 2).padStart(2, '0')}</span>
              <h3>{o.title}</h3>
              <p className="pv-chain">{o.chain.map((c, k) => <span key={k}>{c}</span>)}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="pv-private">
        <div>
          <p className="pv-kicker">Where the trail is kept</p>
          <h2>On your machine, and nowhere else.</h2>
        </div>
        <div className="pv-private__b">
          <p>DataTrust runs locally: the browser interface binds to {local.host}, optional models are pinned files you provide, and nothing is fetched while it analyses.</p>
          <p>For documents and text, reports carry references to evidence; a private locator manifest stays with you, and resolving a reference back to its content is a local command.</p>
          <code>$ datatrust cross-evidence --report report.json --manifest manifest.json --ref …</code>
        </div>
      </section>

      <footer className="pv-foot">
        <div className="pv-foot__about">
          <h2>About DataTrust</h2>
          <p>NUMEK’s reliability analysis for the datasets behind ML and AI — tables, outcomes, time, text, images and connected documents. Every report is HTML, PDF and JSON from one completed result. Model-confidence and LLM-grounding work are research directions, not products.</p>
          <a className="pv-btn pv-btn--l" href={href('provenance', 'app')}>Open DataTrust</a>
        </div>
        <div className="pv-foot__ch">
          <p className="pv-kicker">Chapters</p>
          <ol>
            <li><a href={href('provenance', 'results')}><span>1</span>Tracing a finding through a dataset</a></li>
            <li><a href={href('provenance', 'app')}><span>2</span>Every trace in a workspace</a></li>
            <li><a href={href('provenance', 'results')}><span>3</span>The Adult report, traced</a></li>
          </ol>
        </div>
        <p className="pv-foot__f">© NUMEK · Adult data: UCI Machine Learning Repository</p>
      </footer>
    </div>
  );
}
