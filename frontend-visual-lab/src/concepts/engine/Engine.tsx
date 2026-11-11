import { useEffect, useRef, useState } from 'react';
import { Go, href, type Screen } from '../../shared/router';
import { gsap, useGsap, useSmoothScroll, ScrollTrigger } from '../../shared/motion';
import { run, checks, CHECK_LABELS, SUB_LABELS, SUB_ORDER, conflictGroups, columnsProfile, hours, nf } from '../../shared/engine';
import { grid, dist } from '../../shared/distributions';
import { Spark } from '../../shared/Spark';
import { audits, openFindings, lastRun } from '../../shared/workspace';
import { Exploded, FINDING_CHECKS } from './Exploded';
import './engine.css';
import '@fontsource-variable/bricolage-grotesque/wght';
import '@fontsource/azeret-mono/400';
import '@fontsource/azeret-mono/500';

const C = 'engine';
const FINDING_TO_CHECK: Record<string, string> = {
  conflicting_target_labels: 'label_conflicts',
  target_imbalance: 'classification_target',
  numeric_outlier_concentration: 'numeric_outliers',
  leakage_review_prompts: 'target_leakage',
};

function Mark() {
  return (
    <svg viewBox="0 0 22 22" className="en-mark" aria-hidden="true">
      {[0, 1, 2, 3].map((i) => (
        <ellipse key={i} cx="11" cy={6 + i * 3.4} rx={8 - (i % 2) * 2} ry="2.2" fill="none" stroke="currentColor" strokeWidth="1.3" />
      ))}
    </svg>
  );
}

function Nav({ dark = true }: { dark?: boolean }) {
  return (
    <header className={`en-nav${dark ? '' : ' is-light'}`}>
      <Go to={href(C)} className="en-brand" label="Numek home">
        <Mark /> numek<span>/datatrust</span>
      </Go>
      <nav>
        <a href="#en-engine">Engine</a>
        <a href="#en-map">Evidence</a>
        <Go to={href(C, 'workspace')}>Console</Go>
        <Go to="#/">[ All concepts ]</Go>
      </nav>
      <Go to={href(C, 'workspace')} className="en-cta">
        [ Run an audit ]
      </Go>
    </header>
  );
}

/* ----------------------------------------------------------- density map */

