import { useEffect, useRef, useState } from 'react';
import { Go, href, type Screen } from '../../shared/router';
import { gsap, useGsap, useSmoothScroll } from '../../shared/motion';
import { run, leakRun, checks, CHECK_LABELS, SUB_LABELS, SUB_ORDER, conflictGroups, columnsProfile, hours, nf } from '../../shared/engine';
import { dists, dist } from '../../shared/distributions';
import { Spark } from '../../shared/Spark';
import { audits, openFindings, lastRun } from '../../shared/workspace';
import './proof.css';
import '@fontsource-variable/onest/wght';
import '@fontsource/red-hat-mono/400';
import '@fontsource/red-hat-mono/500';

const C = 'proof';
const CORPORA = ['Adult', 'Bank Marketing', 'German Credit', 'Concrete', 'Bike Sharing', 'Energy', 'Scene', 'COCO val2017', 'SQuAD v2', 'SciFact', 'SMS Spam', 'Online Retail'];

function Logo() {
  return (
    <span className="pf-logo">
      <svg viewBox="0 0 22 22" aria-hidden="true">
        <rect x="1" y="1" width="20" height="20" rx="6" fill="url(#pf-lg)" />
        <path d="M7 15V7l8 8V7" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        <defs>
          <linearGradient id="pf-lg" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#5b5bf0" />
            <stop offset="1" stopColor="#ff8a65" />
          </linearGradient>
        </defs>
      </svg>
      numek
    </span>
  );
}

function Nav() {
  return (
    <header className="pf-nav">
      <Go to={href(C)} label="Numek home">
        <Logo />
      </Go>
      <nav>
        <a href="#pf-product">Product</a>
        <a href="#pf-calc">Baseline check</a>
        <a href="#pf-local">Security</a>
        <Go to="#/">All concepts</Go>
      </nav>
      <div className="pf-nav-r">
        <Go to={href(C, 'workspace')} className="pf-link">
          Sign in
        </Go>
        <Go to={href(C, 'workspace')} className="pf-btn">
          Run an audit <i>›</i>
        </Go>
      </div>
    </header>
  );
}

function useCount(target: number, ms = 1600) {
  const [v, setV] = useState(0);
  useEffect(() => {
    const o = { v: 0 };
    const t = gsap.to(o, { v: target, duration: ms / 1000, ease: 'power3.out', onUpdate: () => setV(Math.round(o.v)) });
    return () => {
      t.kill();
    };
  }, [target, ms]);
  return v;
}

/* ----------------------------------------------------------- UI cards */

function ScoreCard() {
  return (
    <div className="pf-card pf-c-score">
      <header>
        <span>Adult · reliability</span>
        <em className="pf-badge is-elevated">Elevated</em>
      </header>
      <div className="pf-score">
        <b>{run.score}</b>
        <span>/100</span>
      </div>
      <p>
        Evidence {run.evidence} · capped by <b>target balance {run.sub.target_balance}</b>
      </p>
      <div className="pf-mini-subs">
        {SUB_ORDER.map((k) => (
          <i key={k} style={{ height: `${run.sub[k]}%` }} className={run.sub[k] < 50 ? 'is-low' : ''} />
        ))}
      </div>
    </div>
  );
}

function FindingsCard() {
  return (
    <div className="pf-card pf-c-find">
      <header>
        <span>Findings</span>
        <em>4</em>
      </header>
      {run.findings.map((f) => (
        <div key={f.code} className="pf-fi">
          <i className={`is-${f.severity.toLowerCase()}`} />
          <b>{f.title}</b>
        </div>
      ))}
    </div>
  );
}

function PairCard() {
  const g = conflictGroups[1];
  return (
    <div className="pf-card pf-c-pair">
      <header>
        <span>Label conflict · group 2 of 5</span>
      </header>
      {g.map((r) => (
        <div key={r.line} className="pf-pair">
          <code>line {nf(Number(r.line))}</code>
          <span>
            {r.age} · {r.education} · {r.hours_per_week} h
          </span>
          <em className={r.annual_income_over_50k === '>50K' ? 'is-hi' : ''}>{r.annual_income_over_50k.replace('<=', '≤')}</em>
        </div>
      ))}
    </div>
  );
}

function HistCard() {
  return (
    <div className="pf-card pf-c-hist">
      <header>
        <span>hours_per_week</span>
        <em>{hours.outlier_rate}% outside IQR fences</em>
      </header>
      <Spark d={dist('hours_per_week')} width={260} height={74} gap={2} className="pf-spark" hot={(lo, hi) => hi <= 32.5 || lo >= 52.5} />
    </div>
  );
}

