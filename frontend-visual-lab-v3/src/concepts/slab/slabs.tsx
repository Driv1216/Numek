// The NUMEK wordmark built from slabs. With progress p (0 → 1) every slab slides to become part of
// one of five bars whose heights are Adult's real sub-scores: N→Completeness, U→Uniqueness,
// M→Target balance, E→Feature usability, K→Leakage risk.
import { useEffect, useState, type ReactNode, type RefObject } from 'react';
import { reducedMotion } from '../../shell/motion';

type R = [number, number, number, number];
const L: Record<string, R[]> = {
  N: [[0, 0, 1.5, 8], [4.5, 0, 1.5, 8], [1.5, 1, 1.5, 3], [3, 4, 1.5, 3]],
  U: [[0, 0, 1.5, 8], [4.5, 0, 1.5, 8], [1.5, 6.5, 3, 1.5]],
  M: [[0, 0, 1.5, 8], [4.5, 0, 1.5, 8], [1.5, 1, 1.5, 2], [3, 1, 1.5, 2], [2.25, 3, 1.5, 2]],
  E: [[0, 0, 1.5, 8], [1.5, 0, 4.5, 1.5], [1.5, 3.25, 3.5, 1.5], [1.5, 6.5, 4.5, 1.5]],
  K: [[0, 0, 1.5, 8], [1.5, 3, 1.5, 2], [3, 1.5, 1.5, 1.5], [4.5, 0, 1.5, 1.5], [3, 5, 1.5, 1.5], [4.5, 6.5, 1.5, 1.5]],
};
const U = 26, PITCH = 190, X0 = 50, Y0 = 60, BASE = 420, MAXH = 340;
const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

export function SlabMark({ values, p, critical = 50, cap = 69, labels = true, showLines = true }: { values: { label: string; value: number }[]; p: number; critical?: number; cap?: number; labels?: boolean; showLines?: boolean }) {
  const letters = 'NUMEK'.split('');
  const any = values.some((v) => v.value <= critical);
  const y = (v: number) => BASE - (v / 100) * MAXH;
  return (
    <svg viewBox="0 0 1000 470" className="sl-mark" role="img" aria-label={p < 0.5 ? 'NUMEK' : `Five sub-scores: ${values.map((v) => `${v.label} ${v.value}`).join(', ')}`}>
      {letters.map((ch, i) => {
        const rects = L[ch], h = (values[i].value / 100) * MAXH, k = rects.length;
        const crit = values[i].value <= critical;
        return (
          <g key={ch} className={crit && p > 0.6 ? 'is-crit' : ''}>
            {rects.map(([rx, ry, rw, rh], j) => {
              const t = ease(Math.min(1, Math.max(0, (p - j * 0.04 - i * 0.02) / 0.8)));
              const a: R = [X0 + i * PITCH + rx * U, Y0 + ry * U, rw * U, rh * U];
              const b: R = [X0 + i * PITCH, BASE - (h * (j + 1)) / k, 6 * U, h / k - 2];
              const [x, yy, w, hh] = a.map((v, n) => v + (b[n] - v) * t);
              return <rect key={j} x={x} y={yy} width={Math.max(0, w)} height={Math.max(0, hh)} className="sl-block" />;
            })}
            {labels && p > 0.85 && <><text x={X0 + i * PITCH} y={y(values[i].value) - 10} className="sl-v">{values[i].value}</text><text x={X0 + i * PITCH} y={BASE + 26} className="sl-l">{values[i].label.toUpperCase()}</text></>}
          </g>
        );
      })}
      {showLines && p > 0.75 && (
        <g className="sl-lines" style={{ opacity: Math.min(1, (p - 0.75) * 4) }}>
          <line x1={20} x2={980} y1={BASE} y2={BASE} className="sl-base" />
          <line x1={20} x2={980} y1={y(critical)} y2={y(critical)} className="sl-crit" /><text x={980} y={y(critical) - 6} textAnchor="end" className="sl-t sl-t--crit">CRITICAL ≤ {critical}</text>
          {any && <><line x1={20} x2={980} y1={y(cap)} y2={y(cap)} className="sl-cap" /><text x={980} y={y(cap) - 6} textAnchor="end" className="sl-t sl-t--cap">CAP {cap}</text></>}
        </g>
      )}
    </svg>
  );
}

/** A panel hidden behind two slabs that part when it comes into view (or when opened). */
export function Shutter({ open, children, label }: { open: boolean; children: ReactNode; label: string }) {
  return (
    <div className={`sl-shutter ${open ? 'is-open' : ''}`} aria-label={label}>
      <div className="sl-shutter__in">{children}</div>
      <i className="sl-door sl-door--l" aria-hidden="true" /><i className="sl-door sl-door--r" aria-hidden="true" />
    </div>
  );
}

/** Opens when scrolled into view. */
export function useInViewOnce<T extends Element>(ref: RefObject<T | null>) {
  const [seen, setSeen] = useState(reducedMotion());
  useEffect(() => {
    const el = ref.current; if (!el || seen) return;
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setSeen(true); io.disconnect(); } }, { rootMargin: '0px 0px -20% 0px' });
    io.observe(el); return () => io.disconnect();
  }, [ref, seen]);
  return seen;
}

export function Credits({ items }: { items: [string, string][] }) {
  return <dl className="sl-credits">{items.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>;
}
