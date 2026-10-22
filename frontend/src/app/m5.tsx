// M5 · Temporal reliability: the classic temporal declarations as panels, and a result mosaic anchored by
// the Timeline hero tile (series spans from the canonical panel evidence) with the report's own topics.
import { useState, type ReactNode } from 'react';
import type { Fields, SessionInfo } from './api';
import { AddSource, ConfirmFrame, FieldSections, Flow, FlowDownloads, LiveOut, MosaicPage, BoundedTable, ReportViewer, SHADES, SourceCard, defaults, familyTile, flowApi, scalarFacts, type Doc, type FlowJob, type FlowStep, type Section } from './flow';
import type { Tone } from './results/adapter';
import type { Tile } from './results/Tiles';
import { navigate, onLink } from './router';
import { SeparatorSelect } from './parts';

type Flash = (e: unknown) => void;
export const temporalApi = flowApi('/temporal');
export const M5_PREFIX = '/app/temporal';
const AUX = ['history', 'schedule', 'expectations'];
const analytical = (v: Fields) => !AUX.includes(v.role ?? 'dataset');

const SOURCE: Section[] = [
  { title: 'Role and task', fields: [
    { name: 'role', label: 'Source role', kind: 'select', options: ['dataset', 'train', 'validation', 'test', 'reference', 'current', 'history', 'schedule', 'expectations'] },
    { name: 'task', label: 'Base task', kind: 'select', options: ['dataset_profile', 'classification', 'regression', 'multilabel_classification', 'clustering', 'anomaly_detection'] },
    { name: 'targets', label: 'Targets', kind: 'chips' }] },
  { title: 'Observation', when: analytical, note: 'Observation meaning, schedule, layout and entity structure are independent. Exact keys preserve leading zeros and literal identity.', fields: [
    { name: 'observation', label: 'Observation meaning', kind: 'select', options: ['measurement', 'event', 'snapshot'] },
    { name: 'layout', label: 'Measurement layout', kind: 'select', options: ['wide', 'long'] },
    { name: 'entities', label: 'Entity columns', kind: 'chips', hint: 'composite' },
    { name: 'keys', label: 'Exact observation keys', kind: 'chips', hint: 'optional' },
    { name: 'measurement_column', label: 'Long measurement-name column', kind: 'column', when: (v) => v.layout === 'long' },
    { name: 'value_column', label: 'Long value column', kind: 'column', when: (v) => v.layout === 'long' },
    { name: 'dense', label: 'Explicit dense long expectation?', kind: 'select', options: ['no', 'yes'], when: (v) => v.layout === 'long' },
    { name: 'unique', label: 'Require unique observation identities?', kind: 'select', options: ['no', 'yes'] },
    { name: 'arrival', label: 'Source order represents arrival order?', kind: 'select', options: ['no', 'yes'] }] },
  { title: 'Clock', when: analytical, fields: [
    { name: 'clock', label: 'Observation clock column', kind: 'column' },
    { name: 'clock_kind', label: 'Clock interpretation', kind: 'select', options: ['instant', 'civil_date', 'local_datetime'] },
    { name: 'encoding', label: 'Clock encoding', kind: 'select', options: ['iso', 'format', 'epoch', 'native'] },
    { name: 'timezone', label: 'Declared IANA timezone', hint: 'for naive instants' },
    { name: 'format', label: 'Explicit format', when: (v) => v.encoding === 'format' },
    { name: 'epoch_unit', label: 'Epoch unit', hint: 's / ms / us / ns', when: (v) => v.encoding === 'epoch' },
    { name: 'ambiguity', label: 'Repeated DST hour', kind: 'select', options: ['unresolved', 'earlier', 'later'] }] },
  { title: 'Measurements', when: analytical, fields: [
    { name: 'measurements', label: 'Measurements', kind: 'rows', hint: 'units and meanings belong to each named measurement; long layout leaves the column blank',
      columns: [{ label: 'Name' }, { label: 'Wide column', kind: 'column' }, { label: 'Type', options: ['quantitative', 'categorical', 'boolean', 'string'] }, { label: 'Unit' }, { label: 'Meaning' }, { label: 'Past-only', options: ['', 'past'] }] }] },
  { title: 'Scheduling and lifecycle', when: analytical, collapsed: true, fields: [
    { name: 'schedule', label: 'Scheduling expectation', kind: 'select', options: ['none', 'fixed', 'civil', 'supplied'] },
    { name: 'expectation', label: 'Expected population meaning', kind: 'select', options: ['required_record', 'collection_opportunity'] },
    { name: 'cadence', label: 'Fixed cadence', hint: 'exact nanoseconds' }, { name: 'anchor', label: 'Fixed or civil anchor' },
    { name: 'civil_unit', label: 'Civil unit', hint: 'daily / weekly / monthly' }, { name: 'schedule_zone', label: 'Civil schedule timezone' },
    { name: 'month_end', label: 'Monthly anchor beyond month end', kind: 'select', options: ['skip', 'last_day'] },
    { name: 'schedule_source', label: 'Supplied schedule source ID' }, { name: 'schedule_column', label: 'Supplied expected-time column' },
    { name: 'schedule_entities', label: 'Supplied entity columns' }, { name: 'schedule_measurement', label: 'Supplied measurement column', hint: 'optional' },
    { name: 'lifecycle', label: 'Active intervals', kind: 'area', def: '[]', hint: 'JSON; half-open; optional entity/measurement binding', wide: true },
    { name: 'assessment', label: 'Explicit freshness assessment time' }, { name: 'max_gap', label: 'Maximum adjacency gap', hint: 'nanoseconds' },
    { name: 'required_lookback', label: 'Required history lookback', hint: 'nanoseconds' }] },
  { title: 'Feature-bound availability', when: analytical, collapsed: true, note: 'Leave availability unknown unless you can bind evidence to named features. Signed delay and static assertions remain declared assumptions.', fields: [
    { name: 'timing', label: 'Availability rule', kind: 'select', options: ['unknown', 'timestamp', 'delay', 'static'] },
    { name: 'timing_features', label: 'Bound measurement names', hint: 'comma-separated' }, { name: 'cutoff', label: 'Prediction cutoff column', hint: 'ISO' },
    { name: 'available', label: 'Availability or source-time column', hint: 'ISO' }, { name: 'timing_zone', label: 'Timing timezone' },
    { name: 'delay', label: 'Signed delay', hint: 'nanoseconds; delay only' }, { name: 'static', label: 'Static assertion', hint: 'available_at_prediction / unknown' }] },
  { title: 'CSV parsing and base declarations', collapsed: true, fields: [
    { name: 'parsing', label: 'CsvParseOptions', kind: 'area', def: '{}', hint: 'JSON' },
    { name: 'base_config', label: 'AnalysisConfig', kind: 'area', def: '{}', hint: 'JSON; no execution or advanced overrides' }] },
];

