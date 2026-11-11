import { useRef, useState } from 'react';
import { Go, href, type Screen } from '../../shared/router';
import { gsap, useGsap, useSmoothScroll } from '../../shared/motion';
import { run, leakRun, checks, CHECK_LABELS, SUB_LABELS, SUB_ORDER, conflictGroups, hours, nf } from '../../shared/engine';
import { audits, openFindings, lastRun } from '../../shared/workspace';
import { GlassStack } from './GlassStack';
import './assurance.css';
import '@fontsource-variable/instrument-sans/wdth';
import '@fontsource/ibm-plex-mono/400';
import '@fontsource/ibm-plex-mono/500';

const C = 'assurance';

function Logo() {
  return (
    <span className="as-logo">
      <svg viewBox="0 0 20 20" aria-hidden="true">
        <path d="M2 16 L10 3 L18 16 Z" fill="none" stroke="currentColor" strokeWidth="1.6" />
        <path d="M6 16 L10 9 L14 16" fill="none" stroke="currentColor" strokeWidth="1.6" />
      </svg>
      Numek
    </span>
  );
}

function Nav({ tone = 'dark' }: { tone?: 'dark' | 'light' }) {
  return (
    <header className={`as-nav is-${tone}`}>
      <Go to={href(C)} label="Numek home">
        <Logo />
      </Go>
      <nav>
        {['DataTrust', 'Method', 'Security', 'Company'].map((l) => (
          <a key={l}>{l}</a>
        ))}
        <Go to="#/">All concepts</Go>
        <Go to={href(C, 'workspace')} className="as-nav-cta">
          Open workspace <i />
        </Go>
      </nav>
    </header>
  );
}

const THESIS =
  'Teams using AI for real decisions need inspectable evidence about their data before training. Not a badge, not a single number: the rows, the method and the limits, written so the people who answer for the model can read them.';