/* -------------------------------------------------------------- landing */

function Calculator() {
  const [maj, setMaj] = useState(37155);
  const [min, setMin] = useState(11687);
  const total = maj + min || 1;
  const base = (Math.max(maj, min) / total) * 100;
  const ratio = Math.max(maj, min) / Math.max(1, Math.min(maj, min));
  const flagged = base >= 75;
  return (
    <div className="pf-calc">
      <div className="pf-calc-in">
        <p className="pf-eyebrow">Baseline check</p>
        <h3>Tell us about your labels</h3>
        <label>
          <span>Rows in the largest class</span>
          <input type="number" min={0} value={maj} onChange={(e) => setMaj(Math.max(0, Number(e.target.value)))} />
        </label>
        <label>
          <span>Rows in the other class</span>
          <input type="number" min={0} value={min} onChange={(e) => setMin(Math.max(0, Number(e.target.value)))} />
        </label>
        <div className="pf-calc-presets">
          <button onClick={() => (setMaj(37155), setMin(11687))}>Adult</button>
          <button onClick={() => (setMaj(37155), setMin(500))}>Adult, minority cut to 500</button>
          <button onClick={() => (setMaj(700), setMin(300))}>German Credit</button>
        </div>
      </div>
      <div className="pf-calc-out">
        <span>A model that always predicts the largest class is right</span>
        <b>{base.toFixed(2)}%</b>
        <span>of the time. Majority to minority {ratio.toFixed(2)} : 1.</span>
        <p className={flagged ? 'is-flag' : ''}>
          {flagged
            ? 'At or above the current 75% threshold, DataTrust reports a target-imbalance finding.'
            : 'Below the current 75% threshold, so no target-imbalance finding from this alone.'}
        </p>
        <small>Arithmetic only. Sub-scores and guardrails are computed by the engine on your full table.</small>
      </div>
    </div>
  );
}

