// The coverage ledger: what did not complete, what was bounded, what was excluded or does not apply, what was not
// requested, and the methodology notes, the no-score reason first. Consequential groups open by default.
import { useContext } from 'react';
import type { Coverage as C, CoverageItem } from '../model';
import { InterpretationContext, MoreConclusive } from './Interpretation';

function Group({ title, items, open, note }: { title: string; items: CoverageItem[]; open?: boolean; note?: string }) {
  if (!items.length) return null;
  return (
    <details className="ap-cov__g" open={open || undefined}>
      <summary>{title} <span>{items.length}</span></summary>
      {note && <p className="ap-muted">{note}</p>}
      <ul className="nk-ch__cov">{items.map((x, i) => <li key={`${x.text}:${i}`}>{x.text}{x.reason ? <span> — {x.reason}</span> : null}</li>)}</ul>
    </details>
  );
}

/** Declarations that would let the analysis conclude more (interpretation_v1). Shown for results with findings; a clean
 *  result shows them in the findings ledger instead, so they appear once. */
function Conclusive() {
  const { interp } = useContext(InterpretationContext);
  const n = interp?.more_conclusive.length ?? 0;
  if (!n || interp?.clean) return null;
  return <details className="ap-cov__g" open><summary>What would make this more conclusive <span>{n}</span></summary><MoreConclusive /></details>;
}

export function CoverageLedger({ c, unknowns }: { c: C; unknowns: string[] }) {
  return (
    <section className="ap-cov" aria-labelledby="ap-cov-h">
      <h2 id="ap-cov-h" className="ap-sub">Coverage and methodology</h2>
      {c.completed && <p className="ap-muted">{c.completed}.</p>}
      <Group title="Did not complete" items={c.notCompleted} open note="No conclusion is drawn for these; completed evidence is shown." />
      <Group title="Bounded searches" items={c.bounded} open note="Planned limits on how much was searched. They are coverage limits, not failures." />
      <Conclusive />
      <Group title="What this does not establish" items={unknowns.map((u) => ({ text: u }))} />
      <Group title="Excluded for a precondition" items={c.excluded} />
      <Group title="Not applicable to this data" items={c.notApplicable} />
      <Group title="Not requested" items={c.notRequested} />
      <Group title="Methodology" items={c.methodology} />
    </section>
  );
}
