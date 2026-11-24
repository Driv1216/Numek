// Sources and ingestion (proposal step 3). For each source of a deployment:
// - freshness (from health);
// - the contract's declared fields (names and types only);
// - the producer watermark;
// - the funnel, which must reconcile: rows received = accepted + quarantined; facts published = new + duplicate,
//   with conflicting facts quarantined;
// - quarantine reasons with field names (never values);
// - recent batches.
import type { Deployment, Health, SourceFunnel, SourcesView } from './api';
import { Empty, Loading, Refused, useResource, when, words } from './parts';
import { navigate, onLink } from './router';

export function Sources({ deployment }: { deployment: string | null }) {
  const list = useResource<Deployment[]>('/deployments');
  if (list.error) return <Refused error={list.error} />;
  if (!list.data) return <Loading what="deployments" />;
  const chosen = deployment ?? list.data[0]?.id ?? null;
  return (
    <>
      <section className="op-head">
        <span className="op-k">Sources · ingestion</span>
        <h1>What arrived, and what happened to it</h1>
        <p>Every acknowledged batch is accounted for. Rows that fail the contract are quarantined with their reasons and the offending field names; their
          values stay encrypted and are never shown here.</p>
      </section>
      {list.data.length === 0 ? <Empty>No deployments are registered.</Empty> : (
        <>
          <div className="op-seg" role="group" aria-label="Deployment">
            {list.data.map((d) => <button key={d.id} type="button" aria-pressed={d.id === chosen} onClick={() => navigate(`/ops/sources/${d.id}`)}>{d.id}</button>)}
          </div>
          {chosen && <DeploymentSources key={chosen} deployment={chosen} />}
        </>)}
    </>
  );
}

function DeploymentSources({ deployment }: { deployment: string }) {
  const view = useResource<SourcesView>(`/deployments/${deployment}/sources`);
  const health = useResource<Health>(`/deployments/${deployment}/health`);
  if (view.error) return <Refused error={view.error} />;
  if (!view.data) return <Loading what="sources" />;
  if (view.data.sources.length === 0) return <Empty>No active sources on this deployment. Nothing is being ingested, so nothing is monitored.</Empty>;
  const lateness = view.data.allowed_lateness_ns;
  return (
    <>
      {view.data.sources.map((s) => {
        const fresh = health.data?.sources.find((h) => h.source === s.source);
        const silent = health.data?.conditions.some((c) => c.kind === 'source_silent' && c.source === s.source);
        return (
          <section key={s.source} className="op-sec op-source">
            <h2>{s.source} <span className="op-mono">contract v{s.contract_version} · {s.contract_digest.slice(0, 12)}…</span></h2>
            <dl className="op-facts">
              <div><dt>Freshness</dt><dd className={silent ? 'op-hot' : ''}>{!fresh ? '—' : silent ? `not monitored since ${when(fresh.last_received)}` : `last batch ${when(fresh.last_received)} · ${fresh.batches_last_day} in the last day`}</dd></div>
              <div><dt>Watermark</dt><dd>{s.watermark ? <>complete through {when(new Date(Number(s.watermark.through_tick) / 1e6).toISOString())} <span className="op-mono">(declared {when(s.watermark.updated_at)})</span></> : 'none declared · windows close after the allowed lateness'}</dd></div>
              <div><dt>Lateness</dt><dd>{lateness ? `${(Number(lateness) / 3600e9).toFixed(1)} h allowed` : 'no confirmed definition'} · {s.funnel.late_rows} late row{s.funnel.late_rows === 1 ? '' : 's'}</dd></div>
              <div><dt>Format</dt><dd className="op-mono">{s.format} · event time {s.event_time} · registered {when(s.registered_at)}</dd></div>
            </dl>

            <Funnel f={s.funnel} />

            <div className="op-split">
              <div>
                <h3>Quarantine reasons</h3>
                {s.quarantine_reasons.length === 0 ? <Empty>Nothing quarantined.</Empty> : (
                  <table className="op-table op-table--tight"><thead><tr><th>Reason</th><th>Rows</th><th>Fields</th></tr></thead>
                    <tbody>{s.quarantine_reasons.map((q) => <tr key={q.reason}><td>{words(q.reason)}</td><td className="op-mono">{q.rows}</td><td className="op-mono">{(q.fields ?? []).join(', ') || '—'}</td></tr>)}</tbody></table>)}
              </div>
              <div>
                <h3>Declared fields</h3>
                <table className="op-table op-table--tight"><thead><tr><th>Field</th><th>Type</th><th>Role</th></tr></thead>
                  <tbody>{Object.entries(s.fields).map(([name, f]) => <tr key={name}><td className="op-mono">{name}</td><td className="op-mono">{f.type}</td>
                    <td className="op-mono">{[f.identity && 'identity', f.required && 'required', f.probability && 'probability'].filter(Boolean).join(' · ') || '—'}</td></tr>)}</tbody></table>
                <p className="op-mono">Undeclared fields are dropped at parse time and counted ({s.funnel.values_dropped} values so far).</p>
              </div>
            </div>

            <h3>Recent batches</h3>
            <div className="op-scroll">
              <table className="op-table op-table--tight">
                <thead><tr><th>Batch</th><th>State</th><th>Rows in · accepted · quarantined</th><th>Facts new · duplicate · conflict</th><th>K</th><th>Received</th></tr></thead>
                <tbody>{s.batches.map((b) => {
                  const n = (k: string) => (typeof b.counts[k] === 'number' ? (b.counts[k] as number) : 0);
                  return <tr key={b.batch_id}><td className="op-mono">{b.batch_id}{b.mode === 'backfill' ? ' · backfill' : ''}</td>
                    <td className={['failed', 'quarantined'].includes(b.state) ? 'op-hot' : ''}>{words(b.state)}{b.error ? <span className="op-mono"> · {b.error}</span> : null}</td>
                    <td className="op-mono">{n('rows_received')} · {n('rows_accepted')} · {n('rows_quarantined')}{n('late_rows') ? ` · ${n('late_rows')} late` : ''}</td>
                    <td className="op-mono">{n('facts_new')} · {n('facts_duplicate')} · {n('facts_quarantined')}</td>
                    <td className="op-mono">{b.catalog_sequence ?? '—'}</td><td className="op-mono">{when(b.received_at)}</td></tr>;
                })}</tbody>
              </table>
            </div>
          </section>);
      })}
      <p className="op-mono">{view.data.qualification}</p>
      <p className="op-mono"><a href={`/ops/deployments/${deployment}`} onClick={onLink}>Open the deployment →</a></p>
    </>
  );
}

