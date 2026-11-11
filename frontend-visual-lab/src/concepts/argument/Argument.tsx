import { useEffect, useRef, useState } from 'react';
import { Go, href, type Screen } from '../../shared/router';
import { gsap, useGsap, useSmoothScroll } from '../../shared/motion';
import { run, conflictGroups, hours, nf, SUB_LABELS, SUB_ORDER, checks, CHECK_LABELS } from '../../shared/engine';
import { variants } from '../../shared/mutations';
import { audits, lastRun } from '../../shared/workspace';
import './argument.css';
import '@fontsource-variable/schibsted-grotesk/wght';
import '@fontsource-variable/source-serif-4/opsz';
import '@fontsource-variable/source-serif-4/opsz-italic';

const C = 'argument';

function useTween(value: number, decimals = 0) {
  const [shown, setShown] = useState(value);
  const prev = useRef(value);
  useEffect(() => {
    const o = { v: prev.current };
    const tw = gsap.to(o, { v: value, duration: 0.8, ease: 'power3.out', onUpdate: () => setShown(Number(o.v.toFixed(decimals))) });
    prev.current = value;
    return () => {
      tw.kill();
    };
  }, [value, decimals]);
  return shown;
}

function Header({ dark }: { dark?: boolean }) {
  return (
    <header className={`ar-head${dark ? ' is-dark' : ''}`}>
      <Go to={href(C)} className="ar-logo" label="Numek home">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M4 20V4l16 16V4" fill="none" stroke="currentColor" strokeWidth="1.8" />
        </svg>
        Numek
      </Go>
      <nav>
        <Go to={href(C)}>Argument</Go>
        <Go to={href(C, 'workspace')}>Reading room</Go>
        <Go to={href(C, 'results')}>Adult</Go>
        <Go to="#/">All concepts</Go>
      </nav>
    </header>
  );
}

function Slider({ idx, setIdx, compact }: { idx: number; setIdx: (n: number) => void; compact?: boolean }) {
  return (
    <div className={`ar-slider${compact ? ' is-compact' : ''}`}>
      <div className="ar-slider-top">
        <span>Change the dataset</span>
        <em>{variants[idx].change}</em>
      </div>
      <div className="ar-stops" role="radiogroup" aria-label="Dataset variant">
        {variants.map((v, i) => (
          <button key={v.id} role="radio" aria-checked={i === idx} className={i === idx ? 'is-on' : ''} onClick={() => setIdx(i)}>
            <span>{String(i + 1).padStart(2, '0')}</span> {v.label}
          </button>
        ))}
      </div>
      <input
        type="range"
        min={0}
        max={variants.length - 1}
        step={1}
        value={idx}
        onChange={(e) => setIdx(Number(e.target.value))}
        aria-label="Dataset variant"
        style={{ ['--p' as string]: `${(idx / (variants.length - 1)) * 100}%` }}
      />
    </div>
  );
}

