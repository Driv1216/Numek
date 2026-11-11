import { useRef, useState } from 'react';
import { Go, href, type Screen } from '../../shared/router';
import { gsap, useGsap, useSmoothScroll, ScrollTrigger } from '../../shared/motion';
import { run, checks, CHECK_LABELS, SUB_LABELS, SUB_ORDER, conflictGroups, columnsProfile, sampleRows, hours, nf } from '../../shared/engine';
import { dists, dist } from '../../shared/distributions';
import { Spark } from '../../shared/Spark';
import { audits, lastRun } from '../../shared/workspace';
import './provenance.css';
import '@fontsource/spectral/300';
import '@fontsource/spectral/400';
import '@fontsource/spectral/400-italic';
import '@fontsource/spectral/500';
import '@fontsource-variable/geist/wght';

const C = 'provenance';
const SOURCE_BYTES = 5271081;
const pair = conflictGroups.find((g) => g.some((r) => r.line === '850'))!;
const r850 = pair.find((r) => r.line === '850')!;
const r22763 = pair.find((r) => r.line === '22763')!;
const dtypes = Object.fromEntries(columnsProfile.map((c) => [c.name, c.dtype]));

function Mark() {
  return (
    <svg viewBox="0 0 28 28" className="pv-mark" aria-hidden="true">
      <circle cx="14" cy="14" r="12.5" fill="none" stroke="currentColor" strokeWidth="1.2" />
      <circle cx="14" cy="14" r="7.5" fill="none" stroke="currentColor" strokeWidth="1.2" />
      <circle cx="14" cy="14" r="2.6" fill="currentColor" />
    </svg>
  );
}

function Header({ center = true }: { center?: boolean }) {
  return (
    <header className={`pv-head${center ? ' is-center' : ''}`}>
      <Go to={href(C)} className="pv-brand" label="Numek home">
        <Mark />
        <span>Numek</span>
      </Go>
      <nav>
        <Go to={href(C, 'workspace')}>Collection</Go>
        <Go to={href(C, 'results')}>Adult</Go>
        <Go to="#/">All concepts</Go>
      </nav>
    </header>
  );
}

/* ----------------------------------------------------------- row card */