function Landing() {
  const root = useRef<HTMLDivElement>(null);
  const [spin, setSpin] = useState(0);
  useSmoothScroll();
  useGsap(root, (q) => {
    gsap.from(q('.as-hero h1 .w'), { yPercent: 110, opacity: 0, duration: 1.1, stagger: 0.06, ease: 'expo.out', delay: 0.1 });
    gsap.from(q('.as-hero-side > *, .as-hero-actions > *'), { opacity: 0, y: 14, duration: 0.8, stagger: 0.08, delay: 0.5 });
    gsap.from(q('.as-glass-tag'), { opacity: 0, duration: 0.6, stagger: 0.12, delay: 1.2 });
    q('.as-up').forEach((el: Element) =>
      gsap.from(el, { opacity: 0, y: 34, duration: 1, ease: 'power3.out', scrollTrigger: { trigger: el, start: 'top 86%' } }),
    );
    gsap.to({}, {
      scrollTrigger: { trigger: q('.as-hero')[0], start: 'top top', end: 'bottom top', scrub: true, onUpdate: (st) => setSpin(st.progress * 1.2) },
    });
    q('.as-lit .w').forEach((el: Element) =>
      gsap.fromTo(el, { opacity: 0.18 }, { opacity: 1, ease: 'none', scrollTrigger: { trigger: el, start: 'top 82%', end: 'top 62%', scrub: true } }),
    );
    gsap.from(q('.as-device'), { y: 120, rotateX: 18, ease: 'none', scrollTrigger: { trigger: q('.as-device')[0], start: 'top bottom', end: 'top 30%', scrub: true } });
  });

  return (
    <div className="c-assurance" ref={root}>
      <Nav />
      <section className="as-hero">
        <div className="as-hero-grid" aria-hidden="true" />
        <div className="as-hero-copy">
          <h1>
            {['Evidence', 'your', 'board', 'can', 'sign', 'off', 'on'].map((w, i) => (
              <span key={i} className="mask">
                <span className="w">{w}</span>
              </span>
            ))}
          </h1>
          <div className="as-hero-actions">
            <Go to={href(C, 'workspace')} className="as-btn">
              Explore the workspace <i />
            </Go>
            <Go to={href(C, 'results')} className="as-btn is-ghost">
              Read a sample assessment
            </Go>
          </div>
        </div>
        <div className="as-hero-object">
          <GlassStack height="min(74vh, 680px)" scrollSpin={spin} />
        </div>
        <div className="as-hero-side">
          <p>
            DataTrust is Numek's dataset reliability product. It audits training data on your own machine and writes an
            assessment a CTO, risk lead or customer can follow.
          </p>
          <p className="as-hero-note">The plates are Adult's five sub-scores, to scale. The short one is target balance, at 47.86.</p>
        </div>
        <article className="as-news">
          <span>Product update · Oct 2026</span>
          <b>Connected evidence: records reconciled against the documents behind them</b>
        </article>
      </section>

      <section className="as-clarity">
        <div className="as-clarity-grid">
          <div className="as-up">
            <p className="as-kicker">Clarity</p>
            <h2>Clarity at every level of the decision</h2>
            <p className="as-body">
              The engineer gets every check, method and row. The decision-maker gets a score that cannot hide a severe
              weakness, and a recommended next action.
            </p>
          </div>
          <div className="as-chartcard as-up">
            <header>
              <span>Adult · assessment</span>
              <em>{run.methodology}</em>
            </header>
            <svg viewBox="0 0 360 200">
              <defs>
                <linearGradient id="as-area" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0" stopColor="#9fc0ff" stopOpacity="0.45" />
                  <stop offset="1" stopColor="#9fc0ff" stopOpacity="0" />
                </linearGradient>
              </defs>
              {[0, 1, 2, 3].map((i) => (
                <line key={i} x1="20" x2="340" y1={30 + i * 45} y2={30 + i * 45} className="grid" />
              ))}
              {SUB_ORDER.map((k, i) => {
                const x = 40 + i * 70;
                const y = 180 - run.sub[k] * 1.5;
                return (
                  <g key={k}>
                    <rect x={x - 14} y={y} width="28" height={180 - y} fill={run.sub[k] < 50 ? '#ffb36b' : 'url(#as-area)'} stroke={run.sub[k] < 50 ? '#ffb36b' : '#cfe0ff'} />
                    <text x={x} y={y - 8} textAnchor="middle">{run.sub[k].toFixed(1)}</text>
                  </g>
                );
              })}
              <line x1="20" x2="340" y1={180 - run.evidence * 1.5} y2={180 - run.evidence * 1.5} className="ev" />
              <line x1="20" x2="340" y1={180 - run.score * 1.5} y2={180 - run.score * 1.5} className="cap" />
              <text x="344" y={180 - run.evidence * 1.5 + 4} className="lbl">{run.evidence}</text>
              <text x="344" y={180 - run.score * 1.5 + 4} className="lbl hi">{run.score}</text>
            </svg>
            <footer>
              <span>Evidence average {run.evidence}</span>
              <span>Capped at {run.score}</span>
            </footer>
          </div>
          <div className="as-notes as-up">
            <div>
              <em>01</em>
              <b>Every risk is explained</b>
              <p>Evidence, modeling impact, recommended review and score effect, for each finding.</p>
            </div>
            <div>
              <em>02</em>
              <b>Severe risks stay visible</b>
              <p>Guardrails cap the score, so a 47.86 cannot be averaged into an 89.</p>
            </div>
          </div>
        </div>
      </section>

      <section className="as-props">
        <div className="as-props-list">
          <p className="as-kicker">Principles</p>
          <h2 className="as-up">A reliability report, built like infrastructure</h2>
          {[
            ['Transparency', 'Committed to readable evidence', 'Five sub-scores, explained guardrails and a deterministic narrative. The methodology is versioned on every report.'],
            ['Independence', 'Runs where your data lives', 'Local execution, loopback only, process-scoped jobs. The SHA-256 of the exact source bytes is recorded.'],
            ['Restraint', 'A report, not a certificate', 'DataTrust does not claim compliance, fairness or model correctness. It shows evidence and its limits.'],
          ].map(([k, t, d]) => (
            <div key={k} className="as-prop as-up">
              <span>{k}</span>
              <b>{t}</b>
              <p>{d}</p>
            </div>
          ))}
        </div>
        <div className="as-props-obj">
          <GlassStack height={560} labels={false} scrollSpin={spin + 1.4} />
        </div>
      </section>

      <section className="as-thesis">
        <p className="as-kicker">Why Numek exists</p>
        <p className="as-lit">
          {THESIS.split(' ').map((w, i) => (
            <span key={i} className="w">
              {w}{' '}
            </span>
          ))}
        </p>
      </section>

      <section className="as-showcase">
        <div className="as-up as-showcase-head">
          <p className="as-kicker">The workspace</p>
          <h2>Every dataset, its assessment and what is still open</h2>
        </div>
        <div className="as-device-wrap">
          <div className="as-device">
            <div className="as-device-screen">
              <MiniWorkspace />
            </div>
            <div className="as-device-base" />
          </div>
        </div>
      </section>

      <section className="as-cta">
        <h2 className="as-up">Bring the dataset. Keep the data.</h2>
        <div className="as-hero-actions as-up">
          <Go to={href(C, 'workspace')} className="as-btn">
            Explore the workspace <i />
          </Go>
          <Go to={href(C, 'results')} className="as-btn is-ghost">
            Read a sample assessment
          </Go>
        </div>
        <footer className="as-foot">
          <Logo />
          <span>Numek, AI reliability verification. DataTrust is available now; ConfidenceGuard and HallucinationGuard are in development.</span>
        </footer>
      </section>
    </div>
  );
}

