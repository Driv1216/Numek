// The incident workspace: what, where, since and why this priority; the evidence ladder by standing; the
// differential matrix; requirements and investigations; responses, execution evidence and verification (R1, R2
// and R3 kept separate; R4 never claimed); and the timeline. "As known at detection" shows the immutable dossier.
import { type ReactNode, useState } from 'react';
import {
  api, type Comparison, type ConditionRow, type Hypothesis, type IncidentView, type ProposalDetail, type Requirement, type Run,
  type Session, type SignalRow, type Standing,
} from './api';
import { Action, Empty, Glyph, Loading, PriorityMark, Refused, useResource, when, words } from './parts';

const TRANSITIONS: Record<string, string[]> = {
  open: ['acknowledged', 'investigating', 'resolved'], acknowledged: ['investigating', 'resolved'],
  investigating: ['response_proposed', 'resolved'], response_proposed: ['response_executing', 'investigating', 'resolved'],
  response_executing: ['verifying', 'investigating'], verifying: ['resolved', 'investigating'], resolved: ['reopened'],
  reopened: ['acknowledged', 'investigating', 'resolved'], merged: [],
};
const RESOLUTIONS = ['operational_recovery_observed', 'threshold_recovery_established', 'reference_noninferiority_established',
  'accepted_risk', 'operator_false_positive', 'monitoring_artifact', 'closed_without_recovery_evidence'];
const OPERATOR_RESOLUTIONS = ['accepted_risk', 'operator_false_positive', 'monitoring_artifact', 'closed_without_recovery_evidence'];
const LADDER: Standing[] = ['D', 'F', 'P', 'E'];
const LADDER_LABEL: Record<string, string> = { D: 'Deterministic violations', F: 'Formal sequential evidence', P: 'Practical effects (descriptive)', E: 'Estimates (named assumption)' };

export function Incident({ id, session }: { id: string; session: Session }) {
  const [asKnown, setAsKnown] = useState<'now' | 'detection'>('now');
  const view = useResource<IncidentView>(`/incidents/${id}?as_known=${asKnown}`);
  const can = (p: string) => session.permissions.includes(p);
  if (view.error) return <Refused error={view.error} />;
  if (!view.data) return <Loading what="the incident" />;
  const { incident, knowledge, events } = view.data;
  const members = knowledge.conditions.filter((c) => view.data!.members.includes(c.id) || asKnown === 'detection');
  const first = Math.min(...members.map((c) => c.first_window ?? Infinity));
  const impact = incident.priority_basis.impact;

  return (
    <article className="op-inc">
      <header className="op-inc__head">
        <span className="op-k">Incident · {incident.deployment_id}</span>
        <h1>#{incident.number} · {incident.deployment_id}{Number.isFinite(first) ? ` · since window ${first}` : ''}{impact ? ` · ${impact.affected_units} units` : ''}</h1>
        <p className="op-why"><PriorityMark p={incident.priority} /> <b>{incident.priority_basis.why}</b> <span className="op-mono">{incident.priority_basis.table} · {incident.priority_basis.rule}</span>
          {incident.priority_basis.override && <span className="op-mono"> · overridden from {incident.priority_basis.override.from}: {incident.priority_basis.override.reason}</span>}</p>
        {impact?.region && <p className="op-mono">Region {impact.region} ({impact.region_source_standing}) · share {impact.region_share == null ? 'unknown' : impact.region_share.toFixed(3)} · {impact.basis}</p>}
        <div className="op-inc__state">
          <span className="op-state">{words(incident.state)}{incident.resolution ? ` · ${words(incident.resolution)}` : ''}</span>
          <span className="op-mono">owner {incident.owner ?? 'unassigned'} · opened {when(incident.opened_at)}{incident.escalation_level ? ` · escalated ×${incident.escalation_level}` : ''}</span>
        </div>
        <div className="op-seg" role="group" aria-label="Knowledge state">
          <button type="button" aria-pressed={asKnown === 'now'} onClick={() => setAsKnown('now')}>Now · {view.data.as_known}</button>
          <button type="button" aria-pressed={asKnown === 'detection'} onClick={() => setAsKnown('detection')}>As known at detection · K {incident.catalog_sequence}</button>
        </div>
        {asKnown === 'now' && can('operate') && <Actions view={view.data} session={session} onDone={view.reload} />}
        <p className="op-mono op-exports">
          Report: <a href={api.reportUrl(id, 'shareable')} target="_blank" rel="noreferrer">shareable HTML</a>
          {can('evidence:protected:read') && <> · <a href={api.reportUrl(id, 'local')} target="_blank" rel="noreferrer">local HTML</a></>}
        </p>
      </header>

      <nav className="op-toc" aria-label="Sections"><a href="#evidence">Evidence</a><a href="#differential">Differential</a><a href="#investigations">Investigations</a><a href="#responses">Responses</a><a href="#recovery">Recovery</a><a href="#timeline">Timeline</a></nav>

      <Ladder conditions={members} signals={knowledge.signals} events={events} />
      {asKnown === 'now'
        ? <><Differential id={id} matrix={knowledge.differential} /><Investigations id={id} can={can} /><Responses id={id} can={can} me={session.principal.name} /></>
        : <section id="differential" className="op-sec"><h2>As known at detection</h2><p className="op-muted">The detection dossier (K {knowledge.catalog_sequence}, known at {when(knowledge.known_at)}) holds the signals, window evaluations, detectors, reference, health, identity standings and deployment events at opening. Hypotheses, investigations and responses came later; switch to Now to see them.</p></section>}
      <Recovery conditions={members} />
      <Timeline events={events} />
    </article>
  );
}

