// NUMEK foundation: Deep water tokens live in nk.css; this file holds the line kit
// (Markup's language: hairlines, crosshairs, leader lines, dimension lines). The product list is in products.ts.
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { reducedMotion } from './motion';

/** Four crosshairs pinned to the viewport corners — the drafting frame. */
export function Frame() {
  return <div className="nk-frame" aria-hidden="true"><i /><i /><i /><i /></div>;
}

export function Wordmark() {
  return <span className="nk-wm"><span className="nk-wm__x" aria-hidden="true" />NUMEK</span>;
}

export function Status({ tone, children }: { tone: 'on' | 'dev' | 'res'; children: ReactNode }) {
  return <span className={`nk-status nk-status--${tone}`}><i aria-hidden="true" />{children}</span>;
}

/** True once the element is well inside the viewport (lines draw on then). */
export function useDrawn<T extends Element>(margin = '0px 0px -25% 0px') {
  const ref = useRef<T>(null);
  const [on, setOn] = useState(false);
  useEffect(() => {
    const el = ref.current; if (!el) return;
    if (reducedMotion()) { setOn(true); return; }
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setOn(true); io.disconnect(); } }, { rootMargin: margin });
    io.observe(el); return () => io.disconnect();
  }, [margin]);
  return [ref, on] as const;
}

/** An SVG leader: a dot on the object, an elbowed hairline, and a mono label at the end. */
export function Leader({ from, to, label, sub, anchor = 'start', hot = false, i = 0 }: { from: [number, number]; to: [number, number]; label: string; sub?: string; anchor?: 'start' | 'end'; hot?: boolean; i?: number }) {
  const [x0, y0] = from, [x1, y1] = to;
  const elbow = x0 + (x1 - x0) * 0.35;
  const d = `M${x0} ${y0} L${elbow} ${y1} H${x1}`;
  const tx = anchor === 'start' ? x1 + 6 : x1 - 6;
  return (
    <g className={`nk-ld ${hot ? 'is-hot' : ''}`} style={{ ['--i' as string]: i }}>
      <circle cx={x0} cy={y0} r={3.2} className="nk-ld__dot" />
      <path d={d} className="nk-ld__p" pathLength={1} />
      <text x={tx} y={y1 - 5} textAnchor={anchor} className="nk-ld__t">{label}</text>
      {sub && <text x={tx} y={y1 + 13} textAnchor={anchor} className="nk-ld__s">{sub}</text>}
    </g>
  );
}

/** A dimension line with end ticks and a centred mono label. */
export function Dim({ x0, x1, y, label, hot = false }: { x0: number; x1: number; y: number; label: string; hot?: boolean }) {
  return (
    <g className={`nk-dim ${hot ? 'is-hot' : ''}`}>
      <path d={`M${x0} ${y - 6}V${y + 6}M${x1} ${y - 6}V${y + 6}M${x0} ${y}H${x1}`} className="nk-ld__p" pathLength={1} />
      <text x={(x0 + x1) / 2} y={y - 8} textAnchor="middle" className="nk-ld__t">{label}</text>
    </g>
  );
}

/** Corner brackets around a rectangle (SVG). */
export const brackets = (x: number, y: number, w: number, h: number, a = 10) =>
  `M${x} ${y + a}V${y}H${x + a}M${x + w - a} ${y}H${x + w}V${y + a}M${x} ${y + h - a}V${y + h}H${x + a}M${x + w - a} ${y + h}H${x + w}V${y + h - a}`;
