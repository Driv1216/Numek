// Setup: inspect a monitoring definition, then confirm exactly what was inspected (plan J1).
// Inspecting records a new version and computes the frozen reference once per rule and K. Its read is recorded
// as evidence use (purpose reference). The planner shows each detector before it is enabled:
// - admission or refusal;
// - m₀ = U_ref + δ;
// - α;
// - the expected delay, including the window and follow-up lag;
// - power;
// - its standing, with reasons.
import { useEffect, useState } from 'react';
import { api, type DefinitionVersion, type Deployment, type Inspection, type Session } from './api';
import { Action, Empty, Loading, Refused, useResource, when, words } from './parts';
import { navigate, onLink } from './router';

export function Setup({ deployment, session }: { deployment: string | null; session: Session }) {
  const list = useResource<Deployment[]>('/deployments');
  if (list.error) return <Refused error={list.error} />;
  if (!list.data) return <Loading what="deployments" />;
  const chosen = deployment ?? list.data[0]?.id ?? null;
  return (
    <>
      <section className="op-head">
        <span className="op-k">Setup · monitoring definitions</span>
        <h1>Inspect, then confirm</h1>
        <p>Inspection shows the frozen reference and, for every detector, its null level, false-alarm budget, expected detection delay and power, together with every refusal. Confirming enables exactly what you inspected.</p>
      </section>
      {list.data.length === 0 ? <Empty>No deployments are registered.</Empty> : (
        <>
          <div className="op-seg" role="group" aria-label="Deployment">
            {list.data.map((d) => <button key={d.id} type="button" aria-pressed={d.id === chosen} onClick={() => navigate(`/ops/setup/${d.id}`)}>{d.id}</button>)}
          </div>
          {chosen && <Editor key={chosen} deployment={chosen} session={session} />}
        </>)}
    </>
  );
}