const GLOBAL: Section[] = [
  { title: 'Audit', fields: [{ name: 'dataset_name', label: 'Audit name' }, { name: 'purpose', label: 'Purpose / intended use' }] },
  { title: 'Exact-observation revision history', collapsed: true, note: 'Conflicting ties remain ambiguous; null or retracted revisions are never skipped.', fields: [
    { name: 'history_source', label: 'Analytical source ID', hint: 'blank disables guided binding' }, { name: 'history_aux', label: 'History source ID' },
    { name: 'history_features', label: 'Feature names' }, { name: 'history_values', label: 'Corresponding history value columns' },
    { name: 'history_keys', label: 'Exact analytical observation keys' }, { name: 'history_aux_keys', label: 'Corresponding history keys' },
    { name: 'history_available', label: 'Revision availability column', hint: 'ISO' }, { name: 'history_cutoff', label: 'Analytical cutoff column', hint: 'ISO' },
    { name: 'history_zone', label: 'Timezone for naive values' }, { name: 'history_state', label: 'Revision-state column', hint: 'optional' },
    { name: 'history_null', label: 'Null revision semantics', kind: 'select', options: ['unknown', 'known_missing'] },
    { name: 'history_required', label: 'Require latest available state?', kind: 'select', options: ['no', 'yes'] },
    { name: 'histories', label: 'Additional FeatureHistorySpec declarations', kind: 'area', def: '[]', hint: 'JSON array', wide: true }] },
  { title: 'Outcome maturity', collapsed: true, fields: [
    { name: 'maturity_source', label: 'Source ID', hint: 'blank disables guided binding' }, { name: 'maturity_target', label: 'Declared target' },
    { name: 'maturity_clock', label: 'Outcome source-time column', hint: 'ISO' }, { name: 'maturity_zone', label: 'Timezone for naive values' },
    { name: 'maturity_delay', label: 'Signed maturation delay', hint: 'nanoseconds' }, { name: 'maturity_assessment', label: 'Explicit assessment time' },
    { name: 'maturity_fit', label: 'Fit cutoff', hint: 'optional' },
    { name: 'maturity', label: 'Additional OutcomeMaturitySpec declarations', kind: 'area', def: '[]', hint: 'JSON array', wide: true }] },
  { title: 'Supplied evaluation plan', collapsed: true, note: 'These describe plan feasibility; no split or backtest is generated.', fields: [
    { name: 'fold_train', label: 'Training source ID', hint: 'blank disables guided fold' }, { name: 'fold_evaluation', label: 'Evaluation source ID' },
    { name: 'fold_chronology', label: 'Chronology requirement', kind: 'select', options: ['none', 'global', 'within_entity'] },
    { name: 'fold_entities', label: 'Entity separation', kind: 'select', options: ['none', 'disjoint', 'reuse_permitted'] },
    { name: 'fold_origin', label: 'Prediction-origin column', hint: 'ISO; optional' }, { name: 'fold_zone', label: 'Origin timezone' },
    { name: 'fold_lookback', label: 'Lookback', hint: 'nanoseconds' }, { name: 'fold_horizon', label: 'Target horizon', hint: 'nanoseconds' },
    { name: 'fold_gap', label: 'Required gap', hint: 'nanoseconds' }, { name: 'fold_fit', label: 'Fit cutoff' },
    { name: 'folds', label: 'Additional TemporalFoldSpec declarations', kind: 'area', def: '[]', hint: 'JSON array', wide: true }] },
  { title: 'Advanced declarations and JSON import', collapsed: true, note: 'A complete manifest replaces the guided declarations. Its paths must be registered uploads or inside the data roots.', fields: [
    { name: 'availability', label: 'Additional FeatureAvailabilitySpec bindings', kind: 'area', def: '[]', hint: 'JSON array', wide: true },
    { name: 'manifest', label: 'Complete TemporalAuditSpec', kind: 'area', rows: 6, hint: 'JSON', wide: true }] },
  { title: 'Behavior, limits, execution and presentation', collapsed: true, fields: [
    { name: 'configuration', label: 'TemporalAnalysisConfig', kind: 'area', def: '{}', hint: 'JSON', rows: 5, wide: true }] },
];

