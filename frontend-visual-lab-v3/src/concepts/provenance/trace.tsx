import { useEffect, useRef, useState } from 'react';
import { adult } from '../../fixture';
import { reducedMotion } from '../../shell/motion';
import { href } from '../../shell/router';

export const g = adult.conflicts[0];
export const rowA = [...adult.header.slice(0, 14).map((c) => String(g.features[c] ?? '?')), g.labels[0]];
export const rowB = [...rowA.slice(0, 14), g.labels[1]];
export const csvLine = rowA.join(',');

export const stages = [
  { k: 'Source', t: 'It begins as one line of a file.', s: `adult.csv · line 16,685 · sha256 ${adult.sha256.slice(0, 12)}…` },
  { k: 'Parse', t: 'DataTrust reads it into fifteen typed fields.', s: 'Six numeric features, eight categorical, one target.' },
  { k: 'Profile', t: 'Each value is measured against its column.', s: 'hours_per_week = 40, the most common value (46.69%), inside 32.5 – 52.5.' },
  { k: 'Compare', t: 'Another row turns out to be identical.', s: 'Row 34,343 matches on all fourteen features.' },
  { k: 'Conflict', t: 'Except for the answer.', s: '>50K and <=50K. Group 1 of 5 feature-identical groups that disagree.' },
  { k: 'Finding', t: 'The disagreement becomes a finding, with its evidence.', s: 'Potentially conflicting target labels · Moderate · 10 rows · no score effect.' },
  { k: 'Report', t: 'And it can always be traced back.', s: 'Priority action 1 and topic 6 of the report · HTML, PDF and JSON from one result.' },
];

/** Hero: real record cards threaded along an S-curve between two words (after Tracing Art). */
export function Thread({ n = 34 }: { n?: number }) {
  const [t, setT] = useState(0);
  useEffect(() => {
    if (reducedMotion()) return;
    let raf = 0; const t0 = performance.now();
    const tick = (now: number) => { setT(((now - t0) / 40000) % 1); raf = requestAnimationFrame(tick); };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);
  const rows = adult.sampleRows;
  const pt = (u: number) => {
    // cubic S from (0, .62) to (1, .38) in a unit box
    const p = [[0, 0.7], [0.36, -0.25], [0.64, 1.25], [1, 0.3]];
    const m = 1 - u;
    const x = m * m * m * p[0][0] + 3 * m * m * u * p[1][0] + 3 * m * u * u * p[2][0] + u * u * u * p[3][0];
    const y = m * m * m * p[0][1] + 3 * m * m * u * p[1][1] + 3 * m * u * u * p[2][1] + u * u * u * p[3][1];
    return { x, y };
  };
  return (
    <div className="pv-thread" aria-hidden="true">
      {Array.from({ length: n }, (_, i) => {
        const u = (i / n + t) % 1;
        const a = pt(u), b = pt(Math.min(1, u + 0.01));
        const ang = Math.atan2(b.y - a.y, b.x - a.x) * (180 / Math.PI);
        const depth = 0.62 + 0.42 * Math.sin(u * Math.PI);
        const r = rows[i % rows.length];
        const hit = i % 23 === 7;
        return (
          <span key={i} className={`pv-card ${hit ? 'is-hit' : ''} ${r[14] === '>50K' ? 'is-gt' : ''}`} style={{ left: `${a.x * 100}%`, top: `${a.y * 100}%`, transform: `translate(-50%, -50%) rotateY(${ang * 0.9}deg) rotateZ(${ang * 0.18}deg) scale(${depth})`, zIndex: Math.round(depth * 100), opacity: Math.min(1, Math.min(u, 1 - u) * 14) }}>
            <i>{hit ? g.rows[0] : (i % rows.length) + 1}</i>
            {r.slice(0, 5).map((v, k) => <b key={k}>{v}</b>)}
            <em>{hit ? g.labels[0] : r[14]}</em>
          </span>
        );
      })}
    </div>
  );
}

export function RecordCard({ values, other, stage, label = 'Row 16,684', className = '' }: { values: string[]; other?: string[]; stage: number; label?: string; className?: string }) {
  return (
    <article className={`pv-rec ${className}`} data-stage={stage}>
      <header><span>{label}</span><span>adult.csv</span></header>
      <dl>
        {adult.header.map((c, i) => {
          const diff = other && other[i] !== values[i];
          const prof = stage === 2 && c === 'hours_per_week';
          return (
            <div key={c} className={`${diff ? 'is-diff' : ''} ${prof ? 'is-prof' : ''} ${other && !diff ? 'is-same' : ''}`} style={{ ['--i' as string]: i }}>
              <dt>{c}</dt>
              <dd>{values[i]}{prof && <small>mode · 46.69% · inside fences</small>}</dd>
            </div>
          );
        })}
      </dl>
    </article>
  );
}

export function Header({ app = false }: { app?: boolean }) {
  return (
    <header className={`pv-head ${app ? 'pv-head--app' : ''}`}>
      <nav aria-label="Primary" className="pv-head__l">
        <a href={href('provenance', 'landing')}>Method</a>
        <a href={href('provenance', 'app')}>Traces</a>
      </nav>
      <a className="pv-wm" href={href('provenance', 'landing')}>NUMEK</a>
      <nav aria-label="Product" className="pv-head__r">
        <a href={href('provenance', 'results')}>Adult</a>
        <a className="pv-btn" href={href('provenance', 'app')}>Open DataTrust</a>
      </nav>
    </header>
  );
}

export function useStage(n: number) {
  const ref = useRef<HTMLDivElement>(null);
  const [p, setP] = useState(0);
  useEffect(() => {
    const on = () => {
      const el = ref.current; if (!el) return;
      const r = el.getBoundingClientRect();
      setP(Math.min(1, Math.max(0, -r.top / Math.max(1, r.height - innerHeight))));
    };
    on(); addEventListener('scroll', on, { passive: true }); addEventListener('resize', on);
    return () => { removeEventListener('scroll', on); removeEventListener('resize', on); };
  }, []);
  return [ref, p, Math.min(n - 1, Math.floor(p * n * 0.999))] as const;
}