function Actions({ view, session, onDone }: { view: IncidentView; session: Session; onDone: () => void }) {
  const { incident } = view;
  const [resolution, setResolution] = useState(RESOLUTIONS[0]);
  const [reason, setReason] = useState('');
  const next = TRANSITIONS[incident.state] ?? [];
  const move = (to: string, extra: Record<string, unknown> = {}) => api.post(`/incidents/${incident.id}/transition`, { to, expected_revision: incident.revision, ...extra });
  return (
    <div className="op-acts">
      {next.filter((t) => t !== 'resolved').map((t) => <Action key={t} label={words(t)} run={() => move(t)} onDone={onDone} disabled={!api.canMutate()} />)}
      {incident.owner !== `principal:${session.principal.name}` && (
        <Action label="Assign to me" run={() => api.post(`/incidents/${incident.id}/assign`, { owner: `principal:${session.principal.name}`, expected_revision: incident.revision })} onDone={onDone} disabled={!api.canMutate()} />)}
      {next.includes('resolved') && (
        <details className="op-resolve">
          <summary>Resolve…</summary>
          <label>Resolution<select value={resolution} onChange={(e) => setResolution(e.target.value)}>{RESOLUTIONS.map((r) => <option key={r} value={r}>{words(r)}</option>)}</select></label>
          {OPERATOR_RESOLUTIONS.includes(resolution) && <label>Reason (required; an operator decision is never recovery)<input value={reason} onChange={(e) => setReason(e.target.value)} /></label>}
          <p className="op-muted">Outcome-supported resolutions need a member condition recovered with the matching claim; the server checks it.</p>
          <Action label="Resolve" tone="primary" run={() => move('resolved', { resolution, reason: reason || undefined })} onDone={onDone} disabled={!api.canMutate()} />
        </details>
      )}
      {!api.canMutate() && <span className="op-mono">This tab has no action token: sign out and in again to act.</span>}
    </div>
  );
}

