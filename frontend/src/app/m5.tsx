// M5 · Temporal reliability: the classic temporal declarations as panels; the result is the temporal composition
// (results/compositions/temporal.tsx) on the shared results shell.
import { useState, type ReactNode } from 'react';
import type { Fields, SessionInfo, SourceInspection, TimeStructure } from './api';
import { AddSource, ConfirmFrame, FieldSections, Flow, FlowDownloads, LiveOut, ReportViewer, SourceCard, defaults, flowApi, viewAnchor, type Doc, type FlowJob, type FlowStep, type Section, type ViewTarget } from './flow';
import { temporalDashboard } from './results/compositions/temporal';
import { ResultsShell, useCompanion } from './results/shell/ResultsShell';
import { navigate, onLink } from './router';
import { SeparatorSelect } from './parts';
import { Layer } from './configure';

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
          <p className="ap-muted">Add analytical sources and any auxiliary histories, schedules or expectations separately. Each source’s first rows (at most 20,000, or 8 MiB) are inspected here to suggest its clock, entities and spacing; the full file is read only by the analysis.</p>
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

/** Sections by title, retitled as questions and opened inside a configuration layer; every field is kept. */
function pick(sections: Section[], titles: Record<string, string>, collapsed = false): Section[] {
  return Object.entries(titles).map(([t, q]) => { const s = sections.find((x) => x.title === t)!; return { ...s, title: q, collapsed }; });
}
const ESSENTIAL = pick(SOURCE, { 'Role and task': 'Role and task', Clock: 'Clock', Measurements: 'Measurements' });
const RECOMMENDED = pick(SOURCE, { Observation: 'One series or many?', 'Scheduling and lifecycle': 'Should a record exist at a regular interval?' });
const LATER = pick(SOURCE, { 'Feature-bound availability': 'When does each feature become available?', 'CSV parsing and base declarations': 'CSV parsing and base declarations' }, true);
const KIND_TEXT: Record<string, string> = { civil_date: 'a calendar date', instant: 'an instant with its offset', local_datetime: 'a local date-time (no offset)' };
const QUESTIONS = pick(GLOBAL, { 'Exact-observation revision history': 'Does the data have revisions?', 'Outcome maturity': 'When do outcomes become known?', 'Supplied evaluation plan': 'Do you have a fold plan?',
  'Advanced declarations and JSON import': 'Advanced declarations and JSON import', 'Behavior, limits, execution and presentation': 'Behavior, limits, execution and presentation' }, true);

