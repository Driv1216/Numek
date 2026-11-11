import { useEffect, useLayoutEffect, type RefObject } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import Lenis from 'lenis';

gsap.registerPlugin(ScrollTrigger);
export { gsap, ScrollTrigger };

export const prefersReduced = () =>
  typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/** Smooth, inertial page scroll synced with ScrollTrigger (disabled for reduced motion). */
export function useSmoothScroll(enabled = true) {
  useEffect(() => {
    if (!enabled || prefersReduced()) return;
    const lenis = new Lenis({ duration: 1.1, smoothWheel: true });
    lenis.on('scroll', ScrollTrigger.update);
    const tick = (t: number) => lenis.raf(t * 1000);
    gsap.ticker.add(tick);
    gsap.ticker.lagSmoothing(0);
    return () => {
      gsap.ticker.remove(tick);
      lenis.destroy();
    };
  }, [enabled]);
}

/** Runs a GSAP setup scoped to a root element and reverts it on unmount. */
export function useGsap(root: RefObject<HTMLElement | null>, setup: (q: gsap.utils.SelectorFunc) => void, deps: unknown[] = []) {
  useLayoutEffect(() => {
    if (!root.current) return;
    const ctx = gsap.context(() => {
      if (!prefersReduced()) setup(gsap.utils.selector(root.current!));
    }, root);
    requestAnimationFrame(() => ScrollTrigger.refresh());
    return () => ctx.revert();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}