function Sources({ job, info, setJob, flash }: { job: FlowJob | null; info: SessionInfo; setJob: (j: FlowJob | null) => void; flash: Flash }) {
  const [fmt, setFmt] = useState('csv');
  const [sep, setSep] = useState('auto');
  const start = () => temporalApi.start().then((r) => setJob(r.job)).catch(flash);
  const add = (p: Promise<{ job: FlowJob }>) => p.then((r) => setJob(r.job)).catch(flash);
  return (
    <div className="ap-up">
      <header className="ap-head"><span className="nk-label">Step 1 · Sources</span><h1>Check data over time.</h1><p>Chronology, coverage, feature availability, revision histories and supplied evaluation plans, from local CSV or Parquet. No universal temporal score, automatic repair, model fitting or backtest generation.</p></header>
      {!job ? <div className="ap-acts"><button type="button" className="nk-btn" onClick={start}>Start a temporal audit</button></div> : (
        <section className="ap-sec" aria-labelledby="ap-src-h">
          <h2 id="ap-src-h" className="ap-q">Sources · {job.sources.length}</h2>
          <p className="ap-muted">Add analytical sources and any auxiliary histories, schedules or expectations separately. Parquet schemas are validated in the supervised worker; CSV previews remain provisional.</p>
          {job.sources.map((s) => <SourceCard key={s.id} s={s} role={`${s.id} · ${String(s.format ?? '').toUpperCase()}`} />)}
          <AddSource info={info} label="Drop a CSV or Parquet source" accept=".csv,.parquet"
            extra={<><label className="ap-fmt">Format<select value={fmt} onChange={(e) => setFmt(e.target.value)}><option value="csv">CSV</option><option value="parquet">Parquet</option></select></label>{fmt === 'csv' && <SeparatorSelect value={sep} onChange={setSep} />}</>}
            onUpload={(f) => add(temporalApi.upload(f, { format: fmt, delimiter: sep }))} onLocal={(root, rel) => add(temporalApi.local({ root_id: root, relative_path: rel, format: fmt, delimiter: sep }))} />
          <div className="ap-acts">{job.sources.length ? <a className="nk-btn" href={`${M5_PREFIX}/configure`} onClick={onLink}>Declare temporal interpretation →</a> : <span className="nk-btn is-off" aria-disabled="true">Declare →</span>}</div>
        </section>
      )}
    </div>
  );
}

