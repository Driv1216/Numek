import '@fontsource-variable/archivo/standard.css';
import '@fontsource/ibm-plex-mono/400.css';
import '@fontsource/ibm-plex-mono/500.css';
import './evidence.css';
import { useRef, type ReactNode } from 'react';
import { adult, local, representations } from '../../fixture';
import cg from '../../fixture/cg1.generated.json';
import { reducedMotion, useScrollProgress } from '../../shell/motion';
import { FloatMark, Mark, Wordmark, useRegion, useSequence, useSnap } from './mark';

// Real figures. Data: the Adult audit. Model: ConfidenceGuard CG1's recorded German Credit evaluation.
const M = cg.measurements;
const caught = Math.round(M.recall.value * M.recall.denominator); // 13
const missed = cg.bad - caught; // 47
const correct = Math.round(M.accuracy.value * M.accuracy.denominator); // 144
const goodKept = Math.round(M.specificity.value * M.specificity.denominator); // 131
const pct = (v: number) => (v * 100).toFixed(1);
const err = cg.most_confident_error;
const pair = adult.conflicts[0];
const balance = adult.subScores.find((s) => s.value <= 50)!;
const f = (n: number) => n.toLocaleString('en-US');

const go = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: reducedMotion() ? 'auto' : 'smooth', block: 'start' });

export function Header() {
  return (
    <header className="em-head">
      <button type="button" className="em-head__wm" onClick={() => scrollTo({ top: 0, behavior: reducedMotion() ? 'auto' : 'smooth' })} aria-label="NUMEK, back to top"><Wordmark /></button>
      <nav aria-label="Sections">
        {[['em-mission', 'Mission'], ['em-products', 'Products'], ['em-datatrust', 'DataTrust'], ['em-principles', 'Principles']].map(([id, l]) => <button key={id} type="button" onClick={() => go(id)}>{l}</button>)}
      </nav>
      <button type="button" className="em-btn em-btn--sm" onClick={() => go('em-start')}>Run DataTrust</button>
    </header>
  );
}

/* ——— Hero ——— */

function Moment({ k, product, status, children, caption }: { k: string; product: string; status: string; children: ReactNode; caption: ReactNode }) {
  return (
    <figure className="em-spec">
      <figcaption className="em-spec__h"><span className="em-spec__k">{k}</span><span className="em-spec__p">{product} · <em>{status}</em></span></figcaption>
      {children}
      <p className="em-spec__c">{caption}</p>
    </figure>
  );
}

function Hero() {
  const k = useSequence(4, 500, 700);
  const feat = pair.features;
  return (
    <section className="em-hero" aria-labelledby="em-h1">
      <p className="em-kicker">NUMEK · AI reliability verification</p>
      <h1 id="em-h1" className="em-h1">AI makes real decisions.<br />NUMEK shows <Mark on={k >= 1} className="em-h1__m">the evidence.</Mark></h1>
      <div className="em-path">
        <Moment k="Before training · the data" product="DataTrust" status="available" caption={<>Two people identical in all fourteen features, with <strong>different answers</strong>. Adult, rows {f(pair.rows[0])} and {f(pair.rows[1])}.</>}>
          <Mark block n="01" on={k >= 2} note="same features · different label">
            <div className="em-rows" role="table" aria-label="Two Adult rows">
              {pair.rows.map((r, i) => (
                <div role="row" key={r} className="em-rows__r">
                  <span className="em-rows__n">{f(r)}</span>
                  <span className="em-rows__v">{i === 0 ? `${feat.age} · ${feat.education} · ${feat.occupation} · ${feat.hours_per_week} h` : '〃 · 〃 · 〃 · 〃'}</span>
                  <span className="em-rows__l">{pair.labels[i]}</span>
                </div>
              ))}
            </div>
          </Mark>
        </Moment>
        <Moment k="During deployment · the model" product="ConfidenceGuard" status="in development" caption={<>The model was <strong>{Math.round(err.p * 100)}% sure</strong>, and wrong. German Credit, applicant {err.id}, one of {cg.n} held-out predictions in CG1’s recorded evaluation.</>}>
          <Mark block n="02" on={k >= 3} note="confident · wrong">
            <dl className="em-pred">
              <div><dt>prediction</dt><dd>{err.prediction}</dd></div>
              <div><dt>probability</dt><dd>{err.p.toFixed(2)}<i style={{ width: `${err.p * 100}%` }} /></dd></div>
              <div><dt>outcome</dt><dd className="is-x">{err.outcome}</dd></div>
            </dl>
          </Mark>
        </Moment>
        <Moment k="After generation · the output" product="HallucinationGuard" status="research direction" caption={<>A claim with nothing behind it in the source. <span className="em-ill">Illustration</span></>}>
          <Mark block n="03" on={k >= 4} note="no supporting evidence">
            <p className="em-gen">“The application was declined because the file shows <u>two missed payments</u> in the last year.”</p>
          </Mark>
        </Moment>
      </div>
    </section>
  );
}

