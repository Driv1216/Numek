// interpretation_v1 on the dashboard. Every word comes from src/datatrust/interpretation.py through the companion, the
// same source the canonical reports use; nothing here writes interpretation of its own. The shell provides the
// interpretation once, and any finding block, in any composition, renders the recorded guidance for its finding.
import { createContext, useContext } from 'react';
import type { Composition, GuidanceItem, Interpretation } from '../model';
import { onLink } from '../../router';

export const InterpretationContext = createContext<{ interp: Interpretation | null; live: boolean; composition?: Composition }>({ interp: null, live: false });

/** The recorded guidance for a finding: by its reference, or for a contextual finding (recorded as
 *  `context.<code>.<columns>`) by its code. */
export function useGuidance(ref: string | null | undefined, context?: boolean): GuidanceItem | null {
  const { interp } = useContext(InterpretationContext);
  if (!interp || !ref) return null;
  if (!context && interp.findings[ref]) return interp.findings[ref];
  const key = Object.keys(interp.findings).find((k) => k.startsWith(`context.${ref}.`));
  return key ? interp.findings[key] : (interp.findings[ref] ?? null);
}

function Lines({ title, lines }: { title: string; lines: string[] }) {
  if (!lines.length) return null;
  return <div className="ap-guide__g"><h5>{title}</h5><ul>{lines.map((l) => <li key={l}>{l}</li>)}</ul></div>;
}

/** The finding's recorded guidance: what was observed, why it may matter, what to check first, the options with their
 *  conditions, and what it does not establish. Nothing is filled in for results recorded before guidance existed. */
export function GuidanceFor({ refKey, context }: { refKey: string | null | undefined; context?: boolean }) {
  const { interp } = useContext(InterpretationContext);
  const g = useGuidance(refKey, context);
  // A result recorded before guidance existed shows none; the outcome band's "earlier version" note says so once.
  if (!interp?.guidance_recorded || !g) return null;
  return (
    <div className="ap-guide">
      <Lines title="What was observed" lines={g.observed} />
      <Lines title="Why it may matter" lines={g.impact} />
      <Lines title="Check first" lines={g.investigate} />
      {g.options.length > 0 && (
        <details className="ap-guide__opts">
          <summary>Options · {g.options.length}</summary>
          <ul>{g.options.map((o) => (
            <li key={o.option}><b>{o.option}</b>
              <span><em>When</em> {o.prerequisites}</span>
              <span><em>Avoid when</em> {o.avoid_when}</span>
              <span><em>Verify</em> {o.verify}</span>
            </li>
          ))}</ul>
        </details>
      )}
      <Lines title="Not established" lines={g.unknowns} />
    </div>
  );
}

/** The summary sentences, in the order a reader needs them; the recorded statement when no interpretation exists. */
export function SummaryLead({ interp, fallback }: { interp: Interpretation | null | undefined; fallback?: string }) {
  if (interp?.summary.length) return <p className="ap-outcome__lead">{interp.summary.map((s) => s.text).join(' ')}</p>;
  return fallback ? <p className="ap-outcome__lead">{fallback}</p> : null;
}

const CONFIGURE: Partial<Record<Composition, string>> = {
  classification: '/app/core/configure', numeric: '/app/core/configure', profile: '/app/core/configure', annotation: '/app/core/configure',
  multilabel: '/app/core/configure', readiness: '/app/core/configure', comparison: '/app/m4/configure', structure: '/app/m4/configure',
  temporal: '/app/temporal/configure', text: '/app/text/configure', image: '/app/images/configure', cross: '/app/cross/configure',
};

/** Declarations that would let the analysis conclude more, each with what it makes possible. A live result links to its
 *  configuration; a saved one says how to run again. */
export function MoreConclusive({ compact }: { compact?: boolean }) {
  const { interp, live, composition } = useContext(InterpretationContext);
  const items = interp?.more_conclusive ?? [];
  if (!items.length) return null;
  const href = composition ? CONFIGURE[composition] : undefined;
  return (
    <div className={`ap-more-c ${compact ? 'is-compact' : ''}`}>
      <ul>{items.map((m) => <li key={m.key}><b>{m.label}</b><span>{m.why}</span></li>)}</ul>
      <p className="ap-muted">{live && href ? <a href={href} onClick={onLink}>Add these in the configuration and run again</a> : 'Supply these in a new run of this workflow; a saved result keeps what it recorded.'}</p>
    </div>
  );
}