function Configure({ job, setJob, flash }: { job: FlowJob; setJob: (j: FlowJob) => void; flash: Flash }) {
  const [f, setF] = useState<Fields>(() => ({ ...defaults(GLOBAL), ...Object.assign({}, ...job.sources.map((s) => defaults(SOURCE, `${s.id}_`))), ...job.fields }));
  const [busy, setBusy] = useState(false);
  const set = (k: string, v: string) => setF((x) => ({ ...x, [k]: v }));
  const submit = () => { setBusy(true); temporalApi.configure(f).then((r) => { setJob(r.job); navigate(`${M5_PREFIX}/confirm`); }).catch(flash).finally(() => setBusy(false)); };
  return (
    <div className="ap-cf">
      <header className="ap-head"><span className="nk-label">Step 2 · Configure</span><h1>Declare semantics and timing.</h1><p>Results preserve unknowns and assumptions. Behavioral settings identify candidates for investigation.</p></header>
      <FieldSections sections={GLOBAL.slice(0, 1)} values={f} set={set} />
      {job.sources.map((s) => (
        <section key={s.id} className="ap-sec ap-m4src" aria-label={`${s.filename} declarations`}>
          <h2 className="ap-q">{s.id} · {s.filename}</h2>
          {!s.headers.length && <p className="ap-muted">Parquet: type exact column names; they are validated in the worker.</p>}
          <FieldSections sections={SOURCE} values={f} set={set} prefix={`${s.id}_`} headers={s.headers} />
        </section>
      ))}
      <FieldSections sections={GLOBAL.slice(1)} values={f} set={set} />
      <div className="ap-acts">
        <button type="button" className={`nk-btn ${busy ? 'is-run' : ''}`} disabled={busy} onClick={submit}>{busy ? 'Binding the specification…' : 'Review effective specification →'}</button>
        <a className="nk-btn nk-btn--ghost" href={`${M5_PREFIX}/sources`} onClick={onLink}>Back to sources</a>
      </div>
    </div>
  );
}

/* ——— Result ——— */

const TOPICS: [string, string, string[]][] = [
  ['chronology', 'Chronology', ['chronology', 'elapsed_chronology', 'ordering', 'repetition', 'freshness']],
  ['continuity', 'Continuity and history', ['continuity', 'lookback', 'panel']],
  ['behavior', 'Behavioral investigation', ['behavior', 'behavior_windows', 'behavior_series', 'runs', 'volatility', 'seasonality', 'behavior_panel', 'behavior_scope', 'runs_and_volatility', 'multivariate', 'annotation_windows']],
  ['availability', 'Availability and outcome maturity', ['availability', 'availability_unknown', 'past_observation', 'revision_history', 'selected_revision_timing', 'outcome_maturity', 'annotations']],
  ['evaluation', 'Chronological evaluation', ['evaluation']],
];
type Ev = { id: string; check_id: string; measurement: string | null; source_ids: string[]; population: string; data: Doc };
type TFinding = { id: string; title: string; evidence_type: string; evidence_refs: string[]; source_ids: string[]; measurement: string | null; finding: string; next_action: string; limitations: string; priority?: string };
const day = (ns: number) => new Date(ns / 1e6).toISOString().slice(0, 10);

