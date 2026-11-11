import '@fontsource-variable/cormorant';
import '@fontsource-variable/cormorant/wght-italic.css';
import '@fontsource-variable/figtree';
import './relief.css';
import { useEffect, useState, type ReactNode } from 'react';
import { adult, bike, company, finance, local } from '../../fixture';
import { reducedMotion } from '../../shell/motion';
import { href } from '../../shell/router';
import { Relief, adultGrid, bikeGrid, useRelief } from './surface';

export function Header({ here }: { here: 'landing' | 'app' | 'results' }) {
  return (
    <header className="rl-head">
      <a className="rl-wm" href={href('relief', 'landing')}>NUMEK</a>
      <nav aria-label="Primary">
        <a href={href('relief', 'landing')} aria-current={here === 'landing' ? 'page' : undefined}>DataTrust</a>
        <a href={href('relief', 'app')} aria-current={here === 'app' ? 'page' : undefined}>Runs</a>
        <a href={href('relief', 'results')} aria-current={here === 'results' ? 'page' : undefined}>Adult</a>
      </nav>
      <span className="rl-head__r">local · 127.0.0.1</span>
    </header>
  );
}

export const fences = [{ x: (adult.hours.lower - 1) / 98, colour: 'rgba(31, 122, 115, .9)' }, { x: (adult.hours.upper - 1) / 98, colour: 'rgba(31, 122, 115, .9)' }];
const g = adult.conflicts[0];

/** Windows let into the surface: the only places with colour. */
export const windows: { id: string; tone: 'teal' | 'rust'; k: string; caption: string; body: ReactNode }[] = [
  { id: 'target', tone: 'teal', k: 'Target balance', caption: 'One class fills three quarters of the target, so the score is held at 69.', body: <><b className="rl-num">47.86</b><div className="rl-split"><i style={{ flex: adult.classes.le50k }} /><i style={{ flex: adult.classes.gt50k }} /></div><span>{adult.classes.le50k.toLocaleString()} ≤50K · {adult.classes.gt50k.toLocaleString()} &gt;50K · {adult.ratio}</span></> },
  { id: 'conflict', tone: 'rust', k: 'Two rows, one difference', caption: 'Identical in all fourteen features, different in the answer. Five such groups; evidence only.', body: <>{g.rows.map((r, k) => <p key={r} className="rl-row"><b>row {r.toLocaleString()}</b> 46 · Private · HS-grad · Married-civ-spouse · Craft-repair · 40 h · <mark>{g.labels[k]}</mark></p>)}</> },
  { id: 'fences', tone: 'teal', k: 'Fences at 32.5 and 52.5', caption: 'The two lines cut into the surface are hours_per_week’s 1.5 × IQR fences. 13,496 rows lie outside them.', body: <><b className="rl-num">27.63%</b><span>{adult.hours.below.toLocaleString()} below · {adult.hours.above.toLocaleString()} above · reported, not removed</span></> },
  { id: 'score', tone: 'rust', k: 'How the number was made', caption: 'The mean of five measures is 89.15; one of them is critical, so the result is 69.0.', body: <dl className="rl-dl">{adult.subScores.map((s) => <div key={s.key}><dt>{s.label}</dt><dd>{s.value}</dd></div>)}<div className="is-final"><dt>Final</dt><dd>{adult.finalScore.toFixed(1)} · {adult.band}</dd></div></dl> },
];

