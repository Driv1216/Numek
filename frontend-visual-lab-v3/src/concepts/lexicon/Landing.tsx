import '@fontsource-variable/fraunces/full.css';
import '@fontsource-variable/fraunces/full-italic.css';
import '@fontsource-variable/work-sans';
import '@fontsource/dm-mono/400.css';
import './lexicon.css';
import { useEffect, useState } from 'react';
import { company, local } from '../../fixture';
import { href } from '../../shell/router';
import { closing, entries } from './entries';
import { Fragments, Header, useParallax, wordSize } from './parts';

const all = [...entries.map((e) => ({ id: e.id, word: e.word })), { id: 'reliability', word: closing.word }];

function Pill({ active, onIndex }: { active: number; onIndex: () => void }) {
  const go = (i: number) => document.getElementById(`lx-${all[Math.max(0, Math.min(all.length - 1, i))].id}`)?.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
  const cur = all[Math.max(0, active)];
  return (
    <div className={`lx-pill ${active < 0 ? 'is-idle' : ''}`} role="navigation" aria-label="Lexicon">
      <button type="button" onClick={() => go(active - 1)} disabled={active <= 0} aria-label="Previous word">←</button>
      <button type="button" className="lx-pill__w" onClick={onIndex} aria-haspopup="dialog">
        <span>{active < 0 ? '00' : String(active + 1).padStart(2, '0')}</span>
        <b>{active < 0 ? 'Index' : cur.word}</b>
        <i>/ {String(all.length).padStart(2, '0')}</i>
      </button>
      <button type="button" onClick={() => go(active + 1)} disabled={active >= all.length - 1} aria-label="Next word">→</button>
    </div>
  );
}

export default function Landing() {
  useParallax();
  const [active, setActive] = useState(-1);
  const [index, setIndex] = useState(false);

  // The word under the middle of the viewport is the current one; the intro has none.
  useEffect(() => {
    let raf = 0;
    const on = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const mid = innerHeight / 2;
        setActive(all.findIndex((a) => { const r = document.getElementById(`lx-${a.id}`)?.getBoundingClientRect(); return !!r && r.top <= mid && r.bottom > mid; }));
      });
    };
    on();
    addEventListener('scroll', on, { passive: true });
    return () => { removeEventListener('scroll', on); cancelAnimationFrame(raf); };
  }, []);

  useEffect(() => {
    if (!index) return;
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape') setIndex(false); };
    addEventListener('keydown', k);
    return () => removeEventListener('keydown', k);
  }, [index]);

  const jump = (id: string) => { setIndex(false); requestAnimationFrame(() => document.getElementById(`lx-${id}`)?.scrollIntoView({ block: 'start' })); };

  return (
    <div className="lx lx--landing">
      <Header here="landing" />

      <section id="lx-intro" className="lx-intro" data-px>
        <Fragments frags={entries.flatMap((e) => e.frags.slice(0, 1))} seed={3} back />
        <div className="lx-intro__t">
          <p className="lx-kicker">DataTrust by {company.name}</p>
          <h1>Lexicon</h1>
          <p className="lx-intro__s">Nine words for what goes wrong in data, and one for what remains. Each is something DataTrust looks for; each is shown with what it found in real, public datasets.</p>
        </div>
        <p className="lx-scroll">Scroll</p>
      </section>

      {entries.map((e, i) => (
        <section key={e.id} id={`lx-${e.id}`} className="lx-entry" data-px aria-labelledby={`lx-w-${e.id}`}>
          <div className="lx-entry__stick">
            <Fragments frags={e.frags} seed={i * 3} mirror={i % 2 === 1} />
            <h2 id={`lx-w-${e.id}`} className="lx-word" style={{ fontSize: wordSize(e.word) }}>{e.word}</h2>
            <div className="lx-def">
              <p className="lx-def__pos"><i>{e.pos}</i> {e.sense}</p>
              <p className="lx-def__d">{e.def}</p>
              <dl>{e.in.map((x) => <div key={x.run}><dt>{x.run}</dt><dd>{x.line}</dd></div>)}</dl>
              <p className="lx-def__fx">{e.effect}</p>
            </div>
            <span className="lx-num" aria-hidden="true">{String(i + 1).padStart(2, '0')}</span>
          </div>
        </section>
      ))}

      <section id="lx-reliability" className="lx-entry lx-entry--close" data-px aria-labelledby="lx-w-rel">
        <div className="lx-entry__stick">
          <h2 id="lx-w-rel" className="lx-word lx-word--close" style={{ fontSize: wordSize(closing.word, 20, 88) }}>{closing.word}</h2>
          <div className="lx-def lx-def--close">
            <p className="lx-def__pos"><i>{closing.pos}</i></p>
            <p className="lx-def__d">{closing.def}</p>
            <p className="lx-def__fx">{closing.adult}<br />{closing.bike}</p>
            <a className="lx-link" href={href('lexicon', 'results')}>Read the Adult entry →</a>
          </div>
        </div>
      </section>

      <footer className="lx-foot">
        <p className="lx-foot__big">Look the words up in your own data.</p>
        <code>$ {local.commands[0]}</code>
        <p>{company.line}. DataTrust runs locally, with no network at analysis time. {company.direction}</p>
        <p className="lx-dim">{closing.limits}</p>
      </footer>

      <Pill active={active} onIndex={() => setIndex(true)} />

      {index && (
        <div className="lx-index" role="dialog" aria-modal="true" aria-label="Index of words" onClick={(ev) => { if (ev.target === ev.currentTarget) setIndex(false); }}>
          <button type="button" className="lx-index__x" onClick={() => setIndex(false)} autoFocus>Close</button>
          <ol>
            {all.map((a, i) => {
              const e = entries.find((x) => x.id === a.id);
              return (
                <li key={a.id}>
                  <button type="button" onClick={() => jump(a.id)}>
                    <span>{String(i + 1).padStart(2, '0')}</span>
                    <b>{a.word}</b>
                    <em>{e ? e.sense : 'what remains'}</em>
                  </button>
                </li>
              );
            })}
          </ol>
        </div>
      )}
    </div>
  );
}
