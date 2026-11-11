import { useRef, useState } from 'react';
import { Go, href, type Screen } from '../../shared/router';
import { gsap, useGsap, useSmoothScroll, ScrollTrigger } from '../../shared/motion';
import { run, leakRun, checks, CHECK_LABELS, SUB_LABELS, SUB_ORDER, conflictGroups, hours, nf, cliTranscript, columnsProfile } from '../../shared/engine';
import { audits, openFindings, lastRun } from '../../shared/workspace';
import { Sky } from './Sky';
import './continual.css';
import '@fontsource-variable/mona-sans/wdth';
import '@fontsource/geist-mono/400';
import '@fontsource/geist-mono/500';

const C = 'continual';

function Logo() {
  return (
    <span className="ct-logo">
      <svg viewBox="0 0 18 18" aria-hidden="true">
        <circle cx="9" cy="9" r="7.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
        <path d="M5 12.5V5.5l8 7V5.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
      </svg>
      numek
    </span>
  );
}

function Nav({ light }: { light?: boolean }) {
  return (
    <header className={`ct-nav${light ? ' is-light' : ''}`}>
      <nav className="ct-nav-l" aria-label="Site">
        <a href="#product">Product</a>
        <a href="#method">Method</a>
        <a href="#code">Docs</a>
      </nav>
      <Go to={href(C)} className="ct-nav-logo" label="Numek home">
        <Logo />
      </Go>
      <div className="ct-nav-r">
        <Go to="#/" className="ct-nav-link">
          All concepts
        </Go>
        <Go to={href(C, 'workspace')} className="ct-pill">
          Open app
        </Go>
      </div>
    </header>
  );
}

/* ---------------------------------------------------------- line diagrams */

function DiagramConflict() {
  return (
    <svg viewBox="0 0 320 220" className="ct-diag">
      <ellipse cx="160" cy="120" rx="120" ry="34" />
      <ellipse cx="160" cy="120" rx="64" ry="18" className="dim" />
      <line x1="40" y1="120" x2="280" y2="120" className="dim" strokeDasharray="3 4" />
      <line x1="160" y1="40" x2="160" y2="200" className="dim" />
      <circle cx="160" cy="120" r="5" className="node" />
      <path d="M160 120 L230 66" />
      <path d="M160 120 L92 168" />
      <circle cx="230" cy="66" r="3.5" className="node hi" />
      <circle cx="92" cy="168" r="3.5" className="node" />
      <text x="238" y="62">&gt;50K</text>
      <text x="44" y="186">≤50K</text>
      <text x="172" y="112" className="mono">lines 850 · 22,763</text>
    </svg>
  );
}
function DiagramBalance() {
  const share = run.profile.target_distribution[0].percentage / 100;
  const a = share * Math.PI * 2;
  const r = 70;
  return (
    <svg viewBox="0 0 320 220" className="ct-diag">
      <circle cx="160" cy="110" r={r} className="dim" />
      <circle cx="160" cy="110" r={r - 18} className="dim" strokeDasharray="2 4" />
      <path d={`M160 ${110 - r} A ${r} ${r} 0 1 1 ${160 + r * Math.sin(a)} ${110 - r * Math.cos(a)}`} />
      <path d={`M${160 + r * Math.sin(a)} ${110 - r * Math.cos(a)} A ${r} ${r} 0 0 1 160 ${110 - r}`} className="hi" strokeWidth="3" />
      <circle cx="160" cy={110 - r} r="3.5" className="node" />
      <text x="160" y="114" textAnchor="middle" className="big">76.07%</text>
      <text x="160" y="132" textAnchor="middle" className="mono">majority baseline</text>
      <text x="246" y="70" className="mono hi-t">23.93%</text>
    </svg>
  );
}
function DiagramGuard() {
  return (
    <svg viewBox="0 0 320 220" className="ct-diag">
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <ellipse key={i} cx="160" cy="170" rx={120 - i * 18} ry={30 - i * 4.5} className={i ? 'dim' : ''} />
      ))}
      <line x1="160" y1="170" x2="160" y2="56" />
      <circle cx="160" cy="56" r="4" className="node hi" />
      <text x="172" y="52" className="mono">capped at 69</text>
      <text x="172" y="68" className="mono dimt">evidence 89.15</text>
      <line x1="40" y1="110" x2="280" y2="110" strokeDasharray="3 4" className="dim" />
    </svg>
  );
}

