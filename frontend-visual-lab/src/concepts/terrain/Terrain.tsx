import { useRef, useState } from 'react';
import { Go, href, type Screen } from '../../shared/router';
import { gsap, useGsap, useSmoothScroll } from '../../shared/motion';
import { run, conflictGroups, columnsProfile, hours, nf, SUB_LABELS, SUB_ORDER, checks, CHECK_LABELS } from '../../shared/engine';
import { dist } from '../../shared/distributions';
import { Spark } from '../../shared/Spark';
import { audits, lastRun } from '../../shared/workspace';
import { Landscape, peakHigh, type Pin } from './Landscape';
import './terrain.css';
import '@fontsource-variable/jost/wght';

const C = 'terrain';
const ph = peakHigh();
const PINS: Pin[] = [
  { id: 'peak', age: 36, hours: 39, title: 'Densest ground', detail: '35–36 y · 37–40 h · 1,400 rows' },
  { id: 'conflict', age: 39.5, hours: 40.5, title: 'Lines 850 and 22,763', detail: 'Same features, different label', hot: true },
  { id: 'high', side: 'l', age: ph.age, hours: ph.hours, title: '>50K is a smaller ridge', detail: `${ph.ageLabel} y · ${ph.hourLabel} h · ${nf(ph.count)} rows earn >50K` },
  { id: 'tail', age: 45, hours: 70, title: 'The long-hours tail', detail: `${hours.outlier_rate}% of rows sit outside 32.5–52.5 h` },
];

function Mark() {
  return (
    <svg viewBox="0 0 30 30" className="tn-mark" aria-hidden="true">
      {Array.from({ length: 9 }, (_, i) => {
        const a = (i / 9) * Math.PI * 2;
        return <circle key={i} cx={15 + Math.cos(a) * 9} cy={15 + Math.sin(a) * 9} r={1.7} />;
      })}
      {Array.from({ length: 5 }, (_, i) => {
        const a = (i / 5) * Math.PI * 2 + 0.4;
        return <circle key={`i${i}`} cx={15 + Math.cos(a) * 4.5} cy={15 + Math.sin(a) * 4.5} r={1.3} />;
      })}
      <circle cx="15" cy="15" r="1.4" />
    </svg>
  );
}

function Top({ app }: { app?: boolean }) {
  return (
    <header className={`tn-top${app ? ' is-app' : ''}`}>
      <nav>
        <Go to={href(C)} className="is-on">
          Numek
        </Go>
        <Go to={href(C, 'workspace')}>DataTrust</Go>
        <a>ConfidenceGuard</a>
        <a>HallucinationGuard</a>
      </nav>
      <nav className="r">
        <Go to="#/">All concepts</Go>
        <Go to={href(C, 'workspace')}>Open DataTrust</Go>
      </nav>
    </header>
  );
}

