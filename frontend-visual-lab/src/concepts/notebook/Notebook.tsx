import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Go, href, type Screen } from '../../shared/router';
import { gsap, useGsap, useSmoothScroll } from '../../shared/motion';
import { run, conflictGroups, columnsProfile, hours, nf, SUB_LABELS, SUB_ORDER, checks, CHECK_LABELS } from '../../shared/engine';
import { dist } from '../../shared/distributions';
import { Spark } from '../../shared/Spark';
import { audits, lastRun } from '../../shared/workspace';
import { prefersReduced } from '../../shared/motion';
import './notebook.css';
import '@fontsource/libre-baskerville/400';
import '@fontsource/libre-baskerville/400-italic';
import '@fontsource-variable/albert-sans/wght';
import '@fontsource-variable/source-code-pro/wght';

const C = 'notebook';

/* Every output below is what the real Python API returned for adult.csv. */
const CELLS: { code: string; out: ReactNode }[] = [
  {
    code: 'from datatrust import DataTrust\n\naudit = DataTrust("adult.csv", target="annual_income_over_50k", task="classification")\nresult = audit.analyze()',
    out: <span className="nb-out-dim">profile, scores, risks, findings, narrative, context</span>,
  },
  {
    code: 'result["scores"]["overall"], result["scores"]["evidence_score"]',
    out: <span>(69.0, 89.15)</span>,
  },
  {
    code: '[f["title"] for f in result["findings"]]',
    out: (
      <span>
        ['Potentially conflicting target labels',
        <br />
        &nbsp;'Target imbalance',
        <br />
        &nbsp;'Numeric outlier concentration',
        <br />
        &nbsp;'Leakage review prompts']
      </span>
    ),
  },
  {
    code: 'audit.generate_report("adult.html")',
    out: <span className="nb-out-file">adult.html · decision summary, evidence and appendix</span>,
  },
];

function Logo() {
  return (
    <span className="nb-logo">
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <rect x="2" y="3" width="20" height="18" rx="3" fill="none" stroke="currentColor" strokeWidth="1.6" />
        <path d="M7 9l3 3-3 3M12 15h5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      Numek
    </span>
  );
}

function Nav() {
  return (
    <header className="nb-nav">
      <nav>
        <a href="#nb-how">Product</a>
        <a href="#nb-cycle">Method</a>
        <Go to={href(C, 'workspace')}>Notebooks</Go>
      </nav>
      <Go to={href(C)} label="Numek home">
        <Logo />
      </Go>
      <nav className="r">
        <Go to="#/">All concepts</Go>
        <Go to={href(C, 'workspace')} className="nb-btn">
          Get started
        </Go>
      </nav>
    </header>
  );
}

function TypedCell({ code, out, n, start }: { code: string; out: ReactNode; n: number; start: boolean }) {
  const reduced = prefersReduced();
  const [shown, setShown] = useState(reduced ? code.length : 0);
  const [ran, setRan] = useState(reduced);
  useEffect(() => {
    if (!start || reduced) return;
    let i = 0;
    const id = setInterval(() => {
      i += 2;
      setShown(Math.min(i, code.length));
      if (i >= code.length) {
        clearInterval(id);
        setTimeout(() => setRan(true), 280);
      }
    }, 14);
    return () => clearInterval(id);
  }, [start, code, reduced]);
  return (
    <div className={`nb-cell${ran ? ' is-ran' : ''}`}>
      <span className="nb-cell-n">[{ran ? n : start ? '*' : ' '}]</span>
      <pre className="nb-code">
        {code.slice(0, shown)}
        {!ran && start && <i className="nb-caret" />}
      </pre>
      {ran && <div className="nb-out">{out}</div>}
    </div>
  );
}

function HeroNotebook() {
  const [step, setStep] = useState(prefersReduced() ? CELLS.length : 0);
  useEffect(() => {
    if (step >= CELLS.length) return;
    const t = setTimeout(() => setStep((s) => s + 1), step === 0 ? 900 : CELLS[step - 1].code.length * 7 + 900);
    return () => clearTimeout(t);
  }, [step]);
  return (
    <div className="nb-hero-nb">
      <div className="nb-nb-bar">
        <span className="nb-dot" />
        <span className="nb-dot" />
        <span className="nb-dot" />
        <b>adult_audit.ipynb</b>
        <em>Python 3 · local kernel</em>
      </div>
      {CELLS.map((c, i) => (
        <TypedCell key={i} code={c.code} out={c.out} n={i + 1} start={step > i} />
      ))}
    </div>
  );
}