/* ——— Mission ——— */

function Mission() {
  const [ref, on] = useSnap<HTMLParagraphElement>('0px 0px -35% 0px');
  return (
    <section id="em-mission" className="em-mission">
      <span className="em-label">Mission</span>
      <p ref={ref} className="em-statement">
        Teams now use AI to decide who gets credit, cover and work. Before anyone trusts one of those decisions, someone has to see the evidence: about the{' '}
        <Mark on={on} className="em-w em-w--data">data</Mark> it learned from, the{' '}
        <Mark on={on} className="em-w em-w--model">model</Mark> that makes it, and the{' '}
        <Mark on={on} className="em-w em-w--output">output</Mark> it produces. NUMEK verifies all three, and shows its working.
      </p>
    </section>
  );
}

/* ——— The problem: averages hide weaknesses ——— */

function Bar({ label, value, sub, mean, marked, n, note, on }: { label: string; value: number; sub?: string; mean?: number; marked?: boolean; n?: string; note?: string; on: boolean }) {
  const row = (
    <div className={`em-bar ${marked ? 'is-x' : ''}`}>
      <span className="em-bar__l">{label}{sub && <small>{sub}</small>}</span>
      <span className="em-bar__t"><i style={{ width: on ? `${value}%` : 0 }} />{mean != null && <b style={{ left: `${mean}%` }} />}</span>
      <span className="em-bar__v">{value}</span>
    </div>
  );
  return marked ? <Mark block n={n} note={note} on={on}>{row}</Mark> : row;
}

function Problem() {
  const [a, onA] = useSnap<HTMLDivElement>();
  const [b, onB] = useSnap<HTMLDivElement>();
  return (
    <section className="em-problem" aria-labelledby="em-problem-h">
      <div className="em-sec-h">
        <span className="em-label">Why it matters</span>
        <h2 id="em-problem-h" className="em-h2">A healthy number can hide a critical weakness.</h2>
        <p className="em-lede">Both results below look fine at a glance. In both, one measure says otherwise. NUMEK is built to put that measure in front of you.</p>
      </div>
      <div className="em-proofs">
        <article ref={a} className="em-proof">
          <header><span className="em-proof__k">The data · Adult · DataTrust</span><b className="em-proof__big">{adult.evidenceScore}</b><span>the average of five measures</span></header>
          <div className="em-bars">
            {adult.subScores.map((s) => <Bar key={s.key} label={s.label} value={s.value} mean={adult.evidenceScore} marked={s === balance} n="01" note="critical · at or below 50" on={onA} />)}
          </div>
          <p className="em-bars__lg"><i /> average {adult.evidenceScore}</p>
          <footer><b>Final score {adult.finalScore.toFixed(1)}, {adult.band}.</b> A guardrail holds the score at 69 when any measure is critical, so the average cannot hide it.</footer>
        </article>
        <article ref={b} className="em-proof">
          <header><span className="em-proof__k">The model · German Credit · ConfidenceGuard CG1</span><b className="em-proof__big">{Math.round(M.accuracy.value * 100)}%</b><span>accuracy on {cg.n} held-out applications</span></header>
          <div className="em-bars">
            <Bar label="Accuracy" sub={`${correct} of ${cg.n}`} value={+pct(M.accuracy.value)} on={onB} />
            <Bar label="Good credit kept" sub={`${goodKept} of ${M.specificity.denominator}`} value={+pct(M.specificity.value)} on={onB} />
            <Bar label="Bad credit caught" sub={`${caught} of ${cg.bad}`} value={+pct(M.recall.value)} marked n="02" note={`${missed} of ${cg.bad} missed`} on={onB} />
          </div>
          <footer><b>No single score.</b> CG1 reports each measure with the population behind it, so a strong headline cannot cover a weak one.</footer>
        </article>
      </div>
    </section>
  );
}