const METHOD_STEPS = [
  { t: 'Profile every column', b: 'Types, missingness, cardinality, numeric quartiles and outliers for all 15 columns, from the bytes you supplied.' },
  { t: 'Run twelve checks', b: 'Duplicates, label conflicts, target balance, leakage names, parsing fidelity. Each with a named method and population.' },
  { t: 'Cap what is critical', b: 'Five transparent sub-scores average to the evidence score. A critical weakness caps the result, so it cannot be averaged away.' },
  { t: 'Report what you found', b: 'One completed result becomes HTML, PDF and strict JSON. Nothing is recomputed between formats.' },
];

function MethodFigure({ step }: { step: number }) {
  const cols = columnsProfile.length;
  return (
    <svg viewBox="0 0 520 420" className={`ct-method-fig s${step}`}>
      <g className="ct-mf-grid">
        {Array.from({ length: cols }, (_, i) => {
          const c = columnsProfile[i];
          const hot = step >= 1 && (c.name === 'hours_per_week' || c.name === 'annual_income_over_50k' || c.name === 'marital_status');
          const h = 40 + Math.log10(c.unique_count + 1) * 52;
          return (
            <g key={c.name}>
              <line x1={40 + i * 30} x2={40 + i * 30} y1={340} y2={340 - h} className={hot ? 'hot' : ''} />
              <circle cx={40 + i * 30} cy={340 - h} r={hot ? 4 : 2.5} className={`node${hot ? ' hi' : ''}`} />
            </g>
          );
        })}
        <line x1="24" x2="480" y1="340" y2="340" />
      </g>
      <g className="ct-mf-cap" style={{ opacity: step >= 2 ? 1 : 0 }}>
        <line x1="24" x2="480" y1="164" y2="164" strokeDasharray="4 4" className="hi-line" />
        <text x="484" y="160" className="mono">69</text>
        <line x1="24" x2="480" y1="120" y2="120" className="dim" />
        <text x="484" y="116" className="mono dimt">89.15</text>
      </g>
      <g className="ct-mf-report" style={{ opacity: step >= 3 ? 1 : 0 }}>
        <rect x="300" y="30" width="170" height="220" />
        <line x1="316" x2="420" y1="56" y2="56" />
        <line x1="316" x2="454" y1="78" y2="78" className="dim" />
        <line x1="316" x2="440" y1="92" y2="92" className="dim" />
        <rect x="316" y="110" width="60" height="44" className="hi-fill" />
        <line x1="388" x2="454" y1="118" y2="118" className="dim" />
        <line x1="388" x2="446" y1="132" y2="132" className="dim" />
        <text x="316" y="276" className="mono">html · pdf · json</text>
      </g>
      <text x="24" y="390" className="mono dimt">
        {cols} columns · unique values on a log scale · flagged columns lit
      </text>
    </svg>
  );
}

/* ------------------------------------------------------------- app pieces */

function AppSidebar({ active }: { active: 'audits' | 'flags' }) {
  return (
    <aside className="ct-side">
      <div className="ct-side-ws">
        <span className="ct-ws-badge">N</span>
        <div>
          <b>Numek</b>
          <small>Local workspace</small>
        </div>
      </div>
      <button className="ct-search">
        Search or run a command <kbd>⌘K</kbd>
      </button>
      <nav>
        <Go to={href(C, 'workspace')} className={active === 'audits' ? 'is-on' : ''}>
          Audits <span>{audits.length}</span>
        </Go>
        <a>Open flags <span>{openFindings.length}</span></a>
        <a>Reports</a>
        <a>Sources</a>
      </nav>
      <p className="ct-side-h">Datasets</p>
      <nav className="ct-side-ds">
        {audits.slice(0, 5).map((a) => (
          <a key={a.id} className={a.id === 'adult' && active === 'flags' ? 'is-on' : ''}>
            <i className={`dot is-${a.score === null ? 'none' : a.band.toLowerCase()}`} />
            {a.name}
          </a>
        ))}
      </nav>
      <div className="ct-side-foot">
        <i /> Loopback only · nothing uploaded
      </div>
    </aside>
  );
}

