import '@fontsource-variable/geist';
import '@fontsource-variable/geist-mono';
import './camera.css';
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { adult, company, local, representations } from '../../fixture';
import { reducedMotion } from '../../shell/motion';
import { href } from '../../shell/router';
import { Icon, Overview, Sidebar, Topbar, Window } from './ui';

export function Nav() {
  return (
    <header className="cm-nav">
      <a className="cm-nav__wm" href={href('camera', 'landing')}>NUMEK</a>
      <nav aria-label="Primary">
        <a href={href('camera', 'landing')}>DataTrust</a>
        <a href={href('camera', 'app')}>Runs</a>
        <a href={href('camera', 'results')}>Adult result</a>
      </nav>
      <a className="cm-nav__cta" href="#cm-run">Run locally</a>
    </header>
  );
}

interface Stop { sel: string; k: string; t: string; b: string }
const stops: Stop[] = [
  { sel: 'all', k: 'DataTrust', t: 'This is the whole result.', b: '`datatrust ui` opens it in your browser at 127.0.0.1:8000. The file never leaves the machine.' },
  { sel: 'score', k: 'Score', t: 'One number, with its reason attached.', b: `Evidence ${adult.evidenceScore}. Target balance is ${adult.subScores[2].value} — critical — so the result is held at ${adult.finalScore.toFixed(1)}, ${adult.band}.` },
  { sel: 'subs', k: 'Sub-scores', t: 'Five measures, averaged in the open.', b: 'Completeness, uniqueness, target balance, feature usability and leakage risk. Any one at or below 50 caps the score at 69.' },
  { sel: 'findings', k: 'Findings', t: 'Four findings. Two of them changed the score.', b: 'Each says what was seen, what it may mean, what to review — and whether it moved a number.' },
  { sel: 'conflict', k: 'Evidence', t: 'Down to the row.', b: `Rows ${adult.conflicts[0].rows.map((r) => r.toLocaleString()).join(' and ')} agree on all fourteen features and disagree on the label. Shown, not resolved.` },
  { sel: 'hours', k: 'Outliers', t: 'Fences you can check.', b: `Quartiles ${adult.hours.q1} and ${adult.hours.q3} put the fences at ${adult.hours.lower} and ${adult.hours.upper}. ${adult.hours.outliers.toLocaleString()} rows sit outside. Nothing is deleted.` },
  { sel: 'columns', k: 'Columns', t: 'Every column, read from the file.', b: `Distributions, gaps, cardinality and IQR outliers — ${adult.rows.toLocaleString()} rows in ${adult.runtimeSeconds.toFixed(2)} seconds, locally.` },
  { sel: 'export', k: 'Reports', t: 'Three reports, one body of evidence.', b: 'Canonical HTML in eight topics, a PDF with decision pages and an appendix, and strict JSON with every computed value.' },
  { sel: 'side', k: 'Runs', t: 'Not only tables.', b: 'Regression, text, images and record-to-document runs report their evidence too — without a universal score, because none is defined.' },
];

type Cam = { cx: number; cy: number; s: number };
const smooth = (t: number) => t * t * (3 - 2 * t);