/* --------------------------------------------------------------- landing */

function Landing() {
  const root = useRef<HTMLDivElement>(null);
  useSmoothScroll();
  useGsap(root, (q) => {
    gsap.from(q('.nb-hero h1 > span, .nb-chips, .nb-hero-cta'), { opacity: 0, y: 18, stagger: 0.1, duration: 1, ease: 'expo.out' });
    gsap.from(q('.nb-hero-nb'), { opacity: 0, y: 40, duration: 1.2, ease: 'expo.out', delay: 0.3 });
    q('.nb-rise').forEach((el: Element) =>
      gsap.from(el, { opacity: 0, y: 28, duration: 1, ease: 'power3.out', scrollTrigger: { trigger: el, start: 'top 88%' } }),
    );
    gsap.from(q('.nb-orbit-node'), { scale: 0.7, opacity: 0, stagger: 0.15, duration: 0.9, ease: 'back.out(1.6)', scrollTrigger: { trigger: q('.nb-orbit')[0], start: 'top 75%' } });
  });
  return (
    <div className="c-notebook" ref={root}>
      <div className="nb-announce">
        New: connected evidence for records and the documents behind them <span>→</span>
      </div>
      <Nav />
      <section className="nb-hero">
        <h1>
          <span>Know your data</span>
          <span className="nb-serif">before your model does</span>
        </h1>
        <p className="nb-chips">
          Check <span className="nb-chip">◍ label conflicts</span>
          <span className="nb-chip">◍ target balance</span>
          <span className="nb-chip">◍ leakage</span> and <span className="nb-chip">◍ provenance</span> right where you train.
        </p>
        <div className="nb-hero-cta">
          <Go to={href(C, 'workspace')} className="nb-btn is-lg">
            Get started locally
          </Go>
          <Go to={href(C, 'results')} className="nb-btn is-ghost is-lg">
            Open the Adult notebook
          </Go>
        </div>
        <HeroNotebook />
      </section>

      <section className="nb-how" id="nb-how">
        <div className="nb-how-copy nb-rise">
          <h2>A different approach to dataset QA</h2>
          <p>Profiling libraries describe columns. DataTrust decides what deserves attention, explains why, and keeps the evidence attached, all in the same Python session you train in.</p>
        </div>
        <div className="nb-frags">
          <article className="nb-frag nb-rise">
            <span className="nb-frag-tag">Score</span>
            <b className="nb-big">{run.score}</b>
            <p>Elevated · capped from {run.evidence}</p>
            <div className="nb-subs">
              {SUB_ORDER.map((k) => (
                <div key={k} className={run.sub[k] < 50 ? 'is-low' : ''}>
                  <span>{SUB_LABELS[k]}</span>
                  <b>{run.sub[k].toFixed(1)}</b>
                </div>
              ))}
            </div>
          </article>
          <article className="nb-frag nb-rise">
            <span className="nb-frag-tag">hours_per_week</span>
            <b className="nb-big">{hours.outlier_rate}%</b>
            <p>outside the 1.5 × IQR fences</p>
            <Spark d={dist('hours_per_week')} width={280} height={70} gap={2} className="nb-spark" hot={(lo, hi) => hi <= 32.5 || lo >= 52.5} />
          </article>
          <article className="nb-frag nb-rise">
            <span className="nb-frag-tag">Label conflicts</span>
            <b className="nb-big">5</b>
            <p>groups, 10 rows</p>
            <div className="nb-pairs">
              {conflictGroups.slice(0, 2).flat().map((r) => (
                <div key={r.line}>
                  <code>{nf(Number(r.line))}</code>
                  <span>
                    {r.age} · {r.education}
                  </span>
                  <em className={r.annual_income_over_50k === '>50K' ? 'is-hot' : ''}>{r.annual_income_over_50k.replace('<=', '≤')}</em>
                </div>
              ))}
            </div>
          </article>
        </div>
      </section>

      <section className="nb-cycle" id="nb-cycle">
        <div className="nb-orbit nb-rise">
          <svg viewBox="0 0 400 400" aria-hidden="true">
            <circle cx="200" cy="200" r="150" />
            <circle cx="200" cy="200" r="105" className="dash" />
          </svg>
          {[
            ['Audit', 'Twelve checks', 'top'],
            ['Explain', 'Impact and next step', 'right'],
            ['Report', 'HTML · PDF · JSON', 'bottom'],
            ['Decide', 'Fix, then audit again', 'left'],
          ].map(([t, d, pos]) => (
            <div key={t} className={`nb-orbit-node is-${pos}`}>
              <b>{t}</b>
              <span>{d}</span>
            </div>
          ))}
          <div className="nb-orbit-core">
            Evidence
            <br />
            <i>stays attached</i>
          </div>
        </div>
        <div className="nb-cycle-copy nb-rise">
          <h2>
            Ground every decision
            <br />
            <span className="nb-serif">in the rows themselves</span>
          </h2>
          <p>Each finding records its check, method, population and effect on the score, so the person who reads the report can ask the same question you did and get the same answer.</p>
          <div className="nb-check-list">
            {checks.map((c) => (
              <span key={c.id}>{CHECK_LABELS[c.id]}</span>
            ))}
          </div>
        </div>
      </section>

      <section className="nb-local nb-rise">
        <h2>
          Private by default, <span className="nb-serif">not by promise</span>
        </h2>
        <p>Runs in your process or on 127.0.0.1. Nothing is uploaded. Every report carries the SHA-256 of the bytes it read.</p>
        <code>{run.sha256}</code>
      </section>

      <footer className="nb-foot">
        <Logo />
        <span>Numek · DataTrust. A reliability report, not a certificate.</span>
      </footer>
    </div>
  );
}

