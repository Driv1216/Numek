import { useRef, useState } from 'react';
import { Go, href, type Screen } from '../../shared/router';
import { gsap, useGsap, useSmoothScroll, ScrollTrigger } from '../../shared/motion';
import {
  run,
  leakRun,
  checks,
  CHECK_LABELS,
  SUB_LABELS,
  SUB_ORDER,
  columnsProfile,
  conflictGroups,
  hours,
  fences,
  nf,
  cliTranscript,
} from '../../shared/engine';
import { audits, openFindings, lastRun } from '../../shared/workspace';
import { SchemaDrawing, type FlagId } from './SchemaDrawing';
import './inspect.css';
import '@fontsource/host-grotesk/400';
import '@fontsource/host-grotesk/500';
import '@fontsource/host-grotesk/600';
import '@fontsource/host-grotesk/700';
import '@fontsource/jetbrains-mono/400';
import '@fontsource/jetbrains-mono/500';

const C = 'inspect';

function Mark() {
  return (
    <svg viewBox="0 0 22 22" className="ins-mark" aria-hidden="true">
      <rect x="1" y="1" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <path d="M6 16V6l10 10V6" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <rect x="15" y="1" width="6" height="6" fill="#ff4f14" />
    </svg>
  );
}

function Nav({ app }: { app?: boolean }) {
  return (
    <header className={`ins-nav${app ? ' is-app' : ''}`}>
      <Go to={href(C)} className="ins-brand" label="Numek DataTrust">
        <Mark />
        <span>NUMEK</span>
        <em>DataTrust</em>
      </Go>
      {!app && (
        <nav className="ins-links" aria-label="Site">
          <a href="#method">Method</a>
          <a href="#evidence">Evidence</a>
          <a href="#report">Report</a>
          <a href="#security">Local by default</a>
        </nav>
      )}
      <div className="ins-nav-right">
        <Go to="#/" className="ins-btn is-ghost">
          All concepts
        </Go>
        <Go to={href(C, 'workspace')} className="ins-btn">
          {app ? 'New audit' : 'Run an audit'}
        </Go>
      </div>
    </header>
  );
}

const STEPS: { id: string; title: string; body: string; flags: FlagId[] }[] = [
  {
    id: 'observe',
    title: 'Observe',
    body: 'DataTrust parses the file you name, on your machine, and profiles every column and every row. You declare the target. It never guesses one for you.',
    flags: [],
  },
  {
    id: 'flag',
    title: 'Flag',
    body: 'Twelve checks run against the whole table. A flag lands on the exact columns and CSV lines involved, never on a summary.',
    flags: ['conflict', 'outliers'],
  },
  {
    id: 'explain',
    title: 'Explain',
    body: 'Each flag carries its method, its population and what it may do to a model. Severe weaknesses cap the score through guardrails.',
    flags: ['conflict', 'outliers', 'imbalance', 'leakage'],
  },
  {
    id: 'report',
    title: 'Report',
    body: 'The same evidence becomes an HTML, PDF and JSON report a CTO, risk lead or customer can read without opening a notebook.',
    flags: ['conflict', 'outliers', 'imbalance', 'leakage'],
  },
];

/* ------------------------------------------------------------------ landing */