function Funnel({ f }: { f: SourceFunnel }) {
  const rows = Math.max(1, f.rows_received);
  const facts = Math.max(1, f.facts_new + f.facts_duplicate + f.facts_quarantined);
  const pct = (v: number, of: number) => `${(100 * v / of).toFixed(2)}%`;
  return (
    <div className="op-funnel" role="group" aria-label="Ingestion funnel">
      <div className="op-funnel__row">
        <span className="op-k">Rows · {f.batches} batch{f.batches === 1 ? '' : 'es'}</span>
        <div className="op-funnel__bar" aria-hidden="true"><i className="is-ok" style={{ width: pct(f.rows_accepted, rows) }} /><i className="is-hot" style={{ width: pct(f.rows_quarantined, rows) }} /></div>
        <span className="op-mono">{f.rows_received} received = {f.rows_accepted} accepted + <b className={f.rows_quarantined ? 'op-hot' : ''}>{f.rows_quarantined} quarantined</b>
          {' '}<b className={f.reconciled ? 'op-ok-t' : 'op-hot'}>{f.reconciled ? '✓ reconciled' : '✗ does not reconcile'}</b></span>
      </div>
      <div className="op-funnel__row">
        <span className="op-k">Facts</span>
        <div className="op-funnel__bar" aria-hidden="true"><i className="is-ok" style={{ width: pct(f.facts_new, facts) }} /><i className="is-dup" style={{ width: pct(f.facts_duplicate, facts) }} /><i className="is-hot" style={{ width: pct(f.facts_quarantined, facts) }} /></div>
        <span className="op-mono">{f.facts_new} new · {f.facts_duplicate} duplicate (already held) · <b className={f.facts_quarantined ? 'op-hot' : ''}>{f.facts_quarantined} conflicting, quarantined</b></span>
      </div>
      <p className="op-mono">By state: {Object.entries(f.by_state).map(([k, v]) => `${words(k)} ${v}`).join(' · ') || '—'}
        {f.producer_dropped ? <> · <b className="op-hot">{f.producer_dropped} rows dropped by the producer before sending (known loss)</b></> : ' · no known producer loss'}</p>
    </div>
  );
}