function AuditList({ compact }: { compact?: boolean }) {
  const groups: [string, typeof audits][] = [
    ['Needs review', audits.filter((a) => a.band === 'High' || a.band === 'Elevated')],
    ['Within guardrails', audits.filter((a) => a.band === 'Low')],
    ['No score defined', audits.filter((a) => a.score === null)],
  ];
  return (
    <div className={`ct-list${compact ? ' is-compact' : ''}`}>
      {groups.map(([g, list]) => (
        <section key={g}>
          <header>
            <span>{g}</span>
            <em>{list.length}</em>
          </header>
          {list.map((a) => {
            const inner = (
              <>
                <i className={`dot is-${a.score === null ? 'none' : a.band.toLowerCase()}`} />
                <span className="ct-li-id">{a.id.toUpperCase().slice(0, 6)}</span>
                <span className="ct-li-name">{a.name}</span>
                <span className="ct-li-kind">{a.kind}</span>
                <span className="ct-li-shape">
                  {nf(a.rows)}
                  {a.columns ? ` × ${a.columns}` : ''}
                </span>
                <span className="ct-li-score">{a.score === null ? '—' : a.score}</span>
                <span className="ct-li-date">{lastRun[a.id]}</span>
              </>
            );
            return a.id === 'adult' && !compact ? (
              <Go key={a.id} to={href(C, 'results')} className="ct-li is-link">
                {inner}
              </Go>
            ) : (
              <div key={a.id} className="ct-li">
                {inner}
              </div>
            );
          })}
        </section>
      ))}
    </div>
  );
}

/* ---------------------------------------------------------------- landing */