export default function Landing() {
  const sec = useRef<HTMLElement>(null);
  const stage = useRef<HTMLDivElement>(null);
  const tilt = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLDivElement>(null);
  const cams = useRef<Cam[]>([]);
  const [active, setActive] = useState(0);
  const [intro, setIntro] = useState(1);

  // Measure each stop in canvas space, untransformed, and turn it into a camera.
  useLayoutEffect(() => {
    const measure = () => {
      const c = canvas.current!, st = stage.current!;
      // Measure flat: no camera transform and no hero tilt, or the perspective skews every rect.
      const prev = c.style.transform, prevTilt = tilt.current!.style.transform;
      c.style.transform = 'none'; tilt.current!.style.transform = 'none';
      const base = c.getBoundingClientRect();
      const VW = st.clientWidth, VH = st.clientHeight;
      const narrow = VW < 760;
      cams.current = stops.map((s) => {
        if (s.sel === 'all') return { cx: base.width / 2, cy: base.height / 2, s: Math.min((VW * 0.92) / base.width, (VH * (narrow ? 0.5 : 0.74)) / base.height) };
        const el = c.querySelector(`[data-cam="${s.sel}"]`)!.getBoundingClientRect();
        // The export stop also frames the menu that opens beneath the button.
        // Columns: frame the readable left half of the table.
        const r = s.sel === 'export' ? { left: el.right - 400, top: el.top, width: 400, height: 330 }
          : s.sel === 'columns' ? { left: el.left, top: el.top, width: Math.min(el.width, 820), height: el.height } : el;
        const pad = 24;
        const w = r.width + pad * 2, h = r.height + pad * 2;
        return { cx: r.left - base.left + r.width / 2, cy: r.top - base.top + r.height / 2, s: Math.min((VW * (narrow ? 0.96 : 0.62)) / w, (VH * (narrow ? 0.5 : 0.7)) / h, 2.2) };
      });
      c.style.transform = prev; tilt.current!.style.transform = prevTilt;
      apply();
    };
    const apply = () => {
      const el = sec.current, c = canvas.current, st = stage.current;
      if (!el || !c || !st || !cams.current.length) return;
      const r = el.getBoundingClientRect();
      const p = Math.min(1, Math.max(0, -r.top / Math.max(1, r.height - innerHeight)));
      // First 8% of the section: the tilted window settles flat.
      const settle = Math.min(1, p / 0.08);
      const f = Math.max(0, (p - 0.08) / 0.92) * (stops.length - 1);
      const i = Math.min(stops.length - 2, Math.floor(f));
      const raw = f - i;
      const rm = reducedMotion();
      const t = rm ? (raw < 0.5 ? 0 : 1) : smooth(Math.min(1, Math.max(0, (raw - 0.3) / 0.7)));
      const a = cams.current[i], b = cams.current[i + 1];
      const cam = { cx: a.cx + (b.cx - a.cx) * t, cy: a.cy + (b.cy - a.cy) * t, s: Math.exp(Math.log(a.s) + (Math.log(b.s) - Math.log(a.s)) * t) };
      const VW = st.clientWidth, VH = st.clientHeight;
      // Close-ups sit right of centre so the caption has the left; the overview is centred.
      const fxOf = (k: number) => (stops[k].sel === 'all' || VW < 760 ? 0.5 : 0.62);
      const fx = fxOf(i) + (fxOf(i + 1) - fxOf(i)) * t;
      const focusY = VW < 760 ? 0.36 : 0.46;
      c.style.transform = `translate(${VW * fx - cam.cx * cam.s}px, ${VH * focusY - cam.cy * cam.s}px) scale(${cam.s})`;
      if (tilt.current) tilt.current.style.transform = rm ? `translateY(${(1 - settle) * 50}vh)` : `translateY(${(1 - smooth(settle)) * 50}vh) rotateX(${(1 - smooth(settle)) * 22}deg) scale(${0.94 + 0.06 * smooth(settle)})`;
      setIntro(1 - settle);
      setActive(p < 0.08 ? -1 : Math.min(stops.length - 1, Math.round(i + t)));
    };
    measure();
    let raf = 0;
    const on = () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(apply); };
    const ro = new ResizeObserver(() => measure());
    ro.observe(stage.current!);
    addEventListener('scroll', on, { passive: true });
    return () => { ro.disconnect(); removeEventListener('scroll', on); cancelAnimationFrame(raf); };
  }, []);

  // Light the element the camera is looking at; dim the rest.
  useEffect(() => {
    const c = canvas.current; if (!c) return;
    const sel = active >= 0 ? stops[active].sel : 'all';
    c.classList.toggle('is-focus', sel !== 'all');
    c.querySelectorAll('[data-cam]').forEach((n) => n.classList.toggle('is-lit', n.getAttribute('data-cam') === sel));
  }, [active]);

  return (
    <div className="cm cm--landing">
      <Nav />
      <section ref={sec} className="cm-tour" style={{ height: `${stops.length * 110 + 120}vh` }} aria-label="Product tour">
        <div ref={stage} className="cm-stage">
          <div className="cm-hero" style={{ opacity: intro, transform: `translateY(${(1 - intro) * -40}px)`, visibility: intro < 0.02 ? 'hidden' : 'visible' }}>
            <p className="cm-kicker">DataTrust by {company.name}</p>
            <h1>See exactly why a dataset<br />scores what it does.</h1>
            <p className="cm-hero__sub">{company.productLine} Every finding, every sub-score and every row of evidence behind the result — on your own machine.</p>
            <div className="cm-hero__cta"><a className="cm-btn cm-btn--w" href={href('camera', 'results')}>See the Adult result</a><span className="cm-muted">Scroll for the tour ↓</span></div>
          </div>
          <div className="cm-persp">
            <div ref={tilt} className="cm-tilt">
              <div ref={canvas} className="cm-canvas">
                <Window>
                  <div className="cm-app cm-app--canvas">
                    <Sidebar />
                    <div className="cm-main">
                      <Topbar tab="overview" exportOpen={active >= 0 && stops[active].sel === 'export'} />
                      <Overview />
                    </div>
                  </div>
                </Window>
              </div>
            </div>
          </div>
          <div className="cm-caps" aria-live="polite" style={{ opacity: 1 - intro }}>
            {stops.map((s, i) => (
              <div key={s.sel} className={`cm-cap ${i === active ? 'is-on' : ''}`} aria-hidden={i !== active}>
                <span className="cm-cap__k">{String(i + 1).padStart(2, '0')} · {s.k}</span>
                <h2>{s.t}</h2>
                <p>{s.b.split('`').map((x, j) => (j % 2 ? <code key={j}>{x}</code> : x))}</p>
              </div>
            ))}
            <div className="cm-ticks" aria-hidden="true">{stops.map((s, i) => <i key={s.sel} className={i === active ? 'is-on' : i < active ? 'is-past' : ''} />)}</div>
          </div>
        </div>
      </section>

      <section className="cm-scope">
        <h2>What it does, and what it doesn’t.</h2>
        <div className="cm-scope__g">
          <div><h3>Does</h3><ul>
            <li>Profiles every column; finds gaps, duplicates and conflicting labels</li>
            <li>Separates strong leakage evidence from review-only name prompts</li>
            <li>Scores classification tables with transparent sub-scores and guardrails</li>
            <li>Reports regression, time, text, image and document evidence without inventing a score</li>
          </ul></div>
          <div><h3>Doesn’t</h3><ul>
            <li>Upload your data or call the network during analysis</li>
            <li>Clean, impute or delete anything</li>
            <li>Monitor production systems or host a service</li>
            <li>Certify a dataset — findings support human review</li>
          </ul></div>
        </div>
      </section>

      <section className="cm-reps">
        <h2>Six kinds of data, each read by its own unit.</h2>
        <div className="cm-reps__g">
          {representations.map((r) => (
            <article key={r.id} className="cm-card">
              <div className="cm-reps__h"><span className="cm-reps__i">{Icon[r.id === 'tables' ? 'table' : r.id]}</span><b>{r.name}</b><span className="cm-muted">per {r.unit}</span></div>
              <ul>{r.checks.map((c) => <li key={c}>{c}</li>)}</ul>
              <span className="cm-reps__e cm-mono">{r.example}</span>
            </article>
          ))}
        </div>
      </section>

      <section className="cm-run" id="cm-run">
        <div>
          <h2>Two commands.</h2>
          <p className="cm-muted">Audit from the terminal, or open the same views in a browser bound to loopback.</p>
        </div>
        <div className="cm-term">
          <div className="cm-win__bar"><span className="cm-win__dots" aria-hidden="true"><i /><i /><i /></span><span className="cm-win__url">Terminal</span><span /></div>
          <pre><span className="cm-term__p">$</span> {local.commands[0]}{'\n'}<span className="cm-term__o">{local.cliOutput.join('\n')}</span>{'\n\n'}<span className="cm-term__p">$</span> {local.commands[1]}{'\n'}<span className="cm-term__o">→ http://127.0.0.1:8000/</span></pre>
        </div>
      </section>

      <footer className="cm-foot">
        <span className="cm-nav__wm">NUMEK</span>
        <p>{company.line}. DataTrust is the product. {company.direction}</p>
        <p className="cm-muted">Adult · {adult.source} · Findings support human review; they are not certification.</p>
      </footer>
    </div>
  );
}
