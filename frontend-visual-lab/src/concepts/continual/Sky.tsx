import { useEffect, useRef } from 'react';
import { prefersReduced } from '../../shared/motion';

/*
 * A procedurally generated cloud field, quantised through a 4×4 Bayer matrix so
 * it reads as a dithered print rather than a stock photograph. Drifts slowly.
 */
const BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5].map((v) => (v + 0.5) / 16 - 0.5);

function hash(x: number, y: number) {
  const s = Math.sin(x * 127.1 + y * 311.7) * 43758.5453;
  return s - Math.floor(s);
}
function noise(x: number, y: number) {
  const xi = Math.floor(x);
  const yi = Math.floor(y);
  const xf = x - xi;
  const yf = y - yi;
  const u = xf * xf * (3 - 2 * xf);
  const v = yf * yf * (3 - 2 * yf);
  const a = hash(xi, yi);
  const b = hash(xi + 1, yi);
  const c = hash(xi, yi + 1);
  const d = hash(xi + 1, yi + 1);
  return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
}
function fbm(x: number, y: number) {
  let v = 0;
  let amp = 0.55;
  for (let i = 0; i < 5; i++) {
    v += amp * noise(x, y);
    x *= 2.03;
    y *= 2.03;
    amp *= 0.5;
  }
  return v;
}

// sky ramp: slate blue at the top, pale haze, warm cloud highlights
const RAMP = [
  [96, 122, 140],
  [139, 163, 172],
  [176, 194, 196],
  [212, 214, 204],
  [236, 226, 204],
  [250, 244, 230],
];
const LEVELS = RAMP.length - 1;

export function Sky({ cell = 3 }: { cell?: number }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const cv = ref.current!;
    const ctx = cv.getContext('2d')!;
    let W = 0;
    let H = 0;
    let img: ImageData;
    const size = () => {
      W = Math.max(1, Math.ceil(cv.clientWidth / cell));
      H = Math.max(1, Math.ceil(cv.clientHeight / cell));
      cv.width = W;
      cv.height = H;
      img = ctx.createImageData(W, H);
    };
    size();
    let t = 0;
    let raf = 0;
    const draw = () => {
      const d = img.data;
      for (let y = 0; y < H; y++) {
        const gy = y / H;
        for (let x = 0; x < W; x++) {
          const n = fbm(x / 58 + t, y / 34 + t * 0.35);
          // clouds gather in the lower half, sky opens above
          const cloud = Math.max(0, n - 0.5 + gy * 0.22) * 1.55;
          let v = Math.min(1, 0.04 + gy * 0.2 + cloud);
          v += BAYER[(y % 4) * 4 + (x % 4)] / LEVELS;
          const k = Math.max(0, Math.min(LEVELS, Math.round(v * LEVELS)));
          const c = RAMP[k];
          const i = (y * W + x) * 4;
          d[i] = c[0];
          d[i + 1] = c[1];
          d[i + 2] = c[2];
          d[i + 3] = 255;
        }
      }
      ctx.putImageData(img, 0, 0);
    };
    const reduced = prefersReduced();
    let last = 0;
    const loop = (now: number) => {
      if (now - last > 90) {
        t += 0.004;
        draw();
        last = now;
      }
      raf = requestAnimationFrame(loop);
    };
    draw();
    if (!reduced) raf = requestAnimationFrame(loop);
    const ro = new ResizeObserver(() => {
      size();
      draw();
    });
    ro.observe(cv);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, [cell]);
  return <canvas ref={ref} className="ct-sky" aria-hidden="true" />;
}