function Ladder({ conditions, signals, events }: { conditions: ConditionRow[]; signals: SignalRow[]; events: IncidentView['events'] }) {
  const joined = new Map<string, Record<string, unknown>>();
  for (const e of events) if (e.kind === 'condition_joined') joined.set(String(e.payload.condition), e.payload);
  const firstSignal = (c: ConditionRow) => signals.find((s) => s.condition_id === c.id && s.payload.wording) ?? signals.find((s) => s.condition_id === c.id);
  return (
    <section id="evidence" className="op-sec">
      <h2>Evidence ladder</h2>
      <p className="op-muted">Conditions by evidence standing. A formal alarm concerns the included matured observed-label population only.</p>
      {conditions.length === 0 && <Empty>No member conditions.</Empty>}
      {LADDER.filter((s) => conditions.some((c) => c.standing === s)).map((s) => (
        <div key={s} className="op-rung">
          <h3><Glyph s={s} /> {LADDER_LABEL[s]}</h3>
          {conditions.filter((c) => c.standing === s).map((c) => {
            const signal = firstSignal(c);
            const join = joined.get(c.id);
            const link = join?.link as { strength?: string; jaccard?: number; shared_inputs?: string[] } | undefined;
            return (
              <div key={c.id} className="op-cond">
                <p className="op-cond__h"><b className="op-mono">{c.key}</b><span>{words(c.state)} · {c.severity} · {c.first_window == null ? 'not window-bound' : `windows ${c.first_window}–${c.last_window ?? c.first_window}`} · {c.signal_count} signal{c.signal_count === 1 ? '' : 's'}</span></p>
                {join ? <p className="op-mono">joined by {words(String(join.rule))}{link?.strength && words(link.strength) !== words(String(join.rule)) ? ` · ${words(link.strength)}` : ''}{link?.jaccard != null ? ` · J = ${link.jaccard.toFixed(2)}` : ''}{link?.shared_inputs ? ` · shares ${link.shared_inputs.join(', ')}` : ''} to the anchor</p>
                  : <p className="op-mono">anchor or detection member</p>}
                {signal?.payload.wording && <p className={`op-wording ${s === 'F' || s === 'D' ? 'is-hot' : ''}`}>{signal.payload.wording}</p>}
                {signal?.payload.population && <p className="op-mono">{signal.payload.population}</p>}
                {(signal?.payload.not_established || signal?.payload.assumptions) && (
                  <details><summary>What this does not establish · assumptions</summary>
                    {signal.payload.not_established && <p>Not established: {signal.payload.not_established.join('; ')}.</p>}
                    {signal.payload.assumptions && <p>Assumptions: {signal.payload.assumptions.join('; ')}.</p>}
                  </details>)}
                {c.recovery?.claim && c.state === 'recovered' && <p className="op-ok">Recovered · {c.recovery.claim}: {c.recovery.wording ?? c.recovery.interpretation}</p>}
              </div>
            );
          })}
        </div>
      ))}
    </section>
  );
}

function Differential({ id, matrix }: { id: string; matrix?: IncidentView['knowledge']['differential'] }) {
  const judged = useResource<{ hypotheses: Hypothesis[]; requirements: Requirement[] }>(`/incidents/${id}/hypotheses`);
  return (
    <section id="differential" className="op-sec">
      <h2>Differential</h2>
      {matrix ? (
        <>
          <p className="op-muted">{matrix.qualification}</p>
          <div className="op-scroll">
            <table className="op-table op-matrix">
              <thead><tr><th scope="col">Hypothesis</th>{matrix.columns.map((c) => <th key={c.observation} scope="col" title={c.observation}><span>{c.observation.slice(2).replace(/-/g, ' ')}</span><Glyph s={c.standing} /></th>)}</tr></thead>
              <tbody>{matrix.rows.map((r) => {
                const state = judged.data?.hypotheses.find((h) => h.hypothesis_id === r.hypothesis)?.state;
                return (
                  <tr key={r.hypothesis}>
                    <th scope="row"><b className="op-mono">{r.hypothesis}</b> {r.title}{state && <em className={`op-hstate is-${state}`}>{state}</em>}</th>
                    {matrix.columns.map((c) => { const v = r.cells[c.observation]; return <td key={c.observation} className={`op-cell ${v === '✓' ? 'is-yes' : v === '✗' ? 'is-no' : v === '?' ? 'is-unk' : ''}`} aria-label={v === '✓' ? 'consistent' : v === '✗' ? 'inconsistent' : v === '?' ? 'not evaluable' : 'not predicted'}>{v}</td>; })}
                  </tr>);
              })}</tbody>
            </table>
          </div>
          <p className="op-mono">✓ consistent with the prediction · ✗ inconsistent · ? not evaluable · blank: not predicted</p>
        </>
      ) : <Empty>No differential yet: it is computed with the first knowledge revision.</Empty>}
      {judged.error != null && <Refused error={judged.error} />}
      {judged.data && judged.data.requirements.length > 0 && (
        <>
          <h3>Information requirements</h3>
          <table className="op-table">
            <thead><tr><th>Observation</th><th>Status</th><th>Expected / what would make it available</th><th>For</th></tr></thead>
            <tbody>{judged.data.requirements.map((r) => (
              <tr key={r.observation}><td className="op-mono">{r.observation}</td><td>{r.status}</td><td>{r.eta ? `expected ${when(r.eta)} · ` : ''}{r.action ?? words(r.reason)}</td><td className="op-mono">{r.hypotheses.join(', ')}</td></tr>))}</tbody>
          </table>
        </>
      )}
    </section>
  );
}

