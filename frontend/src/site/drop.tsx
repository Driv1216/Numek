// The DataTrust hero, "The Drop": the product moment in about six seconds, then something to explore.
// A real file (adult.csv, 5.3 MB) drops into the intake; its rows stream past while it is fingerprinted
// and counted; six checks resolve with their real results; the score arrives as the 89.15 average and
// is pulled down to the 69 cap; the findings land in plain English with the three report files.
// Clicking a finding swaps the intake for that finding's real evidence, marked in Markup's language.
import './drop.css';
import { useEffect, useRef, useState, type ReactElement } from 'react';
import { adult } from './content';
import { reducedMotion } from '../foundation/motion';
import { brackets } from '../foundation/system';

// Timeline (ms from the start of a run).
const AT = { drop: 450, read: 1050, checks: 2300, evidence: 4200, cap: 5000, findings: 5600, done: 6500 };
type Phase = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7;

const checks: { t: string; r: string; found: 'no' | 'yes' | 'review' | 'critical' }[] = [
  { t: 'Missing values', r: '3,620 rows · 7.41%', found: 'no' },
  { t: 'Repeated rows', r: '52 rows', found: 'no' },
  { t: 'Contradicting labels', r: '5 groups · 10 rows', found: 'yes' },
  { t: 'Unusual values', r: '13,496 rows', found: 'yes' },
  { t: 'Leaked answers', r: '1 column to review', found: 'review' },
  { t: 'Lopsided target', r: '76.07% one answer', found: 'critical' },
];
export type FId = 'imbalance' | 'unusual' | 'conflict' | 'leak';
export const findings: { id: FId; t: string; sev: string; eff: string; tone: 'crit' | 'mod' | 'low' }[] = [
  { id: 'imbalance', t: 'One answer fills 76% of the target', sev: 'Critical', eff: 'holds the score at 69', tone: 'crit' },
  { id: 'unusual', t: '13,496 unusual work-hour values', sev: 'Moderate', eff: 'lowers a measure', tone: 'mod' },
  { id: 'conflict', t: 'Identical people, different answers', sev: 'Moderate', eff: 'shown for review', tone: 'mod' },
  { id: 'leak', t: 'A column name worth a second look', sev: 'Low', eff: 'shown for review', tone: 'low' },
];

/** Counts to `to` over `ms` once `on` is true. */
function useTween(to: number, on: boolean, ms: number, from = 0) {
  const [v, setV] = useState(reducedMotion() ? to : from);
  useEffect(() => {
    if (!on) { setV(reducedMotion() ? to : from); return; }
    if (reducedMotion()) { setV(to); return; }
    let raf = 0; const t0 = performance.now();
    const tick = (t: number) => { const k = Math.min(1, (t - t0) / ms); setV(from + (to - from) * (1 - Math.pow(1 - k, 3))); if (k < 1) raf = requestAnimationFrame(tick); };
    raf = requestAnimationFrame(tick); return () => cancelAnimationFrame(raf);
  }, [to, on, ms, from]);
  return v;
}

/* ——— Evidence views (left panel once a finding is picked) ——— */

