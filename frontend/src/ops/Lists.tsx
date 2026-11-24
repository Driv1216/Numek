// Investigations and Proposals across incidents (proposal step 3). Both reuse the workspace's components: the
// same run row (with an incident column), and the same proposal card, loaded from its incident's comparison so
// prerequisites are re-checked exactly as in the workspace. Approving a proposal records a decision only.
import { useState } from 'react';
import type { Comparison, ProposalListItem, RunListItem, Session } from './api';
import { Proposal, RunRow } from './Incident';
import { Empty, Loading, PriorityMark, Refused, useResource, when, words } from './parts';
import { onLink } from './router';

const RUN_FILTERS = { attention: ['awaiting_approval', 'planned', 'running'], all: null, completed: ['completed', 'reused'], failed: ['failed', 'refused'] } as const;

export function InvestigationsList({ session }: { session: Session }) {
  const [filter, setFilter] = useState<keyof typeof RUN_FILTERS>('attention');
  const list = useResource<{ items: RunListItem[] }>('/investigations?limit=200');
  const can = (p: string) => session.permissions.includes(p);
  if (list.error) return <Refused error={list.error} />;
  if (!list.data) return <Loading what="investigations" />;
  const states = RUN_FILTERS[filter] as readonly string[] | null;
  const items = list.data.items.filter((r) => !states || states.includes(r.state));
  const minutes = list.data.items.filter((r) => r.tier === 'auto' && ['completed', 'running'].includes(r.state)).reduce((a, r) => a + r.cost_minutes, 0);
  return (
    <>
      <section className="op-head">
        <span className="op-k">Investigations · {list.data.items.length} run{list.data.items.length === 1 ? '' : 's'}</span>
        <h1>Investigations across incidents</h1>
        <p>Runs are planned per incident from the templates that can move its open hypotheses. Automatic runs are descriptive and stay within budget
          ({minutes.toFixed(1)} automatic minutes used in this list); confirm-tier runs wait for an analyst; restricted runs consume the sealed reserve
          and need reserve:consume.</p>
      </section>
      <div className="op-seg" role="group" aria-label="Filter">
        {(Object.keys(RUN_FILTERS) as (keyof typeof RUN_FILTERS)[]).map((f) => <button key={f} type="button" aria-pressed={filter === f} onClick={() => setFilter(f)}>{words(f === 'attention' ? 'needs_attention' : f)}</button>)}
      </div>
      {items.length === 0 ? <Empty>No {filter === 'all' ? '' : words(filter === 'attention' ? 'waiting or running' : filter)} investigations.</Empty> : (
        <div className="op-scroll">
          <table className="op-table">
            <thead><tr><th>Incident</th><th>Template</th><th>Tier</th><th>State</th><th>Why</th><th>Settled</th><th /></tr></thead>
            <tbody>{items.map((r) => <RunRow key={r.id} run={r} can={can} onDone={list.reload}
              incident={<><a href={`/ops/incidents/${r.incident_id}`} onClick={onLink} className="op-mono">#{r.incident_number}</a> <PriorityMark p={r.priority} /><br /><span className="op-mono">{r.deployment_id} · {when(r.created_at)}</span></>} />)}</tbody>
          </table>
        </div>)}
    </>
  );
}

const PROPOSAL_FILTERS = { open: ['draft', 'submitted', 'approved', 'handed_off', 'executing', 'verifying'], decided: ['approved', 'rejected'], closed: ['verified', 'not_verified', 'rejected', 'withdrawn'], all: null } as const;

export function ProposalsList({ session }: { session: Session }) {
  const [filter, setFilter] = useState<keyof typeof PROPOSAL_FILTERS>('open');
  const [open, setOpen] = useState<string | null>(null);
  const list = useResource<{ items: ProposalListItem[] }>('/proposals?limit=200');
  if (list.error) return <Refused error={list.error} />;
  if (!list.data) return <Loading what="proposals" />;
  const states = PROPOSAL_FILTERS[filter] as readonly string[] | null;
  const items = list.data.items.filter((p) => !states || states.includes(p.state));
  const waiting = list.data.items.filter((p) => p.state === 'submitted').length;
  return (
    <>
      <section className="op-head">
        <span className="op-k">Proposals · {waiting} awaiting a decision</span>
        <h1>Response proposals</h1>
        <p>NUMEK never changes production. Approving records a decision; the customer executes the change from the handoff, and execution evidence and
          recovery are tracked separately. Hypothetical replay is never merged with what happened after execution.</p>
      </section>
      <div className="op-seg" role="group" aria-label="Filter">
        {(Object.keys(PROPOSAL_FILTERS) as (keyof typeof PROPOSAL_FILTERS)[]).map((f) => <button key={f} type="button" aria-pressed={filter === f} onClick={() => setFilter(f)}>{f}</button>)}
      </div>
      {items.length === 0 ? <Empty>No {filter === 'all' ? '' : filter} proposals.</Empty> : (
        <table className="op-table">
          <thead><tr><th>Incident</th><th>Proposal</th><th>State</th><th>Evidence</th><th>Approver</th><th>Updated</th><th /></tr></thead>
          <tbody>{items.map((p) => (
            <tr key={p.id} className={open === p.id ? 'is-open' : ''}>
              <td><a href={`/ops/incidents/${p.incident_id}`} onClick={onLink} className="op-mono">#{p.incident_number}</a> <PriorityMark p={p.priority} /><br /><span className="op-mono">{p.deployment_id}</span></td>
              <td><b>{p.title}</b><br /><span className="op-mono">{words(p.kind)} · by {p.author.replace(/^principal:/, '')}</span></td>
              <td>{words(p.state)}</td>
              <td className="op-mono">{p.evidence_basis.map(words).join(' · ') || '—'}</td>
              <td className="op-mono">{p.required_role}</td>
              <td className="op-mono">{when(p.updated_at)}</td>
              <td><button type="button" className="op-btn" aria-expanded={open === p.id} onClick={() => setOpen(open === p.id ? null : p.id)}>{open === p.id ? 'Close' : 'Open'}</button></td>
            </tr>))}</tbody>
        </table>)}
      {open && (() => {
        const item = list.data!.items.find((p) => p.id === open);
        return item ? <ProposalPanel key={open} item={item} session={session} onDone={list.reload} /> : null;
      })()}
    </>
  );
}

function ProposalPanel({ item, session, onDone }: { item: ProposalListItem; session: Session; onDone: () => void }) {
  const comparison = useResource<Comparison>(`/incidents/${item.incident_id}/proposals`);
  const can = (p: string) => session.permissions.includes(p);
  const card = comparison.data?.proposals.find((p) => p.proposal === item.id);
  return (
    <section className="op-sec">
      <h2>#{item.incident_number} · {item.title}</h2>
      {comparison.error != null ? <Refused error={comparison.error} /> : !comparison.data ? <Loading what="the proposal" /> : !card
        ? <Empty>This proposal is withdrawn; it no longer appears in its incident's comparison.</Empty>
        : <div className="op-props"><Proposal card={card} can={can} me={session.principal.name} onDone={() => { comparison.reload(); onDone(); }} /></div>}
      <p className="op-mono"><a href={`/ops/incidents/${item.incident_id}`} onClick={onLink}>Compare with the incident's other responses →</a></p>
    </section>
  );
}