/** One investigation run: shared by the incident workspace and the Investigations list. */
export function RunRow({ run: r, can, onDone, incident }: { run: Run; can: (p: string) => boolean; onDone: () => void; incident?: ReactNode }) {
  return (
    <tr>
      {incident !== undefined && <td>{incident}</td>}
      <td>{words(r.template)}</td><td className="op-mono">{r.tier} · {r.cost_minutes} min</td>
      <td>{words(r.state)}{r.stale_fraction != null ? ` · stale by ${(r.stale_fraction * 100).toFixed(1)}%` : ''}{r.error ? <><span className="op-mono"> · {r.error.code}</span><br /><span className="op-muted">{r.error.message}</span></> : null}</td>
      <td className="op-mono">{(r.reasoning.movable ?? []).map((m) => `${m.hypothesis}×${m.weight}`).join(' ') || r.reasoning.note || '—'}</td>
      <td className="op-mono">{Object.keys(r.result?.observations ?? {}).join(', ') || '—'}</td>
      <td>{r.state === 'awaiting_approval' && can('analyze') && <Action label={r.tier === 'restricted' ? 'Approve (reserve:consume)' : 'Approve'} run={() => api.post(`/investigations/${r.id}/approve`, {})} onDone={onDone} disabled={!api.canMutate() || (r.tier === 'restricted' && !can('reserve:consume'))} />}
        {r.state === 'planned' && can('analyze') && <Action label="Queue for workers" run={() => api.post(`/investigations/${r.id}/execute`, {})} onDone={onDone} disabled={!api.canMutate()} />}</td>
    </tr>
  );
}

function Investigations({ id, can }: { id: string; can: (p: string) => boolean }) {
  const runs = useResource<Run[]>(`/incidents/${id}/investigations`);
  return (
    <section id="investigations" className="op-sec">
      <h2>Investigations</h2>
      <p className="op-muted">Planned deterministically within budgets (30 automatic minutes per deployment per day, 5 automatic runs per incident). Confirm-tier runs need an approver; restricted runs need reserve:consume and are never automatic.</p>
      {can('analyze') && <div className="op-acts"><Action label="Plan discriminating investigations" tone="primary" run={() => api.post(`/incidents/${id}/investigations`, {})} onDone={runs.reload} disabled={!api.canMutate()} /></div>}
      {runs.error != null && <Refused error={runs.error} />}
      {runs.data && (runs.data.length === 0 ? <Empty>No investigations yet.</Empty> : (
        <table className="op-table">
          <thead><tr><th>Template</th><th>Tier</th><th>State</th><th>Why</th><th>Settled</th><th /></tr></thead>
          <tbody>{runs.data.map((r) => <RunRow key={r.id} run={r} can={can} onDone={runs.reload} />)}</tbody>
        </table>))}
    </section>
  );
}