function Landing() {
  const root = useRef<HTMLDivElement>(null);
  const [step, setStep] = useState(0);
  const [tab, setTab] = useState<'python' | 'cli' | 'browser'>('python');
  useSmoothScroll();
  useGsap(root, (q) => {
    gsap.from(q('.ct-hero-copy > *'), { opacity: 0, y: 18, stagger: 0.09, duration: 1, ease: 'expo.out', delay: 0.15 });
    gsap.from(q('.ct-trace path'), { strokeDasharray: 1600, strokeDashoffset: 1600, duration: 2.2, ease: 'power2.inOut', delay: 0.4 });
    gsap.from(q('.ct-trace .ct-trace-node'), { opacity: 0, scale: 0.6, stagger: 0.35, duration: 0.5, delay: 1.1 });
    q('.ct-fade').forEach((el: Element) =>
      gsap.from(el, { opacity: 0, y: 30, duration: 1, ease: 'power3.out', scrollTrigger: { trigger: el, start: 'top 85%' } }),
    );
    gsap.from(q('.ct-window'), {
      rotateX: 22,
      y: 80,
      opacity: 0.2,
      ease: 'none',
      scrollTrigger: { trigger: q('.ct-window')[0], start: 'top 95%', end: 'top 35%', scrub: true },
    });
    q('.ct-statement span').forEach((el: Element) =>
      gsap.fromTo(el, { color: '#4a4c52' }, { color: '#f4f5f7', ease: 'none', scrollTrigger: { trigger: el, start: 'top 80%', end: 'top 55%', scrub: true } }),
    );
    ScrollTrigger.create({
      trigger: q('.ct-method')[0],
      start: 'top 30%',
      end: 'bottom 70%',
      onUpdate: (st) => setStep(Math.min(3, Math.floor(st.progress * 4))),
    });
  });

  const W = 1440;
  const pts = [
    { x: 160, y: 300, l: 'profile', v: '15 columns' },
    { x: 560, y: 230, l: 'evidence score', v: '89.15' },
    { x: 900, y: 330, l: 'guardrail', v: 'target balance 47.86' },
    { x: 1240, y: 330, l: 'final', v: '69 elevated' },
  ];
  const code = {
    python: `from datatrust import DataTrust\n\naudit = DataTrust(\n    "adult.csv",\n    target="annual_income_over_50k",\n    task="classification",\n)\naudit.generate_report("adult.html")`,
    cli: cliTranscript.join('\n'),
    browser: `$ datatrust ui\n\nLocal report generator on 127.0.0.1\n1 Upload  ·  2 Configure  ·  3 Confirm  ·  4 Report\nYour CSV is processed by this local application\nand is not sent to a cloud service.`,
  }[tab];

  return (
    <div className="c-continual" ref={root}>
      <div className="ct-banner">
        Connected evidence is here: reconcile records against the documents behind them <span>→</span>
      </div>
      <Nav light />
      <section className="ct-hero">
        <Sky />
        <div className="ct-hero-copy">
          <p className="ct-eyebrow">
            <i /> {nf(run.rows)} rows audited in {run.elapsed.toFixed(2)} s, locally
          </p>
          <h1>Training data you can stand behind</h1>
          <p className="ct-hero-sub">
            DataTrust measures a dataset before you train on it. Twelve checks, transparent scores and a report your
            reviewers can read, all without the data leaving your machine.
          </p>
          <div className="ct-hero-cta">
            <Go to={href(C, 'workspace')} className="ct-pill is-dark">
              Run your first audit
            </Go>
            <Go to={href(C, 'results')} className="ct-pill is-glass">
              View a real report
            </Go>
          </div>
        </div>
        <svg className="ct-trace" viewBox={`0 0 ${W} 420`} preserveAspectRatio="none" aria-label="Adult score path from profile to final score">
          <path d={`M0 330 C 120 330, 120 300, 160 300 S 480 230, 560 230 S 820 330, 900 330 L ${W} 330`} />
          {pts.map((p) => (
            <g key={p.l} className="ct-trace-node">
              <circle cx={p.x} cy={p.y} r="4" />
              <text x={p.x - 6} y={p.y - 30}>{p.l}</text>
              <text x={p.x - 6} y={p.y - 16} className="v">
                {p.v}
              </text>
            </g>
          ))}
        </svg>
      </section>

      <section className="ct-strip">
        <span>Python 3.10+</span>
        <span>CSV · Parquet · JSONL · images</span>
        <span>Offline, loopback only</span>
        <span>HTML · PDF · JSON</span>
        <span>Versioned methodology</span>
      </section>

      <section className="ct-dark" id="product">
        <div className="ct-sec-head ct-fade">
          <p className="ct-tag">Evidence</p>
          <h2>The checks your training run actually needs</h2>
          <p>Bring the table and name the target. DataTrust measures it, flags what matters and explains why.</p>
        </div>
        <div className="ct-cards">
          <article className="ct-card ct-fade">
            <DiagramConflict />
            <h3>Labels that disagree</h3>
            <p>5 feature-identical groups carry different labels. 10 rows, located to the CSV line.</p>
          </article>
          <article className="ct-card ct-fade">
            <DiagramBalance />
            <h3>Accuracy that lies</h3>
            <p>Always guessing ≤50K is already 76.07% accurate. The target-balance sub-score reads 47.86.</p>
          </article>
          <article className="ct-card ct-fade">
            <DiagramGuard />
            <h3>Guardrails, not averages</h3>
            <p>Evidence averages 89.15, but a critical weakness caps the score at 69. Severe risks stay visible.</p>
          </article>
        </div>

        <div className="ct-statement">
          <span>A new standard for dataset review.</span> <span>Every finding names its population, its method and its</span>{' '}
          <span>effect on the score, so an engineer can verify it and a CTO can act on it.</span>
        </div>

        <div className="ct-window-wrap">
          <div className="ct-window">
            <div className="ct-window-bar">
              <i />
              <i />
              <i />
              <span>DataTrust · ~/numek/audits</span>
            </div>
            <div className="ct-window-body">
              <AppSidebar active="audits" />
              <AuditList compact />
            </div>
          </div>
        </div>

        <div className="ct-method" id="method">
          <div className="ct-method-copy">
            <p className="ct-tag">Method</p>
            <h2>Why a whole-table audit matters</h2>
            <p className="ct-method-sub">A notebook samples what you look at. DataTrust reads everything, in the same order every time.</p>
            <ol>
              {METHOD_STEPS.map((s, i) => (
                <li key={s.t} className={i === step ? 'is-on' : ''}>
                  <b>{s.t}</b>
                  <p>{s.b}</p>
                </li>
              ))}
            </ol>
          </div>
          <div className="ct-method-sticky">
            <div className="ct-method-frame">
              <MethodFigure step={step} />
            </div>
          </div>
        </div>

        <div className="ct-code" id="code">
          <div className="ct-sec-head ct-fade">
            <p className="ct-tag">Developers</p>
            <h2>Audit this morning</h2>
            <p>A Python API, a command line and a local browser app. Same engine, same result.</p>
          </div>
          <div className="ct-code-box ct-fade">
            <div className="ct-code-tabs" role="tablist">
              {(['python', 'cli', 'browser'] as const).map((t) => (
                <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}>
                  {t === 'python' ? 'Python' : t === 'cli' ? 'CLI' : 'Browser'}
                </button>
              ))}
            </div>
            <pre>
              {code.split('\n').map((l, i) => (
                <span key={i}>
                  <em>{i + 1}</em>
                  {l}
                  {'\n'}
                </span>
              ))}
            </pre>
          </div>
        </div>

        <div className="ct-local ct-fade">
          <svg viewBox="0 0 600 340" className="ct-diag ct-local-fig">
            {Array.from({ length: 9 }, (_, i) => (
              <ellipse key={i} cx="300" cy="250" rx={260 - i * 28} ry={70 - i * 7.5} className={i ? 'dim' : ''} />
            ))}
            {Array.from({ length: 13 }, (_, i) => (
              <line key={i} x1="300" y1="250" x2={300 + Math.cos((i / 12) * Math.PI) * 280} y2={250 - Math.sin((i / 12) * Math.PI) * 220} className="dim" strokeDasharray="2 5" />
            ))}
            <line x1="300" y1="250" x2="300" y2="90" />
            <circle cx="300" cy="90" r="5" className="node hi" />
            <text x="314" y="86" className="mono">nothing left this machine</text>
          </svg>
          <div>
            <p className="ct-tag">Local by default</p>
            <h2>Private by construction, not by policy</h2>
            <p>
              The browser app binds to loopback, jobs are scoped to the process, and every report records the SHA-256 of
              the exact bytes it read. Source <code>{run.sha256.slice(0, 16)}…</code>
            </p>
          </div>
        </div>

        <footer className="ct-foot">
          <Logo />
          <span>Numek is an AI reliability verification company. DataTrust is its first product.</span>
          <span>Prototype · real local run</span>
        </footer>
      </section>
    </div>
  );
}

