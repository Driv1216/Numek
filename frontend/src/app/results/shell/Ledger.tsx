// The findings ledger: every finding, in recorded rank order, with its full recorded wording, a way into the evidence
// chapter that holds it and a verified way into the report. It adapts to the space it is given and never narrows the
// mosaic: a compact band above the mosaic, or a side column when the results body is wide enough (results.css).
import { useContext, useState } from 'react';
import type { LedgerFinding, Locator, Rank } from '../model';
import { InterpretationContext, MoreConclusive, useGuidance } from './Interpretation';

/** Shape and ink, not colour alone. Priorities: High filled, Moderate ring (coral); Low ink ring. Evidence meanings:
 *  violations a filled ink diamond, the rest an outline diamond. The word is always shown. */
export function RankMark({ rank }: { rank: Rank }) {
  const k = rank.kind === 'priority' ? `is-p-${rank.value.toLowerCase()}` : /violation/.test(rank.value) ? 'is-m-violation' : 'is-m-other';
  return <span className={`ap-rank ${k}`}><i aria-hidden="true" />{rank.label || 'Unranked'}</span>;
}

export function locatorText(l: Locator): string {
  if (l.kind === 'anchor') return 'Opens this finding in the report';
  if (l.kind === 'section') return 'Opens the report section that holds this finding';
  if (l.kind === 'index_position') return `Listed as finding ${l.value} of ${l.of} in the report’s finding index`;
  return 'This report version has no link for it; search the report for its title';
}

function Item({ f, full, onEvidence, onReport }: { f: LedgerFinding; full: boolean; onEvidence: (f: LedgerFinding) => void; onReport: (f: LedgerFinding) => void }) {
  return (
    <li className="ap-ledger__it" data-ref={f.ref ?? undefined}>
      <RankMark rank={f.rank} />
      <div className="ap-ledger__t">
        <b>{f.title}{f.context && <em className="ap-ledger__ctx">Context</em>}</b>
        {f.scope && <span className="ap-ledger__scope">{f.scope}</span>}
        {full && f.statement && <p>{f.statement}</p>}
        {full && f.nextAction && <p className="ap-ledger__next">{f.nextAction}</p>}
        {full && <WhyItMatters f={f} />}
      </div>
      <div className="ap-ledger__acts">
        {f.tile && <button type="button" className="ap-link" onClick={() => onEvidence(f)}>Evidence</button>}
        <button type="button" className="ap-link" onClick={() => onReport(f)} title={locatorText(f.locator)} aria-label={`${f.title}: in the report. ${locatorText(f.locator)}`}>In report</button>
      </div>
    </li>
  );
}

/** The first recorded "why it may matter" line for the finding, from interpretation_v1. */
function WhyItMatters({ f }: { f: LedgerFinding }) {
  const g = useGuidance(f.ref, f.context);
  return g?.impact.length ? <p className="ap-ledger__why"><em>Why it may matter</em> {g.impact[0]}</p> : null;
}

/** A clean result: what was completed, which review thresholds were not met, what is not established, and what further
 *  declarations would add; all from interpretation_v1, or the recorded coverage when there is none. */
function Clean({ clean }: { clean: { checked?: string; unknowns: string[] } }) {
  const { interp } = useContext(InterpretationContext);
  const c = interp?.clean;
  return (
    <div className="ap-ledger__clean">
      <b>No finding met its threshold within the completed scope.</b>
      <p>That is not a statement that the data is reliable.{c ? ` ${c.checks_completed.toLocaleString('en-US')} of ${c.checks_recorded.toLocaleString('en-US')} recorded checks completed.` : clean.checked ? ` ${clean.checked}.` : ''}
        {(c?.not_established.length ?? clean.unknowns.length) ? <> <a href="#ap-cov-h">What this does not establish</a> is listed under coverage.</> : null}</p>
      {!!c?.thresholds.length && (
        <details className="ap-guide__opts"><summary>Review thresholds that were not met · {c.thresholds.length}</summary>
          <ul>{c.thresholds.map((t) => <li key={t.rule}><b>{t.rule}</b><span>{t.threshold}</span></li>)}</ul></details>
      )}
      {!!interp?.more_conclusive.length && <><h3 className="ap-ledger__more-h">What would make this more conclusive</h3><MoreConclusive compact /></>}
    </div>
  );
}

export function FindingsLedger({ findings, clean, onEvidence, onReport }: {
  findings: LedgerFinding[]; clean: { checked?: string; unknowns: string[] }; onEvidence: (f: LedgerFinding) => void; onReport: (f: LedgerFinding) => void;
}) {
  const [all, setAll] = useState(false);
  const shown = all ? findings : findings.slice(0, 5);
  const ranks = findings.every((f) => f.rank.kind === 'priority') ? 'recorded priority' : 'recorded evidence type, in the report’s order';
  return (
    <section className="ap-ledger" aria-labelledby="ap-ledger-h">
      <div className="ap-ledger__h">
        <h2 id="ap-ledger-h" className="ap-sub">{findings.length ? `Findings · ${findings.length}` : 'Findings'}</h2>
        {findings.length > 0 && <span className="ap-ledger__order">By {ranks}</span>}
      </div>
      {findings.length ? (
        <>
          <ul className={`ap-ledger__list ${all ? 'is-all' : ''}`}>{shown.map((f) => <Item key={f.index} f={f} full={all} onEvidence={onEvidence} onReport={onReport} />)}</ul>
          {findings.length > 5 || !all
            ? <button type="button" className="ap-link ap-ledger__more" aria-expanded={all} onClick={() => setAll((x) => !x)}>{all ? 'Show fewer' : findings.length > 5 ? `Show all ${findings.length} findings, with their wording` : 'Show their wording'}</button>
            : null}
        </>
      ) : (
        <Clean clean={clean} />
      )}
    </section>
  );
}