function Responses({ id, can, me }: { id: string; can: (p: string) => boolean; me: string }) {
  const comparison = useResource<Comparison>(`/incidents/${id}/proposals`);
  if (comparison.error) return <section id="responses" className="op-sec"><h2>Responses</h2><Refused error={comparison.error} /></section>;
  if (!comparison.data) return <section id="responses" className="op-sec"><h2>Responses</h2><Loading what="responses" /></section>;
  return (
    <section id="responses" className="op-sec">
      <h2>Responses</h2>
      <p className="op-muted">{comparison.data.qualification}</p>
      {comparison.data.proposals.length === 0 ? <Empty>No response proposals.</Empty> : (
        <div className="op-props">{comparison.data.proposals.map((p) => <Proposal key={p.proposal} card={p} can={can} me={me} onDone={comparison.reload} />)}</div>)}
      {comparison.data.prior_mitigations.length > 0 && (
        <><h3>Previous mitigations on similar incidents</h3>
          <table className="op-table"><thead><tr><th>Similarity</th><th>Proposal</th><th>State</th></tr></thead>
            <tbody>{comparison.data.prior_mitigations.map((m, i) => <tr key={i}><td className="op-mono">{m.jaccard.toFixed(2)}</td><td>{m.title}</td><td>{words(m.state)}</td></tr>)}</tbody></table></>)}
    </section>
  );
}

/** One proposal card with its standings, verification and decision: shared with the Proposals list. */
export function Proposal({ card, can, me, onDone }: { card: Comparison['proposals'][number]; can: (p: string) => boolean; me: string; onDone: () => void }) {
  const detail = useResource<ProposalDetail>(`/proposals/${card.proposal}`);
  const [reason, setReason] = useState('');
  const mine = detail.data?.proposal.author === `principal:${me}`;
  return (
    <div className="op-prop">
      <p className="op-prop__h"><b>{card.title}</b><span className="op-mono">{words(card.kind)} · {words(card.state)} · strongest evidence {words(card.strongest_basis ?? 'none')} · approver {card.required_role}</span></p>
      {card.effects.length > 0 && <p>Expected: {card.effects.map((e) => `${words(e.metric)} → ${e.expected}${e.interval ? ` [${e.interval[0]}, ${e.interval[1]}]` : ''} (${words(e.basis)})`).join('; ')}</p>}
      <p className="op-mono">{card.prerequisites.map((r) => `${words(r.kind)} ${r.pass ? '✓' : '✗'}`).join(' · ')}</p>
      {card.risks.length > 0 && <p>Risks: {card.risks.join('; ')}</p>}
      {detail.data && Object.keys(detail.data.standings).length > 0 && (
        <table className="op-table op-table--tight"><thead><tr><th>Execution evidence</th><th>Outcome</th><th>Kind</th></tr></thead>
          <tbody>{Object.entries(detail.data.standings).map(([k, v]) => <tr key={k}><td>{words(k)}</td><td>{v.outcome}</td><td className="op-mono">{v.evidence_kind}</td></tr>)}</tbody></table>)}
      {detail.data && detail.data.verification.length > 0 && (
        <table className="op-table op-table--tight"><thead><tr><th>Claim</th><th>State</th><th>From window</th><th>Meaning</th></tr></thead>
          <tbody>{detail.data.verification.map((v) => <tr key={v.claim_id}><td className="op-mono">{v.claim} · {v.claim_id}</td><td>{words(v.state)}</td><td className="op-mono">{v.start_window ?? '—'}</td><td>{v.result?.wording ?? v.result?.interpretation ?? ''}</td></tr>)}</tbody></table>)}
      <p className="op-mono">{card.causal_claim}</p>
      {card.state === 'submitted' && can('intervention:approve') && detail.data && (
        <div className="op-acts">
          {mine ? <span className="op-mono">You wrote this proposal; another approver must decide.</span> : <>
            <Action label="Approve" tone="primary" title="Records your approval. Changes nothing in production." run={() => api.post(`/proposals/${card.proposal}/decision`, { decision: 'approved', expected_revision: detail.data!.proposal.revision })} onDone={onDone} disabled={!api.canMutate()} />
            <input aria-label="Reason for rejecting" placeholder="Reason (to reject)" value={reason} onChange={(e) => setReason(e.target.value)} />
            <Action label="Reject" run={() => api.post(`/proposals/${card.proposal}/decision`, { decision: 'rejected', reason, expected_revision: detail.data!.proposal.revision })} onDone={onDone} disabled={!api.canMutate() || !reason} />
            <span className="op-mono">Approval records your decision. It changes nothing in production.</span></>}
        </div>)}
      {can('operate') && detail.data && <AfterApproval id={card.proposal} state={card.state} onDone={() => { detail.reload(); onDone(); }} />}
    </div>
  );
}