/* -------------------------------------------------------------- workspace */

function Workspace() {
  const root = useRef<HTMLDivElement>(null);
  const [sel, setSel] = useState('adult');
  const a = audits.find((x) => x.id === sel)!;
  useGsap(root, (q) => {
    gsap.from(q('.ct-li'), { opacity: 0, y: 6, stagger: 0.03, duration: 0.4, ease: 'power2.out' });
  });
  const flags = openFindings.filter((f) => f.auditId === sel);
  return (
    <div className="c-continual is-app" ref={root}>
      <div className="ct-app">
        <AppSidebar active="audits" />
        <main className="ct-app-main">
          <header className="ct-app-head">
            <div>
              <h1>Audits</h1>
              <span>7 datasets · 2 need review</span>
            </div>
            <div className="ct-app-actions">
              <Go to="#/" className="ct-btn">
                All concepts
              </Go>
              <button className="ct-btn is-primary">New audit</button>
            </div>
          </header>
          <div className="ct-filters">
            <span className="is-on">All</span>
            <span>Classification</span>
            <span>Regression</span>
            <span>Connected evidence</span>
          </div>
          <div className="ct-list">
            {(['Needs review', 'Within guardrails', 'No score defined'] as const).map((g) => {
              const list = audits.filter((x) =>
                g === 'Needs review' ? x.band === 'High' || x.band === 'Elevated' : g === 'Within guardrails' ? x.band === 'Low' : x.score === null,
              );
              return (
                <section key={g}>
                  <header>
                    <span>{g}</span>
                    <em>{list.length}</em>
                  </header>
                  {list.map((x) => (
                    <button key={x.id} className={`ct-li${sel === x.id ? ' is-sel' : ''}`} onClick={() => setSel(x.id)}>
                      <i className={`dot is-${x.score === null ? 'none' : x.band.toLowerCase()}`} />
                      <span className="ct-li-id">{x.id.toUpperCase().slice(0, 6)}</span>
                      <span className="ct-li-name">{x.name}</span>
                      <span className="ct-li-kind">{x.kind}</span>
                      <span className="ct-li-shape">
                        {nf(x.rows)}
                        {x.columns ? ` × ${x.columns}` : ''}
                      </span>
                      <span className="ct-li-score">{x.score === null ? '—' : x.score}</span>
                      <span className="ct-li-date">{lastRun[x.id]}</span>
                    </button>
                  ))}
                </section>
              );
            })}
          </div>
        </main>
        <aside className="ct-detail">
          <p className="ct-detail-kind">{a.kind}</p>
          <h2>{a.name}</h2>
          <div className="ct-detail-score">
            <b>{a.score === null ? '—' : a.score}</b>
            <span>{a.band}</span>
          </div>
          <p className="ct-detail-note">{a.note}</p>
          {a.sub && (
            <div className="ct-bars">
              {a.sub.map((v, i) => (
                <div key={i} className={v < 50 ? 'is-low' : ''}>
                  <span>{SUB_LABELS[SUB_ORDER[i]]}</span>
                  <i>
                    <em style={{ width: `${v}%` }} />
                  </i>
                  <b>{v.toFixed(1)}</b>
                </div>
              ))}
            </div>
          )}
          <p className="ct-detail-h">Open flags</p>
          {flags.length ? (
            <ul className="ct-detail-flags">
              {flags.map((f, i) => (
                <li key={i}>
                  <i className={`sev is-${f.severity.toLowerCase()}`} />
                  <div>
                    <b>{f.title}</b>
                    <span>{f.detail}</span>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="ct-detail-empty">{a.findings} findings recorded in the report. None open.</p>
          )}
          {a.id === 'adult' ? (
            <Go to={href(C, 'results')} className="ct-btn is-primary ct-detail-open">
              Open audit
            </Go>
          ) : (
            <span className="ct-btn ct-detail-open is-muted">Report available as HTML, PDF, JSON</span>
          )}
        </aside>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- results */

function Evidence({ code }: { code: string }) {
  if (code === 'conflicting_target_labels')
    return (
      <div className="ct-ev">
        <div className="ct-ev-h">
          <span>5 groups · 10 rows</span>
          <em>excerpt of 14 identical features</em>
        </div>
        <table className="ct-ev-table">
          <thead>
            <tr>
              <th>line</th>
              <th>age</th>
              <th>education</th>
              <th>occupation</th>
              <th>hours</th>
              <th>label</th>
            </tr>
          </thead>
          {conflictGroups.map((g, i) => (
            <tbody key={i}>
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
      </div>
    );
  if (code === 'numeric_outlier_concentration') {
    const [mn, q1, md, q3, mx] = hours.q!;
    const x = (v: number) => 30 + ((v - mn) / (mx - mn)) * 540;
    return (
      <div className="ct-ev">
        <div className="ct-ev-h">
          <span>hours_per_week</span>
          <em>
            {nf(hours.outlier_count)} rows · {hours.outlier_rate}% outside 1.5 × IQR
          </em>
        </div>
        <svg viewBox="0 0 600 150" className="ct-diag ct-ev-box">
          <line x1="30" x2="570" y1="70" y2="70" className="dim" />
          <rect x={x(32.5)} y="40" width={x(52.5) - x(32.5)} height="60" className="dim" strokeDasharray="3 3" />
          <rect x={x(q1)} y="52" width={x(q3) - x(q1)} height="36" className="hi-fill" />
          <line x1={x(md)} x2={x(md)} y1="46" y2="94" />
          {[mn, 32.5, q1, q3, 52.5, mx].map((v, i) => (
            <text key={i} x={x(v)} y={i % 2 ? 132 : 120} textAnchor="middle" className="mono">
              {v}
            </text>
          ))}
        </svg>
      </div>
    );
  }
  if (code === 'target_imbalance')
    return (
      <div className="ct-ev">
        <div className="ct-ev-h">
          <span>annual_income_over_50k</span>
          <em>majority baseline {run.profile.majority_class_baseline}%</em>
        </div>
        <div className="ct-ev-split">
          {run.profile.target_distribution.map((d) => (
            <div key={d.label} style={{ flexGrow: d.count }} className={d.label.startsWith('>') ? 'hi' : ''}>
              <b>{d.label.replace('<=', '≤')}</b>
              <span>
                {nf(d.count)} · {d.percentage}%
              </span>
            </div>
          ))}
        </div>
      </div>
    );
  return (
    <div className="ct-ev">
      <div className="ct-ev-h">
        <span>marital_status</span>
        <em>review_only · name heuristic</em>
      </div>
      <p className="ct-ev-note">
        Prompted by its generic status-like name. No values were inspected for leakage, and the leakage sub-score stays at{' '}
        {run.sub.leakage_risk}. Compare the planted <code>post_income_outcome</code> column, which caps that dataset at {leakRun.score}.
      </p>
    </div>
  );
}

function Results() {
  const root = useRef<HTMLDivElement>(null);
  const [sel, setSel] = useState(0);
  const f = run.findings[sel];
  useGsap(root, (q) => {
    gsap.from(q('.ct-res-top > *'), { opacity: 0, y: 10, stagger: 0.06, duration: 0.5 });
  });
  return (
    <div className="c-continual is-app" ref={root}>
      <div className="ct-app">
        <AppSidebar active="flags" />
        <main className="ct-res">
          <header className="ct-res-crumbs">
            <span>
              <Go to={href(C, 'workspace')}>Audits</Go> › Adult
            </span>
            <div className="ct-app-actions">
              <button className="ct-btn">JSON</button>
              <button className="ct-btn">PDF</button>
              <button className="ct-btn is-primary">Share report</button>
            </div>
          </header>
          <section className="ct-res-top">
            <div className="ct-res-title">
              <h1>Adult</h1>
              <p>
                Binary classification of <code>annual_income_over_50k</code>. {nf(run.rows)} rows × {run.columns} columns, read in{' '}
                {run.elapsed.toFixed(2)} s.
              </p>
            </div>
            <div className="ct-res-score">
              <svg viewBox="0 0 220 120" className="ct-diag">
                <path d="M20 100 A 90 90 0 0 1 200 100" className="dim" />
                <path d={`M20 100 A 90 90 0 0 1 ${110 - 90 * Math.cos((run.score / 100) * Math.PI)} ${100 - 90 * Math.sin((run.score / 100) * Math.PI)}`} className="hi" strokeWidth="3" />
                <circle cx={110 - 90 * Math.cos((run.evidence / 100) * Math.PI)} cy={100 - 90 * Math.sin((run.evidence / 100) * Math.PI)} r="4" className="node" />
                <text x="110" y="92" textAnchor="middle" className="big">{run.score}</text>
                <text x="110" y="112" textAnchor="middle" className="mono">{run.band.toLowerCase()} · evidence {run.evidence}</text>
              </svg>
            </div>
            <div className="ct-res-guard">
              <p className="ct-tag">Guardrail applied</p>
              <p>{run.guardrails[0].explanation}</p>
              <p className="ct-res-act">{run.action}</p>
            </div>
          </section>

          <section className="ct-res-main">
            <div className="ct-issues">
              <header>
                <span>Findings</span>
                <em>{run.findings.length}</em>
              </header>
              {run.findings.map((x, i) => (
                <button key={x.code} className={`ct-issue${i === sel ? ' is-sel' : ''}`} onClick={() => setSel(i)}>
                  <i className={`sev is-${x.severity.toLowerCase()}`} />
                  <span>
                    <b>{x.title}</b>
                    <em>{x.evidence}</em>
                  </span>
                  <small>{x.severity}</small>
                </button>
              ))}
              <header className="ct-issues-sub">
                <span>Sub-scores</span>
              </header>
              <div className="ct-bars">
                {SUB_ORDER.map((k) => (
                  <div key={k} className={run.sub[k] < 50 ? 'is-low' : ''}>
                    <span>{SUB_LABELS[k]}</span>
                    <i>
                      <em style={{ width: `${run.sub[k]}%` }} />
                    </i>
                    <b>{run.sub[k].toFixed(2)}</b>
                  </div>
                ))}
              </div>
            </div>
            <div className="ct-issue-detail">
              <p className="ct-tag">{f.severity} · {f.code}</p>
              <h2>{f.finding}</h2>
              <Evidence code={f.code} />
              <dl className="ct-kv">
                <dt>Possible modeling impact</dt>
                <dd>{f.modeling_impact}</dd>
                <dt>Recommended review</dt>
                <dd>{f.recommendation}</dd>
                <dt>Score effect</dt>
                <dd>{f.score_effect}</dd>
              </dl>
              <div className="ct-activity">
                <p className="ct-tag">Run log</p>
                {checks.map((c, i) => (
                  <div key={c.id} className="ct-act">
                    <i />
                    <span>
                      <b>{CHECK_LABELS[c.id]}</b> completed with <code>{c.method}</code> over {c.population}
                    </span>
                    <em>{String(i + 1).padStart(2, '0')}</em>
                  </div>
                ))}
              </div>
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}

export default function Continual({ screen }: { screen: Screen }) {
  if (screen === 'workspace') return <Workspace />;
  if (screen === 'results') return <Results />;
  return <Landing />;
}