function MiniWorkspace() {
  return (
    <div className="as-mini">
      <aside>
        <Logo />
        <a className="is-on">Overview</a>
        <a>Audits</a>
        <a>Open findings</a>
        <a>Reports</a>
      </aside>
      <div className="as-mini-main">
        <p className="as-mini-h">Welcome back</p>
        <div className="as-mini-kpis">
          <div>
            <span>Audits</span>
            <b>7</b>
          </div>
          <div>
            <span>Need review</span>
            <b>3</b>
          </div>
          <div>
            <span>Uploaded</span>
            <b>0 bytes</b>
          </div>
        </div>
        <div className="as-mini-rows">
          {audits.slice(0, 5).map((a) => (
            <div key={a.id}>
              <span>{a.name}</span>
              <em>{a.kind}</em>
              <b>{a.score ?? '—'}</b>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------- workspace */

function Workspace() {
  const root = useRef<HTMLDivElement>(null);
  useGsap(root, (q) => {
    gsap.from(q('.as-kpi, .as-panel'), { opacity: 0, y: 14, stagger: 0.05, duration: 0.6, ease: 'power2.out' });
  });
  const scored = audits.filter((a) => a.score !== null);
  return (
    <div className="c-assurance is-app" ref={root}>
      <Nav tone="light" />
      <main className="as-app">
        <section className="as-app-head">
          <div>
            <p className="as-kicker">Workspace · ~/numek/audits</p>
            <h1>Dataset assessments</h1>
          </div>
          <button className="as-btn">New assessment <i /></button>
        </section>
        <section className="as-kpis">
          {[
            ['Datasets assessed', '7', 'Classification, regression, connected evidence'],
            ['Need review', '3', 'Elevated or high, guardrail applied'],
            ['Open findings', String(openFindings.length), '1 high · 5 moderate · 1 low'],
            ['Data uploaded', '0 bytes', 'Loopback only, process-scoped jobs'],
          ].map(([k, v, d]) => (
            <div key={k} className="as-kpi">
              <span>{k}</span>
              <b>{v}</b>
              <em>{d}</em>
            </div>
          ))}
        </section>
        <section className="as-app-grid">
          <div className="as-panel as-accounts">
            <header>
              <b>Assessments</b>
              <span>Score · band · last run</span>
            </header>
            {audits.map((a) => {
              const inner = (
                <>
                  <span className={`as-ico is-${a.score === null ? 'none' : a.band.toLowerCase()}`}>{a.name.slice(0, 1)}</span>
                  <span className="as-acc-name">
                    {a.name}
                    <small>
                      {a.kind} · {nf(a.rows)} {a.kind === 'Connected evidence' ? 'records' : 'rows'}
                    </small>
                  </span>
                  <span className="as-acc-band">{a.score === null ? 'No score defined' : a.band}</span>
                  <span className="as-acc-val">{a.score === null ? '—' : a.score.toFixed(2)}</span>
                  <span className="as-acc-date">{lastRun[a.id]}</span>
                </>
              );
              return a.id === 'adult' ? (
                <Go key={a.id} to={href(C, 'results')} className="as-acc is-link">
                  {inner}
                </Go>
              ) : (
                <div key={a.id} className="as-acc">
                  {inner}
                </div>
              );
            })}
          </div>
          <div className="as-side-col">
            <div className="as-panel as-scorebars">
              <header>
                <b>Scores against guardrails</b>
              </header>
              {scored.map((a) => (
                <div key={a.id} className="as-sb">
                  <span>{a.name}</span>
                  <i>
                    <em style={{ width: `${a.score}%` }} className={`is-${a.band.toLowerCase()}`} />
                    <s style={{ left: '69%' }} />
                    <s style={{ left: '49%' }} />
                  </i>
                  <b>{a.score}</b>
                </div>
              ))}
              <p className="as-sb-note">Marks at 69 and 49 are the guardrail caps seen in these assessments.</p>
            </div>
            <div className="as-panel as-open">
              <header>
                <b>Open findings</b>
              </header>
              {openFindings.slice(0, 5).map((f, i) => (
                <div key={i} className={`as-of is-${f.severity.toLowerCase()}`}>
                  <span>{f.severity}</span>
                  <b>{f.title}</b>
                  <em>{f.audit}</em>
                </div>
              ))}
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

/* ---------------------------------------------------------------- results */

function Results() {
  const root = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(0);
  useGsap(root, (q) => {
    gsap.from(q('.as-memo-head > *, .as-facts'), { opacity: 0, y: 14, stagger: 0.07, duration: 0.7, ease: 'power2.out' });
  });
  return (
    <div className="c-assurance is-app" ref={root}>
      <Nav tone="light" />
      <main className="as-memo">
        <section className="as-memo-head">
          <p className="as-kicker">
            <Go to={href(C, 'workspace')}>Assessments</Go> / Adult
          </p>
          <h1>Adult is not ready for high-stakes use as it stands.</h1>
          <p className="as-memo-lede">
            {run.narrative.overall_assessment as string} {run.narrative.score_explanation as string}
          </p>
          <div className="as-memo-actions">
            <button className="as-btn">Share assessment <i /></button>
            <button className="as-btn is-ghost">Download PDF</button>
            <button className="as-btn is-ghost">JSON evidence</button>
          </div>
        </section>
        <div className="as-memo-body">
          <div className="as-memo-main">
            <section className="as-decision">
              <div>
                <span>Recommended action</span>
                <b>{run.action}</b>
              </div>
              <div>
                <span>Principal evidence</span>
                <p>{run.narrative.principal_evidence_summary as string}</p>
              </div>
            </section>

            <section className="as-sec">
              <h2>Findings, by priority</h2>
              {run.findings.map((f, i) => (
                <article key={f.code} className={`as-find${open === i ? ' is-open' : ''}`}>
                  <button onClick={() => setOpen(open === i ? -1 : i)} aria-expanded={open === i}>
                    <span className={`as-sev is-${f.severity.toLowerCase()}`}>{f.severity}</span>
                    <b>{f.title}</b>
                    <em>{f.evidence}</em>
                    <i />
                  </button>
                  {open === i && (
                    <div className="as-find-body">
                      <p className="as-find-lede">{f.finding}</p>
                      <div className="as-find-cols">
                        <div>
                          <span>What it may do to a model</span>
                          <p>{f.modeling_impact}</p>
                        </div>
                        <div>
                          <span>What to review</span>
                          <p>{f.recommendation}</p>
                        </div>
                        <div>
                          <span>Effect on the score</span>
                          <p>{f.score_effect}</p>
                        </div>
                      </div>
                      {f.code === 'conflicting_target_labels' && (
                        <table className="as-table">
                          <thead>
                            <tr>
                              <th>CSV line</th>
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
                                  <td>{nf(Number(r.line))}</td>
                                  <td>{r.age}</td>
                                  <td>{r.education}</td>
                                  <td>{r.occupation}</td>
                                  <td>{r.hours_per_week}</td>
                                  <td className={r.annual_income_over_50k === '>50K' ? 'hi' : ''}>{r.annual_income_over_50k.replace('<=', '≤')}</td>
                                </tr>
                              ))}
                            </tbody>
                          ))}
                        </table>
                      )}
                      {f.code === 'numeric_outlier_concentration' && (
                        <p className="as-find-fact">
                          hours_per_week quartiles {hours.q!.join(' · ')}. {nf(hours.outlier_count)} rows ({hours.outlier_rate}%) sit outside
                          the 32.5 to 52.5 hour fences.
                        </p>
                      )}
                      {f.code === 'target_imbalance' && (
                        <div className="as-split">
                          {run.profile.target_distribution.map((d) => (
                            <div key={d.label} style={{ flexGrow: d.count }} className={d.label.startsWith('>') ? 'hi' : ''}>
                              <b>{d.label.replace('<=', '≤')}</b> {nf(d.count)} · {d.percentage}%
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </article>
              ))}
            </section>

            <section className="as-sec">
              <h2>What was checked</h2>
              <div className="as-checks">
                {checks.map((c) => (
                  <div key={c.id}>
                    <i />
                    <b>{CHECK_LABELS[c.id]}</b>
                    <code>{c.method}</code>
                  </div>
                ))}
              </div>
              <p className="as-limits">
                <b>Limits.</b> {run.coverage.meaning} Not covered: {run.coverage.unsupported_capabilities.join(', ')}. This assessment does not
                establish compliance, fairness or model correctness.
              </p>
            </section>
          </div>
          <aside className="as-facts">
            <div className="as-facts-score">
              <b>{run.score}</b>
              <span>{run.band}</span>
            </div>
            <div className="as-facts-subs">
              {SUB_ORDER.map((k) => (
                <div key={k} className={run.sub[k] < 50 ? 'is-crit' : ''}>
                  <span>{SUB_LABELS[k]}</span>
                  <b>{run.sub[k].toFixed(2)}</b>
                </div>
              ))}
            </div>
            <dl>
              <dt>Dataset</dt>
              <dd>adult.csv · {nf(run.rows)} × {run.columns}</dd>
              <dt>Target</dt>
              <dd>annual_income_over_50k</dd>
              <dt>Source</dt>
              <dd className="mono">{run.sha256.slice(0, 24)}…</dd>
              <dt>Method</dt>
              <dd className="mono">{run.methodology}</dd>
              <dt>Executed</dt>
              <dd>Locally in {run.elapsed.toFixed(2)} s</dd>
            </dl>
            <p className="as-facts-cmp">
              For contrast, a planted outcome column drops the same table to {leakRun.score} ({leakRun.band}).
            </p>
          </aside>
        </div>
      </main>
    </div>
  );
}

export default function Assurance({ screen }: { screen: Screen }) {
  if (screen === 'workspace') return <Workspace />;
  if (screen === 'results') return <Results />;
  return <Landing />;
}
