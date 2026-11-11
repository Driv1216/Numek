import '@fontsource/ibm-plex-sans/300.css';
import '@fontsource/ibm-plex-sans/400.css';
import '@fontsource/ibm-plex-sans/500.css';
import '@fontsource/ibm-plex-mono/400.css';
import './cutaway.css';
import { useEffect, useRef, useState } from 'react';
import { adult, bike, company, finance, local } from '../../fixture';
import { reducedMotion } from '../../shell/motion';
import { href } from '../../shell/router';
import { Slab, Units, iso, partBox, type Part } from './iso';
import { SCENARIOS, whatIf } from './model';

export function Header({ here }: { here: 'landing' | 'app' | 'results' }) {
  return (
    <header className="cw-head">
      <a className="cw-wm" href={href('cutaway', 'landing')}>NUMEK</a>
      <nav aria-label="Primary">
        <a href={href('cutaway', 'landing')} aria-current={here === 'landing' ? 'page' : undefined}>DataTrust</a>
        <a href={href('cutaway', 'app')} aria-current={here === 'app' ? 'page' : undefined}>Runs</a>
        <a href={href('cutaway', 'results')} aria-current={here === 'results' ? 'page' : undefined}>Adult</a>
      </nav>
      <span className="cw-head__r">local · 127.0.0.1</span>
    </header>
  );
}

const box = (b: number[]) => b.map((v) => v.toFixed(1)).join(' ');
const smooth = (t: number) => t * t * (3 - 2 * t);

const chapters: { part: Part; k: string; title: string; body: string; card: [string, string][] }[] = [
  { part: 'all', k: 'Your data', title: 'Every strip is a column.', body: 'Adult: 48,842 rows deep, 15 columns wide. A strip’s height is how many distinct values it holds; a hollow section is the share of rows where it is empty.', card: [['Rows', '48,842'], ['Columns', '15'], ['Read in', `${adult.runtimeSeconds.toFixed(2)} s, locally`]] },
  { part: 'target', k: 'Target', title: 'One class fills three quarters of the target.', body: 'The target strip is split by class: 37,155 rows at ≤50K, 11,687 above. Target balance falls to 47.86 — at or below 50 is critical — and the final score is held at 69.', card: [['Majority', '76.07%'], ['Ratio', adult.ratio], ['Target balance', '47.86 · critical'], ['Effect', 'Can cap the score']] },
  { part: 'lift', k: 'Disagree', title: 'Two rows, lifted out: identical but for the answer.', body: `Rows ${adult.conflicts[0].rows.map((r) => r.toLocaleString()).join(' and ')} agree on all fourteen features and carry different labels. DataTrust found ${adult.conflicts.length} such groups covering 10 rows.`, card: [['Groups', String(adult.conflicts.length)], ['Rows', '10'], ['Features equal', '14 of 14'], ['Effect', 'Evidence only']] },
  { part: 'section', k: 'Fences', title: 'A section through hours_per_week.', body: `Quartiles at ${adult.hours.q1} and ${adult.hours.q3} put the 1.5 × IQR fences at ${adult.hours.lower} and ${adult.hours.upper}. ${adult.hours.outliers.toLocaleString()} rows sit outside — reported, never deleted.`, card: [['Below', adult.hours.below.toLocaleString()], ['Above', adult.hours.above.toLocaleString()], ['Share', '27.63%'], ['Effect', 'Changes a sub-score']] },
  { part: 'leak', k: 'Review', title: 'A name is a prompt, not proof.', body: 'marital_status has a status-like name, so DataTrust asks you to confirm when it becomes known. It is review only: leakage risk stays at 100 and no cap applies. Strong evidence — a column that rebuilds the target — would cap at 49.', card: [['Column', 'marital_status'], ['Leakage risk', '100'], ['Effect', 'Evidence only']] },
  { part: 'cap', k: 'What if', title: 'Change the split, watch the cap.', body: 'This recomputes the score with DataTrust’s published rules: balance = 100 − (majority − 50) ÷ 50 × 100; any sub-score ≤ 50 caps the result at 69. It is a calculation beside the drawing, not a feature.', card: [] },
];