/* ——— Products: three moments ——— */

const corners = (x: number, y: number, w: number, h: number, a: number) =>
  `M${x} ${y + a}V${y}H${x + a} M${x + w - a} ${y}H${x + w}V${y + a} M${x} ${y + h - a}V${y + h}H${x + a} M${x + w - a} ${y + h}H${x + w}V${y + h - a}`;

function DataDrawing() {
  const C = 15, R = 9, s = 18;
  return (
    <svg viewBox="0 0 300 200" className="em-draw" role="img" aria-label="A table drawn as cells; two rows are inked and marked">
      {Array.from({ length: R * C }, (_, i) => { const r = Math.floor(i / C), c = i % C; const hit = r === 4 || r === 5; return <rect key={i} x={15 + c * s} y={22 + r * s} width={s - 4} height={s - 4} className={hit ? (c === C - 1 ? 'em-d-sig' : 'em-d-ink') : 'em-d-ghost'} />; })}
      <path d={corners(9, 22 + 4 * s - 6, C * s + 8, 2 * s + 8, 10)} className="em-d-mark" />
    </svg>
  );
}
function ModelDrawing() {
  const C = 12, s = 21;
  return (
    <svg viewBox="0 0 300 200" className="em-draw" role="img" aria-label={`${cg.bad} bad-credit applicants: ${caught} caught by the model, ${missed} missed and marked`}>
      {Array.from({ length: cg.bad }, (_, i) => { const r = Math.floor(i / C), c = i % C; return <circle key={i} cx={34 + c * s} cy={46 + r * s} r={6.5} className={i < caught ? 'em-d-ink' : 'em-d-hollow'} />; })}
      <path d={corners(20, 46 + s - 13, C * s + 7, 4 * s - 8, 10)} className="em-d-mark" />
      <text x={20} y={22} className="em-d-t">{caught} CAUGHT · {missed} MISSED</text>
    </svg>
  );
}
function OutputDrawing() {
  const lines = [[0.92], [0.86], [0.3, 0.34, 0.2], [0.78], [0.55]];
  return (
    <svg viewBox="0 0 300 200" className="em-draw" role="img" aria-label="Lines of generated text; one phrase is inked and marked. Schematic.">
      {lines.map((segs, r) => { let x = 24; return segs.map((w, j) => { const el = <rect key={`${r}-${j}`} x={x} y={36 + r * 30} width={w * 252 - 6} height={10} className={r === 2 && j === 1 ? 'em-d-ink' : 'em-d-ghost'} />; x += w * 252; return el; }); })}
      <path d={corners(24 + 0.3 * 252 - 9, 36 + 2 * 30 - 9, 0.34 * 252 + 6, 28, 8)} className="em-d-mark" />
      <text x={24} y={190} className="em-d-t">SCHEMATIC</text>
    </svg>
  );
}

