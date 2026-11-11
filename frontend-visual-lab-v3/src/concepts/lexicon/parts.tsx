import { useEffect, type CSSProperties } from 'react';
import { reducedMotion } from '../../shell/motion';
import { href } from '../../shell/router';
import type { Frag } from './entries';

export function Header({ here }: { here: 'landing' | 'app' | 'results' }) {
  return (
    <header className="lx-head">
      <a className="lx-wm" href={href('lexicon', 'landing')}>NUMEK</a>
      <nav aria-label="Primary">
        <a href={href('lexicon', 'landing')} aria-current={here === 'landing' ? 'page' : undefined}>Lexicon</a>
        <a href={href('lexicon', 'app')} aria-current={here === 'app' ? 'page' : undefined}>Concordance</a>
        <a href={href('lexicon', 'results')} aria-current={here === 'results' ? 'page' : undefined}>Adult</a>
      </nav>
      <span className="lx-head__r">DataTrust · local</span>
    </header>
  );
}

/** Each slot: left %, top %, depth (parallax speed; < 1 sits behind the word). */
const SLOTS: [number, number, number][] = [
  [5, 13, 1.5], [68, 9, 0.55], [80, 40, 1.8], [9, 64, 0.75], [56, 74, 1.3], [33, 6, 0.4], [38, 86, 2.1], [86, 76, 0.65], [21, 34, 1.15], [62, 27, 0.9],
];

export function Fragments({ frags, seed = 0, mirror = false, back = false }: { frags: Frag[]; seed?: number; mirror?: boolean; back?: boolean }) {
  return (
    <div className="lx-frags" aria-hidden="true">
      {frags.map((f, i) => {
        const [x, y, d] = SLOTS[(i + seed) % SLOTS.length];
        const style = { left: `${mirror ? 100 - x - 14 : x}%`, top: `${y}%`, ['--d' as string]: d } as CSSProperties;
        return (
          <div key={i} className={`lx-frag lx-frag--${f.k} ${back || d < 1 ? 'is-back' : 'is-front'}`} style={style}>
            <span>{f.t}</span>
            {f.cap && <em>{f.cap}</em>}
          </div>
        );
      })}
    </div>
  );
}

/** Writes each [data-px] element's progress through the viewport (0 → 1) into --p. */
export function useParallax() {
  useEffect(() => {
    if (reducedMotion()) return;
    const els = Array.from(document.querySelectorAll<HTMLElement>('[data-px]'));
    let raf = 0;
    const on = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const vh = innerHeight;
        for (const el of els) {
          const r = el.getBoundingClientRect();
          if (r.bottom < -vh || r.top > 2 * vh) continue;
          const p = (vh - r.top) / (r.height + vh);
          el.style.setProperty('--p', Math.min(1, Math.max(0, p)).toFixed(4));
        }
      });
    };
    on();
    addEventListener('scroll', on, { passive: true });
    addEventListener('resize', on);
    return () => { removeEventListener('scroll', on); removeEventListener('resize', on); cancelAnimationFrame(raf); };
  }, []);
}

/** Font size that lets a word fill most of the width without overflowing. */
export const wordSize = (w: string, max = 23, width = 92) => `min(${max}vw, ${(width / (w.length * 0.56)).toFixed(2)}vw)`;