function Imbalance() {
  const { le50k, gt50k } = adult.classes, n = le50k + gt50k;
  return (
    <div className="nk-ev">
      <span className="nk-ev__k">annual_income_over_50k · {n.toLocaleString()} answers</span>
      <svg viewBox="0 0 420 170" className="nk-ev__svg" role="img" aria-label={`${le50k.toLocaleString()} answers are ≤50K and ${gt50k.toLocaleString()} are >50K`}>
        <rect x={10} y={40} width={(400 * le50k) / n} height={46} className="nk-ev__ink" />
        <rect x={10 + (400 * le50k) / n} y={40} width={(400 * gt50k) / n} height={46} className="nk-ev__hot" />
        <text x={18} y={70} className="nk-ev__in">≤50K · {le50k.toLocaleString()}</text>
        <text x={14 + (400 * le50k) / n} y={70} className="nk-ev__in">&gt;50K</text>
        <path d={brackets(4, 34, 412, 58, 10)} className="nk-ev__br" />
        <path d={`M10 112V120H${10 + (400 * le50k) / n}V112`} className="nk-ev__dim" />
        <text x={10 + (200 * le50k) / n} y={138} textAnchor="middle" className="nk-ev__t">76.07% · ratio {adult.ratio}</text>
      </svg>
      <p>A model could be right 76% of the time by always answering “≤50K”. Target balance is {adult.subScores[2].value}, which is critical, so DataTrust holds the score at 69.</p>
    </div>
  );
}
function Unusual() {
  const h = adult.hours, c = h.hist.counts, max = Math.sqrt(Math.max(...c)), W = 420, bw = W / c.length;
  const x = (v: number) => ((v - h.hist.start) / c.length) * W;
  return (
    <div className="nk-ev">
      <span className="nk-ev__k">hours_per_week · rows per value (√ scale)</span>
      <svg viewBox="0 0 420 170" className="nk-ev__svg" role="img" aria-label={`Hours per week; ${h.outliers.toLocaleString()} rows fall outside ${h.lower} to ${h.upper}`}>
        {c.map((v, i) => { const hh = (Math.sqrt(v) / max) * 110; const val = h.hist.start + i; return <rect key={i} x={i * bw + 0.5} y={128 - hh} width={Math.max(1, bw - 1)} height={hh} className={val < h.lower || val > h.upper ? 'nk-ev__hot' : 'nk-ev__ink'} />; })}
        {[h.lower, h.upper].map((f) => <g key={f}><line x1={x(f)} x2={x(f)} y1={8} y2={132} className="nk-ev__fence" /><text x={x(f)} y={150} textAnchor="middle" className="nk-ev__t">{f}</text></g>)}
        <text x={x(40)} y={6} textAnchor="middle" className="nk-ev__t nk-ev__t--ink">40 h</text>
      </svg>
      <p>Most people work about 40 hours. {h.below.toLocaleString()} rows fall below 32.5 and {h.above.toLocaleString()} above 52.5. They are reported, not removed, so you decide.</p>
    </div>
  );
}
function Conflict() {
  const g = adult.conflicts[0], f = g.features as Record<string, string | number>;
  const keys = ['age', 'workclass', 'education', 'occupation', 'hours_per_week', 'sex'];
  return (
    <div className="nk-ev">
      <span className="nk-ev__k">rows {g.rows.map((r) => r.toLocaleString()).join(' and ')} · 14 of 14 features equal</span>
      <div className="nk-ev__rows">
        {g.rows.map((r, i) => (
          <div key={r} className="nk-ev__row">
            <b>row {r.toLocaleString()}</b>
            <span>{keys.map((k) => `${f[k]}`).join(' · ')} · …</span>
            <em>{g.labels[i]}</em>
          </div>
        ))}
        <i className="nk-ev__rbr" aria-hidden="true" />
      </div>
      <p>Same age, job, education and hours, and every other feature, yet one row says &gt;50K and the other ≤50K. DataTrust found 5 groups like this. It cannot know which label is right, so it asks a person to look.</p>
    </div>
  );
}
function Leak() {
  return (
    <div className="nk-ev">
      <span className="nk-ev__k">15 columns · names checked for leaked answers</span>
      <ul className="nk-ev__cols">
        {adult.header.map((c) => <li key={c} className={c === 'marital_status' ? 'is-hot' : c === adult.target ? 'is-t' : ''}>{c}{c === 'marital_status' && <em>review only</em>}{c === adult.target && <em>target</em>}</li>)}
      </ul>
      <p>“marital_status” has a name that can hide information known only after the outcome. Its name alone is not proof, so it changes no score: check when the value becomes known.</p>
    </div>
  );
}
export const views: Record<FId, () => ReactElement> = { imbalance: Imbalance, unusual: Unusual, conflict: Conflict, leak: Leak };

/* ——— The drop ——— */

