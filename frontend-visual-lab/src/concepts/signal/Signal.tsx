import { useEffect, useRef, useState } from 'react';
import { Go, href, type Screen } from '../../shared/router';
import { gsap, useGsap, useSmoothScroll, ScrollTrigger } from '../../shared/motion';
import { run, checks, CHECK_LABELS, SUB_LABELS, SUB_ORDER, conflictGroups, hours, nf, cliTranscript, capabilitiesList } from './content';
import { audits, openFindings, lastRun } from '../../shared/workspace';
import './signal.css';
import '@fontsource-variable/figtree/wght';
import '@fontsource/fira-code/400';
import '@fontsource/fira-code/500';

const C = 'signal';

function Ribbons({ quiet }: { quiet?: boolean }) {
  return (
    <div className={`sg-ribbons${quiet ? ' is-quiet' : ''}`} aria-hidden="true">
      {[0, 1, 2, 3, 4].map((i) => (
        <i key={i} style={{ ['--i' as string]: i }} />
      ))}
      <b />
    </div>
  );
}

function Mark() {
  return (
    <svg viewBox="0 0 20 20" className="sg-mark" aria-hidden="true">
      <defs>
        <linearGradient id="sg-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#ff3d8b" />
          <stop offset="1" stopColor="#ff7a45" />
        </linearGradient>
      </defs>
      <rect x="1" y="1" width="18" height="18" rx="5" fill="url(#sg-g)" />
      <path d="M6 14V6l8 8V6" fill="none" stroke="#fff" strokeWidth="1.8" />
    </svg>
  );
}

function Nav() {
  return (
    <header className="sg-nav">
      <Go to={href(C)} className="sg-brand" label="Numek DataTrust">
        <Mark /> DataTrust
      </Go>
      <nav>
        <a href="#features">Features</a>
        <a href="#checks">Checks</a>
        <a href="#local">Local</a>
        <Go to="#/">All concepts</Go>
      </nav>
      <Go to={href(C, 'workspace')} className="sg-btn is-light">
        Open DataTrust
      </Go>
    </header>
  );
}

const FEATURES = [
  { id: 'checks', t: 'Whole-table checks', d: 'Twelve checks over every row, each with a named method and population.' },
  { id: 'guard', t: 'Guardrails that hold', d: 'Five transparent sub-scores. A critical one caps the result.' },
  { id: 'rows', t: 'Evidence you can open', d: 'Every finding resolves to rows, columns and CSV lines.' },
  { id: 'cli', t: 'Python, CLI or browser', d: 'One engine, three ways in. Same result, byte for byte.' },
];