/** The operator's steps after approval. NUMEK still changes nothing: the customer executes from the handoff, and
 * each step records evidence of what the customer did, kept apart from the hypothetical replay. */
function AfterApproval({ id, state, onDone }: { id: string; state: string; onDone: () => void }) {
  const [executed, setExecuted] = useState('');
  if (state === 'approved') return (
    <div className="op-acts"><Action label="Issue execution handoff" run={() => api.post(`/proposals/${id}/handoff`)} onDone={onDone} disabled={!api.canMutate()} />
      <span className="op-mono">An immutable, digest-bound packet for the customer to execute. Nothing is deployed by NUMEK.</span></div>);
  if (state === 'handed_off') return (
    <div className="op-acts">
      <label className="op-inline"><span className="op-mono">Customer executed at (UTC)</span><input type="datetime-local" value={executed} onChange={(e) => setExecuted(e.target.value)} /></label>
      <Action label="Record declared execution" disabled={!api.canMutate() || !executed} run={() => api.post(`/proposals/${id}/execution`, { executed_at: `${executed}:00Z` })} onDone={onDone} />
      <span className="op-mono">Records execution_declared and starts verification. A declaration is the weakest execution standing.</span></div>);
  if (state === 'executing' || state === 'verifying') return (
    <div className="op-acts"><Action label="Check identity against the handoff" run={() => api.post(`/proposals/${id}/standings/identity`)} onDone={onDone} disabled={!api.canMutate()} />
      <span className="op-mono">Compares identities declared by batches received since execution with the handoff's expected identity.</span></div>);
  return null;
}

function Recovery({ conditions }: { conditions: ConditionRow[] }) {
  const by = (claim: string) => conditions.filter((c) => c.state === 'recovered' && c.recovery?.claim === claim).map((c) => c.key);
  const rows: [string, string, string[]][] = [['R1', 'Operational recovery observed (no outcome evidence)', by('R1')], ['R2', 'Threshold recovery established', by('R2')], ['R3', 'Reference non-inferiority established', by('R3')]];
  return (
    <section id="recovery" className="op-sec">
      <h2>Recovery claims</h2>
      <table className="op-table"><tbody>
        {rows.map(([k, label, keys]) => <tr key={k}><th scope="row" className="op-mono">{k}</th><td>{label}</td><td className="op-mono">{keys.length ? keys.join(', ') : 'none'}</td></tr>)}
        <tr><th scope="row" className="op-mono">R4</th><td>Causal effect of an intervention</td><td className="op-mono">not claimed</td></tr>
      </tbody></table>
      <p className="op-muted">An absent alarm is never recovery. R2 and R3 concern the average conditional risk since verification started, not current risk.</p>
    </section>
  );
}

/** The from → to of a transition (incident or hypothesis), and its reason when one was given. */
function detail(payload: unknown) {
  const p = (payload ?? {}) as { from?: string; to?: string; hypothesis?: string; reason?: string | null };
  if (!p.to) return null;
  return <span className="op-mono"> · {p.hypothesis ? `${p.hypothesis} ` : ''}{p.from ? `${words(p.from)} → ` : ''}{words(p.to)}{p.reason ? ` (${p.reason})` : ''}</span>;
}

function Timeline({ events }: { events: IncidentView['events'] }) {
  return (
    <section id="timeline" className="op-sec">
      <h2>Timeline</h2>
      <table className="op-table op-table--tight"><thead><tr><th>When</th><th>Event</th><th>By</th></tr></thead>
        <tbody>{[...events].reverse().map((e) => <tr key={e.seq}><td className="op-mono">{when(e.at)}</td><td>{words(e.kind)}{detail(e.payload)}</td><td className="op-mono">{e.actor}</td></tr>)}</tbody></table>
    </section>
  );
}
