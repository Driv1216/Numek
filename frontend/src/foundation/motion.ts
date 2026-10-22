import { useEffect, useRef, useState } from 'react';

export const reducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;

/** True once the element has entered the viewport (fires once). */
export function useInView<T extends Element>(margin = '0px 0px -12% 0px') {
  const ref = useRef<T>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (reducedMotion()) { setSeen(true); return; }
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setSeen(true); io.disconnect(); } }, { rootMargin: margin });
    io.observe(el);
    return () => io.disconnect();
  }, [margin]);
  return [ref, seen] as const;
}

/** Scroll progress (0–1) of an element travelling through the viewport. */
export function useScrollProgress<T extends HTMLElement>(mode: 'through' | 'pinned' = 'through') {
  const ref = useRef<T>(null);
  const [p, setP] = useState(0);
  useEffect(() => {
    let raf = 0;
    const on = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const el = ref.current;
        if (!el) return;
        const r = el.getBoundingClientRect();
        const h = innerHeight;
        const v = mode === 'pinned' ? -r.top / Math.max(1, r.height - h) : (h - r.top) / (r.height + h);
        setP(Math.min(1, Math.max(0, v)));
      });
    };
    on();
    addEventListener('scroll', on, { passive: true });
    addEventListener('resize', on);
    return () => { removeEventListener('scroll', on); removeEventListener('resize', on); cancelAnimationFrame(raf); };
  }, [mode]);
  return [ref, p] as const;
}

/** Counts up to a value once `active` is true. */
export function useCount(target: number, active: boolean, ms = 1100, decimals = 0) {
  const [v, setV] = useState(active && reducedMotion() ? target : 0);
  useEffect(() => {
    if (!active) return;
    if (reducedMotion()) { setV(target); return; }
    const t0 = performance.now();
    let raf = 0;
    const tick = (t: number) => {
      const k = Math.min(1, (t - t0) / ms);
      const e = 1 - Math.pow(1 - k, 4);
      setV(target * e);
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, active, ms]);
  return v.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

export const clamp = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));
export const seg = (p: number, a: number, b: number) => clamp((p - a) / (b - a));
export const fmt = (n: number) => n.toLocaleString('en-US');