const products = [
  { id: 'data', k: '01 · Before training', name: 'DataTrust', status: 'Available', tone: 'on', draw: <DataDrawing />,
    body: 'Dataset reliability for training, fine-tuning and evaluation. DataTrust reads tables, outcomes, time series, text, images and records against their documents, on your machine.',
    facts: ['Transparent sub-scores and guardrails for classification', 'Evidence-only findings everywhere else; no invented scores', 'HTML, PDF and strict JSON reports'] },
  { id: 'model', k: '02 · During deployment', name: 'ConfidenceGuard', status: 'In development · CG1 implemented, awaiting review', tone: 'dev', draw: <ModelDrawing />,
    body: 'Model reliability from the predictions you already have. CG1 evaluates supplied binary, multiclass and regression predictions against recorded outcomes. It never fits or runs your model.',
    facts: ['Performance with the population behind every measure', 'Calibration, high-confidence errors, cohorts, paired comparisons', 'Exact local reports and conservative shareable ones'] },
  { id: 'output', k: '03 · After generation', name: 'HallucinationGuard', status: 'Research direction', tone: 'res', draw: <OutputDrawing />,
    body: 'Grounding for generated outputs: whether an answer is supported by its sources, what it cites, and where it contradicts them. Not yet a product.',
    facts: ['Supporting evidence for claims', 'Citation quality and contradictions', 'Shown here as direction only'] },
];

