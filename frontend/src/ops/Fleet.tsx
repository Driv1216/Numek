// Fleet: coverage first, never a health score. One Modules tile per deployment, then the open incidents.
import { useEffect, useState } from 'react';
import { api, type Deployment, type DetectorRow, type Health, type IncidentSummary } from './api';
import { Empty, Loading, PriorityMark, Refused, useResource, when, words } from './parts';
import { onLink } from './router';

const STATUS_CELL: Record<string, string> = {
  formal: 'is-formal', descriptive: 'is-desc', descriptive_measures_only: 'is-desc', insufficient_power: 'is-weak',
  not_configured: 'is-none', stale: 'is-stale',
};

interface Row { deployment: Deployment; health?: Health; detectors?: DetectorRow[]; error?: unknown }

export function Fleet() {
  const deployments = useResource<Deployment[]>('/deployments');
  const incidents = useResource<{ items: IncidentSummary[] }>('/incidents?limit=200');
  const [rows, setRows] = useState<Row[] | null>(null);

  useEffect(() => {
    if (!deployments.data) return;
    Promise.all(deployments.data.map(async (deployment) => {
      try {
        const [health, detectors] = await Promise.all([api.get<Health>(`/deployments/${deployment.id}/health`),
          api.get<DetectorRow[]>(`/deployments/${deployment.id}/detectors`)]);
        return { deployment, health, detectors };
      } catch (error) { return { deployment, error }; }
    })).then(setRows);
  }, [deployments.data]);

  if (deployments.error) return <Refused error={deployments.error} />;
  if (!deployments.data || !rows) return <Loading what="the fleet" />;
  const open = (incidents.data?.items ?? []).filter((i) => !['resolved', 'merged'].includes(i.state));
  const alarms = rows.flatMap((r) => r.detectors ?? []).map((d) => d.plan.expected_false_alarms_per_30_days).filter((v): v is number => typeof v === 'number');
  const statement = rows.flatMap((r) => r.detectors ?? []).find((d) => d.plan.false_alarm_statement)?.plan.false_alarm_statement;

  return (
    <>
      <section className="op-head">
        <span className="op-k">Fleet · {rows.length} deployment{rows.length === 1 ? '' : 's'}</span>
        <h1>What is monitored, and how well</h1>
        {alarms.length > 0 && (
          <p className="op-fleetline"><b className="op-mono">{alarms.reduce((a, b) => a + b, 0).toFixed(2)}</b> expected false alarms per 30 days across the fleet
            {statement && <small>{statement}</small>}</p>
        )}
      </section>

      {rows.length === 0 ? <Empty>No deployments are registered. Nothing is monitored.</Empty> : (
        <div className="op-tiles">
          {rows.map(({ deployment, health, detectors, error }) => {
            const mine = open.filter((i) => i.deployment_id === deployment.id);
            const silent = health?.conditions.filter((c) => c.kind === 'source_silent') ?? [];
            const gaps = health?.conditions.filter((c) => c.kind !== 'source_silent') ?? [];
            return (
              <article key={deployment.id} className="op-tile">
                <header><span className="op-k">{deployment.system_id} · tier {deployment.tier}</span><h2><a href={`/ops/deployments/${deployment.id}`} onClick={onLink}>{deployment.name}</a></h2><span className="op-mono">{deployment.id}</span></header>
                {error != null ? <Refused error={error} /> : health && (
                  <>
                    <div className="op-cov" role="list" aria-label="Coverage map">
                      {Object.entries(health.coverage).map(([dimension, cell]) => (
                        <span key={dimension} role="listitem" className={`op-cov__c ${STATUS_CELL[cell.status] ?? ''}`} title={cell.note ?? (cell.detectors ?? []).join(', ')}>
                          <i aria-hidden="true" /><b>{words(dimension)}</b><em>{words(cell.status)}</em>
                        </span>))}
                    </div>
                    <dl className="op-facts">
                      <div><dt>Freshness</dt><dd>{health.sources.length === 0 ? 'no sources' : health.sources.map((s) => (
                        <span key={s.source} className={silent.some((c) => c.source === s.source) ? 'op-hot' : ''}>
                          {silent.some((c) => c.source === s.source) ? `not monitored since ${when(s.last_received)}` : `last batch ${when(s.last_received)}`}</span>))}</dd></div>
                      {health.windows && <div><dt>Maturity</dt><dd>{health.windows.maturity_backlog_windows} window{health.windows.maturity_backlog_windows === 1 ? '' : 's'} awaiting outcomes · next {when(health.windows.next_maturity)}</dd></div>}
                      <div><dt>Detectors</dt><dd>{(detectors ?? []).length === 0 ? 'none confirmed' : (detectors ?? []).map((d) => `${d.detector_id} ${words(d.standing)}`).join(' · ')}</dd></div>
                      {gaps.length > 0 && <div><dt>Conditions</dt><dd className="op-hot">{gaps.map((c) => words(c.kind)).join(' · ')}</dd></div>}
                    </dl>
                    <footer>
                      {mine.length === 0 ? <span className="op-mono">no open incidents</span> : mine.map((i) => (
                        <a key={i.id} href={`/ops/incidents/${i.id}`} onClick={onLink} className="op-chip"><PriorityMark p={i.priority} />#{i.number} · {words(i.state)}</a>))}
                    </footer>
                    <p className="op-statement">{health.statement}</p>
                  </>
                )}
              </article>
            );
          })}
        </div>
      )}
    </>
  );
}
