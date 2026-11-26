// Chart primitives for recorded evidence. Each one requires a caption and a denominator and states both; given no
// denominator or no values it draws nothing and says what is unavailable instead, never a zero.
// Coral marks only what a finding cites (`hot`); everything else is ink or ghost.

export interface Bar { label: string; value: number | null; hot?: boolean; note?: string }

function Unavailable({ what }: { what: string }) {
  return <p className="ap-chart__na">{what}</p>;
}

/** Ranked horizontal bars of recorded values over one recorded denominator (or an absolute scale with its unit). */
export function BarList({ bars, denominator, unit, caption, max: limit = 12, more, scale = 'max', bounded }: {
  bars: Bar[]; denominator: number | null; unit: string; caption: string; max?: number; more?: string;
  /** The values are a recorded measure bounded 0–1 (the caption names it); no denominator is stated. */
  bounded?: boolean;
  /** Bar length: relative to the largest shown value, to the denominator (counts out of a whole), or to 100 (percentages). */
  scale?: 'max' | 'denominator' | 'percent';
}) {
  const known = bars.filter((b) => typeof b.value === 'number' && Number.isFinite(b.value));
  if (!denominator || !known.length) return <Unavailable what={`${caption}: unavailable in this result`} />;
  const shown = known.slice(0, limit);
  const top = scale === 'denominator' ? denominator : scale === 'percent' ? 100 : Math.max(...shown.map((b) => b.value as number), 0) || 1;
  return (
    <figure className="ap-chart ap-bars">
      <ul aria-label={caption}>
        {shown.map((b) => (
          <li key={b.label} className={b.hot ? 'is-hot' : ''}>
            <span className="ap-bars__l">{b.label}</span>
            <span className="ap-bars__t" aria-hidden="true"><i style={{ width: `${Math.min(100, ((b.value as number) / top) * 100)}%` }} /></span>
            <span className="ap-bars__v">{(b.value as number).toLocaleString('en-US')}{unit === '%' ? '%' : ''}{b.note ? ` · ${b.note}` : ''}</span>
          </li>
        ))}
      </ul>
      <figcaption>{caption}{bounded ? '' : ` · denominator ${denominator.toLocaleString('en-US')}${unit && unit !== '%' ? ` ${unit}` : ''}`}{known.length > shown.length ? ` · ${shown.length} of ${known.length} shown${more ? `; all in ${more}` : ''}` : ''}</figcaption>
    </figure>
  );
}

/** One recorded count over its recorded denominator. */
export function ProportionBar({ count, denominator, caption, hot }: { count: number | null; denominator: number | null; caption: string; hot?: boolean }) {
  if (count == null || !denominator) return <Unavailable what={`${caption}: unavailable in this result`} />;
  const share = (count / denominator) * 100;
  return (
    <figure className="ap-chart ap-prop">
      <span className="ap-prop__t" aria-hidden="true"><i className={hot ? 'is-hot' : ''} style={{ width: `${Math.min(100, share)}%` }} /></span>
      <figcaption><b>{count.toLocaleString('en-US')}</b> of {denominator.toLocaleString('en-US')} · {share.toLocaleString('en-US', { maximumFractionDigits: 1 })}% · {caption}</figcaption>
    </figure>
  );
}

/** Parts of one recorded whole. Only for parts that partition the denominator; overlapping counts use BarList. */
export function StackedBar({ parts, denominator, caption }: { parts: { label: string; count: number; hot?: boolean }[]; denominator: number | null; caption: string }) {
  const sum = parts.reduce((t, p) => t + p.count, 0);
  if (!denominator || !parts.length || sum > denominator) return <Unavailable what={`${caption}: unavailable in this result`} />;
  return (
    <figure className="ap-chart ap-stack">
      <span className="ap-stack__t" role="img" aria-label={`${caption}: ${parts.map((p) => `${p.label} ${p.count}`).join(', ')} of ${denominator}`}>
        {parts.map((p, i) => <i key={p.label} className={`is-${i % 3} ${p.hot ? 'is-hot' : ''}`} style={{ width: `${(p.count / denominator) * 100}%` }} />)}
      </span>
      <figcaption>{parts.map((p) => `${p.label} ${p.count.toLocaleString('en-US')}`).join(' · ')} · of {denominator.toLocaleString('en-US')} · {caption}</figcaption>
    </figure>
  );
}