export default function Landing() {
  const [count, setCount] = useState(reducedMotion() ? adult.rows : 0);
  const [done, setDone] = useState(reducedMotion());
  const { ref, draw } = useRelief(adultGrid, { lines: fences, azimuth: 300 });

  // Loader: counts the rows the surface is cast from.
  useEffect(() => {
    if (reducedMotion()) return;
    const t0 = performance.now(); let raf = 0;
    const tick = (t: number) => { const k = Math.min(1, (t - t0) / 1400); setCount(Math.round(adult.rows * (1 - Math.pow(1 - k, 3)))); if (k < 1) raf = requestAnimationFrame(tick); else setTimeout(() => setDone(true), 350); };
    raf = requestAnimationFrame(tick); return () => cancelAnimationFrame(raf);
  }, []);
  // The raking light travels across the relief as you scroll.
  useEffect(() => {
    if (reducedMotion()) return;
    let raf = 0;
    const on = () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(() => { const p = Math.min(1, scrollY / Math.max(1, document.documentElement.scrollHeight - innerHeight)); draw(300 - p * 200); }); };
    addEventListener('scroll', on, { passive: true }); return () => { removeEventListener('scroll', on); cancelAnimationFrame(raf); };
  }, [draw]);

  return (
    <div className="rl rl--landing">
      {!done && <div className="rl-loader" aria-hidden="true"><span>Casting the surface from</span><b>{count.toLocaleString()}</b><span>rows of adult.csv</span></div>}
      <Header here="landing" />
      <div className="rl-stage" aria-hidden="true"><canvas ref={ref} className="rl-canvas rl-canvas--stage" /></div>
      <section className="rl-hero">
        <p className="rl-kicker">DataTrust by {company.name}</p>
        <h1>Cast from<br /><em>your data.</em></h1>
        <p className="rl-cap">The surface behind this page is Adult: age from 17 (top) to 90, hours worked per week from 1 (left) to 99. Its height is how many of the 48,842 rows fall near each point (a smoothed density). The ridge is forty hours — 46.69% of rows.</p>
      </section>
      {windows.map((w, i) => (
        <section key={w.id} className={`rl-win-sec ${i % 2 ? 'is-right' : ''}`}>
          <div className={`rl-win rl-win--${w.tone}`}><span className="rl-win__k">{w.k}</span>{w.body}</div>
          <p className="rl-cap">{w.caption}</p>
        </section>
      ))}
      <section className="rl-others">
        <h2>Every run has its own <em>surface</em>.</h2>
        <div className="rl-others__g">
          <figure><Relief grid={bikeGrid} azimuth={315} sigma={0.8} label="Bike sharing: mean hourly count by weekday and hour" className="rl-canvas--small" /><figcaption><b>Bike sharing, hourly</b><span>Mean count by weekday × hour, 17,379 rows. {bike.relationship}: two High findings, no score defined.</span></figcaption></figure>
          <figure><div className="rl-lines" aria-hidden="true">{Array.from({ length: 14 }, (_, i) => <i key={i} style={{ width: `${45 + ((i * 29) % 50)}%` }} />)}</div><figcaption><b>SMS collection</b><span>5,574 records, read as text: near-duplicate candidates from calibrated MinHash search.</span></figcaption></figure>
          <figure><div className="rl-tiles" aria-hidden="true">{Array.from({ length: 128 }, (_, i) => <i key={i} className={i < 61 ? 'is-x' : ''} />)}</div><figcaption><b>COCO subset</b><span>128 images, 875 objects; 61 ICC-bearing images excluded from default visual methods.</span></figcaption></figure>
          <figure><div className="rl-pairs" aria-hidden="true">{Array.from({ length: finance.records }, (_, i) => <i key={i} className={i === 6 || i === 13 ? 'is-x' : ''} />)}</div><figcaption><b>Records ↔ PDFs</b><span>{finance.agreements} agree · {finance.discrepancies} discrepancy · {finance.conflicts} conflict, each with a page locator.</span></figcaption></figure>
        </div>
      </section>
      <section className="rl-close">
        <h2>Cast from your own data, <em>on your own machine.</em></h2>
        <pre>$ {local.commands[0]}{'\n'}{local.cliOutput.join('\n')}</pre>
        <p className="rl-dim">{company.line}. DataTrust is the product. {company.direction} Findings support human review; they are not certification.</p>
      </section>
    </div>
  );
}