function DensityMap({ height = 460 }: { height?: number }) {
  const cv = useRef<HTMLCanvasElement>(null);
  const [size, setSize] = useState({ w: 800, h: height });
  const rows = grid.counts.length; // age bins
  const cols = grid.counts[0].length; // hour bins
  useEffect(() => {
    const c = cv.current!;
    const draw = () => {
      const w = c.clientWidth;
      const h = c.clientHeight;
      setSize({ w, h });
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      c.width = w * dpr;
      c.height = h * dpr;
      const ctx = c.getContext('2d')!;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      const max = Math.max(...grid.counts.flat());
      const cw = w / rows;
      const ch = h / cols;
      for (let a = 0; a < rows; a++)
        for (let b = 0; b < cols; b++) {
          const v = grid.counts[a][b];
          if (!v) continue;
          const t = Math.pow(v / max, 0.42);
          ctx.fillStyle = `rgba(233,230,224,${0.06 + t * 0.9})`;
          const s = 0.18 + t * 0.62;
          ctx.fillRect(a * cw + (cw * (1 - s)) / 2, h - (b + 1) * ch + (ch * (1 - s)) / 2, cw * s, ch * s);
        }
    };
    draw();
    const ro = new ResizeObserver(draw);
    ro.observe(c);
    return () => ro.disconnect();
  }, [rows, cols]);
  const ax = (age: number) => ((age - grid.age_edges[0]) / (grid.age_edges[rows] - grid.age_edges[0])) * size.w;
  const hy = (hr: number) => size.h - ((hr - grid.hour_edges[0]) / (grid.hour_edges[cols] - grid.hour_edges[0])) * size.h;
  const highHours = grid.counts.reduce((s, r) => s + r.slice(20).reduce((a, b) => a + b, 0), 0);
  const boxes = [
    { x0: 37, x1: 41, y0: 37, y1: 45, t: 'lines 850 · 22,763', s: 'age 39 · 40 h · labels disagree', hot: true },
    { x0: 35, x1: 37, y0: 37, y1: 41, t: 'densest cell', s: '1,400 rows · 35–36 y · 37–40 h' },
    { x0: 17, x1: 91, y0: 81, y1: 101, t: `≥ 81 h · ${nf(highHours)} rows`, s: 'beyond the 52.5 h fence' },
  ];
  return (
    <div className="en-map" style={{ height }}>
      <canvas ref={cv} />
      {boxes.map((b) => (
        <div
          key={b.t}
          className={`en-zoom${b.hot ? ' is-hot' : ''}`}
          style={{ left: ax(b.x0), top: hy(b.y1), width: ax(b.x1) - ax(b.x0), height: hy(b.y0) - hy(b.y1) }}
        >
          <span>
            <b>{b.t}</b>
            {b.s}
          </span>
        </div>
      ))}
      <div className="en-map-axis x">
        <span>age 17</span>
        <span>90</span>
      </div>
      <div className="en-map-axis y">
        <span>99 h</span>
        <span>1 h</span>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------- landing */

function Landing() {
  const root = useRef<HTMLDivElement>(null);
  const [explode, setExplode] = useState(0.15);
  const [scrub, setScrub] = useState(0);
  useSmoothScroll();
  useGsap(root, (q) => {
    gsap.from(q('.en-hero-copy > *'), { opacity: 0, y: 22, stagger: 0.08, duration: 1.1, ease: 'expo.out' });
    ScrollTrigger.create({
      trigger: q('.en-explode')[0],
      start: 'top top',
      end: 'bottom bottom',
      onUpdate: (st) => {
        setExplode(0.15 + st.progress * 0.85);
        setScrub(st.progress);
      },
    });
    q('.en-rise').forEach((el: Element) =>
      gsap.from(el, { opacity: 0, y: 30, duration: 1, ease: 'power3.out', scrollTrigger: { trigger: el, start: 'top 88%' } }),
    );
  });

  return (
    <div className="c-engine" ref={root}>
      <Nav />
      <section className="en-hero">
        <div className="en-hero-copy">
          <h1>
            The truth is
            <br />
            in the rows.
          </h1>
          <p>DataTrust turns a training table into evidence: twelve checks over every row, each with a named method, run on your own machine.</p>
          <div className="en-hero-cta">
            <code>$ datatrust audit data.csv --target …</code>
            <Go to={href(C, 'results')} className="en-link">
              [ See a real audit ]
            </Go>
          </div>
        </div>
        <div className="en-hero-obj">
          <Exploded explode={0.08} height="min(82vh, 760px)" labels={false} />
          <div className="en-dial" aria-hidden="true">
            <svg viewBox="0 0 200 200">
              <circle cx="100" cy="100" r="92" />
              <circle cx="100" cy="100" r="92" className="arc" style={{ strokeDasharray: `${(run.score / 100) * 578} 578` }} />
            </svg>
            <b>{run.score}</b>
            <span>Adult · elevated</span>
          </div>
        </div>
        <div className="en-scroll">[ scroll ]</div>
      </section>

      <section className="en-explode" id="en-engine">
        <div className="en-explode-pin">
          <div className="en-explode-head">
            <h2>Every check, taken apart</h2>
            <p>Twelve checks run in order over the whole table. The four in red produced Adult's findings.</p>
          </div>
          <Exploded explode={explode} height="100%" />
          <div className="en-scrubber" aria-hidden="true">
            {Array.from({ length: 40 }, (_, i) => (
              <i key={i} className={i / 40 < scrub ? 'on' : ''} />
            ))}
          </div>
        </div>
      </section>

      <section className="en-props" id="en-map">
        <div className="en-props-list">
          <p className="en-label">What it finds</p>
          {[
            ['Detect what notebooks miss', 'Feature-identical rows with different labels, located to the CSV line. Five groups in Adult.'],
            ['From profile to finding', 'Column profiles feed the checks; each finding names its population, method and modeling impact.'],
            ['Trusted because it is shown', 'Severe weaknesses cap the score. Every number traces back to rows you can open.'],
          ].map(([t, d], i) => (
            <div key={t} className="en-prop en-rise">
              <span className="en-prop-ico">
                <i style={{ height: `${30 + i * 25}%` }} />
                <i style={{ height: `${80 - i * 20}%` }} />
                <i style={{ height: `${50 + i * 10}%` }} />
              </span>
              <div>
                <b>{t}</b>
                <p>{d}</p>
              </div>
            </div>
          ))}
        </div>
        <div className="en-rise">
          <DensityMap />
          <p className="en-map-cap">All {nf(run.rows)} Adult rows by age and hours per week, from the pinned CSV. Brighter squares hold more rows.</p>
        </div>
      </section>

      <section className="en-close">
        <h2 className="en-rise">Audit the data before the model learns it.</h2>
        <div className="en-close-row en-rise">
          <Go to={href(C, 'workspace')} className="en-cta is-big">
            [ Open the console ]
          </Go>
          <span>Runs locally · loopback only · nothing uploaded</span>
        </div>
        <footer>
          <span>numek/datatrust</span>
          <span>A reliability report, not a certificate.</span>
        </footer>
      </section>
    </div>
  );
}

/* ------------------------------------------------------------ workspace */

function Workspace() {
  const root = useRef<HTMLDivElement>(null);
  const [sel, setSel] = useState(0);
  const a = audits[sel];
  useGsap(root, (q) => {
    gsap.from(q('.en-row'), { opacity: 0, x: -10, stagger: 0.04, duration: 0.5 });
  });
  return (
    <div className="c-engine is-app" ref={root}>
      <Nav />
      <main className="en-console">
        <section className="en-con-list">
          <header>
            <span>audits</span>
            <span>~/numek/audits · 7</span>
          </header>
          {audits.map((x, i) => (
            <button key={x.id} className={`en-row${i === sel ? ' is-on' : ''}`} onClick={() => setSel(i)}>
              <span className="en-row-i">{String(i + 1).padStart(2, '0')}</span>
              <span className="en-row-name">{x.name}</span>
              <span className="en-row-kind">{x.kind.toLowerCase()}</span>
              <span className={`en-row-score${x.band === 'High' || x.band === 'Elevated' ? ' is-hot' : ''}`}>{x.score ?? '--'}</span>
            </button>
          ))}
          <div className="en-con-new">
            <span>[ + new audit ]</span>
            <code>datatrust audit data.csv --target …</code>
          </div>
        </section>
        <section className="en-con-detail">
          <div className="en-con-top">
            <div>
              <p className="en-label">{a.kind.toLowerCase()} · {lastRun[a.id]}</p>
              <h1>{a.name}</h1>
              <p className="en-con-note">{a.note}.</p>
            </div>
            <div className="en-con-score">
              <b className={a.band === 'High' || a.band === 'Elevated' ? 'is-hot' : ''}>{a.score ?? '--'}</b>
              <span>{a.band.toLowerCase()}</span>
            </div>
          </div>
          <div className="en-con-grid">
            <div className="en-box">
              <p className="en-label">engine</p>
              {a.id === 'adult' ? <Exploded explode={0.6} height={460} labels={false} spin /> : <div className="en-box-empty">Engine trace available for Adult in this prototype.</div>}
            </div>
            <div className="en-box">
              <p className="en-label">sub-scores</p>
              {a.sub ? (
                a.sub.map((v, i) => (
                  <div key={i} className={`en-bar${v < 50 ? ' is-hot' : ''}`}>
                    <span>{SUB_LABELS[SUB_ORDER[i]].toLowerCase()}</span>
                    <i>
                      {Array.from({ length: 20 }, (_, k) => (
                        <em key={k} className={k < Math.round(v / 5) ? 'on' : ''} />
                      ))}
                    </i>
                    <b>{v.toFixed(1)}</b>
                  </div>
                ))
              ) : (
                <div className="en-box-empty">No scoring policy for this task. Evidence only.</div>
              )}
              <p className="en-label en-gap">open findings</p>
              {openFindings
                .filter((f) => f.auditId === a.id)
                .map((f, i) => (
                  <div key={i} className="en-find">
                    <i className={`is-${f.severity.toLowerCase()}`} />
                    <span>
                      <b>{f.title}</b>
                      <em>{f.detail}</em>
                    </span>
                  </div>
                ))}
              {!openFindings.some((f) => f.auditId === a.id) && <div className="en-box-empty">{a.findings} findings in the report.</div>}
            </div>
          </div>
          {a.id === 'adult' && (
            <Go to={href(C, 'results')} className="en-cta is-big">
              [ Open the Adult audit ]
            </Go>
          )}
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
    gsap.from(q('.en-res-head > *'), { opacity: 0, y: 14, stagger: 0.07, duration: 0.8 });
  });
  return (
    <div className="c-engine is-app" ref={root}>
      <Nav />
      <main className="en-res">
        <section className="en-res-head">
          <p className="en-label">
            <Go to={href(C, 'workspace')}>[ console ]</Go> / adult
          </p>
          <h1>Adult</h1>
          <div className="en-res-stats">
            <span>
              score <b className="is-hot">{run.score}</b>
            </span>
            <span>
              evidence <b>{run.evidence}</b>
            </span>
            <span>
              rows <b>{nf(run.rows)}</b>
            </span>
            <span>
              checks <b>12/12</b>
            </span>
            <span>
              elapsed <b>{run.elapsed.toFixed(2)} s</b>
            </span>
          </div>
        </section>
        <section className="en-res-body">
          <div className="en-res-engine">
            <Exploded explode={0.75} height={560} focus={FINDING_TO_CHECK[f.code]} />
          </div>
          <div className="en-res-panel">
            <div className="en-tabs">
              {run.findings.map((x, i) => (
                <button key={x.code} className={i === sel ? 'is-on' : ''} onClick={() => setSel(i)}>
                  <span>{String(i + 1).padStart(2, '0')}</span>
                  {x.title}
                </button>
              ))}
            </div>
            <p className="en-label">
              {f.severity.toLowerCase()} · check {CHECK_LABELS[FINDING_TO_CHECK[f.code]].toLowerCase()} · {checks.find((c) => c.id === FINDING_TO_CHECK[f.code])!.method}
            </p>
            <h2>{f.finding}</h2>
            {f.code === 'conflicting_target_labels' && (
              <table className="en-table">
                <thead>
                  <tr>
                    <th>line</th>
                    <th>age</th>
                    <th>education</th>
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
                        <td>{r.education}</td>
                        <td>{r.hours_per_week}</td>
                        <td className={r.annual_income_over_50k === '>50K' ? 'hot' : ''}>{r.annual_income_over_50k.replace('<=', '≤')}</td>
                      </tr>
                    ))}
                  </tbody>
                ))}
              </table>
            )}
            {f.code === 'numeric_outlier_concentration' && (
              <div className="en-ev">
                <Spark d={dist('hours_per_week')} width={500} height={140} gap={3} className="en-spark" hot={(lo, hi) => hi <= 32.5 || lo >= 52.5} />
                <p>
                  {nf(hours.outlier_count)} rows · {hours.outlier_rate}% outside 32.5–52.5 h (1.5 × IQR on quartiles {hours.q![1]}–{hours.q![3]})
                </p>
              </div>
            )}
            {f.code === 'target_imbalance' && (
              <div className="en-ev en-split">
                {run.profile.target_distribution.map((d) => (
                  <div key={d.label} style={{ flexGrow: d.count }} className={d.label.startsWith('>') ? 'hot' : ''}>
                    <b>{d.percentage}%</b>
                    <span>{d.label.replace('<=', '≤')}</span>
                  </div>
                ))}
              </div>
            )}
            {f.code === 'leakage_review_prompts' && (
              <div className="en-ev">
                <Spark d={dist('marital_status')} width={500} height={40} className="en-spark" />
                <p>marital_status · review_only · name heuristic. Confirm when the value is known.</p>
              </div>
            )}
            <dl className="en-kv">
              <dt>impact</dt>
              <dd>{f.modeling_impact}</dd>
              <dt>review</dt>
              <dd>{f.recommendation}</dd>
              <dt>score</dt>
              <dd>{f.score_effect}</dd>
            </dl>
            <div className="en-res-actions">
              <span className="en-cta">[ html ]</span>
              <span className="en-cta">[ pdf ]</span>
              <span className="en-cta">[ json ]</span>
            </div>
          </div>
        </section>
        <section className="en-res-cols">
          <p className="en-label">column profile · 15</p>
          <div className="en-cols">
            {columnsProfile.map((c) => (
              <div key={c.name} className={c.outlier_rate > 5 || c.name === 'marital_status' || c.role === 'target' ? 'is-hot' : ''}>
                <code>{c.name}</code>
                <Spark d={dist(c.name)} width={160} height={30} className="en-spark" />
                <span>
                  {c.dtype} · {nf(c.unique_count)} distinct{c.missing_count ? ` · ${nf(c.missing_count)} missing` : ''}
                </span>
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}

export default function Engine({ screen }: { screen: Screen }) {
  if (screen === 'workspace') return <Workspace />;
  if (screen === 'results') return <Results />;
  return <Landing />;
}

export { FINDING_CHECKS };
