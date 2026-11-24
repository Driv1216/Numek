// Deployments: the list, and one deployment's tiles. The tiles show:
// - the identity-standings ladder;
// - definition versions;
// - detectors with standing, power and lag;
// - label maturity;
// - the estimator ledger;
// - region exposure;
// - the window series, drawn once in the line language, with alarm windows marked in coral.
import {
  type Deployment, type DetectorRow, type EstimatesView, type Health, type IdentityView, type DefinitionVersion, type WindowsView,
} from './api';
import { Empty, Loading, Refused, useResource, when, words } from './parts';
import { onLink } from './router';

export function Deployments() {
  const list = useResource<Deployment[]>('/deployments');
  if (list.error) return <Refused error={list.error} />;
  if (!list.data) return <Loading what="deployments" />;
  return (
    <>
      <section className="op-head"><span className="op-k">Deployments</span><h1>Deployments</h1></section>
      {list.data.length === 0 ? <Empty>No deployments are registered.</Empty> : (
        <table className="op-table">
          <thead><tr><th>Deployment</th><th>System</th><th>Tier</th><th>Registered identity</th><th>Registered</th></tr></thead>
          <tbody>{list.data.map((d) => (
            <tr key={d.id}><td><a href={`/ops/deployments/${d.id}`} onClick={onLink}>{d.name}</a> <span className="op-mono">{d.id}</span></td>
              <td className="op-mono">{d.system_id}</td><td className="op-mono">{d.tier}</td>
              <td className="op-mono">{Object.entries(d.registered_identity ?? {}).filter(([k]) => k !== 'predictor_spec').map(([k, v]) => `${k} ${String(v)}`).join(' · ') || 'none'}</td>
              <td className="op-mono">{when(d.created_at)}</td></tr>))}</tbody>
        </table>)}
    </>
  );
}

const OUTCOME_CLASS: Record<string, string> = { established: 'is-yes', failed: 'is-fail', not_evaluable: 'is-unk' };

