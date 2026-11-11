import { useEffect, useRef } from 'react';

// 4×4 Bayer matrix: an ordered dither turns a fraction into a texture whose
// density is the value itself, so tone carries data instead of decoration.
const BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5].map((v) => (v + 0.5) / 16);

export function Dither({
  level,
  color,
  cell = 3,
  className,
  fillFrom = 'none',
  fill = 1,
}: {
  /** density 0–1 of the texture */
  level: number;
  color: string;
  cell?: number;
  className?: string;
  /** optionally only fill part of the box (a bar growing from an edge) */
  fillFrom?: 'none' | 'bottom' | 'left';
  fill?: number;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const cv = ref.current!;
    const draw = () => {
      const w = cv.clientWidth;
      const h = cv.clientHeight;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      cv.width = w * dpr;
      cv.height = h * dpr;
      const ctx = cv.getContext('2d')!;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = color;
      const cols = Math.ceil(w / cell);
      const rows = Math.ceil(h / cell);
      for (let y = 0; y < rows; y++) {
        for (let x = 0; x < cols; x++) {
          if (fillFrom === 'bottom' && (rows - y) / rows > fill) continue;
          if (fillFrom === 'left' && x / cols > fill) continue;
          if (level > BAYER[(y % 4) * 4 + (x % 4)]) ctx.fillRect(x * cell, y * cell, cell, cell);
        }
      }
    };
    draw();
    const ro = new ResizeObserver(draw);
    ro.observe(cv);
    return () => ro.disconnect();
  }, [level, color, cell, fillFrom, fill]);
  return <canvas ref={ref} className={className} aria-hidden="true" />;
}
