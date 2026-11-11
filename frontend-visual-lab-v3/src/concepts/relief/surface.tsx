// A plaster relief cast from a real 2D count grid, lit by a moving raking light (2D hillshade).
// Height = log(1 + count) of a Gaussian-smoothed count (a kernel-density surface of the real grid), so the
// relief reads as landform rather than as the exact integer spikes of self-reported hours.
import { useEffect, useRef } from 'react';
import relief from '../../fixture/relief.generated.json';

export const adultGrid = relief.adult.grid as number[][]; // [age 17..90][hours 1..99]
export const bikeGrid = relief.bike.mean_cnt as number[][]; // [weekday 0..6][hour 0..23]

/** Separable Gaussian; sx smooths across columns (e.g. the heaping of hours at 5, 10, 40…), sy down rows. */
function blur(g: number[][], sx: number, sy: number) {
  const pass = (m: number[][], horiz: boolean, sigma: number) => {
    if (sigma <= 0) return m;
    const r = Math.ceil(sigma * 2.5), k = Array.from({ length: 2 * r + 1 }, (_, i) => Math.exp(-((i - r) ** 2) / (2 * sigma * sigma)));
    return m.map((row, y) => row.map((_, x) => {
      let a = 0, w = 0;
      for (let i = -r; i <= r; i++) { const xx = horiz ? x + i : x, yy = horiz ? y : y + i; if (yy < 0 || yy >= m.length || xx < 0 || xx >= row.length) continue; a += m[yy][xx] * k[i + r]; w += k[i + r]; }
      return a / w;
    }));
  };
  return pass(pass(g, true, sx), false, sy);
}

export function useRelief(grid: number[][], { scale = 0, azimuth = 315, elevation = 26, height = 30, sigma = 1.3, sigmaX = 0, lines = [] as { x: number; colour: string }[] } = {}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const rows = grid.length, cols = grid[0].length;
  const sc = scale || Math.max(4, Math.ceil(420 / cols));
  const W = (cols - 1) * sc + 1, H = (rows - 1) * sc + 1;
  // Heights, upsampled once.
  const field = useRef<Float32Array | null>(null);
  if (!field.current || field.current.length !== W * H) {
    const sm = blur(grid, sigmaX || sigma * 1.8, sigma);
    const max = Math.max(...sm.map((r) => Math.max(...r)));
    const h0 = sm.map((r) => r.map((v) => Math.log1p(v) / Math.log1p(max)));
    const f = new Float32Array(W * H);
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      const gx = x / sc, gy = y / sc, x0 = Math.floor(gx), y0 = Math.floor(gy), x1 = Math.min(cols - 1, x0 + 1), y1 = Math.min(rows - 1, y0 + 1), tx = gx - x0, ty = gy - y0;
      f[y * W + x] = (h0[y0][x0] * (1 - tx) + h0[y0][x1] * tx) * (1 - ty) + (h0[y1][x0] * (1 - tx) + h0[y1][x1] * tx) * ty;
    }
    // A pixel-level box blur (one cell wide) removes the facets bilinear interpolation leaves.
    const r = Math.max(1, Math.round(sc / 2)), tmp = new Float32Array(W * H);
    for (let y = 0; y < H; y++) { let acc = 0, n = 0; for (let x = -r; x < W + r; x++) { if (x + r < W) { acc += f[y * W + x + r]; n++; } if (x - r - 1 >= 0) { acc -= f[y * W + x - r - 1]; n--; } if (x >= 0 && x < W) tmp[y * W + x] = acc / n; } }
    for (let x = 0; x < W; x++) { let acc = 0, n = 0; for (let y = -r; y < H + r; y++) { if (y + r < H) { acc += tmp[(y + r) * W + x]; n++; } if (y - r - 1 >= 0) { acc -= tmp[(y - r - 1) * W + x]; n--; } if (y >= 0 && y < H) f[y * W + x] = acc / n; } }
    field.current = f;
  }
  const draw = (az: number) => {
    const c = ref.current; if (!c) return;
    const ctx = c.getContext('2d'); if (!ctx) return;
    if (c.width !== W) { c.width = W; c.height = H; }
    const img = ctx.createImageData(W, H), d = img.data, f = field.current!;
    const a = (az * Math.PI) / 180, e = (elevation * Math.PI) / 180;
    const lx = Math.cos(e) * Math.cos(a), ly = Math.cos(e) * Math.sin(a), lz = Math.sin(e);
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      const i = y * W + x;
      const dx = (f[y * W + Math.min(W - 1, x + 1)] - f[y * W + Math.max(0, x - 1)]) * height;
      const dy = (f[Math.min(H - 1, y + 1) * W + x] - f[Math.max(0, y - 1) * W + x]) * height;
      const n = 1 / Math.hypot(dx, dy, 1);
      const shade = Math.max(0, (-dx * lx - dy * ly + lz) * n);
      const v = 0.62 + shade * 0.42;
      d[i * 4] = Math.min(255, 233 * v); d[i * 4 + 1] = Math.min(255, 232 * v); d[i * 4 + 2] = Math.min(255, 226 * v); d[i * 4 + 3] = 255;
    }
    ctx.putImageData(img, 0, 0);
    for (const l of lines) { ctx.fillStyle = l.colour; ctx.fillRect(Math.round(l.x * (W - 1)), 0, 1, H); }
  };
  useEffect(() => { draw(azimuth); });
  return { ref, draw, W, H };
}

export function Relief({ grid, azimuth = 315, className = '', label, lines, sigma }: { grid: number[][]; azimuth?: number; className?: string; label: string; lines?: { x: number; colour: string }[]; sigma?: number }) {
  const { ref } = useRelief(grid, { azimuth, lines, sigma });
  return <canvas ref={ref} className={`rl-canvas ${className}`} role="img" aria-label={label} />;
}