function FeaturePanel({ id }: { id: string }) {
  if (id === 'guard')
    return (
      <div className="sg-panel-card">
        <div className="sg-seg">
          <span className="is-on">Sub-scores</span>
          <span>Guardrails</span>
        </div>
        {SUB_ORDER.map((k) => (
          <div key={k} className={`sg-bench${run.sub[k] < 50 ? ' is-hot' : ''}`}>
            <span>{SUB_LABELS[k].toUpperCase()}</span>
            <i>
              <em style={{ width: `${run.sub[k]}%` }} />
            </i>
            <b>{run.sub[k].toFixed(2)}</b>
          </div>
        ))}
        <div className="sg-bench-cap">
          Evidence {run.evidence} → capped at <b>{run.score}</b>
        </div>
      </div>
    );
  if (id === 'rows')
    return (
      <div className="sg-panel-card sg-panel-table">
        <p>label_conflicts · 5 groups · 10 rows</p>
        <table>
          <tbody>
            {conflictGroups.slice(0, 3).flat().map((r) => (
              <tr key={r.line}>
                <td>{nf(Number(r.line))}</td>
                <td>{r.age}</td>
                <td>{r.education}</td>
                <td>{r.occupation}</td>
                <td className={r.annual_income_over_50k === '>50K' ? 'hot' : ''}>{r.annual_income_over_50k.replace('<=', '≤')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  if (id === 'cli')
    return (
      <div className="sg-panel-card sg-term">
        <span className="sg-term-tag">Terminal</span>
        <pre>{cliTranscript.join('\n')}</pre>
      </div>
    );
  return (
    <div className="sg-panel-card sg-checklist">
      {checks.map((c, i) => (
        <div key={c.id} style={{ ['--d' as string]: `${i * 60}ms` }}>
          <i />
          <span>{CHECK_LABELS[c.id]}</span>
          <code>{c.method}</code>
        </div>
      ))}
    </div>
  );
}

function Palette({ open = true }: { open?: boolean }) {
  const [q, setQ] = useState('');
  const items = [
    { g: 'Audits', t: 'Open Adult', s: '69 · Elevated · 4 findings', k: '↵' },
    { g: 'Audits', t: 'Open Adult with planted leakage', s: '49 · High', k: '' },
    { g: 'Findings', t: 'Show conflicting labels in Adult', s: '5 groups · 10 rows', k: '' },
    { g: 'Findings', t: 'Show hours_per_week outliers', s: `${hours.outlier_rate}% outside 1.5 × IQR`, k: '' },
    { g: 'Actions', t: 'New audit from file…', s: 'CSV, Parquet, JSONL, images', k: '⌘N' },
    { g: 'Actions', t: 'Export Adult report', s: 'HTML · PDF · JSON', k: '⌘E' },
  ].filter((x) => x.t.toLowerCase().includes(q.toLowerCase()));
  if (!open) return null;
  return (
    <div className="sg-palette" role="dialog" aria-label="Command palette">
      <div className="sg-palette-in">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search audits, findings and actions…" aria-label="Command" />
        <span className="sg-kbd">esc</span>
      </div>
      <div className="sg-palette-list">
        {items.map((x, i) => (
          <div key={x.t} className={`sg-pi${i === 0 ? ' is-on' : ''}`}>
            {(i === 0 || items[i - 1].g !== x.g) && <p>{x.g}</p>}
            <div>
              <i className={`sg-pi-ico is-${x.g.toLowerCase()}`} />
              <b>{x.t}</b>
              <span>{x.s}</span>
              {x.k && <kbd>{x.k}</kbd>}
            </div>
          </div>
        ))}
      </div>
      <div className="sg-palette-foot">
        <span>
          <Mark /> DataTrust · local
        </span>
        <span>
          Open <kbd>↵</kbd> Actions <kbd>⌘K</kbd>
        </span>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- landing */

function Landing() {
  const root = useRef<HTMLDivElement>(null);
  const [feat, setFeat] = useState(0);
  useSmoothScroll();
  useGsap(root, (q) => {
    gsap.from(q('.sg-hero h1, .sg-hero p, .sg-hero-ctas, .sg-hero-meta'), { opacity: 0, y: 24, stagger: 0.09, duration: 1, ease: 'expo.out' });
    gsap.from(q('.sg-hero-app'), { opacity: 0, y: 80, scale: 0.96, duration: 1.4, ease: 'expo.out', delay: 0.3 });
    gsap.from(q('.sg-chip'), { opacity: 0, y: 14, scale: 0.9, stagger: 0.15, duration: 0.7, delay: 1.1, ease: 'back.out(2)' });
    q('.sg-rise').forEach((el: Element) =>
      gsap.from(el, { opacity: 0, y: 40, duration: 1, ease: 'power3.out', scrollTrigger: { trigger: el, start: 'top 86%' } }),
    );
    ScrollTrigger.create({
      trigger: q('.sg-feat')[0],
      start: 'top 40%',
      end: 'bottom 60%',
      onUpdate: (st) => setFeat(Math.min(FEATURES.length - 1, Math.floor(st.progress * FEATURES.length))),
    });
    gsap.from(q('.sg-ext'), { opacity: 0, y: 30, stagger: 0.05, duration: 0.8, scrollTrigger: { trigger: q('.sg-exts')[0], start: 'top 80%' } });
  });

  return (
    <div className="c-signal" ref={root}>
      <Nav />
      <section className="sg-hero">
        <Ribbons />
        <div className="sg-hero-copy">
          <p className="sg-pill-tag">
            <span>New</span> Connected evidence for records and their documents
          </p>
          <h1>
            Find the flaw
            <br />
            before the model does.
          </h1>
          <p>A fast, local reliability check for training data. Twelve checks, transparent scores and the exact rows behind every finding.</p>
          <div className="sg-hero-ctas">
            <Go to={href(C, 'workspace')} className="sg-btn is-grad">
              Open DataTrust
            </Go>
            <code className="sg-cmd">$ datatrust ui</code>
          </div>
          <p className="sg-hero-meta">Python 3.10+ · runs offline · loopback only</p>
        </div>
        <div className="sg-hero-app">
          <div className="sg-desktop">
            <div className="sg-desktop-bar">
              <span>DataTrust</span>
              <span>~/numek/audits</span>
              <span>loopback · 127.0.0.1</span>
            </div>
            <Palette />
          </div>
          <div className="sg-chip c1">
            <span>Adult · final score</span>
            <b>69 · Elevated</b>
          </div>
          <div className="sg-chip c2">
            <span>Read locally</span>
            <b>{nf(run.rows)} rows in {run.elapsed.toFixed(2)} s</b>
          </div>
          <div className="sg-chip c3">
            <span>Uploaded</span>
            <b>0 bytes</b>
          </div>
        </div>
      </section>

      <section className="sg-stats">
        {[
          [nf(run.rows), 'rows audited'],
          [`${run.elapsed.toFixed(2)} s`, 'on a laptop'],
          ['12 / 12', 'checks completed'],
          ['3', 'report formats'],
        ].map(([v, l]) => (
          <div key={l} className="sg-rise">
            <b>{v}</b>
            <span>{l}</span>
          </div>
        ))}
      </section>

      <section className="sg-feat" id="features">
        <div className="sg-feat-l">
          <p className="sg-eyebrow">Why DataTrust</p>
          <div className="sg-feat-list">
            {FEATURES.map((f, i) => (
              <button key={f.id} className={i === feat ? 'is-on' : ''} onClick={() => setFeat(i)}>
                <b>{f.t}</b>
                {i === feat && <span>{f.d}</span>}
              </button>
            ))}
          </div>
        </div>
        <div className="sg-feat-r">
          <div className="sg-feat-stage">
            <Ribbons quiet />
            <div className="sg-feat-panel" key={FEATURES[feat].id}>
              <FeaturePanel id={FEATURES[feat].id} />
            </div>
          </div>
        </div>
      </section>

      <section className="sg-exts" id="checks">
        <div className="sg-exts-head sg-rise">
          <h2>
            There is a check for that.
            <span> Tables, time, text, images and the documents behind records.</span>
          </h2>
        </div>
        <div className="sg-exts-grid">
          {capabilitiesList.map((c, i) => (
            <article key={c.name} className="sg-ext" style={{ ['--h' as string]: `${(i * 37) % 360}deg` }}>
              <i />
              <b>{c.name}</b>
              <span>{c.detail}</span>
            </article>
          ))}
        </div>
      </section>

      <section className="sg-local" id="local">
        <Ribbons quiet />
        <div className="sg-local-in sg-rise">
          <h2>Your data never leaves your machine.</h2>
          <p>
            Loopback-only browser app, process-scoped jobs and the SHA-256 of the source bytes on every report.
            <br />
            <code>{run.sha256.slice(0, 32)}…</code>
          </p>
          <Go to={href(C, 'results')} className="sg-btn is-light">
            See the Adult audit
          </Go>
        </div>
      </section>

      <footer className="sg-foot">
        <span>
          <Mark /> Numek DataTrust
        </span>
        <span>A reliability report, not a certificate.</span>
      </footer>
    </div>
  );
}

/* -------------------------------------------------------------- workspace */

function Workspace() {
  const root = useRef<HTMLDivElement>(null);
  const [sel, setSel] = useState(0);
  const [pal, setPal] = useState(false);
  const a = audits[sel];
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setPal((p) => !p);
      }
      if (e.key === 'Escape') setPal(false);
      if (e.key === 'ArrowDown') setSel((s) => Math.min(audits.length - 1, s + 1));
      if (e.key === 'ArrowUp') setSel((s) => Math.max(0, s - 1));
    };
    window.addEventListener('keydown', on);
    return () => window.removeEventListener('keydown', on);
  }, []);
  useGsap(root, (q) => {
    gsap.from(q('.sg-row'), { opacity: 0, x: -8, stagger: 0.035, duration: 0.4 });
  });
  const flags = openFindings.filter((f) => f.auditId === a.id);
  return (
    <div className="c-signal is-app" ref={root}>
      <Ribbons quiet />
      <div className="sg-win">
        <header className="sg-win-bar">
          <Go to={href(C)} className="sg-brand">
            <Mark /> DataTrust
          </Go>
          <button className="sg-search" onClick={() => setPal(true)}>
            Search audits, findings and actions <kbd>⌘K</kbd>
          </button>
          <div className="sg-win-r">
            <Go to="#/" className="sg-btn is-ghost">
              All concepts
            </Go>
            <button className="sg-btn is-grad">New audit</button>
          </div>
        </header>
        <div className="sg-win-body">
          <div className="sg-rows" role="listbox" aria-label="Audits">
            <p className="sg-rows-h">
              Audits <span>↑↓ to move · ↵ to open</span>
            </p>
            {audits.map((x, i) => (
              <button key={x.id} role="option" aria-selected={sel === i} className={`sg-row${sel === i ? ' is-on' : ''}`} onClick={() => setSel(i)}>
                <i className={`sg-badge is-${x.score === null ? 'none' : x.band.toLowerCase()}`}>{x.score === null ? '—' : Math.round(x.score)}</i>
                <span>
                  <b>{x.name}</b>
                  <em>
                    {x.kind} · {nf(x.rows)} {x.kind === 'Connected evidence' ? 'records' : 'rows'}
                  </em>
                </span>
                <small>{lastRun[x.id]}</small>
              </button>
            ))}
          </div>
          <div className="sg-detail">
            <div className="sg-detail-hero">
              <Ribbons quiet />
              <div>
                <p className="sg-eyebrow">{a.kind}</p>
                <h1>{a.name}</h1>
                <p>{a.note}.</p>
              </div>
              <div className="sg-detail-score">
                <b>{a.score === null ? '—' : a.score}</b>
                <span>{a.band}</span>
              </div>
            </div>
            <div className="sg-detail-grid">
              <div className="sg-card">
                <p className="sg-card-h">Sub-scores</p>
                {a.sub ? (
                  a.sub.map((v, i) => (
                    <div key={i} className={`sg-bench${v < 50 ? ' is-hot' : ''}`}>
                      <span>{SUB_LABELS[SUB_ORDER[i]].toUpperCase()}</span>
                      <i>
                        <em style={{ width: `${v}%` }} />
                      </i>
                      <b>{v.toFixed(1)}</b>
                    </div>
                  ))
                ) : (
                  <p className="sg-muted">No scoring policy is defined for this task. DataTrust reports evidence without inventing a score.</p>
                )}
              </div>
              <div className="sg-card">
                <p className="sg-card-h">Open findings</p>
                {flags.length ? (
                  flags.map((f, i) => (
                    <div key={i} className="sg-flag">
                      <i className={`is-${f.severity.toLowerCase()}`} />
                      <span>
                        <b>{f.title}</b>
                        <em>{f.detail}</em>
                      </span>
                    </div>
                  ))
                ) : (
                  <p className="sg-muted">{a.findings} findings in the report, none open.</p>
                )}
              </div>
            </div>
            <div className="sg-detail-actions">
              {a.id === 'adult' ? (
                <Go to={href(C, 'results')} className="sg-btn is-grad">
                  Open audit <kbd>↵</kbd>
                </Go>
              ) : (
                <span className="sg-btn is-ghost">Only Adult is prototyped</span>
              )}
              <span className="sg-btn is-ghost">
                Export <kbd>⌘E</kbd>
              </span>
            </div>
          </div>
        </div>
      </div>
      {pal && (
        <div className="sg-overlay" onClick={() => setPal(false)}>
          <div onClick={(e) => e.stopPropagation()}>
            <Palette />
          </div>
        </div>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------- results */

function Results() {
  const root = useRef<HTMLDivElement>(null);
  const [sel, setSel] = useState(0);
  const f = run.findings[sel];
  useGsap(root, (q) => {
    gsap.from(q('.sg-res-chip'), { opacity: 0, y: 10, scale: 0.94, stagger: 0.08, duration: 0.6, ease: 'back.out(2)' });
  });
  const [mn, q1, md, q3, mx] = hours.q!;
  const x = (v: number) => 4 + ((v - mn) / (mx - mn)) * 92;
  return (
    <div className="c-signal is-app" ref={root}>
      <Ribbons quiet />
      <div className="sg-win">
        <header className="sg-win-bar">
          <Go to={href(C, 'workspace')} className="sg-brand">
            <Mark /> Audits / Adult
          </Go>
          <button className="sg-search">
            Jump to finding, column or line <kbd>⌘K</kbd>
          </button>
          <div className="sg-win-r">
            <span className="sg-btn is-ghost">JSON</span>
            <span className="sg-btn is-ghost">PDF</span>
            <span className="sg-btn is-grad">Share report</span>
          </div>
        </header>
        <div className="sg-res">
          <aside className="sg-res-list">
            <div className="sg-res-score">
              <b>{run.score}</b>
              <div>
                <span>Elevated</span>
                <em>evidence {run.evidence} · capped</em>
              </div>
            </div>
            {run.findings.map((x2, i) => (
              <button key={x2.code} className={`sg-row${i === sel ? ' is-on' : ''}`} onClick={() => setSel(i)}>
                <i className={`sg-sev is-${x2.severity.toLowerCase()}`}>{x2.severity.slice(0, 1)}</i>
                <span>
                  <b>{x2.title}</b>
                  <em>{x2.evidence}</em>
                </span>
              </button>
            ))}
            <div className="sg-card sg-res-subs">
              {SUB_ORDER.map((k) => (
                <div key={k} className={`sg-bench${run.sub[k] < 50 ? ' is-hot' : ''}`}>
                  <span>{SUB_LABELS[k].toUpperCase()}</span>
                  <i>
                    <em style={{ width: `${run.sub[k]}%` }} />
                  </i>
                  <b>{run.sub[k].toFixed(2)}</b>
                </div>
              ))}
            </div>
          </aside>
          <section className="sg-canvas">
            <p className="sg-eyebrow">
              {f.severity} · {f.code}
            </p>
            <h2>{f.finding}</h2>
            <div className="sg-stage">
              {f.code === 'conflicting_target_labels' && (
                <table className="sg-ev">
                  <thead>
                    <tr>
                      <th>line</th>
                      <th>age</th>
                      <th>workclass</th>
                      <th>education</th>
                      <th>occupation</th>
                      <th>sex</th>
                      <th>hours</th>
                      <th>label</th>
                    </tr>
                  </thead>
                  {conflictGroups.map((g, gi) => (
                    <tbody key={gi}>
                      {g.map((r) => (
                        <tr key={r.line}>
                          <td>{nf(Number(r.line))}</td>
                          <td>{r.age}</td>
                          <td>{r.workclass}</td>
                          <td>{r.education}</td>
                          <td>{r.occupation}</td>
                          <td>{r.sex}</td>
                          <td>{r.hours_per_week}</td>
                          <td className={r.annual_income_over_50k === '>50K' ? 'hot' : ''}>{r.annual_income_over_50k.replace('<=', '≤')}</td>
                        </tr>
                      ))}
                    </tbody>
                  ))}
                </table>
              )}
              {f.code === 'numeric_outlier_concentration' && (
                <div className="sg-box">
                  <div className="sg-box-axis">
                    <span className="fence" style={{ left: `${x(32.5)}%`, width: `${x(52.5) - x(32.5)}%` }} />
                    <span className="iqr" style={{ left: `${x(q1)}%`, width: `${x(q3) - x(q1)}%` }} />
                    <span className="med" style={{ left: `${x(md)}%` }} />
                  </div>
                  <div className="sg-box-ticks">
                    {[mn, 32.5, q1, q3, 52.5, mx].map((v, i) => (
                      <span key={i} style={{ left: `${x(v)}%`, top: i % 2 ? 22 : 0 }}>
                        {v}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {f.code === 'target_imbalance' && (
                <div className="sg-split">
                  {run.profile.target_distribution.map((d) => (
                    <div key={d.label} style={{ flexGrow: d.count }} className={d.label.startsWith('>') ? 'is-min' : ''}>
                      <b>{d.label.replace('<=', '≤')}</b>
                      <span>
                        {nf(d.count)} · {d.percentage}%
                      </span>
                    </div>
                  ))}
                </div>
              )}
              {f.code === 'leakage_review_prompts' && (
                <div className="sg-col">
                  <code>marital_status</code>
                  <span>review_only · generic status-like name · leakage sub-score stays {run.sub.leakage_risk}</span>
                </div>
              )}
              <div className="sg-res-chip k1">
                <span>Evidence</span>
                <b>{f.evidence}</b>
              </div>
              <div className="sg-res-chip k2">
                <span>Score effect</span>
                <b>{f.score_effect}</b>
              </div>
            </div>
            <div className="sg-kv">
              <div>
                <span>Possible modeling impact</span>
                <p>{f.modeling_impact}</p>
              </div>
              <div>
                <span>Recommended review</span>
                <p>{f.recommendation}</p>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

export default function Signal({ screen }: { screen: Screen }) {
  if (screen === 'workspace') return <Workspace />;
  if (screen === 'results') return <Results />;
  return <Landing />;
}