function Landing() {
  const root = useRef<HTMLDivElement>(null);
  const [step, setStep] = useState(0);
  useSmoothScroll();
  useGsap(root, (q) => {
    gsap.from(q('.ins-hero .ins-draw > *, .ins-hero .ins-draw'), {
      strokeDasharray: 1400,
      strokeDashoffset: 1400,
      duration: 1.3,
      ease: 'power2.out',
      stagger: 0.004,
    });
    gsap.from(q('.ins-hero .ins-flag'), { opacity: 0, y: 8, duration: 0.5, stagger: 0.18, delay: 0.9, ease: 'power2.out' });
    gsap.from(q('.ins-hero-title .ins-line'), { yPercent: 105, duration: 1, stagger: 0.08, ease: 'expo.out', delay: 0.2 });
    gsap.from(q('.ins-log li'), { opacity: 0, x: -6, duration: 0.3, stagger: 0.07, delay: 0.6 });
    q('.ins-reveal').forEach((el: Element) =>
      gsap.from(el, { opacity: 0, y: 26, duration: 0.9, ease: 'power3.out', scrollTrigger: { trigger: el, start: 'top 85%' } }),
    );
    gsap.from(q('.ins-statement-dot'), {
      scale: 0,
      duration: 0.6,
      ease: 'back.out(3)',
      scrollTrigger: { trigger: q('.ins-statement')[0], start: 'top 60%' },
    });
    ScrollTrigger.create({
      trigger: q('.ins-steps')[0],
      start: 'top top',
      end: 'bottom bottom',
      onUpdate: (st) => setStep(Math.min(STEPS.length - 1, Math.floor(st.progress * STEPS.length))),
    });
  });

  return (
    <div className="c-inspect" ref={root}>
      <Nav />
      <main>
        <section className="ins-hero ins-sheet">
          <span className="ins-cross tl" />
          <span className="ins-cross tr" />
          <div className="ins-hero-meta">
            <dl>
              <dt>Product</dt>
              <dd>DataTrust, dataset reliability</dd>
              <dt>Company</dt>
              <dd>Numek, AI reliability verification</dd>
              <dt>Runs</dt>
              <dd>On your machine. Nothing uploaded</dd>
              <dt>Output</dt>
              <dd>HTML, PDF and JSON report</dd>
            </dl>
            <ol className="ins-log" aria-label="Checks run on the Adult dataset">
              {checks.map((c, i) => (
                <li key={c.id}>
                  <span>{String(i + 1).padStart(3, '0')}</span> {CHECK_LABELS[c.id].toUpperCase()}
                </li>
              ))}
            </ol>
          </div>
          <SchemaDrawing className="ins-hero-drawing" />
          <h1 className="ins-hero-title">
            <span className="ins-mask"><span className="ins-line">Know what is wrong</span></span>
            <span className="ins-mask"><span className="ins-line">with your data before</span></span>
            <span className="ins-mask"><span className="ins-line">your model does.</span></span>
          </h1>
          <div className="ins-hero-cta">
            <p>
              DataTrust audits a training dataset before you train on it, and flags every risk on the rows and columns
              where it lives.
            </p>
            <div>
              <Go to={href(C, 'workspace')} className="ins-btn">
                Run an audit
              </Go>
              <Go to={href(C, 'results')} className="ins-btn is-ghost">
                See the Adult audit
              </Go>
            </div>
          </div>
        </section>

        <section className="ins-problem ins-sheet" id="method">
          <div className="ins-problem-head ins-reveal">
            <p className="ins-kicker">Problem</p>
            <h2>Your notebook answers what you ask. Nothing more.</h2>
          </div>
          <p className="ins-problem-body ins-reveal">
            Accuracy looks fine until you learn the majority class is 76% of rows, two people are recorded twice with
            different labels, or a column only exists after the outcome. DataTrust checks for these before the first
            epoch, across the whole table.
          </p>
          <div className="ins-formats ins-reveal">
            {['CSV', 'Parquet', 'JSONL', 'Image folders', 'Python API', 'Command line', 'Browser'].map((f) => (
              <span key={f}>{f}</span>
            ))}
          </div>
        </section>

        <section className="ins-statement">
          <h2>
            Right there with y<span className="ins-statement-o">o<i className="ins-statement-dot" /></span>ur data
          </h2>
        </section>

        <section className="ins-steps" id="evidence">
          <div className="ins-steps-sticky">
            <div className="ins-steps-drawing ins-sheet">
              <span className="ins-cross tl" />
              <span className="ins-cross br" />
              <SchemaDrawing show={STEPS[step].flags} className={`ins-step-svg is-${STEPS[step].id}`} />
              {STEPS[step].id === 'report' && (
                <figure className="ins-step-report">
                  <img src="round2/report-adult-top.jpg" alt="First page of the real DataTrust report for Adult" />
                </figure>
              )}
            </div>
            <div className="ins-steps-rail">
              {STEPS.map((s, i) => (
                <div key={s.id} className={`ins-step${i === step ? ' is-on' : ''}${i < step ? ' is-done' : ''}`}>
                  <div className="ins-step-bar">
                    <span>{String(i + 1).padStart(2, '0')}</span>
                    <b>{s.title.toUpperCase()}</b>
                    <i />
                  </div>
                  <p>{s.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="ins-tags-sec ins-sheet">
          <div className="ins-tags-head ins-reveal">
            <p className="ins-kicker">Every flag cites its source</p>
            <h2>Findings you can check, not opinions you have to trust.</h2>
          </div>
          <div className="ins-tags-grid">
            {run.findings.map((f) => {
              const check = { conflicting_target_labels: 'LABEL_CONFLICTS', target_imbalance: 'CLASSIFICATION_TARGET', numeric_outlier_concentration: 'NUMERIC_OUTLIERS', leakage_review_prompts: 'TARGET_LEAKAGE' }[f.code];
              return (
                <article key={f.code} className="ins-tagcard ins-reveal">
                  <header>
                    <span>{check}</span>
                    <em className={`is-${f.severity.toLowerCase()}`}>{f.severity}</em>
                  </header>
                  <h3>{f.title}</h3>
                  <p className="ins-tagcard-ev">{f.evidence}</p>
                  <p>{f.modeling_impact}</p>
                  <footer>{f.score_effect}</footer>
                </article>
              );
            })}
          </div>
        </section>

        <section className="ins-report ins-sheet" id="report">
          <div className="ins-report-copy ins-reveal">
            <p className="ins-kicker">The deliverable</p>
            <h2>A report the decision-maker can read in two minutes.</h2>
            <p>
              A decision surface first: score, why, principal evidence and next action. The technical appendix follows
              for whoever has to fix it. Generated as HTML, PDF and strict JSON from one completed result.
            </p>
            <pre className="ins-cli">{cliTranscript.join('\n')}</pre>
          </div>
          <figure className="ins-report-sheet ins-reveal">
            <img src="round2/report-adult-full.jpg" alt="Real DataTrust report generated for the Adult dataset" />
            <figcaption>Actual output of datatrust audit for Adult, unedited.</figcaption>
          </figure>
        </section>

        <section className="ins-local ins-sheet" id="security">
          <div className="ins-reveal">
            <p className="ins-kicker">Local by default</p>
            <h2>Your data never leaves the room.</h2>
          </div>
          <dl className="ins-spec ins-reveal">
            <div>
              <dt>Execution</dt>
              <dd>Loopback only, single user, process-scoped jobs</dd>
            </div>
            <div>
              <dt>Provenance</dt>
              <dd>SHA-256 of the exact source bytes on every report</dd>
            </div>
            <div>
              <dt>Method</dt>
              <dd>Versioned methodology id, published thresholds</dd>
            </div>
            <div>
              <dt>Claims</dt>
              <dd>A reliability report. Not a certificate of fairness or compliance</dd>
            </div>
          </dl>
        </section>

        <footer className="ins-foot">
          <p className="ins-foot-word">NUMEK</p>
          <div className="ins-foot-row">
            <span>DataTrust · ConfidenceGuard and HallucinationGuard in development</span>
            <span>Prototype · figures from a real local run</span>
          </div>
        </footer>
      </main>
    </div>
  );
}

/* ---------------------------------------------------------------- workspace */

function Workspace() {
  const root = useRef<HTMLDivElement>(null);
  useGsap(root, (q) => {
    gsap.from(q('.ins-row'), { opacity: 0, y: 8, stagger: 0.04, duration: 0.5, ease: 'power2.out' });
    gsap.from(q('.ins-att li'), { opacity: 0, x: 10, stagger: 0.05, duration: 0.5, delay: 0.2 });
  });
  const counts = (id: string) => openFindings.filter((f) => f.auditId === id);
  return (
    <div className="c-inspect is-app" ref={root}>
      <Nav app />
      <div className="ins-app">
        <aside className="ins-side">
          <p className="ins-side-title">Workspace</p>
          <nav>
            <a className="is-on">Audits <span>7</span></a>
            <a>Open flags <span>{openFindings.length}</span></a>
            <a>Reports</a>
            <a>Sources</a>
          </nav>
          <p className="ins-side-title">Location</p>
          <p className="ins-side-path">~/numek/audits</p>
          <div className="ins-side-local">
            <i /> Running locally · loopback only
          </div>
        </aside>
        <main className="ins-app-main">
          <div className="ins-app-head">
            <div>
              <p className="ins-kicker">Audits</p>
              <h1>Seven datasets, two need attention</h1>
            </div>
            <div className="ins-drop">
              <span>Drop a CSV, Parquet, JSONL file or image folder</span>
              <code>datatrust audit data.csv --target …</code>
            </div>
          </div>
          <div className="ins-table" role="table" aria-label="Audits">
            <div className="ins-row is-head" role="row">
              <span>Dataset</span>
              <span>Task</span>
              <span>Shape</span>
              <span>Score</span>
              <span>Flags</span>
              <span>Run</span>
            </div>
            {audits.map((a) => {
              const fl = counts(a.id);
              const cells = (
                <>
                  <span className="ins-row-name">
                    {a.name}
                    <small>{a.note}</small>
                  </span>
                  <span>{a.kind}</span>
                  <span className="ins-mono">
                    {nf(a.rows)}
                    {a.columns ? ` × ${a.columns}` : ' rec.'}
                  </span>
                  <span className="ins-row-score">
                    {a.score === null ? <em>No score</em> : <b>{a.score}</b>}
                    {a.score !== null && <i className={`band is-${a.band.toLowerCase()}`}>{a.band}</i>}
                  </span>
                  <span className="ins-flags">
                    {fl.length ? fl.map((f, i) => <i key={i} className={`is-${f.severity.toLowerCase()}`} />) : <em>{a.findings} findings</em>}
                  </span>
                  <span className="ins-mono">{lastRun[a.id]}</span>
                </>
              );
              const cls = `ins-row${a.band === 'High' ? ' is-hot' : ''}${a.id === 'adult' ? ' is-link' : ''}`;
              return a.id === 'adult' ? (
                <Go key={a.id} to={href(C, 'results')} className={cls}>
                  {cells}
                </Go>
              ) : (
                <div key={a.id} className={cls} role="row">
                  {cells}
                </div>
              );
            })}
          </div>
        </main>
        <aside className="ins-att">
          <p className="ins-kicker">Open flags</p>
          <ul>
            {openFindings.map((f, i) => (
              <li key={i} className={`is-${f.severity.toLowerCase()}`}>
                <header>
                  <span>{f.severity}</span>
                  <em>{f.audit}</em>
                </header>
                <b>{f.title}</b>
                <p>{f.detail}</p>
              </li>
            ))}
          </ul>
        </aside>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ results */

function Evidence({ code }: { code: string }) {
  if (code === 'conflicting_target_labels') {
    const cols = ['line', 'age', 'workclass', 'education', 'marital_status', 'occupation', 'sex', 'hours_per_week', 'annual_income_over_50k'];
    return (
      <div className="ins-ev">
        <p className="ins-ev-cap">All 10 rows in the 5 conflicting groups. Shown columns are an excerpt; every one of the 14 features matches within a group.</p>
        <table className="ins-ev-table">
          <thead>
            <tr>
              {cols.map((c) => (
                <th key={c}>{c === 'annual_income_over_50k' ? 'label' : c}</th>
              ))}
            </tr>
          </thead>
          {conflictGroups.map((g, gi) => (
            <tbody key={gi}>
              {g.map((r) => (
                <tr key={r.line}>
                  {cols.map((c) => (
                    <td key={c} className={c === 'annual_income_over_50k' && r[c] === '>50K' ? 'is-hot' : ''}>
                      {c === 'line' ? nf(Number(r.line)) : r[c]}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          ))}
        </table>
      </div>
    );
  }
  if (code === 'numeric_outlier_concentration') {
    const [lo, hi] = fences(hours)!;
    const [mn, q1, md, q3, mx] = hours.q!;
    const x = (v: number) => 40 + ((v - mn) / (mx - mn)) * 620;
    return (
      <div className="ins-ev">
        <p className="ins-ev-cap">
          hours_per_week from the engine profile. {nf(hours.outlier_count)} rows ({hours.outlier_rate}%) fall outside the 1.5 × IQR
          fences derived from its quartiles.
        </p>
        <svg viewBox="0 0 700 170" className="ins-box">
          <line x1="40" x2="660" y1="80" y2="80" stroke="#1d1d1b" strokeWidth="1" />
          <rect x={x(lo)} y="50" width={x(hi) - x(lo)} height="60" fill="none" stroke="#ff4f14" strokeDasharray="4 3" />
          <rect x={x(q1)} y="60" width={Math.max(4, x(q3) - x(q1))} height="40" fill="#1d1d1b" />
          <line x1={x(md)} x2={x(md)} y1="56" y2="104" stroke="#ff4f14" strokeWidth="2" />
          {[mn, lo, q1, q3, hi, mx].map((v, i) => (
            <g key={i}>
              <line x1={x(v)} x2={x(v)} y1="120" y2="128" stroke="#1d1d1b" />
              <text x={x(v)} y={i % 2 ? 160 : 146} textAnchor="middle" className="ins-svg-mono" fontSize="11">
                {v}
              </text>
            </g>
          ))}
          <text x={x(lo) + 4} y="44" className="ins-svg-mono hot" fontSize="11">fences 32.5 to 52.5</text>
        </svg>
      </div>
    );
  }
  if (code === 'target_imbalance') {
    const d = run.profile.target_distribution;
    return (
      <div className="ins-ev">
        <p className="ins-ev-cap">Labelled rows by class. A model that always predicts the majority is right {run.profile.majority_class_baseline}% of the time.</p>
        <div className="ins-split">
          {d.map((c) => (
            <div key={c.label} style={{ flexGrow: c.count }} className={c.label.startsWith('>') ? 'is-min' : ''}>
              <b>{c.label.replace('<=', '≤')}</b>
              <span>
                {nf(c.count)} · {c.percentage}%
              </span>
            </div>
          ))}
        </div>
      </div>
    );
  }
  return (
    <div className="ins-ev">
      <p className="ins-ev-cap">Name-based prompt only. The column is kept, scored and reported. Confirm with the source owner when its value becomes known.</p>
      <div className="ins-colnote">
        <code>marital_status</code>
        <span>review_only · generic status-like name</span>
      </div>
    </div>
  );
}

function Results() {
  const root = useRef<HTMLDivElement>(null);
  const [sel, setSel] = useState(0);
  const f = run.findings[sel];
  useGsap(root, (q) => {
    gsap.from(q('.ins-res .ins-draw, .ins-res .ins-draw > *'), { strokeDasharray: 1400, strokeDashoffset: 1400, duration: 1.1, ease: 'power2.out' });
    gsap.from(q('.ins-res-score > *'), { opacity: 0, y: 12, stagger: 0.08, duration: 0.6 });
  });
  const flagFor: Record<string, FlagId> = {
    conflicting_target_labels: 'conflict',
    target_imbalance: 'imbalance',
    numeric_outlier_concentration: 'outliers',
    leakage_review_prompts: 'leakage',
  };
  return (
    <div className="c-inspect is-app" ref={root}>
      <Nav app />
      <main className="ins-res">
        <section className="ins-res-head">
          <div>
            <p className="ins-kicker">
              <Go to={href(C, 'workspace')}>Audits</Go> / Adult
            </p>
            <h1>ADULT</h1>
          </div>
          <dl className="ins-res-meta">
            <dt>Task</dt>
            <dd>Binary classification · annual_income_over_50k</dd>
            <dt>Shape</dt>
            <dd>
              {nf(run.rows)} × {run.columns}
            </dd>
            <dt>Source</dt>
            <dd className="ins-mono">sha256 {run.sha256.slice(0, 20)}…</dd>
            <dt>Method</dt>
            <dd className="ins-mono">{run.methodology}</dd>
            <dt>Run</dt>
            <dd>{run.elapsed.toFixed(2)} s on this machine</dd>
          </dl>
          <div className="ins-res-actions">
            <button className="ins-btn is-ghost">JSON</button>
            <button className="ins-btn is-ghost">PDF</button>
            <button className="ins-btn">Share report</button>
          </div>
        </section>

        <section className="ins-res-body">
          <div className="ins-res-sheet ins-sheet">
            <span className="ins-cross tl" />
            <span className="ins-cross br" />
            <SchemaDrawing show={[flagFor[f.code]]} />
          </div>
          <aside className="ins-res-score">
            <div className="ins-score">
              <b>{run.score}</b>
              <span className="band is-elevated">{run.band}</span>
            </div>
            <p className="ins-score-why">
              Evidence {run.evidence} → capped at {run.guardrails[0].cap}. {run.guardrails[0].explanation}
            </p>
            <div className="ins-subs">
              {SUB_ORDER.map((k) => (
                <div key={k} className={`ins-sub${run.sub[k] < 50 ? ' is-hot' : ''}`}>
                  <span>{SUB_LABELS[k]}</span>
                  <i>
                    <em style={{ width: `${run.sub[k]}%` }} />
                    <s style={{ left: '50%' }} />
                  </i>
                  <b>{run.sub[k].toFixed(2)}</b>
                </div>
              ))}
              <p className="ins-subs-note">Tick marks 50, the critical line for guardrails.</p>
            </div>
            <p className="ins-action">{run.action}</p>
          </aside>
        </section>

        <section className="ins-findings">
          <div className="ins-find-tabs" role="tablist" aria-label="Findings">
            {run.findings.map((x, i) => (
              <button key={x.code} role="tab" aria-selected={i === sel} className={i === sel ? 'is-on' : ''} onClick={() => setSel(i)}>
                <span className={`sev is-${x.severity.toLowerCase()}`}>{x.severity}</span>
                {x.title}
              </button>
            ))}
          </div>
          <div className="ins-find-body" role="tabpanel">
            <div className="ins-find-text">
              <h2>{f.finding}</h2>
              <dl>
                <dt>Evidence</dt>
                <dd>{f.evidence}</dd>
                <dt>Possible modeling impact</dt>
                <dd>{f.modeling_impact}</dd>
                <dt>Recommended review</dt>
                <dd>{f.recommendation}</dd>
                <dt>Score effect</dt>
                <dd>{f.score_effect}</dd>
              </dl>
            </div>
            <Evidence code={f.code} />
          </div>
        </section>

        <section className="ins-ledger">
          <div className="ins-ledger-head">
            <p className="ins-kicker">Coverage</p>
            <h2>12 of 12 applicable checks completed</h2>
            <p>{run.coverage.meaning} Not covered by this run: {run.coverage.unsupported_capabilities.join(', ')}.</p>
          </div>
          <div className="ins-ledger-grid">
            {checks.map((c, i) => (
              <div key={c.id}>
                <span>{String(i + 1).padStart(3, '0')}</span>
                <b>{CHECK_LABELS[c.id]}</b>
                <code>{c.method}</code>
                <em>{c.population}</em>
              </div>
            ))}
          </div>
          <div className="ins-cols">
            <p className="ins-kicker">Column profile</p>
            <div className="ins-cols-grid">
              {columnsProfile.map((c) => (
                <div key={c.name} className={c.outlier_rate > 5 || c.name === 'marital_status' || c.role === 'target' ? 'is-hot' : ''}>
                  <code>{c.name}</code>
                  <span>{c.dtype}</span>
                  <span>{nf(c.unique_count)} unique</span>
                  <span>{c.missing_count ? `${nf(c.missing_count)} missing` : 'complete'}</span>
                </div>
              ))}
            </div>
          </div>
          <p className="ins-compare">
            Compare: the same table with a planted <code>post_income_outcome</code> column scores {leakRun.score} ({leakRun.band}).{' '}
            {leakRun.guardrails[0].explanation}
          </p>
        </section>
      </main>
    </div>
  );
}

export default function Inspect({ screen }: { screen: Screen }) {
  if (screen === 'workspace') return <Workspace />;
  if (screen === 'results') return <Results />;
  return <Landing />;
}
