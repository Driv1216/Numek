import { useEffect, useRef } from 'react';
import { useReducedMotion } from '../../shared/hooks';

interface Group {
  count: number;
  color: string;
}

/**
 * Every square is a fixed number of rows. Squares start as an unordered crowd and
 * settle into class order, so the size of each population becomes visible.
 */
export function PopulationField({
  groups,
  perDot = 20,
  size = 6,
  gap = 3,
  sorted,
  height,
}: {
  groups: Group[];
  perDot?: number;
  size?: number;
  gap?: number;
  sorted: boolean;
  height?: number;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const state = useRef<{ t: number; raf: number; dots: { c: string; sx: number; sy: number; d: number }[] }>({
    t: 0,
    raf: 0,
    dots: [],
  });
  const reduced = useReducedMotion();

  useEffect(() => {
    const cv = canvas.current!;
    const ctx = cv.getContext('2d')!;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const st = state.current;

    const colors: string[] = [];
    groups.forEach((g) => {
      for (let i = 0; i < Math.round(g.count / perDot); i++) colors.push(g.color);
    });

    let W = 0;
    let H = 0;
    let cols = 0;
    const layout = () => {
      W = cv.parentElement!.clientWidth;
      const step = size + gap;
      cols = Math.max(10, Math.floor((W + gap) / step));
      const rows = Math.ceil(colors.length / cols);
      H = height ?? rows * step - gap;
      cv.width = W * dpr;
      cv.height = H * dpr;
      cv.style.height = `${H}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      // Deterministic pseudo-random scatter so screenshots are repeatable.
      let seed = 7;
      const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
      st.dots = colors.map((c) => ({ c, sx: rnd(), sy: rnd(), d: rnd() }));
    };

    const draw = (p: number) => {
      ctx.clearRect(0, 0, W, H);
      const step = size + gap;
      const rows = Math.ceil(colors.length / cols);
      st.dots.forEach((dot, i) => {
        // Column-major fill: classes read left to right as contiguous blocks.
        const col = Math.floor(i / rows);
        const row = i % rows;
        const tx = col * step;
        const ty = row * step;
        const fx = dot.sx * (W - size);
        const fy = dot.sy * (H - size);
        const local = Math.min(1, Math.max(0, (p - dot.d * 0.45) / 0.55));
        const e = local < 0.5 ? 4 * local ** 3 : 1 - (-2 * local + 2) ** 3 / 2;
        ctx.fillStyle = dot.c;
        ctx.fillRect(fx + (tx - fx) * e, fy + (ty - fy) * e, size, size);
      });
    };

    layout();
    const target = sorted ? 1 : 0;
    if (reduced) {
      st.t = target;
      draw(st.t);
    } else {
      const tick = () => {
        const diff = target - st.t;
        st.t += Math.sign(diff) * Math.min(Math.abs(diff), 0.011);
        draw(st.t);
        if (st.t !== target) st.raf = requestAnimationFrame(tick);
      };
      cancelAnimationFrame(st.raf);
      tick();
    }
    const ro = new ResizeObserver(() => {
      layout();
      draw(st.t);
    });
    ro.observe(cv.parentElement!);
    return () => {
      cancelAnimationFrame(st.raf);
      ro.disconnect();
    };
  }, [groups, perDot, size, gap, sorted, height, reduced]);

  return <canvas ref={canvas} className="cn-field" aria-hidden="true" />;
}