function Landing() {
  const root = useRef<HTMLDivElement>(null);
  const rows = useCount(run.rows);
  useSmoothScroll();
  useGsap(root, (q) => {
    gsap.from(q('.pf-hero-copy > *'), { opacity: 0, y: 20, stagger: 0.08, duration: 1, ease: 'expo.out' });
    gsap.from(q('.pf-stack .pf-card'), { opacity: 0, y: 60, rotate: (i: number) => (i % 2 ? 4 : -4), stagger: 0.12, duration: 1.3, ease: 'expo.out', delay: 0.25 });
    q('.pf-rise').forEach((el: Element) =>
      gsap.from(el, { opacity: 0, y: 36, duration: 1, ease: 'power3.out', scrollTrigger: { trigger: el, start: 'top 88%' } }),
    );
    gsap.to(q('.pf-stack'), { yPercent: -12, ease: 'none', scrollTrigger: { trigger: q('.pf-hero')[0], start: 'top top', end: 'bottom top', scrub: true } });
  });

  return (
    <div className="c-proof" ref={root}>
      <Nav />
      <section className="pf-hero">
        <div className="pf-mesh" aria-hidden="true">
          <i />
          <i />
          <i />
          <i />
        </div>
        <div className="pf-hero-copy">
          <p className="pf-live">
            Rows audited on this laptop: <b>{nf(rows)}</b> <span>in {run.elapsed.toFixed(2)} s</span>
          </p>
          <h1>
            Dataset reliability you can check yourself. <span>DataTrust audits training data before you train, flags every risk in its rows, and writes the report your reviewers need.</span>
          </h1>
          <div className="pf-hero-cta">
            <Go to={href(C, 'workspace')} className="pf-btn is-lg">
              Run an audit <i>›</i>
            </Go>
            <Go to={href(C, 'results')} className="pf-link">
              See a real audit ›
            </Go>
          </div>
        </div>
        <div className="pf-stack">
          <ScoreCard />
          <FindingsCard />
          <PairCard />
          <HistCard />
        </div>
      </section>

      <section className="pf-corpora">
        <p>Validated against public corpora, from census tables to images and retrieval sets</p>
        <div className="pf-marquee">
          <div>
            {[...CORPORA, ...CORPORA].map((c, i) => (
              <span key={i}>{c}</span>
            ))}
          </div>
        </div>
      </section>

      <section className="pf-mods" id="pf-product">
        <div className="pf-sec-head pf-rise">
          <h2>
            A complete audit, end to end. <span>From the first byte read to a report a CTO can sign, every step is inspectable.</span>
          </h2>
        </div>
        <div className="pf-mod-grid">
          <article className="pf-mod pf-rise is-wide">
            <div className="pf-mod-copy">
              <h3>Read the whole table</h3>
              <p>Profiles every column of every row. These are Adult's real distributions.</p>
            </div>
            <div className="pf-mod-ui pf-cols">
              {dists.slice(0, 8).map((d) => (
                <div key={d.name}>
                  <code>{d.name}</code>
                  <Spark d={d} width={140} height={26} className="pf-spark" />
                </div>
              ))}
            </div>
          </article>
          <article className="pf-mod pf-rise">
            <div className="pf-mod-copy">
              <h3>Twelve checks, named methods</h3>
              <p>Every check reports its population and method.</p>
            </div>
            <div className="pf-mod-ui pf-checks">
              {checks.slice(0, 6).map((c) => (
                <div key={c.id}>
                  <i />
                  <span>{CHECK_LABELS[c.id]}</span>
                  <code>{c.method}</code>
                </div>
              ))}
              <div className="pf-more">+ 6 more</div>
            </div>
          </article>
          <article className="pf-mod pf-rise">
            <div className="pf-mod-copy">
              <h3>Guardrails, not averages</h3>
              <p>A planted outcome column drops the same table from {run.score} to {leakRun.score}.</p>
            </div>
            <div className="pf-mod-ui pf-guard">
              {[run, leakRun].map((r) => (
                <div key={r.name}>
                  <span>{r.name}</span>
                  <i>
                    <em style={{ width: `${r.evidence}%` }} />
                    <s style={{ left: `${r.score}%` }} />
                  </i>
                  <b>{r.score}</b>
                </div>
              ))}
              <small>Bar: evidence average. Mark: final score after guardrails.</small>
            </div>
          </article>
          <article className="pf-mod pf-rise is-wide">
            <div className="pf-mod-copy">
              <h3>A report people can read</h3>
              <p>One completed result becomes HTML, PDF and strict JSON. This is the real Adult report.</p>
            </div>
            <div className="pf-mod-ui pf-report">
              <img src="round2/report-adult-top.jpg" alt="Real DataTrust report for Adult" />
            </div>
          </article>
        </div>
      </section>

      <section className="pf-calc-sec" id="pf-calc">
        <div className="pf-sec-head pf-rise">
          <p className="pf-eyebrow">Try it</p>
          <h2>
            What is your accuracy hiding? <span>Start with the simplest check DataTrust runs: what a model that learns nothing would score.</span>
          </h2>
        </div>
        <div className="pf-rise">
          <Calculator />
        </div>
      </section>

      <section className="pf-local" id="pf-local">
        <div className="pf-rise">
          <p className="pf-eyebrow">Security</p>
          <h2>Your data stays on your machine.</h2>
          <p>The browser app binds to loopback, jobs are scoped to the process, and every report records the SHA-256 of the bytes it read.</p>
        </div>
        <div className="pf-local-ui pf-rise">
          <div className="pf-term">
            <span>127.0.0.1 · datatrust ui</span>
            <code>source sha256 {run.sha256}</code>
            <code>uploaded 0 bytes</code>
          </div>
        </div>
      </section>

      <footer className="pf-foot">
        <Logo />
        <div>
          <b>Product</b>
          <span>DataTrust</span>
          <span>ConfidenceGuard, in development</span>
          <span>HallucinationGuard, in development</span>
        </div>
        <div>
          <b>Method</b>
          <span>Five sub-scores</span>
          <span>Guardrails</span>
          <span>A report, not a certificate</span>
        </div>
      </footer>
    </div>
  );
}

/* ------------------------------------------------------------ workspace */

function Sidebar({ on }: { on: string }) {
  return (
    <aside className="pf-side">
      <Go to={href(C)} label="Numek home">
        <Logo />
      </Go>
      <nav>
        {['Home', 'Audits', 'Findings', 'Columns', 'Reports'].map((n) => (
          <a key={n} className={on === n ? 'is-on' : ''}>
            {n}
          </a>
        ))}
      </nav>
      <p className="pf-side-h">Workspace</p>
      <p className="pf-side-path">~/numek/audits</p>
      <div className="pf-side-foot">
        <i /> Local · loopback
      </div>
    </aside>
  );
}