/* ------------------------------------------------------------- workspace */

function Workspace() {
  const root = useRef<HTMLDivElement>(null);
  useGsap(root, (q) => {
    gsap.from(q('.nb-proj'), { opacity: 0, y: 14, stagger: 0.05, duration: 0.6 });
  });
  return (
    <div className="c-notebook is-app" ref={root}>
      <Nav />
      <main className="nb-projects">
        <header className="nb-proj-head">
          <div>
            <h1>
              Notebooks <span className="nb-serif">in ~/numek/audits</span>
            </h1>
            <p>One notebook per audit. Each holds the result, its evidence and the exported report.</p>
          </div>
          <button className="nb-btn">New audit notebook</button>
        </header>
        <div className="nb-proj-grid">
          {audits.map((a) => {
            const inner = (
              <>
                <div className="nb-proj-thumb">
                  {a.sub ? (
                    <div className="nb-proj-bars">
                      {a.sub.map((v, i) => (
                        <i key={i} style={{ height: `${v}%` }} className={v < 50 ? 'is-low' : ''} />
                      ))}
                    </div>
                  ) : (
                    <pre>{`# ${a.kind.toLowerCase()}\n# no score defined\nfindings = ${a.findings}`}</pre>
                  )}
                </div>
                <div className="nb-proj-meta">
                  <b>{a.name}</b>
                  <span>
                    {a.kind} · {nf(a.rows)} {a.kind === 'Connected evidence' ? 'records' : 'rows'}
                  </span>
                  <span className="nb-proj-foot">
                    {a.score === null ? <em className="nb-tag">evidence only</em> : <em className={`nb-tag is-${a.band.toLowerCase()}`}>{a.score} · {a.band}</em>}
                    <i>{lastRun[a.id]}</i>
                  </span>
                </div>
              </>
            );
            return a.id === 'adult' ? (
              <Go key={a.id} to={href(C, 'results')} className="nb-proj is-link">
                {inner}
              </Go>
            ) : (
              <div key={a.id} className="nb-proj">
                {inner}
              </div>
            );
          })}
        </div>
      </main>
    </div>
  );
}

/* --------------------------------------------------------------- results */