function Editor({ deployment, session }: { deployment: string; session: Session }) {
  const versions = useResource<DefinitionVersion[]>(`/deployments/${deployment}/definitions`);
  const [text, setText] = useState('');
  const [inspection, setInspection] = useState<Inspection | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState<string | null>(null);
  const can = (p: string) => session.permissions.includes(p);
  const current = versions.data?.find((v) => v.state === 'confirmed') ?? versions.data?.[versions.data.length - 1];

  useEffect(() => {
    if (current && !text) setText(JSON.stringify(current.spec, null, 2));
  }, [current]); // eslint-disable-line react-hooks/exhaustive-deps

  if (versions.error) return <Refused error={versions.error} />;
  if (!versions.data) return <Loading what="definition versions" />;
  const pending = versions.data.filter((v) => v.state === 'inspected');

  const inspect = async () => {
    setParseError(null); setConfirmed(null);
    let spec: unknown;
    try { spec = JSON.parse(text); } catch (e) { setParseError(`The definition is not valid JSON: ${(e as Error).message}`); throw e; }
    setInspection(await api.post<Inspection>(`/deployments/${deployment}/definitions`, { spec }));
    versions.reload();
  };

  return (
    <div className="op-setup">
      <section className="op-sec">
        <h2>Versions</h2>
        <table className="op-table op-table--tight"><thead><tr><th>Version</th><th>State</th><th>Created</th><th>Confirmed</th></tr></thead>
          <tbody>{versions.data.map((v) => <tr key={v.version}><td className="op-mono">v{v.version}</td><td>{v.state}</td><td className="op-mono">{when(v.created_at)}</td><td className="op-mono">{v.confirmed_at ? `${when(v.confirmed_at)} · ${v.confirmed_by}` : '—'}</td></tr>)}</tbody></table>
        <p className="op-mono"><a href={`/ops/deployments/${deployment}`} onClick={onLink}>Open the deployment →</a></p>
      </section>

      <section className="op-sec">
        <h2>Definition</h2>
        <p className="op-muted">The definition as JSON (schema confidenceguard.monitoring_definition/1.0). It starts from the {current ? `v${current.version} (${current.state})` : 'empty'} definition. Inspection never changes what is running.</p>
        <textarea className="op-json" spellCheck={false} value={text} onChange={(e) => setText(e.target.value)} aria-label="Monitoring definition (JSON)" rows={22} />
        {parseError && <p className="op-refused">{parseError}</p>}
        {can('analyze') ? <div className="op-acts"><Action label="Inspect" tone="primary" run={inspect} disabled={!api.canMutate() || !text.trim()} />
          <span className="op-mono">Records a new inspected version; computes the reference if its rule or K changed (recorded as evidence use, purpose reference).</span></div>
          : <p className="op-mono">Inspecting and confirming need the analyze permission.</p>}
      </section>

      {inspection && <InspectionView inspection={inspection} can={can} onConfirmed={(v) => { setConfirmed(v); versions.reload(); }} deployment={deployment} />}
      {!inspection && pending.length > 0 && (
        <section className="op-sec"><h2>Inspected, not confirmed</h2>
          {pending.map((v) => <InspectionView key={v.version} inspection={{ ...v.inspection, version: v.version, inspection_digest: v.inspection_digest }} can={can} onConfirmed={(x) => { setConfirmed(x); versions.reload(); }} deployment={deployment} />)}
        </section>)}
      {confirmed && <p className="op-ok">Confirmed {confirmed}. The previous version is superseded; its detectors stop and the new version's detectors start at their first window.</p>}
    </div>
  );
}

function InspectionView({ inspection, can, onConfirmed, deployment }: { inspection: Inspection; can: (p: string) => boolean; onConfirmed: (v: string) => void; deployment: string }) {
  return (
    <section className="op-sec op-inspection">
      <h2>Inspection · v{inspection.version}</h2>
      <p className="op-mono">K {inspection.catalog_sequence} · variant {inspection.variant.slice(0, 22)}… · digest {inspection.inspection_digest.slice(0, 16)}…</p>
      <dl className="op-facts">
        <div><dt>Reference</dt><dd>{inspection.reference.units} units · label availability {fmt(inspection.reference.inclusion.label_availability_rate, 3)} · evidence use {inspection.reference.evidence_use}</dd></div>
        <div><dt>Windows</dt><dd>from {when(inspection.windows.start)} · length {days(inspection.windows.length_ns)} · lateness {days(inspection.windows.allowed_lateness_ns)} · maturity {words(inspection.windows.maturity.policy)} {inspection.windows.maturity.followup_ns ? days(inspection.windows.maturity.followup_ns) : ''}</dd></div>
        <div><dt>Family</dt><dd>{inspection.family.expected_false_alarms_per_30_days.toFixed(3)} expected false alarms per 30 days</dd></div>
      </dl>
      <div className="op-scroll">
        <table className="op-table op-table--tight">
          <thead><tr><th>Detector</th><th>Admission</th><th>Reference</th><th>m₀</th><th>α</th><th>Expected delay</th><th>Power</th><th>Reasons</th></tr></thead>
          <tbody>{inspection.detectors.map((d) => d.admitted ? (
            <tr key={d.id}><td className="op-mono">{d.id}<br />{words(d.statistic)}{d.region ? ` @ ${d.region} (${d.region_source_standing})` : ''}</td>
              <td>{words(d.standing)}</td>
              <td className="op-mono">{d.reference_n} units · {d.reference_design ?? 'descriptive'}<br />mean {fmt(d.reference_mean, 4)} · upper {fmt(d.reference_upper, 4)}</td>
              <td className="op-mono">{fmt(d.m0, 4)}<br />δ {d.delta}</td><td className="op-mono">{d.alpha?.toExponential(2)}</td>
              <td className="op-mono">{Math.round(d.planner?.expected_delay_units ?? 0)} units{d.planner?.expected_delay_days != null ? ` ≈ ${d.planner.expected_delay_days.toFixed(1)} d` : ''}<br />total {d.expected_total_delay_days == null ? '—' : `${d.expected_total_delay_days.toFixed(1)} d`} (max {d.max_useful_delay_days} d)</td>
              <td className={d.power === 'insufficient_power' ? 'op-hot' : ''}>{words(d.power)}</td>
              <td className="op-mono">{(d.reasons ?? []).map(words).join('; ') || '—'}</td></tr>
          ) : (
            <tr key={d.id} className="op-refused-row"><td className="op-mono">{d.id}<br />{words(d.statistic)}</td><td colSpan={7}><b>refused</b> · {words(d.refusal)}</td></tr>
          ))}</tbody>
        </table>
      </div>
      {inspection.detectors.find((d) => d.false_alarm_statement) && <p className="op-mono">{inspection.detectors.find((d) => d.false_alarm_statement)!.false_alarm_statement}</p>}
      {inspection.qualifications.map((q) => <p key={q} className="op-mono">{q}</p>)}
      {can('analyze') && (
        <div className="op-acts">
          <Action label={`Confirm v${inspection.version} as inspected`} tone="primary" disabled={!api.canMutate()}
            run={async () => { await api.post(`/deployments/${deployment}/definitions/${inspection.version}/confirm`, { inspection_digest: inspection.inspection_digest }); onConfirmed(`v${inspection.version}`); }} />
          <span className="op-mono">Confirmation sends this inspection's digest; if anything changed since, the server refuses it as stale.</span>
        </div>)}
    </section>
  );
}

const fmt = (v: number | null | undefined, digits: number) => (v == null ? '—' : v.toFixed(digits));
const days = (ns: string | undefined) => (ns ? `${(Number(ns) / 86400e9).toFixed(Number(ns) % 86400e9 ? 2 : 0)} d` : '—');