function RowCard({ r, stage, twin }: { r: Record<string, string>; stage: number; twin?: boolean }) {
  const fields = ['age', 'workclass', 'education', 'marital_status', 'occupation', 'sex', 'hours_per_week', 'annual_income_over_50k'];
  const isLabel = (f: string) => f === 'annual_income_over_50k';
  return (
    <article className={`pv-card${twin ? ' is-twin' : ''} s${stage}`}>
      <header>
        <span>adult.csv</span>
        <b>line {nf(Number(r.line))}</b>
      </header>
      {stage === 0 ? (
        <pre className="pv-bytes">
          {Object.values(r)
            .slice(1)
            .join(',')
            .replace('<=', '<=')}
          {'\n\n'}
          sha256 {run.sha256.slice(0, 32)}
          {'\n'}
          {run.sha256.slice(32)}
        </pre>
      ) : (
        <dl>
          {fields.map((f) => (
            <div key={f} className={`${isLabel(f) && stage >= 4 ? 'is-label' : ''}${f === 'hours_per_week' && stage === 2 ? ' is-profiled' : ''}`}>
              <dt>{f === 'annual_income_over_50k' ? 'label' : f}</dt>
              <dd>
                {r[f].replace('<=', '≤')}
                {stage === 1 && <em>{dtypes[f]}</em>}
                {stage === 2 && f === 'hours_per_week' && <Spark d={dist('hours_per_week')} width={70} height={14} className="pv-spark" />}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </article>
  );
}

const STAGES = [
  { k: 'Bytes', t: `It begins as bytes: ${nf(SOURCE_BYTES)} of them, fingerprinted before anything is read.` },
  { k: 'Parse', t: 'Line 850 is parsed into fifteen typed fields. Nothing is guessed silently; the parser is recorded.' },
  { k: 'Profile', t: `Every column is profiled. hours_per_week has ${hours.unique_count} distinct values and a median of ${hours.q![2]}.` },
  { k: 'Group', t: 'Grouped on all fourteen features, line 850 turns out to have a twin: line 22,763.' },
  { k: 'Flag', t: 'Same features, different label. The label_conflicts check records the group, deterministically.' },
  { k: 'Report', t: 'It reaches the report with its evidence attached, so a reviewer can follow it back.' },
];

/* -------------------------------------------------------------- landing */

function Landing() {
  const root = useRef<HTMLDivElement>(null);
  const [stage, setStage] = useState(0);
  const [prog, setProg] = useState(0);
  useSmoothScroll();
  useGsap(root, (q) => {
    gsap.from(q('.pv-hero-copy > *'), { opacity: 0, y: 18, stagger: 0.1, duration: 1.2, ease: 'power3.out' });
    gsap.from(q('.pv-float'), { opacity: 0, scale: 0.92, stagger: 0.06, duration: 1.4, ease: 'power3.out', delay: 0.3 });
    q('.pv-float').forEach((el: Element, i: number) =>
      gsap.to(el, { y: (i % 3) * -120 - 60, ease: 'none', scrollTrigger: { trigger: q('.pv-hero')[0], start: 'top top', end: 'bottom top', scrub: true } }),
    );
    ScrollTrigger.create({
      trigger: q('.pv-story')[0],
      start: 'top top',
      end: 'bottom bottom',
      onUpdate: (st) => {
        setProg(st.progress);
        setStage(Math.min(STAGES.length - 1, Math.floor(st.progress * STAGES.length)));
      },
    });
    q('.pv-up').forEach((el: Element) =>
      gsap.from(el, { opacity: 0, y: 30, duration: 1.1, ease: 'power3.out', scrollTrigger: { trigger: el, start: 'top 88%' } }),
    );
  });

  const floats = sampleRows.slice(0, 9);
  return (
    <div className="c-provenance" ref={root}>
      <Header />
      <section className="pv-hero">
        {floats.map((r, i) => (
          <div key={i} className={`pv-float f${i}`} aria-hidden="true">
            <span>line {i + 2}</span>
            <b>
              {r.age} · {r.education}
            </b>
            <em>{r.occupation}</em>
          </div>
        ))}
        <div className="pv-hero-copy">
          <p className="pv-kicker">{nf(run.rows)} rows, twelve checks, one report</p>
          <h1>Here is how DataTrust traces a risk back to the row it came from.</h1>
          <a href="#pv-story" className="pv-scroll">
            ↓ Scroll down
          </a>
        </div>
      </section>

      <section className="pv-story" id="pv-story">
        <div className="pv-story-pin">
          {sampleRows.slice(9, 14).map((r, i) => (
            <div key={i} className={`pv-float pv-ctx c${i}`} aria-hidden="true" style={{ transform: `translateY(${(prog - 0.5) * (i % 2 ? -80 : 60)}px)` }}>
              <span>line {i + 11}</span>
              <b>
                {r.age} · {r.education}
              </b>
              <em>{r.occupation}</em>
            </div>
          ))}
          <div className="pv-stage">
            {stage === 5 ? (
              <figure className="pv-report">
                <img src="round2/report-adult-top.jpg" alt="The real DataTrust report for Adult" />
                <figcaption>Decision summary, adult.html</figcaption>
              </figure>
            ) : (
              <div className={`pv-cards${stage >= 3 ? ' is-pair' : ''}`}>
                <RowCard r={r850} stage={stage} />
                {stage >= 3 && <RowCard r={r22763} stage={stage} twin />}
              </div>
            )}
          </div>
          <p className="pv-sentence" key={stage}>
            {STAGES[stage].t}
          </p>
          <div className="pv-scrub" aria-label={`Stage ${stage + 1} of ${STAGES.length}`}>
            <div className="pv-scrub-track">
              <i style={{ width: `${prog * 100}%` }} />
            </div>
            <div className="pv-scrub-ticks">
              {STAGES.map((s, i) => (
                <span key={s.k} className={i === stage ? 'is-on' : i < stage ? 'is-past' : ''}>
                  {s.k}
                </span>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="pv-chains">
        <div className="pv-sec-head pv-up">
          <p className="pv-kicker">Every finding keeps its provenance</p>
          <h2>Four findings, each with the path that produced it.</h2>
        </div>
        <div className="pv-chain-list">
          {run.findings.map((f) => {
            const check = { conflicting_target_labels: 'label_conflicts', target_imbalance: 'classification_target', numeric_outlier_concentration: 'numeric_outliers', leakage_review_prompts: 'target_leakage' }[f.code]!;
            const c = checks.find((x) => x.id === check)!;
            return (
              <article key={f.code} className="pv-chain pv-up">
                <h3>{f.title}</h3>
                <ol>
                  <li>
                    <span>Source</span>adult.csv · {run.sha256.slice(0, 10)}…
                  </li>
                  <li>
                    <span>Check</span>
                    {CHECK_LABELS[check]}
                  </li>
                  <li>
                    <span>Method</span>
                    <code>{c.method}</code>
                  </li>
                  <li>
                    <span>Population</span>
                    {c.population}
                  </li>
                  <li>
                    <span>Evidence</span>
                    {f.evidence}
                  </li>
                  <li>
                    <span>Effect</span>
                    {f.score_effect}
                  </li>
                </ol>
              </article>
            );
          })}
        </div>
      </section>

      <section className="pv-catalogue">
        <div className="pv-sec-head pv-up">
          <p className="pv-kicker">The whole table, catalogued</p>
          <h2>Fifteen columns, read in full.</h2>
          <p>Each entry is the real distribution of that column across all {nf(run.rows)} rows.</p>
        </div>
        <div className="pv-cat-grid">
          {dists.map((d) => {
            const p = columnsProfile.find((c) => c.name === d.name)!;
            return (
              <figure key={d.name} className="pv-cat pv-up">
                <Spark d={d} width={220} height={70} className="pv-cat-spark" />
                <figcaption>
                  <b>{d.name}</b>
                  <span>
                    {p.dtype} · {nf(p.unique_count)} distinct{d.missing ? ` · ${nf(d.missing)} missing` : ''}
                  </span>
                </figcaption>
              </figure>
            );
          })}
        </div>
      </section>

      <section className="pv-close">
        <h2 className="pv-up">Know where every finding came from.</h2>
        <div className="pv-close-actions pv-up">
          <Go to={href(C, 'workspace')} className="pv-btn">
            Browse the collection
          </Go>
          <Go to={href(C, 'results')} className="pv-btn is-ghost">
            Open the Adult record
          </Go>
        </div>
        <footer>
          <span>Numek · DataTrust</span>
          <span>Runs locally. A reliability report, not a certificate.</span>
        </footer>
      </section>
    </div>
  );
}

/* ------------------------------------------------------------ workspace */

function Workspace() {
  const root = useRef<HTMLDivElement>(null);
  useGsap(root, (q) => {
    gsap.from(q('.pv-entry'), { opacity: 0, y: 16, stagger: 0.05, duration: 0.8, ease: 'power3.out' });
  });
  return (
    <div className="c-provenance is-app" ref={root}>
      <Header center={false} />
      <main className="pv-coll">
        <section className="pv-coll-head">
          <p className="pv-kicker">The collection · ~/numek/audits</p>
          <h1>Seven datasets, each with its record.</h1>
          <div className="pv-coll-filters">
            <span className="is-on">All 7</span>
            <span>Classification 4</span>
            <span>Regression 2</span>
            <span>Connected evidence 1</span>
          </div>
        </section>
        <section className="pv-entries">
          {audits.map((a) => {
            const isAdult = a.id === 'adult';
            const body = (
              <>
                <div className="pv-entry-vis">
                  {a.sub ? (
                    <div className="pv-entry-subs">
                      {a.sub.map((v, i) => (
                        <i key={i} style={{ height: `${v}%` }} className={v < 50 ? 'is-low' : ''} title={`${SUB_LABELS[SUB_ORDER[i]]} ${v}`} />
                      ))}
                    </div>
                  ) : (
                    <span className="pv-entry-none">No score defined</span>
                  )}
                </div>
                <div className="pv-entry-meta">
                  <h2>{a.name}</h2>
                  <p>
                    {a.kind}, {nf(a.rows)} {a.kind === 'Connected evidence' ? 'records' : 'rows'}
                    {a.columns ? ` × ${a.columns}` : ''}
                  </p>
                  <p className="pv-entry-note">{a.note}.</p>
                  <dl>
                    <dt>Score</dt>
                    <dd>{a.score === null ? '—' : `${a.score} · ${a.band}`}</dd>
                    <dt>Findings</dt>
                    <dd>{a.findings}</dd>
                    <dt>Read</dt>
                    <dd>{lastRun[a.id]}</dd>
                  </dl>
                </div>
              </>
            );
            return isAdult ? (
              <Go key={a.id} to={href(C, 'results')} className="pv-entry is-link">
                {body}
              </Go>
            ) : (
              <div key={a.id} className="pv-entry">
                {body}
              </div>
            );
          })}
          <div className="pv-entry is-new">
            <div className="pv-entry-vis">
              <span className="pv-entry-plus">+</span>
            </div>
            <div className="pv-entry-meta">
              <h2>Add a dataset</h2>
              <p>Name the file and the outcome. DataTrust records the bytes before it reads them.</p>
              <code>datatrust audit data.csv --target …</code>
            </div>
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
    gsap.from(q('.pv-rec-head > *, .pv-rec-meta'), { opacity: 0, y: 14, stagger: 0.06, duration: 0.9, ease: 'power3.out' });
  });
  const steps = [
    ['Source', `adult.csv, ${nf(SOURCE_BYTES)} bytes`],
    ['Fingerprint', `sha256 ${run.sha256.slice(0, 16)}…`],
    ['Parser', 'pandas.read_csv, utf-8, pandas_default missing values'],
    ['Profile', `${nf(run.rows)} rows × ${run.columns} columns`],
    ['Checks', '12 of 12 applicable checks completed'],
    ['Method', run.methodology],
    ['Elapsed', `${run.elapsed.toFixed(2)} s, on this machine`],
  ];
  return (
    <div className="c-provenance is-app" ref={root}>
      <Header center={false} />
      <main className="pv-rec">
        <section className="pv-rec-head">
          <p className="pv-kicker">
            <Go to={href(C, 'workspace')}>Collection</Go> / Adult
          </p>
          <h1>Adult</h1>
          <p className="pv-rec-dek">
            Binary classification of <i>annual_income_over_50k</i>. Final score {run.score}, {run.band.toLowerCase()}: the evidence
            averages {run.evidence}, and the target-balance guardrail caps it.
          </p>
        </section>

        <section className="pv-rec-body">
          <div className="pv-rec-main">
            <div className="pv-tabs" role="tablist">
              {run.findings.map((x, i) => (
                <button key={x.code} role="tab" aria-selected={i === sel} className={i === sel ? 'is-on' : ''} onClick={() => setSel(i)}>
                  <span>{x.severity}</span>
                  {x.title}
                </button>
              ))}
            </div>
            <figure className="pv-specimen">
              {f.code === 'conflicting_target_labels' && (
                <div className="pv-pairs">
                  {conflictGroups.map((g, gi) => (
                    <div key={gi} className="pv-pairrow">
                      {g.map((r) => (
                        <div key={r.line}>
                          <span>line {nf(Number(r.line))}</span>
                          <b>
                            {r.age}, {r.education}, {r.occupation}, {r.hours_per_week} h
                          </b>
                          <em className={r.annual_income_over_50k === '>50K' ? 'is-hi' : ''}>{r.annual_income_over_50k.replace('<=', '≤')}</em>
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              )}
              {f.code === 'numeric_outlier_concentration' && (
                <div className="pv-hist">
                  <Spark d={dist('hours_per_week')} width={640} height={200} gap={3} className="pv-hist-svg" hot={(lo, hi) => hi <= 32.5 || lo >= 52.5} />
                  <div className="pv-hist-axis">
                    <span>1 h</span>
                    <span>fences at 32.5 and 52.5 h</span>
                    <span>99 h</span>
                  </div>
                </div>
              )}
              {f.code === 'target_imbalance' && (
                <div className="pv-classes">
                  {run.profile.target_distribution.map((d) => (
                    <div key={d.label} style={{ flexGrow: d.count }} className={d.label.startsWith('>') ? 'is-min' : ''}>
                      <b>{d.percentage}%</b>
                      <span>
                        {d.label.replace('<=', '≤')}, {nf(d.count)} rows
                      </span>
                    </div>
                  ))}
                </div>
              )}
              {f.code === 'leakage_review_prompts' && (
                <div className="pv-colrec">
                  <Spark d={dist('marital_status')} width={560} height={46} className="pv-colrec-spark" />
                  <b>marital_status</b>
                  <span>Seven values, complete. Flagged only because of its name: confirm when the status is known.</span>
                </div>
              )}
              <figcaption>{f.finding}</figcaption>
            </figure>
            <div className="pv-rec-text">
              <div>
                <span>Possible modeling impact</span>
                <p>{f.modeling_impact}</p>
              </div>
              <div>
                <span>Recommended review</span>
                <p>{f.recommendation}</p>
              </div>
              <div>
                <span>Effect on the score</span>
                <p>{f.score_effect}</p>
              </div>
            </div>
          </div>
          <aside className="pv-rec-meta">
            <p className="pv-kicker">Provenance</p>
            <ol className="pv-prov">
              {steps.map(([k, v]) => (
                <li key={k}>
                  <span>{k}</span>
                  <b>{v}</b>
                </li>
              ))}
            </ol>
            <div className="pv-rec-subs">
              {SUB_ORDER.map((k) => (
                <div key={k} className={run.sub[k] < 50 ? 'is-low' : ''}>
                  <span>{SUB_LABELS[k]}</span>
                  <b>{run.sub[k].toFixed(2)}</b>
                </div>
              ))}
            </div>
            <div className="pv-rec-actions">
              <button className="pv-btn">Download report</button>
              <button className="pv-btn is-ghost">JSON evidence</button>
            </div>
          </aside>
        </section>

        <section className="pv-rec-cols">
          <p className="pv-kicker">Columns in this record</p>
          <div className="pv-cat-grid is-dense">
            {dists.map((d) => {
              const p = columnsProfile.find((c) => c.name === d.name)!;
              const flagged = d.name === 'hours_per_week' || d.name === 'marital_status' || d.name === 'annual_income_over_50k';
              return (
                <figure key={d.name} className={`pv-cat${flagged ? ' is-flag' : ''}`}>
                  <Spark d={d} width={200} height={44} className="pv-cat-spark" />
                  <figcaption>
                    <b>{d.name}</b>
                    <span>
                      {p.dtype} · {nf(p.unique_count)} distinct{d.missing ? ` · ${nf(d.missing)} missing` : ''}
                    </span>
                  </figcaption>
                </figure>
              );
            })}
          </div>
        </section>
      </main>
    </div>
  );
}

export default function Provenance({ screen }: { screen: Screen }) {
  if (screen === 'workspace') return <Workspace />;
  if (screen === 'results') return <Results />;
  return <Landing />;
}