function Timeline({ a, findings, big }: { a: Doc; findings: TFinding[]; big?: boolean }) {
  const ev = (a.evidence as Ev[]).filter((e) => e.check_id === 'panel');
  const bands = ev.map((e) => ({ source: e.source_ids[0], series: ((e.data.retained_histories as Doc[] | undefined) ?? []).map((h) => ({ m: String(h.measurement ?? ''), a: Number(h.first_tick), b: Number(h.last_tick) })).filter((h) => Number.isFinite(h.a) && Number.isFinite(h.b)) })).filter((b) => b.series.length);
  if (!bands.length) return null;
  const lo = Math.min(...bands.flatMap((b) => b.series.map((s) => s.a))), hi = Math.max(...bands.flatMap((b) => b.series.map((s) => s.b)));
  const W = 400, x = (t: number) => (hi > lo ? 10 + ((t - lo) / (hi - lo)) * (W - 20) : W / 2);
  let y = big ? 22 : 10; const rows: ReactNode[] = [];
  for (const b of bands) {
    if (big) rows.push(<text key={`${b.source}-l`} x={10} y={y} className="md-t md-t--s">{b.source}</text>);
    y += big ? 8 : 2;
    for (const s of b.series) {
      const hot = findings.some((f) => f.source_ids.includes(b.source) && (!f.measurement || f.measurement === s.m));
      rows.push(<g key={`${b.source}-${s.m}`} className="md-grow"><line x1={x(s.a)} x2={x(s.b)} y1={y} y2={y} className={`md-tl ${hot ? 'is-hot' : ''}`} strokeWidth={big ? 5 : 4} />{hot && <circle cx={x(s.b)} cy={y} r={3.4} className="md-hot" />}{big && <text x={x(s.a)} y={y - 5} className="md-t md-t--s">{s.m}</text>}</g>);
      y += big ? 22 : 12;
    }
    y += big ? 10 : 6;
  }
  return (
    <svg viewBox={`0 0 ${W} ${y + (big ? 18 : 4)}`} className="md-viz" preserveAspectRatio="xMidYMid meet">
      {rows}
      {big && <><text x={10} y={y + 12} className="md-t md-t--s">{day(lo)}</text><text x={W - 10} y={y + 12} className="md-t md-t--r md-t--s">{day(hi)}</text></>}
    </svg>
  );
}