export function DeploymentPage({ id }: { id: string }) {
  const health = useResource<Health>(`/deployments/${id}/health`);
  const detectors = useResource<DetectorRow[]>(`/deployments/${id}/detectors`);
  const identity = useResource<IdentityView>(`/deployments/${id}/identity`);
  const definitions = useResource<DefinitionVersion[]>(`/deployments/${id}/definitions`);
  const estimates = useResource<EstimatesView>(`/deployments/${id}/estimates`);
  const series = useResource<WindowsView>(`/deployments/${id}/windows?limit=26`);
  const signals = useResource<{ items: { window_index: number | null; source: string; payload: { kind?: string } }[] }>(`/deployments/${id}/signals?limit=500`);
  if (health.error) return <Refused error={health.error} />;
  if (!health.data) return <Loading what="the deployment" />;
  const plans = new Map((detectors.data ?? []).map((d) => [d.detector_id, d]));
  const alarmWindows = new Set((signals.data?.items ?? []).filter((s) => s.payload.kind === 'sequential_alarm' && s.window_index != null).map((s) => s.window_index as number));
  const regions = (() => {
    const last = [...(series.data?.windows ?? [])].reverse().find((w) => w.close && Object.keys(w.close.region_shares).length);
    return last?.close ? { window: last.window, shares: last.close.region_shares } : null;
  })();

  return (
    <>
      <section className="op-head">
        <span className="op-k">Deployment · <a href="/ops/deployments" onClick={onLink}>all deployments</a></span>
        <h1>{id}</h1>
        <p className="op-statement">{health.data.statement}</p>
      </section>
      <div className="op-tiles op-tiles--wide">
        <article className="op-tile op-tile--span">
          <header><span className="op-k">Window series</span><h2>Selected units per closed window</h2></header>
          {series.error != null ? <Refused error={series.error} /> : !series.data ? <Loading what="windows" /> :
            <Series windows={series.data.windows} alarms={alarmWindows} />}
        </article>

        <article className="op-tile">
          <header><span className="op-k">Identity</span><h2>Standings ladder</h2></header>
          {identity.error != null ? <Refused error={identity.error} /> : !identity.data ? <Loading what="identity" /> : (
            <>
              <ol className="op-ladder">{identity.data.ladder.map((step) => {
                const row = identity.data!.latest.find((r) => r.standing === step);
                return <li key={step} className={row ? OUTCOME_CLASS[row.outcome] ?? '' : 'is-none'}><i aria-hidden="true" /><b>{words(step)}</b><em>{row ? `${words(row.outcome)} · ${when(row.recorded_at)}` : 'no evidence recorded'}</em></li>;
              })}</ol>
              <p className="op-mono">{identity.data.qualification}</p>
            </>)}
        </article>

        <article className="op-tile">
          <header><span className="op-k">Detectors</span><h2>Standing, power and lag</h2></header>
          {(health.data.detectors ?? []).length === 0 ? <Empty>No detectors on the confirmed definition.</Empty> : (
            <table className="op-table op-table--tight"><thead><tr><th>Detector</th><th>Standing</th><th>m₀ · α</th><th>Units · alarms</th><th>Lag</th></tr></thead>
              <tbody>{(health.data.detectors ?? []).map((d) => {
                const plan = plans.get(d.id)?.plan as Record<string, unknown> | undefined;
                return <tr key={d.id}><td className="op-mono">{d.id}<br />{d.kind} · {words(d.statistic)}</td><td>{words(d.standing)}<br /><span className="op-mono">{words(d.power ?? '')}</span></td>
                  <td className="op-mono">{typeof plan?.m0 === 'number' ? plan.m0.toFixed(4) : '—'} · {typeof plan?.alpha === 'number' ? plan.alpha.toExponential(2) : '—'}</td>
                  <td className="op-mono">{d.units} · <span className={d.alarms ? 'op-hot' : ''}>{d.alarms}</span>{d.late_excluded ? ` · ${d.late_excluded} late` : ''}</td>
                  <td className="op-mono">{d.lag_windows ?? '—'}</td></tr>;
              })}</tbody></table>)}
        </article>

        <article className="op-tile">
          <header><span className="op-k">Label maturity</span><h2>Outcomes still to arrive</h2></header>
          {health.data.windows ? (
            <dl className="op-facts">
              <div><dt>Closed</dt><dd>through window {health.data.windows.last_closed ?? '—'} (expected {health.data.windows.expected_closed})</dd></div>
              <div><dt>Matured</dt><dd>through window {health.data.windows.last_matured ?? '—'} (expected {health.data.windows.expected_matured})</dd></div>
              <div><dt>Backlog</dt><dd>{health.data.windows.maturity_backlog_windows} window{health.data.windows.maturity_backlog_windows === 1 ? '' : 's'}</dd></div>
              <div><dt>Next</dt><dd>{when(health.data.windows.next_maturity)}</dd></div>
            </dl>) : <Empty>No confirmed definition.</Empty>}
          <p className="op-mono">Outcome detectors cannot alarm before their windows mature; outcome-free evidence covers the gap.</p>
        </article>

        <article className="op-tile">
          <header><span className="op-k">Estimators · ○ standing E</span><h2>Accountability ledger</h2></header>
          {estimates.error != null ? <Refused error={estimates.error} /> : !estimates.data ? <Loading what="estimates" /> :
            Object.keys(estimates.data.estimators).length === 0 ? <Empty>No outcome-free estimators are declared.</Empty> : (
              <>
                <table className="op-table op-table--tight"><thead><tr><th>Estimator</th><th>Matched</th><th>Bias</th><th>Exceedances</th></tr></thead>
                  <tbody>{Object.entries(estimates.data.estimators).map(([name, e]) => (
                    <tr key={name}><td>{words(name)}<br /><span className="op-mono">{words(e.assumption)}</span></td><td className="op-mono">{e.summary.matched_windows}</td>
                      <td className="op-mono">{e.summary.mean_signed_bias == null ? '—' : e.summary.mean_signed_bias.toFixed(3)}</td>
                      <td className="op-mono"><span className={e.summary.exceedances ? 'op-hot' : ''}>{e.summary.exceedances ?? 0}</span></td></tr>))}</tbody></table>
                <p className="op-mono">{estimates.data.qualification}</p>
              </>)}
        </article>

        <article className="op-tile">
          <header><span className="op-k">Regions</span><h2>Exposure</h2></header>
          {regions ? (
            <table className="op-table op-table--tight"><thead><tr><th>Region</th><th>Share (window {regions.window})</th><th>Source</th></tr></thead>
              <tbody>{Object.entries(regions.shares).map(([name, r]) => <tr key={name}><td className="op-mono">{name}</td><td className="op-mono">{r.share == null ? '—' : r.share.toFixed(3)} · {r.members}/{r.defined}</td><td>{r.source_standing}</td></tr>)}</tbody></table>
          ) : <Empty>No frozen CG4 regions are declared on this definition.</Empty>}
        </article>

        <article className="op-tile">
          <header><span className="op-k">Definitions</span><h2>Versions</h2></header>
          {definitions.error != null ? <Refused error={definitions.error} /> : !definitions.data ? <Loading what="definitions" /> : (
            <table className="op-table op-table--tight"><thead><tr><th>Version</th><th>State</th><th>Confirmed</th></tr></thead>
              <tbody>{definitions.data.map((v) => <tr key={v.version}><td className="op-mono">v{v.version}</td><td>{v.state}</td><td className="op-mono">{v.confirmed_at ? `${when(v.confirmed_at)} · ${v.confirmed_by}` : '—'}</td></tr>)}</tbody></table>)}
          <p><a className="op-link" href={`/ops/setup/${id}`} onClick={onLink}>Inspect a new version →</a></p>
        </article>
      </div>
    </>
  );
}

