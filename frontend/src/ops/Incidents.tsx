// Incidents: a dense, scannable table (newest first), filterable by state.
import { useState } from 'react';
import type { IncidentSummary } from './api';
import { Empty, Loading, PriorityMark, Refused, useResource, when, words } from './parts';
import { onLink } from './router';

const FILTERS = ['open', 'all', 'resolved'] as const;

export function Incidents() {
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>('open');
  const list = useResource<{ items: IncidentSummary[] }>('/incidents?limit=200');
  if (list.error) return <Refused error={list.error} />;
  if (!list.data) return <Loading what="incidents" />;
  const items = list.data.items.filter((i) => filter === 'all' || (filter === 'resolved' ? i.state === 'resolved' : !['resolved', 'merged'].includes(i.state)));
  return (
    <>
      <section className="op-head"><span className="op-k">Incidents</span><h1>Incidents</h1></section>
      <div className="op-seg" role="group" aria-label="Filter">
        {FILTERS.map((f) => <button key={f} type="button" aria-pressed={filter === f} onClick={() => setFilter(f)}>{f}</button>)}
      </div>
      {items.length === 0 ? <Empty>No {filter === 'all' ? '' : filter} incidents. That is not evidence of health: check the fleet's coverage and freshness.</Empty> : (
        <table className="op-table">
          <thead><tr><th>#</th><th>Priority</th><th>Deployment</th><th>State</th><th>Why</th><th>Owner</th><th>Opened</th></tr></thead>
          <tbody>{items.map((i) => (
            <tr key={i.id}>
              <td className="op-mono"><a href={`/ops/incidents/${i.id}`} onClick={onLink}>#{i.number}</a></td>
              <td><PriorityMark p={i.priority} /></td><td>{i.deployment_id}</td>
              <td>{words(i.state)}{i.resolution ? ` · ${words(i.resolution)}` : ''}</td>
              <td className="op-mono">{i.rule}</td><td>{i.owner ?? '—'}</td><td className="op-mono">{when(i.opened_at)}</td>
            </tr>))}</tbody>
        </table>
      )}
    </>
  );
}