function Experiment({ idx, setIdx }: { idx: number; setIdx: (n: number) => void }) {
  const v = variants[idx];
  const score = useTween(v.score);
  const ev = useTween(v.evidence, 2);
  return (
    <div className="ar-exp">
      <div className="ar-exp-left">
        <Slider idx={idx} setIdx={setIdx} />
        <p className="ar-exp-head">{v.headline}</p>
        <ul className="ar-guards">
          {v.guardrails.map((g) => (
            <li key={g}>{g}</li>
          ))}
        </ul>
      </div>
      <div className="ar-exp-right">
        <div className="ar-exp-score">
          <div>
            <span>Final score</span>
            <b className={v.band === 'High' ? 'is-high' : ''}>{score}</b>
            <em>{v.band}</em>
          </div>
          <div className="ar-exp-ev">
            <span>Evidence average</span>
            <b>{ev.toFixed(2)}</b>
            <em>{nf(v.rows)} rows</em>
          </div>
        </div>
        <div className="ar-exp-bars">
          {SUB_ORDER.map((k) => (
            <div key={k} className={v.sub[k] < 50 ? 'is-crit' : v.sub[k] < variants[0].sub[k] - 0.5 ? 'is-moved' : ''}>
              <span>{SUB_LABELS[k]}</span>
              <i>
                <em style={{ width: `${v.sub[k]}%` }} />
              </i>
              <b>{v.sub[k].toFixed(2)}</b>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- landing */

const COUPLETS: [string, string][] = [
  ['First, we read every row.', 'Not a sample, not a notebook glance.'],
  ['Then, we weighed the evidence.', 'Five sub-scores anyone can recompute.'],
  ['And the score learned restraint.', 'One critical weakness caps the rest.'],
];

const CARDS = [
  { k: 'Final score', v: '69', d: 'Elevated, capped by a guardrail', tone: 'cobalt' },
  { k: 'Labels that disagree', v: '5 groups', d: '10 rows, located to the CSV line', tone: 'paper' },
  { k: 'Where it ran', v: '0.20 s', d: 'On this machine. Nothing uploaded', tone: 'ink' },
];

function Landing() {
  const root = useRef<HTMLDivElement>(null);
  const [idx, setIdx] = useState(0);
  useSmoothScroll();
  useGsap(root, (q) => {
    gsap.from(q('.ar-hero-title .ln'), { yPercent: 100, duration: 1.2, ease: 'expo.out', stagger: 0.1 });
    gsap.from(q('.ar-hero-foot > *'), { opacity: 0, y: 16, duration: 0.9, stagger: 0.1, delay: 0.5 });
    q('.ar-couplet').forEach((el: Element) =>
      gsap.from(el, { opacity: 0, y: 50, duration: 1.1, ease: 'power3.out', scrollTrigger: { trigger: el, start: 'top 82%' } }),
    );
    gsap.fromTo(q('.ar-avg-word'), { backgroundSize: '100% 0%' }, { backgroundSize: '100% 100%', ease: 'none', scrollTrigger: { trigger: q('.ar-avg')[0], start: 'top 70%', end: 'center center', scrub: true } });
    q('.ar-read .w').forEach((el: Element) =>
      gsap.fromTo(el, { color: '#b9b7b0' }, { color: '#151515', ease: 'none', scrollTrigger: { trigger: el, start: 'top 85%', end: 'top 65%', scrub: true } }),
    );
    const cards = q('.ar-card');
    gsap.from(cards, {
      y: (i: number) => 120 + i * 40,
      rotate: (i: number) => (i - 1) * 9,
      opacity: 0,
      stagger: 0.12,
      duration: 1.1,
      ease: 'power3.out',
      scrollTrigger: { trigger: q('.ar-cards')[0], start: 'top 75%' },
    });
  });

  return (
    <div className="c-argument" ref={root}>
      <Header />
      <section className="ar-hero">
        <div className="ar-hero-meta">
          <p>
            A reliability company
            <br />
            for AI systems.
          </p>
          <p className="r">
            DataTrust, available now.
            <br />
            ConfidenceGuard, in development.
          </p>
        </div>
        <h1 className="ar-hero-title">
          <span className="mk">
            <span className="ln">Trust is a</span>
          </span>
          <span className="mk">
            <span className="ln">measurement</span>
          </span>
        </h1>
        <div className="ar-hero-foot">
          <p className="ar-hero-intro">
            Every dataset makes a claim about the world. DataTrust tests the claim before a model learns it.
            <span>This is how it reasons.</span>
          </p>
          <div className="ar-hero-widget">
            <Slider idx={idx} setIdx={setIdx} compact />
            <p className="ar-hero-read">
              Score <b>{variants[idx].score}</b> · evidence {variants[idx].evidence} · {variants[idx].band.toLowerCase()}
            </p>
          </div>
          <a className="ar-begin" href="#ar-argument">
            Read the argument
            <i />
          </a>
        </div>
      </section>

      <section className="ar-couplets" id="ar-argument">
        <p className="ar-label">An argument in three moves</p>
        {COUPLETS.map(([a, b]) => (
          <p key={a} className="ar-couplet">
            {a}
            <br />
            <span>{b}</span>
          </p>
        ))}
      </section>

      <section className="ar-avg">
        <div className="ar-avg-top">
          <span>02 / 04</span>
          <span>The question</span>
          <span>Adult, {nf(run.rows)} rows</span>
        </div>
        <p className="ar-avg-q">Can an average be trusted?</p>
        <p className="ar-avg-word" aria-label="89.15">
          89.15
        </p>
        <p className="ar-avg-a">
          That is the mean of Adult's five sub-scores. It hides a target-balance score of 47.86. DataTrust reports 69.
        </p>
      </section>

      <section className="ar-experiment">
        <div className="ar-exp-intro">
          <p className="ar-label">The experiment</p>
          <h2>Change the data. Watch the reasoning.</h2>
          <p>
            Five real runs of the same table from the repository's controlled suite. The score moves only when a guardrail
            says it must.
          </p>
        </div>
        <Experiment idx={idx} setIdx={setIdx} />
      </section>

      <section className="ar-chapter">
        <div className="ar-chapter-l">
          <p className="ar-label">03 · The evidence</p>
          <h2>A finding is only as good as the rows behind it.</h2>
          <Go to={href(C, 'results')} className="ar-chapter-link">
            Read the Adult audit <i />
          </Go>
        </div>
        <div className="ar-chapter-r">
          <p className="ar-read">
            {`DataTrust does not ask you to trust a score. It shows the population a finding concerns, the method that produced it, and what it may do to a model. When two people are recorded with identical features and different incomes, it gives you their CSV lines. When a column only makes sense after the outcome, it names it. When the target is lopsided, it says how accurate a model that learns nothing would already be.`
              .split(' ')
              .map((w, i) => (
                <span key={i} className="w">
                  {w}{' '}
                </span>
              ))}
          </p>
          <div className="ar-archive">
            <div className="ar-archive-h">
              <span>Inside the evidence</span>
              <span>Selected rows</span>
            </div>
            {conflictGroups.slice(0, 3).map((g) => (
              <div key={g[0].line} className="ar-archive-row">
                <span>
                  {nf(Number(g[0].line))} · {nf(Number(g[1].line))}
                </span>
                <b>
                  {g[0].age}, {g[0].education}, {g[0].occupation}: {g[0].annual_income_over_50k.replace('<=', '≤')} and{' '}
                  {g[1].annual_income_over_50k.replace('<=', '≤')}
                </b>
                <i />
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="ar-cards-sec">
        <p className="ar-label">04 · What you take away</p>
        <div className="ar-cards">
          {CARDS.map((c) => (
            <article key={c.k} className={`ar-card is-${c.tone}`}>
              <span>{c.k}</span>
              <b>{c.v}</b>
              <em>{c.d}</em>
              <small>Adult · DataTrust</small>
            </article>
          ))}
        </div>
        <Go to={href(C, 'workspace')} className="ar-cta">
          Open the reading room
        </Go>
      </section>

      <footer className="ar-foot">
        <span>Numek</span>
        <span>Evidence before conclusions.</span>
        <span>A report, not a certificate.</span>
      </footer>
      <div className="ar-chapters-bar" aria-hidden="true">
        <span>Chapters 01 / 04</span>
        <span>Real local run · prototype</span>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------- workspace */

function Workspace() {
  const root = useRef<HTMLDivElement>(null);
  const [sel, setSel] = useState('adult');
  const a = audits.find((x) => x.id === sel)!;
  useGsap(root, (q) => {
    gsap.from(q('.ar-room-list li'), { opacity: 0, x: -10, stagger: 0.05, duration: 0.5 });
  }, []);
  return (
    <div className="c-argument is-app" ref={root}>
      <Header />
      <main className="ar-room">
        <aside className="ar-room-list">
          <p className="ar-label">Reading room · ~/numek/audits</p>
          <ol>
            {audits.map((x, i) => (
              <li key={x.id}>
                <button className={sel === x.id ? 'is-on' : ''} onClick={() => setSel(x.id)}>
                  <span>{String(i + 1).padStart(2, '0')}</span>
                  <b>{x.name}</b>
                  <em>{x.score === null ? '—' : x.score}</em>
                </button>
              </li>
            ))}
          </ol>
          <div className="ar-new">
            <b>Start a new audit</b>
            <span>Name the file and the outcome. DataTrust never chooses the target for you.</span>
            <code>datatrust audit data.csv --target …</code>
          </div>
        </aside>
        <article className="ar-room-doc" key={a.id}>
          <p className="ar-label">
            {a.kind} · last read {lastRun[a.id]}
          </p>
          <h1>{a.name}</h1>
          {a.id === 'adult' ? (
            <>
              <p className="ar-doc-lede">{run.narrative.overall_assessment as string}</p>
              <p>{run.narrative.score_explanation as string}</p>
              <p>{run.narrative.target_interpretation as string}</p>
              <p>{run.narrative.duplicate_interpretation as string}</p>
              <p>{run.narrative.missingness_interpretation as string}</p>
              <Go to={href(C, 'results')} className="ar-chapter-link">
                Read the full audit <i />
              </Go>
            </>
          ) : (
            <>
              <p className="ar-doc-lede">
                {a.score === null
                  ? `${a.kind} audits report evidence without a score: no scoring policy is defined for this task, and DataTrust does not invent one.`
                  : `Scored ${a.score}, ${a.band.toLowerCase()}.`}
              </p>
              <p>{a.note}.</p>
              <p>
                {nf(a.rows)} {a.kind === 'Connected evidence' ? 'records' : 'rows'}
                {a.columns ? ` across ${a.columns} columns` : ''}, {a.findings} findings recorded. The full report is available as HTML, PDF
                and JSON.
              </p>
            </>
          )}
        </article>
        <aside className="ar-room-margin">
          <div className="ar-margin-score">
            <span>Score</span>
            <b>{a.score === null ? '—' : a.score}</b>
            <em>{a.band}</em>
          </div>
          {a.sub && (
            <div className="ar-margin-subs">
              {a.sub.map((v, i) => (
                <div key={i} className={v < 50 ? 'is-crit' : ''}>
                  <span>{SUB_LABELS[SUB_ORDER[i]]}</span>
                  <b>{v.toFixed(2)}</b>
                </div>
              ))}
            </div>
          )}
          <p className="ar-margin-note">Margin figures come from the stored run. Nothing here is recomputed in the browser.</p>
        </aside>
      </main>
    </div>
  );
}

/* ---------------------------------------------------------------- results */

function Results() {
  const root = useRef<HTMLDivElement>(null);
  const [idx, setIdx] = useState(0);
  const [chapter, setChapter] = useState(0);
  useSmoothScroll();
  useGsap(root, (q) => {
    gsap.from(q('.ar-rep-title > *'), { opacity: 0, y: 20, stagger: 0.08, duration: 0.9, ease: 'power3.out' });
    q('.ar-rep-ch').forEach((el: Element, i: number) =>
      gsap.to({}, { scrollTrigger: { trigger: el, start: 'top 50%', end: 'bottom 50%', onToggle: (st) => st.isActive && setChapter(i) } }),
    );
  });
  const [mn, q1, md, q3, mx] = hours.q!;
  const hx = (v: number) => 20 + ((v - mn) / (mx - mn)) * 560;
  return (
    <div className="c-argument is-report" ref={root}>
      <Header />
      <main className="ar-rep">
        <section className="ar-rep-title">
          <p className="ar-label">
            <Go to={href(C, 'workspace')}>Reading room</Go> / Adult
          </p>
          <h1>Adult</h1>
          <p className="ar-rep-dek">
            A census table of {nf(run.rows)} people, audited for a binary classifier of <i>annual_income_over_50k</i>. Read in{' '}
            {run.elapsed.toFixed(2)} seconds, on this machine.
          </p>
          <div className="ar-rep-figs">
            <div>
              <b>{run.score}</b>
              <span>Final score, {run.band.toLowerCase()}</span>
            </div>
            <div>
              <b>{run.evidence}</b>
              <span>Evidence average</span>
            </div>
            <div>
              <b>{run.findings.length}</b>
              <span>Findings</span>
            </div>
            <div>
              <b>12/12</b>
              <span>Checks completed</span>
            </div>
          </div>
        </section>

        {run.findings.map((f, i) => (
          <section key={f.code} className="ar-rep-ch">
            <div className="ar-rep-side">
              <span>
                {String(i + 1).padStart(2, '0')} — {f.severity}
              </span>
              <h2>{f.title}</h2>
            </div>
            <div className="ar-rep-body">
              <p className="ar-rep-lede">{f.finding}</p>
              <p>
                {f.modeling_impact} {f.recommendation}
              </p>
              {f.code === 'conflicting_target_labels' && (
                <figure className="ar-fig">
                  <table>
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
                  <figcaption>Fig. 1 — The ten rows in the five conflicting groups. All fourteen features match within each pair.</figcaption>
                </figure>
              )}
              {f.code === 'target_imbalance' && (
                <figure className="ar-fig">
                  <Experiment idx={idx} setIdx={setIdx} />
                  <figcaption>Fig. 2 — Guardrails across five controlled runs. Target balance holds four of them at 69; planted leakage caps the fifth at 49.</figcaption>
                </figure>
              )}
              {f.code === 'numeric_outlier_concentration' && (
                <figure className="ar-fig">
                  <svg viewBox="0 0 600 120" className="ar-box">
                    <line x1="20" x2="580" y1="50" y2="50" />
                    <rect x={hx(32.5)} y="26" width={hx(52.5) - hx(32.5)} height="48" className="fence" />
                    <rect x={hx(q1)} y="34" width={hx(q3) - hx(q1)} height="32" className="iqr" />
                    <line x1={hx(md)} x2={hx(md)} y1="30" y2="70" className="med" />
                    {[mn, 32.5, q1, q3, 52.5, mx].map((v, k) => (
                      <text key={k} x={hx(v)} y={k % 2 ? 106 : 94} textAnchor="middle">
                        {v}
                      </text>
                    ))}
                  </svg>
                  <figcaption>
                    Fig. 3 — hours_per_week. {nf(hours.outlier_count)} rows ({hours.outlier_rate}%) fall outside the 1.5 × IQR fences at 32.5 and 52.5 hours.
                  </figcaption>
                </figure>
              )}
              <p className="ar-rep-effect">{f.score_effect}</p>
            </div>
          </section>
        ))}

        <section className="ar-rep-ch ar-rep-method">
          <div className="ar-rep-side">
            <span>05 — Method</span>
            <h2>What was checked</h2>
          </div>
          <div className="ar-rep-body">
            <ol className="ar-checks">
              {checks.map((c) => (
                <li key={c.id}>
                  <b>{CHECK_LABELS[c.id]}</b> <span>{c.method}</span>
                </li>
              ))}
            </ol>
            <p className="ar-rep-effect">
              {run.coverage.meaning} Outside this run: {run.coverage.unsupported_capabilities.join(', ')}.
            </p>
          </div>
        </section>
      </main>
      <div className="ar-chapters-bar">
        <span>Chapters {String(Math.min(chapter + 1, 5)).padStart(2, '0')} / 05</span>
        <span>
          <button>HTML</button> <button>PDF</button> <button>JSON</button>
        </span>
      </div>
    </div>
  );
}

export default function Argument({ screen }: { screen: Screen }) {
  if (screen === 'workspace') return <Workspace />;
  if (screen === 'results') return <Results />;
  return <Landing />;
}