function Series({ windows, alarms }: { windows: WindowsView['windows']; alarms: Set<number> }) {
  if (windows.length === 0) return <Empty>No windows have been evaluated yet.</Empty>;
  const W = 760, H = 200, left = 44, bottom = 32, top = 18;
  const max = Math.max(1, ...windows.map((w) => w.close?.units ?? 0));
  const step = (W - left - 12) / windows.length;
  const y = (v: number) => H - bottom - (v / max) * (H - bottom - top);
  const label = (w: (typeof windows)[number]) => (w.close?.start ? new Date(w.close.start / 1e6).toISOString().slice(5, 10) : String(w.window));
  return (
    <figure className="op-series">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Selected units in ${windows.length} windows; coral marks windows with a sequential alarm`}>
        <path d={`M${left} ${top}V${H - bottom}H${W - 8}`} className="nk-ld__p" />
        <text x={left - 6} y={top + 4} textAnchor="end" className="nk-ld__s">{max}</text>
        <text x={left - 6} y={H - bottom} textAnchor="end" className="nk-ld__s">0</text>
        {windows.map((w, i) => {
          const units = w.close?.units ?? 0;
          const x = left + i * step + step * 0.2;
          const hot = alarms.has(w.window);
          return (
            <g key={w.window}>
              <rect x={x} y={y(units)} width={step * 0.6} height={H - bottom - y(units)} className={hot ? 'op-bar-hot' : units === 0 ? 'op-bar-empty' : 'op-bar'} />
              {units === 0 && <rect x={x} y={H - bottom - 3} width={step * 0.6} height={3} className="op-bar-gap" />}
              {(i % Math.ceil(windows.length / 9) === 0 || hot) && <text x={x + step * 0.3} y={H - bottom + 14} textAnchor="middle" className="nk-ld__s">{label(w)}</text>}
              <title>{`window ${w.window}: ${units} units${w.maturity ? `, label availability ${w.maturity.label_availability_rate == null ? '—' : (w.maturity.label_availability_rate * 100).toFixed(0) + '%'}` : ', not matured'}${hot ? ', sequential alarm' : ''}`}</title>
            </g>);
        })}
      </svg>
      <figcaption className="op-mono">Bars: units selected when each window closed. Coral: a window with a sequential alarm. A flat dash: a closed window with no data (not monitored, not healthy).</figcaption>
    </figure>
  );
}