export function temporalTiles(a: Doc, live: boolean, investigate?: (q: string) => void): Tile[] {
  const ev = a.evidence as Ev[], findings = (a.findings as TFinding[]) ?? [];
  const inputs = (((a.spec as Doc)?.inputs as Doc[]) ?? []);
  const panel = ev.filter((e) => e.check_id === 'panel').flatMap((e) => (e.data.retained_histories as Doc[] | undefined) ?? []);
  const ticks = panel.flatMap((h) => [Number(h.first_tick), Number(h.last_tick)]).filter(Number.isFinite);
  const cites = (ids: Set<string>) => findings.filter((f) => f.evidence_refs.some((r) => ids.has(r)));
  const findingList = (fs: TFinding[]) => fs.map((f) => <div key={f.id} className="nk-ch__f"><b>{f.title} <em>{f.priority ?? f.evidence_type.replace(/_/g, ' ')}</em></b><p>{f.finding}</p><p>{f.next_action}</p><p className="nk-ch__lim">{f.limitations}</p></div>);
  const hero: Tile = {
    id: 'timeline', hero: true, name: 'Timeline', n: '01', kicker: `${inputs.length} source${inputs.length === 1 ? '' : 's'}`, bg: '#163F52', light: true,
    tone: findings.length ? 'finding' : 'info',
    label: ticks.length ? `${day(Math.min(...ticks))} → ${day(Math.max(...ticks))}` : 'No span in the evidence',
    detail: findings[0]?.title ?? 'No qualifying finding within completed scope.',
    viz: <Timeline a={a} findings={findings} />, bigViz: <Timeline a={a} findings={findings} big />,
    chapter: (
      <>
        <h3>Timeline</h3>
        <div className="nk-ch__run"><span>Observed spans from the canonical panel evidence</span><b>{panel.length} series</b><p>Coral marks the series a finding cites. Spans the evidence does not hold are not drawn.</p></div>
        <dl>{inputs.map((i) => { const t = i.temporal as Doc | null; const c = (t?.clock ?? {}) as Doc; return <div key={String(i.id)}><dt>{String(i.id)} · {String(i.role)}</dt><dd>{t ? `${c.column} · ${c.kind}${c.timezone ? ` · ${c.timezone}` : ''} · schedule ${String((t.schedule as Doc)?.kind ?? 'none')}` : 'auxiliary source'}</dd></div>; })}</dl>
        {findingList(findings)}
        {live && investigate && <div className="ap-acts">{[...new Set(findings.map((f) => f.measurement).filter(Boolean))].map((m) => <button key={m} type="button" className="ap-sheet__dl" onClick={() => investigate(`measurement=${encodeURIComponent(String(m))}`)}>Investigate {m}</button>)}</div>}
      </>
    ),
  };
  const topics = TOPICS.map(([id, name, checks], i) => {
    const recs = ev.filter((e) => checks.includes(e.check_id));
    if (!recs.length) return null;
    const fs = cites(new Set(recs.map((e) => e.id)));
    const tone: Tone = fs.some((f) => f.priority === 'High') ? 'critical' : fs.length ? 'finding' : 'info';
    return familyTile({ id, name, n: i + 2, kicker: `${recs.length} record${recs.length === 1 ? '' : 's'}`, shade: SHADES[i % SHADES.length], tone,
      label: fs.length ? `${fs.length} finding${fs.length === 1 ? '' : 's'}` : 'No finding', detail: fs[0]?.title ?? [...new Set(recs.map((e) => e.check_id.replace(/_/g, ' ')))].join(' · '),
      body: (
        <>
          <h3>{name}</h3>
          <div className="nk-ch__run"><span>{recs.length} evidence records</span><b>{fs.length ? `${fs.length} finding${fs.length === 1 ? '' : 's'}` : 'No finding'}</b><p>{[...new Set(recs.map((e) => e.population))].join(' · ')}</p></div>
          {findingList(fs)}
          {recs.slice(0, 6).map((e) => (
            <div key={e.id} className="nk-ch__f"><b>{e.check_id.replace(/_/g, ' ')}{e.measurement ? ` · ${e.measurement}` : ''}</b>
              {!!scalarFacts(e.data).length && <dl>{scalarFacts(e.data).map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>}
              <BoundedTable data={e.data} />
              {live && investigate && <button type="button" className="ap-link" onClick={() => investigate(`family=${e.check_id}${e.measurement ? `&measurement=${encodeURIComponent(e.measurement)}` : ''}`)}>Open in the investigation view</button>}
            </div>
          ))}
          {recs.length > 6 && <p className="nk-ch__not">{recs.length - 6} more records in the canonical JSON.</p>}
        </>
      ) });
  }).filter(Boolean) as Tile[];
  const checks = (a.checks as Doc[]) ?? [];
  const blocked = checks.filter((c) => c.applicability === 'blocked' || c.execution === 'failed');
  topics.push(familyTile({ id: 'methodology', name: 'Methodology and coverage', n: topics.length + 2, kicker: `${checks.length} checks`, shade: SHADES[4], tone: blocked.length ? 'finding' : 'info',
    label: blocked.length ? `${blocked.length} blocked or failed` : 'All checks completed', detail: String((a.methodology_id as string) ?? ''),
    body: <><h3>Methodology</h3><div className="nk-ch__run"><span>{String(a.methodology_id)}</span><b>{checks.length} checks</b><p>Schema {String(a.schema_version)}.</p></div>
      <div className="ap-chtab"><table><thead><tr><th>check</th><th>applicability</th><th>execution</th><th>reason</th></tr></thead><tbody>{checks.slice(0, 40).map((c, i) => <tr key={i}><td>{String(c.check_id)}</td><td>{String(c.applicability)}</td><td>{String(c.execution)}</td><td>{String(c.reason ?? '')}</td></tr>)}</tbody></table></div></> }));
  return [hero, ...topics];
}

export function TemporalPage({ a, out, live, investigate, onOpen }: { a: Doc; out: ReactNode; live: boolean; investigate?: (q: string) => void; onOpen: () => void }) {
  const ctx = (a.context as Doc) ?? {}, findings = (a.findings as TFinding[]) ?? [];
  const files = (((a.spec as Doc)?.inputs as Doc[]) ?? []).map((i) => String(((i.source as Doc)?.source_filename) ?? (i.id)));
  return (
      <MosaicPage checks={a.checks} guidance={a.guidance} name={String(ctx.dataset_name ?? 'Temporal audit')} sub={`${files.join(' · ')} · Temporal`} when={String(a.generated_at)} findings={findings.length}
        status="No universal temporal score: findings are candidates for investigation." partial={(a.execution as Doc)?.status === 'partial'} label="Temporal checks"
        tiles={temporalTiles(a, live, investigate)} actions={findings.map((f) => ({ id: f.id, priority: f.priority, title: f.title, text: `${f.next_action} ${f.limitations}`, scope: [f.source_ids.join(', '), f.measurement].filter(Boolean).join(' · ') }))}
        summary={String((a.narrative as Doc)?.summary ?? '')} out={out} onOpen={onOpen}
        coverage={<><p className="ap-muted">Execution: {String((a.execution as Doc)?.status)} · backend {String((a.execution as Doc)?.backend ?? '—')}.</p><p className="ap-muted">Filtering and exports use completed evidence. Deeper searches require revised declarations and a new run.</p></>} />
  );
}

export function M5Flow({ path, info, flash, saving, onRail, onSaved }: { path: string; info: SessionInfo; flash: Flash; saving: boolean; onRail: (s: FlowStep, ok: FlowStep[]) => void; onSaved: () => void }) {
  const [inv, setInv] = useState<string | null>(null);
  const [view, setView] = useState(false);
  return (
    <Flow path={path} prefix={M5_PREFIX} api={temporalApi} info={info} flash={flash} onRail={onRail} onSaved={onSaved} label="Temporal audit"
      render={({ step, job, setJob, analysis, onNew }) => (
        <>
          {step === 'sources' && <Sources job={job} info={info} setJob={setJob} flash={flash} />}
          {job && step === 'configure' && <Configure key={job.sources.map((s) => s.id).join()} job={job} setJob={setJob} flash={flash} />}
          {job && step === 'confirm' && <ConfirmFrame job={job} api={temporalApi} flash={flash} saving={saving} prefix={M5_PREFIX} onRun={setJob}
            task={<><b>Temporal audit · {job.sources.length} source{job.sources.length === 1 ? '' : 's'}</b><span>Confirmation binds sources, timezone data and declarations. The worker re-checks every source hash before publishing.</span></>} />}
          {job && step === 'report' && analysis && (
            <>
              <TemporalPage a={analysis} live investigate={(q) => setInv(q)} onOpen={() => setView(true)} out={<LiveOut saved={!!job.saved_entry} onView={() => setView(true)} onNew={onNew} newLabel="New temporal audit"
                downloads={<FlowDownloads route="/api/datatrust/v1/temporal/download" kinds={['pdf', 'html', 'json']} flash={flash} />} />} />
              {view && <ReportViewer name="Temporal audit" src={temporalApi.report} downloads={<FlowDownloads route="/api/datatrust/v1/temporal/download" kinds={['pdf', 'html', 'json']} flash={flash} />} onClose={() => setView(false)} />}
              {inv && <ReportViewer name="Filtered investigation" src={`/api/datatrust/v1/temporal/investigate?${inv}`} downloads={null} onClose={() => setInv(null)} />}
            </>
          )}
        </>
      )} />
  );
}