export default function Landing() {
  const sec = useRef<HTMLElement>(null);
  const svg = useRef<SVGSVGElement>(null);
  const [step, setStep] = useState(0);
  const [maj, setMaj] = useState(adult.majorityBaseline);
  const w = whatIf(maj);

  useEffect(() => {
    const boxes = chapters.map((c) => partBox('adult', c.part === 'cap' ? 'all' : c.part));
    let raf = 0;
    const on = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const el = sec.current, s = svg.current; if (!el || !s) return;
        const r = el.getBoundingClientRect();
        const p = Math.min(1, Math.max(0, -r.top / Math.max(1, r.height - innerHeight)));
        const f = p * (chapters.length - 1), i = Math.min(chapters.length - 2, Math.floor(f));
        const raw = f - i, t = reducedMotion() ? (raw < 0.5 ? 0 : 1) : smooth(Math.min(1, Math.max(0, (raw - 0.35) / 0.65)));
        const a = boxes[i], b = boxes[i + 1];
        s.setAttribute('viewBox', box(a.map((v, k) => v + (b[k] - v) * t)));
        setStep(Math.min(chapters.length - 1, Math.round(i + t)));
      });
    };
    on();
    addEventListener('scroll', on, { passive: true });
    addEventListener('resize', on);
    return () => { removeEventListener('scroll', on); removeEventListener('resize', on); cancelAnimationFrame(raf); };
  }, []);

  const goto = (k: number) => {
    const el = sec.current; if (!el) return;
    const y = el.offsetTop + (k / (chapters.length - 1)) * (el.offsetHeight - innerHeight);
    scrollTo({ top: y + 2, behavior: reducedMotion() ? 'auto' : 'smooth' });
  };
  const c = chapters[step];
  const heroBox = partBox('adult', 'all');

  return (
    <div className="cw cw--landing">
      <Header here="landing" />
      <section className="cw-hero">
        <div className="cw-hero__t">
          <p className="cw-kicker">DataTrust by {company.name}</p>
          <h1>See inside your dataset.</h1>
          <p className="cw-hero__s">DataTrust reads a dataset on your machine and shows what it found. Here it is drawn: every strip is a real column of the public Adult dataset, every notch and split a real measurement.</p>
          <div className="cw-hero__cta"><a className="cw-btn" href={href('cutaway', 'results')}>Open the Adult cutaway</a><a href="#cw-tour" className="cw-link">Take the tour ↓</a></div>
        </div>
        <svg className="cw-svg cw-svg--hero" viewBox={box(heroBox)} role="img" aria-label="Isometric drawing of the Adult dataset: fifteen column strips on a base, the target strip split 76 to 24.">
          <g className="cw-assemble"><Slab run="adult" /></g>
        </svg>
      </section>

      <section id="cw-tour" ref={sec} className="cw-tour" style={{ height: `${chapters.length * 100 + 60}vh` }} aria-label="Guided tour of the Adult cutaway">
        <div className="cw-stage">
          <svg ref={svg} className="cw-svg cw-svg--stage" viewBox={box(heroBox)} role="img" aria-label={`Cutaway, ${c.k}`}>
            <Slab run="adult" focus={c.part} lift={c.part === 'lift' || step > 2} section={c.part === 'section'} split={c.part === 'cap' ? maj / 100 : undefined} />
          </svg>
          <article className="cw-card" key={step} aria-live="polite">
            <span className="cw-card__k">{String(step + 1).padStart(2, '0')} · {c.k}</span>
            <h2>{c.title}</h2>
            <p>{c.body}</p>
            {c.card.length > 0 && <dl>{c.card.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>}
            {c.part === 'cap' && (
              <div className="cw-whatif">
                <div className="cw-seg" role="radiogroup" aria-label="Target majority share">
                  {SCENARIOS.map(([l, v]) => <button key={l} type="button" role="radio" aria-checked={maj === v} onClick={() => setMaj(v)}>{l}</button>)}
                </div>
                <dl>
                  <div><dt>Majority</dt><dd>{maj.toFixed(2)}%</dd></div>
                  <div><dt>Target balance</dt><dd className={w.balance <= 50 ? 'is-red' : ''}>{w.balance.toFixed(2)}</dd></div>
                  <div><dt>Evidence (mean of five)</dt><dd>{w.evidence.toFixed(2)}</dd></div>
                  <div><dt>Final</dt><dd className="cw-final">{w.final.toFixed(w.capped ? 1 : 2)} · {w.band}{w.capped ? ' · capped' : ''}</dd></div>
                </dl>
              </div>
            )}
          </article>
          <nav className="cw-index" aria-label="Chapters">
            {chapters.map((ch, k) => <button key={ch.k} type="button" className={k === step ? 'is-on' : ''} onClick={() => goto(k)}>{ch.k}</button>)}
          </nav>
        </div>
      </section>

      <section className="cw-kinds">
        <h2>Every kind of data is drawn in its own units.</h2>
        <div className="cw-kinds__g">
          {[
            { t: 'Tables', s: 'Adult · classification · scored', draw: <Slab run="adult" labels={false} />, run: 'adult' },
            { t: 'Outcomes', s: `Bike hourly · ${bike.relationship} · no score defined`, draw: <Slab run="bike" focus="relation" labels={false} />, run: 'bike' },
            { t: 'Text', s: 'SMS · 5,574 records · near-duplicate candidates', draw: <Units run="sms" />, run: 'sms' },
            { t: 'Images', s: 'COCO subset · 128 images · 875 objects', draw: <Units run="coco" />, run: 'coco' },
            { t: 'Records ↔ documents', s: `${finance.records} records · ${finance.documents} PDFs · ${finance.agreements} agree`, draw: <Units run="finance" />, run: 'finance' },
            { t: 'Time', s: 'Exact clocks, declared availability, revisions (schematic)', draw: <TimeSketch />, run: 'time' },
          ].map((k) => (
            <figure key={k.t} className="cw-kind">
              <svg className="cw-svg" viewBox={k.run === 'adult' || k.run === 'bike' ? box(partBox(k.run, 'all')) : k.run === 'time' ? '-20 -60 260 160' : '-80 -90 330 230'} aria-hidden="true">{k.draw}</svg>
              <figcaption><b>{k.t}</b><span>{k.s}</span></figcaption>
            </figure>
          ))}
        </div>
      </section>

      <section className="cw-run">
        <div><h2>Draw your own.</h2><p>Two commands. Nothing leaves the machine.</p></div>
        <pre><span>$</span> {local.commands[0]}{'\n'}<em>{local.cliOutput.join('\n')}</em>{'\n\n'}<span>$</span> {local.commands[1]}{'\n'}<em>→ http://127.0.0.1:8000/</em></pre>
      </section>

      <footer className="cw-foot">
        <span className="cw-wm">NUMEK</span>
        <p>{company.line}. DataTrust is the product. {company.direction}</p>
        <p className="cw-dim">{adult.source} · Findings support human review; they are not certification.</p>
      </footer>
    </div>
  );
}

/** Time is not among the seven local runs, so it is drawn as a labelled schematic. */
function TimeSketch() {
  const ev = [0, 26, 48, 70, 100, 128, 150, 176, 200];
  const cut = 110;
  return (
    <g className="cw-slab">
      {ev.map((x, i) => { const [a, b] = iso(x, 0, 0); return <rect key={i} x={a - 4} y={b - (x < cut ? 18 : 10)} width={8} height={x < cut ? 18 : 10} className={x < cut ? 'cw-ev' : 'cw-ev cw-ev--late'} />; })}
      {(() => { const [a, b] = iso(cut, 0, 0); return <g className="cw-label"><line x1={a} y1={b + 10} x2={a} y2={b - 50} /><text x={a + 3} y={b - 52}>PREDICTION TIME · SCHEMATIC</text></g>; })()}
    </g>
  );
}