function Results() {
  const root = useRef<HTMLDivElement>(null);
  useGsap(root, (q) => {
    gsap.from(q('.nb-doc > *'), { opacity: 0, y: 12, stagger: 0.04, duration: 0.6 });
  });
  return (
    <div className="c-notebook is-app" ref={root}>
      <Nav />
      <main className="nb-ide">
        <aside className="nb-files">
          <p className="nb-files-h">~/numek/audits</p>
          {audits.map((a) => (
            <span key={a.id} className={a.id === 'adult' ? 'is-on' : ''}>
              {a.id}_audit.ipynb
            </span>
          ))}
          <p className="nb-files-h">Artifacts</p>
          <span>adult.html</span>
          <span>adult.pdf</span>
          <span>adult.json</span>
        </aside>
        <article className="nb-doc">
          <div className="nb-doc-title">
            <p className="nb-crumb">
              <Go to={href(C, 'workspace')}>Notebooks</Go> / adult_audit.ipynb
            </p>
            <h1>
              Adult <span className="nb-serif">reliability audit</span>
            </h1>
            <p>
              {run.narrative.overall_assessment as string} {run.narrative.score_explanation as string}
            </p>
          </div>
          {CELLS.slice(0, 2).map((c, i) => (
            <div key={i} className="nb-cell is-ran">
              <span className="nb-cell-n">[{i + 1}]</span>
              <pre className="nb-code">{c.code}</pre>
              <div className="nb-out">{c.out}</div>
            </div>
          ))}
          {run.findings.map((f, i) => (
            <section key={f.code} className="nb-md">
              <h2>
                {i + 1}. {f.title} <em className={`nb-tag is-${f.severity.toLowerCase()}`}>{f.severity}</em>
              </h2>
              <p>{f.finding}</p>
              <p className="nb-md-meta">
                <b>Impact.</b> {f.modeling_impact} <b>Review.</b> {f.recommendation}
              </p>
              {f.code === 'conflicting_target_labels' && (
                <div className="nb-cell is-ran">
                  <span className="nb-cell-n">[{3}]</span>
                  <pre className="nb-code">{`import pandas as pd\ndf = pd.read_csv("adult.csv")\ndf.loc[[${conflictGroups.flat().map((r) => Number(r.line) - 2).join(', ')}],\n       ["age", "education", "occupation", "hours_per_week", "annual_income_over_50k"]]`}</pre>
                  <div className="nb-out">
                    <table className="nb-df">
                      <thead>
                        <tr>
                          <th />
                          <th>age</th>
                          <th>education</th>
                          <th>occupation</th>
                          <th>hours_per_week</th>
                          <th>annual_income_over_50k</th>
                        </tr>
                      </thead>
                      <tbody>
                        {conflictGroups.flat().map((r) => (
                          <tr key={r.line}>
                            <th>{Number(r.line) - 2}</th>
                            <td>{r.age}</td>
                            <td>{r.education}</td>
                            <td>{r.occupation}</td>
                            <td>{r.hours_per_week}</td>
                            <td className={r.annual_income_over_50k === '>50K' ? 'is-hot' : ''}>{r.annual_income_over_50k}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <p className="nb-df-note">Index is the zero-based row; CSV line = index + 2.</p>
                  </div>
                </div>
              )}
              {f.code === 'numeric_outlier_concentration' && (
                <div className="nb-plot">
                  <Spark d={dist('hours_per_week')} width={640} height={160} gap={3} className="nb-spark" hot={(lo, hi) => hi <= 32.5 || lo >= 52.5} />
                  <p>
                    hours_per_week · {nf(hours.outlier_count)} rows outside 32.5–52.5 h
                  </p>
                </div>
              )}
              {f.code === 'target_imbalance' && (
                <div className="nb-plot nb-split">
                  {run.profile.target_distribution.map((d) => (
                    <div key={d.label} style={{ flexGrow: d.count }} className={d.label.startsWith('>') ? 'is-hot' : ''}>
                      <b>{d.percentage}%</b>
                      <span>
                        {d.label} · {nf(d.count)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
              <p className="nb-effect">{f.score_effect}</p>
            </section>
          ))}
          <div className="nb-cell is-ran">
            <span className="nb-cell-n">[{4}]</span>
            <pre className="nb-code">{CELLS[3].code}</pre>
            <div className="nb-out">{CELLS[3].out}</div>
          </div>
        </article>
        <aside className="nb-context">
          <p className="nb-files-h">Columns</p>
          {columnsProfile.map((c) => (
            <div key={c.name} className={`nb-ctx-col${c.outlier_rate > 5 || c.name === 'marital_status' || c.role === 'target' ? ' is-flag' : ''}`}>
              <code>{c.name}</code>
              <Spark d={dist(c.name)} width={120} height={20} className="nb-spark" />
              <span>
                {c.dtype}
                {c.missing_count ? ` · ${nf(c.missing_count)} na` : ''}
              </span>
            </div>
          ))}
          <div className="nb-ctx-actions">
            <button className="nb-btn">Export report</button>
          </div>
        </aside>
      </main>
    </div>
  );
}

export default function Notebook({ screen }: { screen: Screen }) {
  if (screen === 'workspace') return <Workspace />;
  if (screen === 'results') return <Results />;
  return <Landing />;
}