export function Drop() {
  const stage = useRef<HTMLDivElement>(null);
  const [run, setRun] = useState(0);
  const [phase, setPhase] = useState<Phase>(reducedMotion() ? 7 : 0);
  const [pick, setPick] = useState<FId>('imbalance');

  // Start when the stage is in view; replays restart the timeline.
  useEffect(() => {
    if (reducedMotion()) { setPhase(7); return; }
    setPhase(0);
    let timers: number[] = [];
    const start = () => {
      const seq: [number, Phase][] = [[AT.drop, 1], [AT.read, 2], [AT.checks, 3], [AT.evidence, 4], [AT.cap, 5], [AT.findings, 6], [AT.done, 7]];
      timers = seq.map(([ms, ph]) => window.setTimeout(() => setPhase(ph), ms));
    };
    const el = stage.current; if (!el) return;
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { io.disconnect(); start(); } }, { threshold: 0.35 });
    io.observe(el);
    return () => { io.disconnect(); timers.forEach(clearTimeout); };
  }, [run]);

  const rows = useTween(adult.rows, phase >= 2, 1100);
  const score = useTween(adult.evidenceScore, phase >= 4, 700);
  const capped = phase >= 5;
  const View = views[pick];
  const sx = (v: number) => (v / 100) * 100; // percent across the scale

  return (
    <div ref={stage} className={`nk-dp p${phase}`}>
      <i className="nk-dp__x" aria-hidden="true" /><i className="nk-dp__x" aria-hidden="true" /><i className="nk-dp__x" aria-hidden="true" /><i className="nk-dp__x" aria-hidden="true" />
      <div className="nk-dp__pipe" aria-hidden="true"><i className="nk-dp__seg nk-dp__seg--a" /><i className="nk-dp__seg nk-dp__seg--b" /><b className="nk-dp__dot" /></div>

      {/* A · intake, then evidence */}
      <section className="nk-dp__p nk-dp__p--a" aria-label={phase >= 7 ? 'Evidence for the selected finding' : 'Intake'}>
        <header className="nk-dp__h"><span className="nk-dp__n">01</span>{phase >= 7 ? 'Evidence' : 'Your file'}<em>{phase >= 7 ? findings.find((f) => f.id === pick)!.sev : 'stays on this machine'}</em></header>
        {phase < 7 ? (
          <div className="nk-dp__zone">
            <div className="nk-dp__tray" aria-hidden="true">
              <svg viewBox="0 0 40 40"><path d="M20 6V24M12 16L20 24L28 16" /><path d="M6 26V33H34V26" /></svg>
              <span>Drop a dataset</span><small>CSV or Parquet · nothing is uploaded</small>
            </div>
            <div className="nk-dp__file">
              <span className="nk-dp__fold" aria-hidden="true" />
              <b>adult.csv</b><span className="nk-dp__meta">5.3 MB · {adult.task.toLowerCase()}</span>
              <span className="nk-dp__sha">sha256 <i>{adult.sha256.slice(0, 16)}…</i></span>
              <span className="nk-dp__count"><b>{Math.round(rows).toLocaleString()}</b> rows · 15 columns</span>
              <div className="nk-dp__rows" aria-hidden="true"><div className="nk-dp__rows-in">
                {[...adult.sampleRows, ...adult.sampleRows].map((r, i) => <span key={i}>{[r[0], r[1], r[3], r[6], r[12], r[14]].join('  ·  ')}</span>)}
              </div></div>
            </div>
            <span className="nk-dp__ripple" aria-hidden="true" />
          </div>
        ) : <div className="nk-dp__ev" key={pick}><View /></div>}
      </section>

      {/* B · checks */}
      <section className="nk-dp__p nk-dp__p--b" aria-label="Checks">
        <header className="nk-dp__h"><span className="nk-dp__n">02</span>Checks<em>{phase >= 3 ? '6 of 6' : 'waiting'}</em></header>
        <ol className="nk-dp__checks">
          {checks.map((c, k) => (
            <li key={c.t} className={`is-${c.found}`} style={{ ['--k' as string]: k }}>
              <i aria-hidden="true" />
              <span>{c.t}</span>
              <em>{c.r}</em>
            </li>
          ))}
        </ol>
        <p className="nk-dp__legend"><i className="is-no" /> clear <i className="is-yes" /> found</p>
      </section>

      {/* C · result */}
      <section className="nk-dp__p nk-dp__p--c" aria-label="Result" aria-live="polite">
        <header className="nk-dp__h"><span className="nk-dp__n">03</span>Result<em>{phase >= 6 ? `${adult.runtimeSeconds.toFixed(2)} s` : '…'}</em></header>
        <div className="nk-dp__score">
          <b className={capped ? 'is-capped' : ''}>{capped ? adult.finalScore.toFixed(1) : score.toFixed(2)}</b>
          <div>
            <span className={capped ? 'nk-dp__was' : ''}>{capped ? `average ${adult.evidenceScore}` : 'average of five measures'}</span>
            <em>{capped ? `${adult.band} · held at the cap` : ' '}</em>
          </div>
        </div>
        <div className="nk-dp__scale" aria-hidden="true">
          <i className="nk-dp__track" />
          <i className="nk-dp__ev89" style={{ left: `${sx(adult.evidenceScore)}%` }} />
          <i className="nk-dp__cap" style={{ left: `${sx(69)}%` }}><span>cap 69</span></i>
          <i className="nk-dp__fin" style={{ left: `${capped ? sx(69) : sx(score)}%` }} />
          <span className="nk-dp__s0">0</span><span className="nk-dp__s100">100</span>
        </div>
        <ul className="nk-dp__finds">
          {findings.map((f, k) => (
            <li key={f.id} style={{ ['--k' as string]: k }}>
              <button type="button" className={`is-${f.tone} ${pick === f.id && phase >= 7 ? 'is-on' : ''}`} aria-pressed={pick === f.id && phase >= 7} disabled={phase < 7} onClick={() => setPick(f.id)}>
                <i aria-hidden="true" /><span>{f.t}</span><em>{f.sev} · {f.eff}</em>
              </button>
            </li>
          ))}
        </ul>
        <div className="nk-dp__files">{['adult.html', 'adult.pdf', 'adult.json'].map((x, k) => <span key={x} style={{ ['--k' as string]: k }}>{x}</span>)}</div>
      </section>

      <div className="nk-dp__foot">
        <span>{phase >= 7 ? 'Pick a finding to see its rows.' : 'Reading adult.csv on this machine…'}</span>
        <button type="button" className="nk-dp__replay" onClick={() => { setPick('imbalance'); setRun((r) => r + 1); }}>↻ Replay</button>
      </div>
    </div>
  );
}