function Landing() {
  const root = useRef<HTMLDivElement>(null);
  const [drift, setDrift] = useState(0);
  useSmoothScroll();
  useGsap(root, (q) => {
    gsap.from(q('.tn-lockup > *'), { opacity: 0, y: 10, stagger: 0.12, duration: 1.6, ease: 'power2.out', delay: 0.3 });
    gsap.from(q('.tn-pin'), { opacity: 0, duration: 1.2, stagger: 0.2, delay: 1.2 });
    gsap.to({}, { scrollTrigger: { trigger: q('.tn-fly')[0], start: 'top top', end: 'bottom bottom', scrub: true, onUpdate: (st) => setDrift(st.progress) } });
    q('.tn-say').forEach((el: Element) =>
      gsap.fromTo(el, { opacity: 0, y: 40 }, { opacity: 1, y: 0, ease: 'none', scrollTrigger: { trigger: el, start: 'top 85%', end: 'top 45%', scrub: true } }),
    );
    q('.tn-rise').forEach((el: Element) =>
      gsap.from(el, { opacity: 0, y: 24, duration: 1.2, ease: 'power2.out', scrollTrigger: { trigger: el, start: 'top 88%' } }),
    );
  });
  return (
    <div className="c-terrain" ref={root}>
      <Top />
      <section className="tn-fly">
        <div className="tn-fly-pin">
          <Landscape height="100%" pins={[PINS[1], PINS[3]]} drift={drift} />
          <div className="tn-lockup">
            <Mark />
            <span className="tn-bar" />
            <span className="tn-word">NUMEK</span>
          </div>
          <p className="tn-discover">Scroll down to discover</p>
        </div>
        <div className="tn-says">
          <p className="tn-say l">
            Numek is an AI reliability
            <br />
            verification company.
          </p>
          <p className="tn-say r">
            DataTrust reads the true shape
            <br />
            of your training data
            <br />
            before a model learns it.
          </p>
          <p className="tn-say l">
            This landscape is Adult:
            <br />
            {nf(run.rows)} people by age
            <br />
            and hours worked each week.
          </p>
        </div>
      </section>

      <section className="tn-terrain-notes">
        <div className="tn-note-head tn-rise">
          <span className="tn-circle" />
          <p>
            We read every row, flag what the shape hides, and write it down so the people who answer for the model can follow it.
          </p>
          <Go to={href(C, 'results')} className="tn-arrow">
            Read the Adult assessment <i>→</i>
          </Go>
        </div>
        <div className="tn-notes">
          {[
            ['A lopsided target', `Three in four rows earn ≤50K. A model that always says so is right ${run.profile.majority_class_baseline}% of the time. Target balance scores ${run.sub.target_balance}, and the guardrail holds the result at ${run.score}.`],
            ['Two people on one spot', 'Five groups share all fourteen features yet carry different labels. Lines 850 and 22,763 are one such pair.'],
            ['A long tail of hours', `${nf(hours.outlier_count)} rows work outside the 32.5 to 52.5 hour fences. Real edge cases, or entry errors; DataTrust asks you to look.`],
          ].map(([t, d]) => (
            <div key={t} className="tn-note tn-rise">
              <h3>{t}</h3>
              <p>{d}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="tn-divisions">
        <p className="tn-label tn-rise">One company, three disciplines</p>
        {[
          ['DataTrust', 'Dataset reliability before training. Available now, local by default.', true],
          ['ConfidenceGuard', 'Model confidence, calibration and drift. In development.', false],
          ['HallucinationGuard', 'Grounding and citations in generated output. In development.', false],
        ].map(([n, d, live]) => (
          <div key={n as string} className={`tn-div tn-rise${live ? ' is-live' : ''}`}>
            <span>{n}</span>
            <p>{d}</p>
            {live ? (
              <Go to={href(C, 'workspace')} className="tn-arrow">
                Open <i>→</i>
              </Go>
            ) : (
              <em>Soon</em>
            )}
          </div>
        ))}
      </section>

      <footer className="tn-foot">
        <div className="tn-lockup is-small">
          <Mark />
          <span className="tn-bar" />
          <span className="tn-word">NUMEK</span>
        </div>
        <p>Evidence about data before training. A reliability report, not a certificate.</p>
      </footer>
    </div>
  );
}

function Workspace() {
  const root = useRef<HTMLDivElement>(null);
  const [sel, setSel] = useState(0);
  const a = audits[sel];
  useGsap(root, (q) => {
    gsap.from(q('.tn-ds'), { opacity: 0, y: 10, stagger: 0.05, duration: 0.8 });
  });
  return (
    <div className="c-terrain is-app" ref={root}>
      <Top app />
      <main className="tn-ws">
        <aside className="tn-ws-list">
          <p className="tn-label">Datasets · ~/numek/audits</p>
          {audits.map((x, i) => (
            <button key={x.id} className={`tn-ds${sel === i ? ' is-on' : ''}`} onClick={() => setSel(i)}>
              <span>{x.name}</span>
              <em>{x.score ?? '—'}</em>
            </button>
          ))}
          <div className="tn-new">
            <p className="tn-label">New audit</p>
            <p>Name a file and the outcome you intend to predict.</p>
            <code>datatrust audit data.csv --target …</code>
          </div>
        </aside>
        <section className="tn-ws-main">
          <div className="tn-ws-land">
            {a.id === 'adult' || a.id === 'adult-leak' ? (
              <Landscape height="100%" pins={[PINS[1]]} />
            ) : (
              <div className="tn-ws-empty">
                <span className="tn-circle" />
                <p>Landscape shown for Adult in this prototype.</p>
              </div>
            )}
          </div>
          <div className="tn-ws-info">
            <p className="tn-label">
              {a.kind} · read {lastRun[a.id]}
            </p>
            <h1>{a.name.toUpperCase()}</h1>
            <p className="tn-ws-note">{a.note}.</p>
            <dl>
              <dt>Score</dt>
              <dd>{a.score === null ? 'Not defined for this task' : `${a.score}, ${a.band.toLowerCase()}`}</dd>
              <dt>Rows</dt>
              <dd>{nf(a.rows)}</dd>
              <dt>Findings</dt>
              <dd>{a.findings}</dd>
            </dl>
            {a.id === 'adult' && (
              <Go to={href(C, 'results')} className="tn-arrow">
                Read the assessment <i>→</i>
              </Go>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}

function Results() {
  const root = useRef<HTMLDivElement>(null);
  const [sel, setSel] = useState(0);
  const f = run.findings[sel];
  useGsap(root, (q) => {
    gsap.from(q('.tn-res-side > *'), { opacity: 0, y: 12, stagger: 0.06, duration: 0.9 });
  });
  const pinFor: Record<string, Pin[]> = {
    conflicting_target_labels: [PINS[1]],
    target_imbalance: [PINS[0], PINS[2]],
    numeric_outlier_concentration: [PINS[3]],
    leakage_review_prompts: [],
  };
  return (
    <div className="c-terrain is-app" ref={root}>
      <Top app />
      <main className="tn-res">
        <section className="tn-res-land">
          <Landscape height="100%" pins={pinFor[f.code]} interactive />
          <div className="tn-res-title">
            <p className="tn-label">
              <Go to={href(C, 'workspace')}>DataTrust</Go> / Adult
            </p>
            <h1>ADULT</h1>
            <p>Drag to turn the landscape.</p>
          </div>
          <div className="tn-res-score">
            <b>{run.score}</b>
            <span>Elevated · evidence {run.evidence}</span>
          </div>
        </section>
        <aside className="tn-res-side">
          <p className="tn-label">Findings</p>
          {run.findings.map((x, i) => (
            <button key={x.code} className={`tn-find${i === sel ? ' is-on' : ''}`} onClick={() => setSel(i)}>
              <span>{x.severity}</span>
              <b>{x.title}</b>
            </button>
          ))}
          <div className="tn-find-body">
            <h2>{f.finding}</h2>
            <p>{f.modeling_impact}</p>
            <p>
              <b>Review.</b> {f.recommendation}
            </p>
            <p className="tn-muted">{f.score_effect}</p>
            {f.code === 'conflicting_target_labels' && (
              <div className="tn-pairs">
                {conflictGroups.map((g, gi) => (
                  <div key={gi}>
                    {g.map((r) => (
                      <span key={r.line} className={r.annual_income_over_50k === '>50K' ? 'is-hot' : ''}>
                        line {nf(Number(r.line))} · {r.annual_income_over_50k.replace('<=', '≤')}
                      </span>
                    ))}
                  </div>
                ))}
              </div>
            )}
            {f.code === 'leakage_review_prompts' && (
              <div className="tn-colline">
                <Spark d={dist('marital_status')} width={300} height={22} className="tn-spark" />
                <span>marital_status · 7 values, complete</span>
              </div>
            )}
          </div>
          <p className="tn-label tn-gap">Sub-scores</p>
          {SUB_ORDER.map((k) => (
            <div key={k} className={`tn-sub${run.sub[k] < 50 ? ' is-low' : ''}`}>
              <span>{SUB_LABELS[k]}</span>
              <i>
                <em style={{ width: `${run.sub[k]}%` }} />
              </i>
              <b>{run.sub[k].toFixed(2)}</b>
            </div>
          ))}
        </aside>
        <section className="tn-res-cols">
          <p className="tn-label">Columns</p>
          <div className="tn-cols">
            {columnsProfile.map((c) => (
              <div key={c.name}>
                <Spark d={dist(c.name)} width={200} height={34} className="tn-spark" />
                <span>{c.name}</span>
                <em>
                  {c.dtype} · {nf(c.unique_count)} distinct{c.missing_count ? ` · ${nf(c.missing_count)} missing` : ''}
                </em>
              </div>
            ))}
          </div>
          <p className="tn-label tn-gap">Checks completed</p>
          <p className="tn-checks">{checks.map((c) => CHECK_LABELS[c.id]).join(' · ')}</p>
        </section>
      </main>
    </div>
  );
}

export default function Terrain({ screen }: { screen: Screen }) {
  if (screen === 'workspace') return <Workspace />;
  if (screen === 'results') return <Results />;
  return <Landing />;
}