function Workspace() {
  const root = useRef<HTMLDivElement>(null);
  useGsap(root, (q) => {
    gsap.from(q('.pf-panel, .pf-kpi'), { opacity: 0, y: 12, stagger: 0.04, duration: 0.6, ease: 'power2.out' });
  });
  const colIssues = columnsProfile
    .filter((c) => c.missing_count > 0 || c.outlier_rate > 5 || c.name === 'marital_status')
    .map((c) => ({
      name: c.name,
      what: c.outlier_rate > 5 ? `${c.outlier_rate}% outside 1.5 × IQR` : c.name === 'marital_status' ? 'Review prediction-time availability' : `${nf(c.missing_count)} missing (${c.missing_rate}%)`,
    }));
  const sev = { High: 0, Moderate: 0, Low: 0 } as Record<string, number>;
  openFindings.forEach((f) => (sev[f.severity] += 1));
  return (
    <div className="c-proof is-app" ref={root}>
      <Sidebar on="Home" />
      <main className="pf-app">
        <header className="pf-app-head">
          <input className="pf-search" placeholder="Search audits, columns and findings" aria-label="Search" />
          <div>
            <Go to="#/" className="pf-link">
              All concepts
            </Go>
            <button className="pf-btn">New audit</button>
          </div>
        </header>
        <h1 className="pf-app-title">Home</h1>
        <section className="pf-kpis">
          <div className="pf-kpi">
            <span>Audits</span>
            <b>7</b>
            <em>4 scored · 3 evidence only</em>
          </div>
          <div className="pf-kpi">
            <span>Need review</span>
            <b>3</b>
            <em>Guardrail applied</em>
          </div>
          <div className="pf-kpi">
            <span>Open findings</span>
            <b>{openFindings.length}</b>
            <em>
              <i className="d hi" />
              {sev.High} high <i className="d mo" />
              {sev.Moderate} moderate <i className="d lo" />
              {sev.Low} low
            </em>
          </div>
          <div className="pf-kpi">
            <span>Rows audited</span>
            <b>{nf(audits.reduce((s, a) => s + a.rows, 0))}</b>
            <em>Across all seven datasets</em>
          </div>
        </section>
        <section className="pf-grid2">
          <div className="pf-panel">
            <header>
              <b>Audits</b>
              <span>Score</span>
            </header>
            <table className="pf-table">
              <thead>
                <tr>
                  <th>Dataset</th>
                  <th>Task</th>
                  <th>Rows</th>
                  <th>Status</th>
                  <th className="r">Score</th>
                  <th className="r">Run</th>
                </tr>
              </thead>
              <tbody>
                {audits.map((a) => (
                  <tr key={a.id} className={a.id === 'adult' ? 'is-link' : ''} onClick={() => a.id === 'adult' && (window.location.hash = href(C, 'results'))}>
                    <td>
                      <b>{a.name}</b>
                    </td>
                    <td>{a.kind}</td>
                    <td className="mono">{nf(a.rows)}</td>
                    <td>
                      <em className={`pf-badge is-${a.score === null ? 'none' : a.band.toLowerCase()}`}>{a.score === null ? 'Evidence only' : a.band}</em>
                    </td>
                    <td className="r mono">{a.score ?? '—'}</td>
                    <td className="r">{lastRun[a.id]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="pf-panel">
            <header>
              <b>Columns needing review</b>
              <span>Adult</span>
            </header>
            {colIssues.map((c) => (
              <div key={c.name} className="pf-colrow">
                <div>
                  <code>{c.name}</code>
                  <span>{c.what}</span>
                </div>
                <Spark d={dist(c.name)} width={110} height={26} className="pf-spark" />
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}

/* -------------------------------------------------------------- results */

function Results() {
  const root = useRef<HTMLDivElement>(null);
  const [sel, setSel] = useState(0);
  const f = run.findings[sel];
  useGsap(root, (q) => {
    gsap.from(q('.pf-panel'), { opacity: 0, y: 12, stagger: 0.05, duration: 0.6, ease: 'power2.out' });
  });
  return (
    <div className="c-proof is-app" ref={root}>
      <Sidebar on="Audits" />
      <main className="pf-app">
        <header className="pf-app-head">
          <p className="pf-crumbs">
            <Go to={href(C, 'workspace')}>Audits</Go> › Adult
          </p>
          <div>
            <button className="pf-btn is-ghost">JSON</button>
            <button className="pf-btn is-ghost">PDF</button>
            <button className="pf-btn">Share report</button>
          </div>
        </header>
        <section className="pf-res-top">
          <div>
            <p className="pf-eyebrow">Binary classification · annual_income_over_50k</p>
            <h1>
              Adult <em className="pf-badge is-elevated">Elevated</em>
            </h1>
          </div>
          <dl className="pf-kv">
            <div>
              <dt>Score</dt>
              <dd>{run.score}</dd>
            </div>
            <div>
              <dt>Evidence</dt>
              <dd>{run.evidence}</dd>
            </div>
            <div>
              <dt>Rows</dt>
              <dd>{nf(run.rows)}</dd>
            </div>
            <div>
              <dt>Checks</dt>
              <dd>12 / 12</dd>
            </div>
            <div>
              <dt>Elapsed</dt>
              <dd>{run.elapsed.toFixed(2)} s</dd>
            </div>
          </dl>
        </section>
        <section className="pf-grid2 is-res">
          <div className="pf-panel">
            <header>
              <b>Findings</b>
              <span>{run.guardrails[0].explanation}</span>
            </header>
            <div className="pf-find-tabs">
              {run.findings.map((x, i) => (
                <button key={x.code} className={i === sel ? 'is-on' : ''} onClick={() => setSel(i)}>
                  <i className={`is-${x.severity.toLowerCase()}`} />
                  {x.title}
                </button>
              ))}
            </div>
            <div className="pf-find-body">
              <h3>{f.finding}</h3>
              <p>{f.modeling_impact}</p>
              <p className="pf-next">
                <b>Review:</b> {f.recommendation}
              </p>
              <p className="pf-effect">{f.score_effect}</p>
              {f.code === 'conflicting_target_labels' && (
                <table className="pf-table is-tight">
                  <thead>
                    <tr>
                      <th>Line</th>
                      <th>Age</th>
                      <th>Education</th>
                      <th>Occupation</th>
                      <th>Hours</th>
                      <th>Label</th>
                    </tr>
                  </thead>
                  {conflictGroups.map((g, gi) => (
                    <tbody key={gi}>
                      {g.map((r) => (
                        <tr key={r.line}>
                          <td className="mono">{nf(Number(r.line))}</td>
                          <td>{r.age}</td>
                          <td>{r.education}</td>
                          <td>{r.occupation}</td>
                          <td>{r.hours_per_week}</td>
                          <td>
                            <em className={`pf-badge ${r.annual_income_over_50k === '>50K' ? 'is-hi' : 'is-none'}`}>{r.annual_income_over_50k.replace('<=', '≤')}</em>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  ))}
                </table>
              )}
            </div>
          </div>
          <div className="pf-panel">
            <header>
              <b>Sub-scores</b>
            </header>
            {SUB_ORDER.map((k) => (
              <div key={k} className={`pf-sub${run.sub[k] < 50 ? ' is-low' : ''}`}>
                <span>{SUB_LABELS[k]}</span>
                <i>
                  <em style={{ width: `${run.sub[k]}%` }} />
                </i>
                <b>{run.sub[k].toFixed(2)}</b>
              </div>
            ))}
            <header className="pf-sub-h">
              <b>Timeline</b>
            </header>
            <ol className="pf-timeline">
              <li>
                <b>Source fingerprinted</b>
                <span>sha256 {run.sha256.slice(0, 18)}…</span>
              </li>
              {checks.slice(0, 5).map((c) => (
                <li key={c.id}>
                  <b>{CHECK_LABELS[c.id]}</b>
                  <span>{c.method}</span>
                </li>
              ))}
              <li>
                <b>+ 7 more checks</b>
                <span>all completed</span>
              </li>
              <li className="is-end">
                <b>Report written</b>
                <span>HTML · PDF · JSON</span>
              </li>
            </ol>
          </div>
        </section>
        <section className="pf-panel pf-colpanel">
          <header>
            <b>Column profile</b>
            <span>All 15 columns, real distributions</span>
          </header>
          <table className="pf-table">
            <thead>
              <tr>
                <th>Column</th>
                <th>Type</th>
                <th className="r">Distinct</th>
                <th className="r">Missing</th>
                <th className="r">Outliers</th>
                <th>Distribution</th>
              </tr>
            </thead>
            <tbody>
              {columnsProfile.map((c) => (
                <tr key={c.name}>
                  <td>
                    <code>{c.name}</code>
                    {c.role === 'target' && <em className="pf-badge is-none">target</em>}
                  </td>
                  <td>{c.dtype}</td>
                  <td className="r mono">{nf(c.unique_count)}</td>
                  <td className={`r mono${c.missing_count ? ' warn' : ''}`}>{c.missing_count ? nf(c.missing_count) : '—'}</td>
                  <td className={`r mono${c.outlier_rate > 5 ? ' warn' : ''}`}>{c.is_numeric ? `${c.outlier_rate}%` : '—'}</td>
                  <td>
                    <Spark d={dist(c.name)} width={180} height={24} className="pf-spark" hot={c.name === 'hours_per_week' ? (lo, hi) => hi <= 32.5 || lo >= 52.5 : undefined} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </main>
    </div>
  );
}

export default function Proof({ screen }: { screen: Screen }) {
  if (screen === 'workspace') return <Workspace />;
  if (screen === 'results') return <Results />;
  return <Landing />;
}
