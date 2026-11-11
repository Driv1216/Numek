import { useState } from 'react';
import { runs } from '../../fixture';
import { Dial, RowRange, runCols, type Col } from './dial';
import { questions } from './questions';

/** One instrument, one screen: questions left, the dial centre, the legend right, the row range along the foot. */
export function Instrument({ run, initial = 0, compact = false }: { run: string; initial?: number; compact?: boolean }) {
  const qs = questions[run] ?? [];
  const [qi, setQi] = useState(initial);
  const [hover, setHover] = useState<Col | null>(null);
  const rows = runCols[run].rows;
  const [range, setRange] = useState<[number, number]>([0, rows]);
  const q = qs[Math.min(qi, qs.length - 1)];
  const r = runs.find((x) => x.id === run)!;
  const inRange = (q?.marks ?? []).filter((m) => m >= range[0] && m <= range[1]).length;
  return (
    <div className={`in-inst ${compact ? 'is-compact' : ''}`}>
      <ol className="in-qs" aria-label="Questions">
        {qs.map((x, i) => (
          <li key={x.q}><button type="button" aria-pressed={i === qi} className={i === qi ? 'is-on' : ''} onClick={() => setQi(i)}><span>{String(i + 1).padStart(2, '0')}</span><em>{x.q}</em></button></li>
        ))}
      </ol>
      <div className="in-centre">
        <Dial run={run} mode={q?.mode ?? 'none'} hover={hover?.name} onHover={setHover} core={r.score == null ? ['—', 'no score defined'] : [r.score.toFixed(1), q?.mode === 'target' ? 'final · capped' : r.band ?? '']} />
        <p className="in-hint">hover a sector · pick a question · drag the range</p>
      </div>
      <aside className="in-legend" aria-live="polite">
        {hover ? (
          <>
            <span className="in-legend__k">Sector · {hover.kind}</span>
            <h3>{hover.name}</h3>
            <dl><div><dt>distinct</dt><dd>{hover.unique.toLocaleString()}</dd></div><div><dt>missing</dt><dd>{hover.missing.toLocaleString()}</dd></div>{hover.kind === 'numeric' && <><div><dt>range</dt><dd>{hover.min} – {hover.max}</dd></div><div><dt>quartiles</dt><dd>{hover.q1} · {hover.q3}</dd></div></>}{hover.target && <div><dt>role</dt><dd>target</dd></div>}</dl>
          </>
        ) : q ? (
          <>
            <span className="in-legend__k">Answer · {r.name}</span>
            <h3>{q.q}</h3>
            <dl>{q.answer.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
            <p>{q.note}</p>
            {q.marks && <p className="in-legend__m">{inRange} of {q.marks.length} rows in the selected range</p>}
            {q.json && <code>{q.json}</code>}
          </>
        ) : <p>{r.lead}.</p>}
      </aside>
      <div className="in-foot"><RowRange rows={rows} marks={q?.marks} range={range} onRange={setRange} /></div>
    </div>
  );
}