function TimeSuggestions({ s, f, set, part }: { s: FlowJob['sources'][number]; f: Fields; set: (k: string, v: string) => void; part: 'essential' | 'recommended' }) {
  const t = s.time as TimeStructure | null | undefined;
  const k = (name: string) => `${s.id}_${name}`;
  if (!t || t.error || !analytical(Object.fromEntries(Object.entries(f).filter(([x]) => x.startsWith(`${s.id}_`)).map(([x, v]) => [x.slice(s.id.length + 1), v])))) return null;
  const rows = (f[k('measurements')] ?? '').split('\n').filter((l) => l.trim());
  const named = new Set(rows.map((l) => l.split('|')[1]?.trim()));
  const clock = t.clocks.find((c) => c.column === f[k('clock')]) ?? null;
  if (part === 'essential') {
    const pending = t.measurements.filter((m) => !named.has(m.column));
    if (!t.clocks.length && !pending.length) return null;
    return (
      <div className="ap-suggestbox">
        {t.clocks.length > 0 && <p className="ap-suggest">Clock: {t.clocks.map((c) => f[k('clock')] === c.column && f[k('clock_kind')] === c.kind
          ? <span key={c.column} className="ap-chip is-done">{c.column} ✓</span>
          : <button key={c.column} type="button" className="ap-chip" title={`${c.rule}: parses as ${KIND_TEXT[c.kind] ?? c.kind}${c.encoding === 'epoch' ? ` (epoch ${c.epoch_unit})` : ''}`}
              onClick={() => { set(k('clock'), c.column); set(k('clock_kind'), c.kind); set(k('encoding'), c.encoding); if (c.epoch_unit) set(k('epoch_unit'), c.epoch_unit); }}>
              {c.column} as {KIND_TEXT[c.kind] ?? c.kind}{c.encoding === 'epoch' ? `, epoch ${c.epoch_unit}` : ''}? <code>{c.rule}</code></button>)}</p>}
        {clock?.naive && <p className="ap-note">{clock.column} has no UTC offset, so it is suggested as a local date-time. If its values are instants, choose “instant” as the clock interpretation and declare their IANA timezone (for example Asia/Shanghai).</p>}
        {pending.length > 0 && <p className="ap-suggest">Measurements: {pending.map((m) => (
          <button key={m.column} type="button" className="ap-chip" title="R-NUM-1: numeric, finite and not constant in the inspected rows" onClick={() => set(k('measurements'), [...rows, `${m.column}|${m.column}|${m.type}|||`].join('\n'))}>{m.column} ({m.type})?</button>
        ))}</p>}
      </div>
    );
  }
  const shown = clock ?? t.clocks[0] ?? null;
  const spacing = shown?.spacing ?? null;
  const entity = t.entities.filter((e) => !shown || e.clock === shown.column);
  return (
    <div className="ap-suggestbox">
      {entity.length > 0 ? <p className="ap-suggest">Entity: {entity.map((e) => f[k('entities')] === e.column
        ? <span key={e.column} className="ap-chip is-done">{e.column} ✓</span>
        : <button key={e.column} type="button" className="ap-chip" title={e.text} onClick={() => set(k('entities'), e.column)}>one series per {e.column}? <code>{e.rule}</code></button>)}</p>
        : t.statement && <p className="ap-muted">{t.statement}</p>}
      {spacing && <p className="ap-suggest">{spacing.text} {f[k('schedule')] === 'fixed' && f[k('cadence')] === String(spacing.nanoseconds)
        ? <span className="ap-chip is-done">every {spacing.label} ✓</span>
        : <button type="button" className="ap-chip" onClick={() => { set(k('schedule'), 'fixed'); set(k('cadence'), String(spacing.nanoseconds)); set(k('anchor'), spacing.first); }}>expect a record every {spacing.label} from {spacing.first}?</button>}</p>}
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
      <header className="ap-head"><span className="nk-label">Step 2 · Configure</span><h1>What is the clock, and what should it show?</h1><p>Results preserve unknowns and assumptions. Suggestions come from each source’s inspected rows and apply only when you choose them.</p></header>
      {job.sources.map((s) => {
        const insp = s.inspection as SourceInspection | null | undefined;
        return (
          <section key={s.id} className="ap-m4src" aria-label={`${s.filename} declarations`}>
            <h2 className="ap-q">{s.id} · {s.filename}</h2>
            {insp?.coverage && <p className="ap-muted">{insp.coverage.statement}</p>}
            <Layer kind="essential" title="When was each record observed, and what was measured?" why="The clock orders the records; every chronology, gap and availability check is measured on it." ifMissing="Nothing temporal can be checked.">
              <TimeSuggestions s={s} f={f} set={set} part="essential" />
              <FieldSections sections={ESSENTIAL} values={f} set={set} prefix={`${s.id}_`} headers={s.headers} />
            </Layer>
            <Layer kind="recommended" title="One series or many, and how often should records arrive?" why="Entities separate interleaved series; an expected schedule turns missing timestamps into checked gaps." ifMissing="Without a schedule, continuity is not assessed. Without entities, all rows form one series.">
              <TimeSuggestions s={s} f={f} set={set} part="recommended" />
              <FieldSections sections={RECOMMENDED} values={f} set={set} prefix={`${s.id}_`} headers={s.headers} />
              <FieldSections sections={LATER.slice(0, 1)} values={f} set={set} prefix={`${s.id}_`} headers={s.headers} />
            </Layer>
            <Layer kind="advanced" title="CSV parsing and base declarations">
              <FieldSections sections={LATER.slice(1)} values={f} set={set} prefix={`${s.id}_`} headers={s.headers} />
            </Layer>
          </section>
        );
      })}
      <Layer kind="advanced" title="Revisions, outcome maturity, fold plans, name and behavior">
        <FieldSections sections={GLOBAL.slice(0, 1)} values={f} set={set} />
        <FieldSections sections={QUESTIONS} values={f} set={set} />
      </Layer>
      <div className="ap-acts">
        <button type="button" className={`nk-btn ${busy ? 'is-run' : ''}`} disabled={busy} onClick={submit}>{busy ? 'Binding the specification…' : 'Review effective specification →'}</button>
        <a className="nk-btn nk-btn--ghost" href={`${M5_PREFIX}/sources`} onClick={onLink}>Back to sources</a>
      </div>
    </div>
  );
}

/* ——— Result ——— */

export function TemporalPage({ a, out, live, investigate, onOpen, presentation, saved }: {
  a: Doc; out: ReactNode; live: boolean; investigate?: (q: string) => void; onOpen: (anchor?: string) => void; presentation: string | null; saved?: boolean;
}) {
  const companion = useCompanion(presentation);
  if (companion === undefined) return <div className="ap-rs"><div className="nk-mosaic nk-mosaic--big nk-mosaic--run ap-rs__wait" aria-busy="true" /></div>;
  const d = temporalDashboard(a, companion, !!saved, { live, investigate });
  return <ResultsShell d={d} label="Temporal checks" out={out} onOpenReport={onOpen} live={live} />;
}

export function M5Flow({ path, info, flash, saving, onRail, onSaved }: { path: string; info: SessionInfo; flash: Flash; saving: boolean; onRail: (s: FlowStep, ok: FlowStep[]) => void; onSaved: () => void }) {
  const [inv, setInv] = useState<string | null>(null);
  const [view, setView] = useState<ViewTarget>(false);
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
              <TemporalPage a={analysis} live presentation={temporalApi.presentation} investigate={(q) => setInv(q)} onOpen={(x) => setView(x ?? true)} out={<LiveOut saved={!!job.saved_entry} onView={() => setView(true)} onNew={onNew} newLabel="New temporal audit"
                downloads={<FlowDownloads route="/api/datatrust/v1/temporal/download" kinds={['pdf', 'html', 'json']} flash={flash} />} />} />
              {view && <ReportViewer name="Temporal audit" src={temporalApi.report} anchor={viewAnchor(view)} downloads={<FlowDownloads route="/api/datatrust/v1/temporal/download" kinds={['pdf', 'html', 'json']} flash={flash} />} onClose={() => setView(false)} />}
              {inv && <ReportViewer name="Filtered investigation" src={`/api/datatrust/v1/temporal/investigate?${inv}`} downloads={null} onClose={() => setInv(null)} />}
            </>
          )}
        </>
      )} />
  );
}
