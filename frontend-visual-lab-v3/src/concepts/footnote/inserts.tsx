// Small live inserts that sit inside a line of text like words. All drawn from real values.
import { useEffect, useState, type ReactNode } from 'react';
import { adult } from '../../fixture';
import { reducedMotion } from '../../shell/motion';

export function Spark({ label = 'hours_per_week distribution, 1 to 99 hours, fences at 32.5 and 52.5' }: { label?: string }) {
  const c = adult.hours.hist.counts, m = Math.max(...c);
  return (
    <span className="fn-ins fn-ins--spark" role="img" aria-label={label}>
      <svg viewBox="0 0 98 20" preserveAspectRatio="none">
        {c.map((v, i) => { const h = Math.max(0.6, Math.sqrt(v / m) * 18); const out = i + 1 < adult.hours.lower || i + 1 > adult.hours.upper; return <rect key={i} x={i} y={20 - h} width={0.8} height={h} className={out ? 'is-out' : ''} />; })}
      </svg>
    </span>
  );
}

export function Waffle() {
  const maj = Math.round(adult.majorityBaseline);
  return (
    <span className="fn-ins fn-ins--waffle" role="img" aria-label="Target classes: 76% at or below 50K, 24% above">
      {Array.from({ length: 50 }, (_, i) => <i key={i} className={i < maj / 2 ? '' : 'is-min'} />)}
    </span>
  );
}

export function RowChip() {
  const g = adult.conflicts[0];
  return (
    <span className="fn-ins fn-ins--row" aria-label={`Rows ${g.rows.join(' and ')} with identical features and different labels`}>
      <span><b>{g.rows[0].toLocaleString()}</b> 46 · Private · HS-grad · Craft-repair · <mark>{g.labels[0]}</mark></span>
      <span><b>{g.rows[1].toLocaleString()}</b> 46 · Private · HS-grad · Craft-repair · <mark>{g.labels[1]}</mark></span>
    </span>
  );
}

/** A number that unfolds into how it was made. */
export function Token({ value, lines, label }: { value: string; lines: [string, string][]; label: string }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="fn-tok-w">
      <button type="button" className={`fn-tok ${open ? 'is-open' : ''}`} aria-expanded={open} aria-label={`${value}: ${label}. Show calculation`} onClick={() => setOpen(!open)}>{value}</button>
      {open && <span className="fn-calc" role="note">{lines.map(([k, v]) => <span key={k}><em>{k}</em><b>{v}</b></span>)}</span>}
    </span>
  );
}

/** Cycles through inserts in place, the way a word can change inside a sentence. */
export function Cycle({ items, ms = 2600, label }: { items: ReactNode[]; ms?: number; label: string }) {
  const [i, setI] = useState(0);
  useEffect(() => {
    if (reducedMotion()) return;
    const t = setInterval(() => setI((k) => (k + 1) % items.length), ms);
    return () => clearInterval(t);
  }, [items.length, ms]);
  return <span className="fn-cycle" aria-label={label} key={i}>{items[i]}</span>;
}

export const fileChip = (name: string) => <span className="fn-ins fn-ins--file">{name}</span>;
