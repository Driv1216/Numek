import { useEffect, useRef } from 'react';
import { adult, fmt } from '../../shared/data';

/*
 * "Stills" are the concept's imagery: real Adult evidence rendered and graded
 * like film frames. No stock photography, no generated pictures.
 */

const CREAM = '#efe4cf';
const AMBER = '#e0a052';

export function StillPopulation() {
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
      const n0 = Math.round(adult.classes[0].count / 20);
      const n1 = Math.round(adult.classes[1].count / 20);
      const total = n0 + n1;
      const ratio = w / h;
      const rows = Math.ceil(Math.sqrt(total / ratio));
      const cols = Math.ceil(total / rows);
      const step = Math.min(w / cols, h / rows);
      const ox = (w - cols * step) / 2;
      const oy = (h - rows * step) / 2;
      for (let i = 0; i < total; i++) {
        const c = Math.floor(i / rows);
        const r = i % rows;
        const x = ox + c * step + step / 2;
        const y = oy + r * step + step / 2;
        // Soft focus away from the centre, like a shallow depth of field.
        const d = Math.hypot(x / w - 0.5, y / h - 0.5);
        ctx.globalAlpha = Math.max(0.18, 1 - d * 1.5);
        ctx.fillStyle = i < n0 ? CREAM : AMBER;
        ctx.beginPath();
        ctx.arc(x, y, step * (0.26 + d * 0.16), 0, Math.PI * 2);
        ctx.fill();
      }
    };
    draw();
    const ro = new ResizeObserver(draw);
    ro.observe(cv);
    return () => ro.disconnect();
  }, []);
  return <canvas ref={ref} className="sc-canvas" aria-label="Adult population, one dot per 20 rows, majority cream and minority amber" />;
}

export function StillHours() {
  const max = Math.max(...adult.hourBins.map((b) => b.low + b.high));
  const W = 400;
  const H = 260;
  const bw = W / adult.hourBins.length;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="sc-svg" preserveAspectRatio="none" role="img" aria-label="hours_per_week distribution">
      <defs>
        <linearGradient id="sc-leak" x1="0" x2="1">
          <stop offset="0" stopColor={AMBER} stopOpacity="0.35" />
          <stop offset="0.5" stopColor={AMBER} stopOpacity="0" />
        </linearGradient>
      </defs>
      {adult.hourBins.map((b, i) => {
        const t = b.low + b.high;
        const h = (t / max) * (H - 40);
        const hh = (b.high / max) * (H - 40);
        return (
          <g key={b.label}>
            <rect x={i * bw + 6} y={H - 20 - h} width={bw - 12} height={h - hh} fill={CREAM} opacity="0.88" />
            <rect x={i * bw + 6} y={H - 20 - hh} width={bw - 12} height={hh} fill={AMBER} />
          </g>
        );
      })}
      <rect width={W} height={H} fill="url(#sc-leak)" />
    </svg>
  );
}

export function StillConflict() {
  return (
    <div className="sc-cards" role="img" aria-label="CSV lines 850 and 22,763, identical features with different labels">
      {adult.conflictPair.map((r, i) => (
        <div key={r.row} className={`sc-card sc-card--${i}`}>
          <span className="sc-card-no">CSV line {fmt(r.row)}</span>
          <dl>
            <div>
              <dt>age</dt>
              <dd>{r.age}</dd>
            </div>
            <div>
              <dt>education</dt>
              <dd>{r.education}</dd>
            </div>
            <div>
              <dt>hours</dt>
              <dd>{r.hours}</dd>
            </div>
          </dl>
          <span className="sc-card-label">{r.label}</span>
        </div>
      ))}
    </div>
  );
}

export function StillMissing() {
  const fields = adult.missingness;
  return (
    <div className="sc-missing" role="img" aria-label="Missing values per column">
      {fields.map((m) => {
        const share = m.count / adult.rows;
        return (
          <div key={m.field} className="sc-missing-col">
            <div className="sc-missing-bar">
              <span style={{ height: `${Math.max(share * 100 * 6, 2)}%` }} />
            </div>
            <b>{fmt(m.count)}</b>
            <em>{m.field}</em>
          </div>
        );
      })}
      <p className="sc-missing-note">Gap height ×6 for legibility. 7.41% of rows miss at least one feature.</p>
    </div>
  );
}

export function StillColumn() {
  return (
    <div className="sc-column" role="img" aria-label="marital_status column name">
      <span>marital_status</span>
    </div>
  );
}

export const stillFor = (code: string) =>
  code === 'conflicting_target_labels' ? (
    <StillConflict />
  ) : code === 'target_imbalance' ? (
    <StillPopulation />
  ) : code === 'numeric_outlier_concentration' ? (
    <StillHours />
  ) : (
    <StillColumn />
  );

export function Frame({
  children,
  caption,
  className = '',
  style,
}: {
  children: React.ReactNode;
  caption?: string;
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <figure className={`sc-frame ${className}`} style={style}>
      <div className="sc-frame-inner">
        {children}
        <span className="sc-grain" aria-hidden="true" />
        <span className="sc-vignette" aria-hidden="true" />
      </div>
      {caption && <figcaption>{caption}</figcaption>}
    </figure>
  );
}
