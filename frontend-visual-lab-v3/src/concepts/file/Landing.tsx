import '@fontsource/dm-serif-display/400.css';
import '@fontsource/dm-serif-display/400-italic.css';
import '@fontsource-variable/dm-sans';
import './file.css';
import { useEffect, useRef, useState } from 'react';
import { bike, company, finance, local, runs } from '../../fixture';
import { reducedMotion } from '../../shell/motion';
import { href } from '../../shell/router';
import { Stack, states } from './stack';

export function Header({ here }: { here: 'landing' | 'app' | 'results' }) {
  return (
    <header className="fl-head">
      <a className="fl-wm" href={href('file', 'landing')}>NUMEK</a>
      <nav aria-label="Primary">
        <a href={href('file', 'landing')} aria-current={here === 'landing' ? 'page' : undefined}>The file</a>
        <a href={href('file', 'app')} aria-current={here === 'app' ? 'page' : undefined}>Shelf</a>
        <a href={href('file', 'results')} aria-current={here === 'results' ? 'page' : undefined}>Adult</a>
      </nav>
      <a className="fl-cta" href={href('file', 'app')}>Open DataTrust</a>
    </header>
  );
}

export default function Landing() {
  const sec = useRef<HTMLElement>(null);
  const [i, setI] = useState(0);
  useEffect(() => {
    let raf = 0;
    const on = () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(() => {
      const el = sec.current; if (!el) return;
      const r = el.getBoundingClientRect();
      const p = Math.min(0.9999, Math.max(0, -r.top / Math.max(1, r.height - innerHeight)));
      setI(Math.floor(p * states.length));
    }); };
    on(); addEventListener('scroll', on, { passive: true });
    return () => { removeEventListener('scroll', on); cancelAnimationFrame(raf); };
  }, []);
  const s = states[i];
  const go = (k: number) => { const el = sec.current; if (!el) return; scrollTo({ top: el.offsetTop + ((k + 0.5) / states.length) * (el.offsetHeight - innerHeight), behavior: reducedMotion() ? 'auto' : 'smooth' }); };
  return (
    <div className="fl fl--landing">
      <Header here="landing" />
      <section ref={sec} className="fl-tour" style={{ height: `${states.length * 90 + 40}vh` }} aria-label="adult.csv, state by state">
        <div className={`fl-stage f-${s.id}`}>
          <div className="fl-copy" key={s.id}>
            <span className="fl-k">{s.k}</span>
            <h1>{s.title}</h1>
            <p>{s.caption}</p>
            {s.note && <small>{s.note}</small>}
          </div>
          <Stack state={s.id} />
          <div className="fl-fig" key={`f-${s.id}`}><b>{s.figure}</b></div>
          <nav className="fl-dots" aria-label="States">{states.map((x, k) => <button key={x.id} type="button" aria-label={x.k} aria-current={k === i} onClick={() => go(k)} />)}</nav>
        </div>
      </section>

      <section className="fl-shelf">
        <h2>Every file gets the same treatment.</h2>
        <div className="fl-shelf__g">
          {runs.filter((r) => r.id !== 'adult').map((r) => (
            <a key={r.id} className="fl-book" href={href('file', 'app')}>
              <div className="fl-book__obj"><span>{r.file}</span></div>
              <b>{r.name}</b>
              <em>{r.id === 'bike' ? `${bike.relationship} · no score defined` : r.id === 'finance' ? `${finance.agreements} agree · ${finance.discrepancies} discrepancy · ${finance.conflicts} conflict` : r.score == null ? `${r.lead} · no score defined` : `${r.score.toFixed(1)} · ${r.band}`}</em>
            </a>
          ))}
        </div>
      </section>

      <section className="fl-close">
        <div className="fl-close__obj"><Stack state="reports" compact /></div>
        <div>
          <h2>Bring your own file.</h2>
          <pre>$ {local.commands[0]}{'\n'}{local.cliOutput.join('\n')}</pre>
          <p className="fl-dim">{company.line}. DataTrust is the product. {company.direction} Findings support human review; they are not certification.</p>
        </div>
      </section>
    </div>
  );
}