function Products() {
  const [ref, on] = useSnap<HTMLDivElement>('0px 0px -20% 0px');
  return (
    <section id="em-products" className="em-products" aria-labelledby="em-products-h">
      <div className="em-sec-h">
        <span className="em-label">Products</span>
        <h2 id="em-products-h" className="em-h2">Three moments where an AI decision can go wrong. One standard of evidence.</h2>
      </div>
      <div ref={ref} className={`em-tiles ${on ? 'is-on' : ''}`}>
        {products.map((p, i) => (
          <article key={p.id} className={`em-tile em-tile--${p.id}`} style={{ transitionDelay: `${i * 120}ms` }}>
            <div className="em-tile__field">{p.draw}</div>
            <div className="em-tile__b">
              <span className="em-tile__k">{p.k}</span>
              <h3 className="em-tile__n">{p.name}</h3>
              <span className={`em-status em-status--${p.tone}`}><i />{p.status}</span>
              <p>{p.body}</p>
              <ul>{p.facts.map((x) => <li key={x}>{x}</li>)}</ul>
              {p.id === 'data' && <button type="button" className="em-link" onClick={() => go('em-datatrust')}>DataTrust in depth ↓</button>}
              {p.id === 'model' && <code className="em-code">confidenceguard evaluate --spec evaluation.json</code>}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

/* ——— DataTrust in depth: one mark travels across the real table ——— */

const cols = [
  { key: 'age', label: 'age', i: 0, hide: true }, { key: 'workclass', label: 'workclass', i: 1, hide: true },
  { key: 'marital_status', label: 'marital_status', i: 5, tag: 'm' }, { key: 'occupation', label: 'occupation', i: 6, hide: true }, { key: 'hours_per_week', label: 'hours_per_week', i: 12, tag: 'h' },
  { key: 'annual_income_over_50k', label: 'income', i: 14, tag: 't' },
];
const steps = [
  { sel: '[data-c="1"]', note: 'same 14 features · different label', f: adult.findings[0], fig: '5 groups · 10 rows' },
  { sel: '[data-k="t"]', note: `${adult.majorityBaseline}% ≤50K`, f: adult.findings[1], fig: `balance ${balance.value} → score held at 69` },
  { sel: '[data-k="h"]', note: `fences ${adult.hours.lower} – ${adult.hours.upper}`, f: adult.findings[2], fig: `${f(adult.hours.below + adult.hours.above)} rows outside` },
  { sel: '[data-k="m"]', note: 'review only', f: adult.findings[3], fig: 'name prompt, no score change' },
];
const outside = (v: string) => +v < adult.hours.lower || +v > adult.hours.upper;

function DataTrust() {
  const [sec, p] = useScrollProgress<HTMLElement>('pinned');
  const box = useRef<HTMLDivElement>(null);
  const k = Math.min(steps.length - 1, Math.floor(p * steps.length * 0.999));
  const st = steps[k];
  const rect = useRegion(box, st.sel, 5);
  const featVals = adult.header.map((h) => String((pair.features as Record<string, string | number>)[h] ?? ''));
  const table: { n: number | null; v: string[]; c?: boolean }[] = [
    ...adult.sampleRows.slice(0, 9).map((v, i) => ({ n: i + 1, v })),
    { n: null, v: [] },
    ...pair.rows.map((n, i) => ({ n, v: [...featVals.slice(0, 14), pair.labels[i]], c: true })),
  ];
  return (
    <section id="em-datatrust" ref={sec} className="em-dt" aria-labelledby="em-dt-h" style={{ height: `${steps.length * 85 + 40}vh` }}>
      <div className="em-dt__pin">
        <div className="em-dt__top">
          <span className="em-label">DataTrust, today</span>
          <h2 id="em-dt-h" className="em-h2 em-h2--s">Every finding is marked on the evidence it came from.</h2>
        </div>
        <div className="em-dt__grid">
          <div ref={box} className="em-sheet" aria-label={`adult.csv, ${f(adult.rows)} rows × ${adult.header.length} columns, excerpt`}>
            <div className="em-sheet__cap"><span>adult.csv</span><span>{f(adult.rows)} rows · {cols.length} of {adult.header.length} columns shown</span></div>
            <table>
              <thead><tr><th className="em-sheet__n">row</th>{cols.map((c) => <th key={c.key} data-k={c.tag} className={c.hide ? 'em-hide' : ''}>{c.label}</th>)}</tr></thead>
              <tbody>
                {table.map((r, j) => r.n == null ? (
                  <tr key={`g${j}`} className="em-sheet__gap"><td colSpan={cols.length + 1}>⋮ {f(adult.rows - 11)} rows</td></tr>
                ) : (
                  <tr key={r.n} data-c={r.c ? '1' : undefined} className={`${r.c && k === 0 ? 'is-hot' : ''} ${!r.c && r.n > 5 ? 'em-mob-hide' : ''}`}>
                    <td className="em-sheet__n">{f(r.n)}</td>
                    {cols.map((c) => <td key={c.key} data-k={c.tag} className={`${c.hide ? 'em-hide' : ''} ${c.tag === 'h' && k === 2 && outside(r.v[c.i]) ? 'is-out' : ''} ${c.tag === 't' && (k === 1 || (k === 0 && r.c)) ? 'is-lab' : ''}`}>{r.v[c.i]}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
            <FloatMark rect={rect} n={String(k + 1).padStart(2, '0')} note={st.note} />
          </div>
          <div className="em-dt__copy" aria-live="polite">
            <div className="em-dt__count">{steps.map((_, i) => <i key={i} className={i === k ? 'is-on' : i < k ? 'is-past' : ''} />)}<span>{String(k + 1).padStart(2, '0')} / {String(steps.length).padStart(2, '0')}</span></div>
            <div key={k} className="em-dt__f">
              <span className={`em-sev em-sev--${st.f.severity.toLowerCase()}`}>{st.f.severity}</span>
              <span className="em-eff">{st.f.scoreEffect.startsWith('Evidence only') ? 'Evidence only' : 'Changes the score'}</span>
              <h3>{st.f.title}</h3>
              <p className="em-dt__fig">{st.fig}</p>
              <p>{st.f.finding}</p>
              <p className="em-dim">{st.f.review}</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function Reads() {
  return (
    <section className="em-reads" aria-labelledby="em-reads-h">
      <h2 id="em-reads-h" className="em-h3">DataTrust reads six kinds of data, and marks the evidence in each.</h2>
      <ol className="em-reads__l">
        {representations.map((r, i) => <li key={r.id}><span className="em-reads__n">{String(i + 1).padStart(2, '0')}</span><b>{r.name}</b><span>{r.example}</span><small>{r.checks[0]}</small></li>)}
      </ol>
    </section>
  );
}

/* ——— Two readings ——— */

function Readings() {
  const [ref, on] = useSnap<HTMLDivElement>();
  const c = adult.findings[0];
  return (
    <section className="em-readings" aria-labelledby="em-readings-h">
      <div className="em-sec-h">
        <span className="em-label">One analysis, two readers</span>
        <h2 id="em-readings-h" className="em-h2">The engineer gets the evidence. The decision-maker gets the meaning.</h2>
      </div>
      <div ref={ref} className="em-two">
        <div className="em-term" aria-label="Command line and JSON">
          <span className="em-two__k">For the ML engineer · terminal and adult.json</span>
          <pre><span className="em-term__p">$</span> {local.commands[0]}{'\n'}<span className="em-term__o">{local.cliOutput.join('\n')}</span></pre>
          <pre className="em-term__json">{'{\n'}  <Mark n="01" on={on} tone="ink">{`"code": "${c.code}"`}</Mark>,{'\n'}  "severity": "{c.severity}",{'\n'}  "evidence": "{c.evidence}",{'\n'}  "score_effect": "Evidence only; …"{'\n}'}</pre>
          <small>One finding as written to the JSON report (excerpt).</small>
        </div>
        <div className="em-page" aria-label="Decision summary page">
          <span className="em-two__k">For the risk lead · report, decision summary</span>
          <div className="em-page__sheet">
            <span className="em-page__h">Decision Summary · adult.csv</span>
            <b className="em-page__score">{adult.finalScore.toFixed(1)} <small>{adult.band} risk</small></b>
            <p>Evidence score {adult.evidenceScore} → final score {adult.finalScore.toFixed(1)} after applied guardrails: the target balance sub-score is {balance.value}, indicating a critical weakness.</p>
            <Mark block n="01" on={on} className="em-page__f"><p>{c.finding} {c.evidence}</p></Mark>
            <p className="em-page__next">{adult.nextAction}</p>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ——— Principles ——— */

const principles = [
  ['Evidence before verdicts.', 'Every finding names the rows, columns, predictions or pages it came from, so it can be checked, not just believed.'],
  ['A report, not a certificate.', 'NUMEK shows what was found and what to review. It does not certify data, models or compliance.'],
  ['Your data stays where it is.', 'Analysis runs on your machine. The browser interface binds to 127.0.0.1, and nothing is uploaded.'],
  ['A score only where it means something.', 'DataTrust scores classification datasets, with every guardrail explained. Elsewhere, and in ConfidenceGuard, there is evidence and no universal score.'],
];
function Principles() {
  return (
    <section id="em-principles" className="em-principles" aria-labelledby="em-pr-h">
      <span className="em-label em-label--inv">Principles</span>
      <h2 id="em-pr-h" className="em-sr">Principles</h2>
      <ol>
        {principles.map(([t, b], i) => <Principle key={t} n={String(i + 1).padStart(2, '0')} t={t} b={b} />)}
      </ol>
    </section>
  );
}
function Principle({ n, t, b }: { n: string; t: string; b: string }) {
  const [ref, on] = useSnap<HTMLLIElement>('0px 0px -25% 0px');
  return <li ref={ref}><Mark n={n} on={on} tone="paper"><span className="em-pr__t">{t}</span></Mark><p>{b}</p></li>;
}

/* ——— Start ——— */

function Start() {
  return (
    <section id="em-start" className="em-start" aria-labelledby="em-start-h">
      <div>
        <span className="em-label">Start with the data</span>
        <h2 id="em-start-h" className="em-h2">Run DataTrust on your own data, on your own machine.</h2>
        <ul className="em-facts">{local.facts.map((x) => <li key={x.label}><b>{x.value}</b><span>{x.label}</span></li>)}</ul>
      </div>
      <div className="em-cmds">
        {[[local.commands[0], 'Audit a file: HTML, PDF and JSON'], [local.commands[1], 'Or open the guided interface at 127.0.0.1:8000']].map(([c, l]) => <div key={c}><span>{l}</span><code><i>$</i> {c}</code></div>)}
      </div>
    </section>
  );
}

export function Footer() {
  return (
    <footer className="em-foot">
      <Wordmark big />
      <div className="em-foot__cols">
        <p>NUMEK · AI reliability verification</p>
        <p>DataTrust · available<br />ConfidenceGuard · in development (CG1 implemented, awaiting review)<br />HallucinationGuard · research direction</p>
        <p>Reports support human review. They are not certification, and do not establish compliance, fairness or safety.</p>
      </div>
    </footer>
  );
}

export default function Landing() {
  return (
    <div className="em">
      <Header />
      <main>
        <Hero />
        <Mission />
        <Problem />
        <Products />
        <DataTrust />
        <Reads />
        <Readings />
        <Principles />
        <Start />
      </main>
      <Footer />
    </div>
  );
}
