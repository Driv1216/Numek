// The six M3 modes: per-column roles and meanings, annotation declarations, and the representation
// acknowledgement. Same Configure and Confirm vocabulary as the core flow; the classic field contract.
import { useState, type ReactNode } from 'react';
import { ContextPanel, contextField, emptyContext } from './context';
import { reducedMotion } from '../foundation/motion';
import { api, type Fields, type JobView, type M3Mode, type SaveResult } from './api';
import { MiB, fmt } from './parts';
import { appliesTo, m3Label } from './results/adapter';
import { mods } from './results/modules';
import { navigate, onLink, stepHref } from './router';

type Flash = (e: unknown) => void;
const ROLES = ['feature', 'target', 'metadata', 'group', 'ignored'];
const MEANINGS = ['undeclared', 'quantitative', 'categorical', 'identifier', 'unknown'];
const POLICIES = ['pandas_default', 'empty_only', 'custom'];
const unlabeled = (m: string) => ['clustering', 'anomaly_detection', 'role_profile'].includes(m);

function defaultRole(job: JobView, c: string) {
  const t = job.m3?.task;
  if (!t) return 'feature';
  return t.groups.includes(c) ? 'group' : t.targets.includes(c) ? 'target' : t.metadata.includes(c) ? 'metadata' : t.features == null || t.features.includes(c) ? 'feature' : 'ignored';
}

export function M3Configure({ job, submit, busy, separator }: { job: JobView; submit: (f: Fields) => void; busy: boolean; separator?: ReactNode }) {
  const mode = job.mode as M3Mode, m3 = job.m3!, cols = job.inspection.columns, p = job.config.parsing;
  const [roles, setRoles] = useState<Record<string, string>>(() => Object.fromEntries(cols.map((c) => [c, defaultRole(job, c)])));
  const [meaning, setMeaning] = useState<Record<string, string>>(() => Object.fromEntries(cols.map((c) => [c, m3.semantic_types[c] ?? 'undeclared'])));
  const [expectation, setExpectation] = useState(m3.annotation?.expectation ?? 'unknown');
  const [statusColumn, setStatusColumn] = useState(m3.annotation?.status_column ?? '');
  const [json, setJson] = useState({ ...m3.json });
  const [scale, setScale] = useState(m3.scale_sensitive == null ? 'unknown' : String(m3.scale_sensitive));
  const [encoding, setEncoding] = useState(p.encoding);
  const [policy, setPolicy] = useState(p.missing_policy);
  const [na, setNa] = useState(JSON.stringify(p.na_values));
  const [types, setTypes] = useState(JSON.stringify(p.column_types));
  const [name, setName] = useState(job.dataset_name ?? '');
  const [purpose, setPurpose] = useState(job.purpose ?? '');
  const [ctx, setCtx] = useState(() => job.config.context ?? emptyContext());
  const setJ = (k: keyof typeof json, v: string) => setJson((x) => ({ ...x, [k]: v }));

  const fields = (): Fields => {
    const f: Fields = { dataset_name: name, purpose, encoding, missing_policy: policy, na_values: na, column_types: types, context: contextField(ctx) };
    for (const c of cols) { f[`role_${c}`] = roles[c]; f[`semantic_${c}`] = meaning[c]; }
    if (!unlabeled(mode)) Object.assign(f, { annotation_expectation: expectation, status_column: statusColumn, status_values: json.status_values, per_target_annotations: json.per_target_annotations });
    if (mode === 'annotation_regression') Object.assign(f, { expectations_by_target: json.expectations_by_target, feature_availability: json.feature_availability });
    if (mode === 'multilabel_classification') f.multilabel_options = json.multilabel_options;
    if (mode === 'clustering' || mode === 'anomaly_detection') f.scale_sensitive = scale;
    return f;
  };
  const counts = ROLES.map((r) => [r, cols.filter((c) => roles[c] === r).length] as const).filter(([, k]) => k);

  return (
    <div className="ap-cf">
      <header className="ap-head"><span className="nk-label">Step 2 · Configure</span><h1>Declare the roles.</h1><p>{m3Label[mode]}. Names do not determine roles. {unlabeled(mode) ? 'Declare the input representation and metadata explicitly.' : 'Select intended targets explicitly.'}</p></header>
      {separator}
      <dl className="ap-cards">{[['File', job.source_filename], ['Size', `${MiB(job.file_size)} MiB`], ['Columns', fmt(job.inspection.column_count)], ['Roles', counts.map(([r, k]) => `${k} ${r}`).join(' · ')]].map(([k, v]) => <div key={k}><dt>{k}</dt><dd className={k === 'Roles' ? 'ap-cards__small' : ''}>{v}</dd></div>)}</dl>

      <section className="ap-sec" aria-labelledby="ap-roles-h">
        <h2 id="ap-roles-h" className="ap-q">Each column’s role and meaning</h2>
        <div className="ap-table ap-roles" tabIndex={0} aria-label="Column roles, scrollable">
          <table>
            <thead><tr><th>Column</th><th>First rows</th><th>Role</th><th>Feature meaning</th></tr></thead>
            <tbody>{cols.map((c) => (
              <tr key={c} className={roles[c] === 'target' ? 'is-t' : roles[c] === 'ignored' ? 'is-off' : ''}>
                <td><b>{c}</b></td>
                <td className="ap-roles__eg">{job.inspection.preview.slice(0, 3).map((r) => r[c]).join(' · ')}</td>
                <td><select aria-label={`Role for ${c}`} value={roles[c]} onChange={(e) => setRoles((x) => ({ ...x, [c]: e.target.value }))}>{ROLES.filter((r) => r !== 'target' || !unlabeled(mode)).map((r) => <option key={r}>{r}</option>)}</select></td>
                <td><select aria-label={`Meaning for ${c}`} value={meaning[c]} onChange={(e) => setMeaning((x) => ({ ...x, [c]: e.target.value }))}>{MEANINGS.map((m) => <option key={m}>{m}</option>)}</select></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
        <p className="ap-muted ap-co__text">Group keys and annotation status columns are metadata. Ignored columns remain visible in source structure but are excluded from input diagnostics. Integer codes and identifiers are not assumed quantitative.</p>
      </section>

      {!unlabeled(mode) && (
        <section className="ap-sec" aria-labelledby="ap-ann-h">
          <h2 id="ap-ann-h" className="ap-q">Annotation expectations and status</h2>
          <div className="ap-fields ap-fields--two">
            <label>Default annotation expectation<select value={expectation} onChange={(e) => setExpectation(e.target.value)}>{['unknown', 'expected', 'optional'].map((v) => <option key={v}>{v}</option>)}</select></label>
            <label>Shared annotation status column<select value={statusColumn} onChange={(e) => setStatusColumn(e.target.value)}><option value="">None declared</option>{cols.map((c) => <option key={c}>{c}</option>)}</select></label>
          </div>
          <p className="ap-note">Unknown: annotation requirements are undeclared. Expected: an annotation is required. Optional: absence is allowed, but is not automatically intentional. Valid observed values are retained under all expectations. Uncertain label validity is a separate status declaration.</p>
          <details className="ap-more">
            <summary>Per-target expectations and custom status tokens</summary>
            <p className="ap-muted">Canonical exact tokens: expected, optional, observed, intentionally_unlabeled, unknown, uncertain. Other or missing tokens produce unresolved metadata.</p>
            <div className="ap-fields ap-fields--two">
              <label>Custom shared status mapping <span>JSON object, or null for canonical mapping</span><textarea rows={3} value={json.status_values} onChange={(e) => setJ('status_values', e.target.value)} /></label>
              <label>Per-target AnnotationSpec mappings <span>JSON object</span><textarea rows={3} value={json.per_target_annotations} onChange={(e) => setJ('per_target_annotations', e.target.value)} /></label>
            </div>
            <p className="ap-muted">Example: {'{"pending": {"expectation": "expected", "annotation_status": "unknown"}}'}</p>
          </details>
        </section>
      )}
      {mode === 'annotation_regression' && (
        <details className="ap-more ap-sec">
          <summary>Numerical expectations and prediction-time availability</summary>
          <p className="ap-muted">Each output retains separate units and declarations. Observed integers do not establish count semantics.</p>
          <div className="ap-fields ap-fields--two">
            <label>Expectations by target <span>JSON object</span><textarea rows={3} value={json.expectations_by_target} onChange={(e) => setJ('expectations_by_target', e.target.value)} /></label>
            <label>Input availability <span>JSON object</span><textarea rows={3} value={json.feature_availability} onChange={(e) => setJ('feature_availability', e.target.value)} /></label>
          </div>
          <p className="ap-muted">Example: {'{"heating": {"kind": "continuous", "minimum": 0, "units": "kW"}}'}</p>
        </details>
      )}
      {mode === 'multilabel_classification' && (
        <details className="ap-more ap-sec">
          <summary>Optional recorded-label constraints</summary>
          <div className="ap-fields"><label>MultilabelOptions <span>JSON object</span><textarea rows={3} value={json.multilabel_options} onChange={(e) => setJ('multilabel_options', e.target.value)} /></label></div>
          <p className="ap-muted">minimum_positive, maximum_positive, mutually_exclusive groups, and directed requires pairs. Unknown assignments can leave constraints inconclusive.</p>
        </details>
      )}
      {(mode === 'clustering' || mode === 'anomaly_detection') && (
        <section className="ap-sec">
          <div className="ap-fields"><label>Is the intended method sensitive to feature scales?<select value={scale} onChange={(e) => setScale(e.target.value)}><option value="unknown">Undeclared</option><option value="true">Yes</option><option value="false">No</option></select></label></div>
          <p className="ap-note">Undeclared numeric geometry remains conditional on representation. Low-cardinality integer/binary codes remain ambiguous unless you declare their meaning. These diagnostics do not assess clustering quality or anomaly correctness.</p>
        </section>
      )}
      <details className="ap-more ap-sec">
        <summary>CSV interpretation</summary>
        <div className="ap-fields ap-fields--two">
          <label>Encoding<input value={encoding} onChange={(e) => setEncoding(e.target.value)} /></label>
          <label>Missing policy<select value={policy} onChange={(e) => setPolicy(e.target.value)}>{POLICIES.map((v) => <option key={v}>{v}</option>)}</select></label>
          <label>Custom missing tokens <span>JSON list</span><textarea rows={2} value={na} onChange={(e) => setNa(e.target.value)} /></label>
          <label>Column storage overrides <span>JSON object</span><textarea rows={2} value={types} onChange={(e) => setTypes(e.target.value)} /></label>
        </div>
      </details>
      <div className="ap-fields">
        <label>Dataset name <span>optional · 120 characters</span><input type="text" maxLength={120} value={name} onChange={(e) => setName(e.target.value)} /></label>
        <label>Purpose <span>optional · 1,000 characters</span><textarea maxLength={1000} rows={3} value={purpose} onChange={(e) => setPurpose(e.target.value)} /></label>
      </div>
      <ContextPanel job={{ ...job, target: cols.find((c) => roles[c] === 'target') ?? null }} value={ctx} onChange={setCtx} availability={mode !== 'annotation_regression'} />
      <div className="ap-acts">
        <button type="button" className={`nk-btn ${busy ? 'is-run' : ''}`} disabled={busy} onClick={() => submit(fields())}>{busy ? 'Checking declarations…' : 'Review declarations and coverage →'}</button>
        <a className="nk-btn nk-btn--ghost" href="/app/" onClick={onLink}>Back</a>
      </div>
    </div>
  );
}

interface M3Info { rows: number; roles: { targets: string[]; features: string[]; metadata: string[]; ignored: string[] }; methodology: string; assumed_quantitative_count: number; ambiguous_count: number;
  annotations: { targets: { target: string; observed: number; total_rows: number; supplied_expected: number; expected: number; unknown_expectation_population: number; uncertain_observed: number }[] } | null }
const CORE_POLICIES = ['classification_legacy_2026_08_13', 'tabular_regression_v1', 'unlabeled_csv_profile_v1'];

export function M3Confirm({ job, onJob, flash, saving, onSaved }: { job: JobView; onJob: (j: JobView) => void; flash: Flash; saving: boolean; onSaved: (r: SaveResult) => void }) {
  const mode = job.mode as M3Mode, t = job.target_info as unknown as M3Info;
  const [ack, setAck] = useState(false);
  const [keep, setKeep] = useState(true);
  const [run, setRun] = useState(false);
  const planned = appliesTo(mode).filter((id) => !['score', 'local', 'reports'].includes(id)).map((id) => mods.find((m) => m.id === id)!.name);
  const go = () => {
    if (run || !ack) return;
    setRun(true);
    api.generate({ representation_ack: 'confirmed', save_to_history: saving && keep ? 'yes' : 'no' })
      .then((r) => { onJob(r.job); onSaved(r.history); navigate(stepHref('report')); })
      .catch((e) => { setRun(false); flash(e); }).finally(() => scrollTo({ top: 0, behavior: reducedMotion() ? 'auto' : 'smooth' }));
  };
  const n = (a: string[]) => a.length;
  return (
    <div className="ap-co">
      <header className="ap-head"><span className="nk-label">Step 3 · Confirm</span><h1>Confirm the analysis.</h1></header>
      <div className="ap-co__task"><b>{m3Label[mode]}</b><span>{job.dataset_name || job.source_filename} · {fmt(t.rows)} parsed rows. Policy: {t.methodology}. Scoring: {t.methodology === 'classification_legacy_2026_08_13' ? 'legacy compatibility policy' : 'not defined'}.</span></div>
      <dl className="ap-cards">{[['Targets', t.roles.targets.join(', ') || 'None'], ['Input features', fmt(n(t.roles.features))], ['Metadata', fmt(n(t.roles.metadata))], ['Ignored', fmt(n(t.roles.ignored))]].map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
      {t.annotations && (
        <section className="ap-sec">
          <h2 className="ap-sub">Annotation coverage</h2>
          <div className="ap-table" tabIndex={0}><table>
            <thead><tr><th>Target</th><th>Observed / rows</th><th>Supplied / expected</th><th>Unknown expectation</th><th>Uncertain observed</th></tr></thead>
            <tbody>{t.annotations.targets.map((c) => <tr key={c.target}><td>{c.target}</td><td>{fmt(c.observed)} / {fmt(c.total_rows)}</td><td>{fmt(c.supplied_expected)} / {fmt(c.expected)}{c.expected === 0 ? ' (unavailable: no resolved requirements)' : ''}</td><td>{fmt(c.unknown_expectation_population)} / {fmt(c.total_rows)}</td><td>{fmt(c.uncertain_observed)}</td></tr>)}</tbody>
          </table></div>
        </section>
      )}
      <section className="ap-sec">
        <h2 className="ap-sub">Planned checks</h2>
        <ol className={`ap-co__checks ${run ? 'is-run' : ''}`}>{planned.map((c, k) => <li key={c} style={{ ['--k' as string]: k }}><i aria-hidden="true" />{c}</li>)}</ol>
        <p className="ap-muted ap-co__text">{CORE_POLICIES.includes(t.methodology) ? 'This equivalent declaration uses the existing analytical and report policy. Its scores, schemas, and applicable feature diagnostics are preserved.' : `${fmt(t.assumed_quantitative_count)} undeclared numeric fields enter conditional quantitative summaries; ${fmt(t.ambiguous_count)} code-like fields remain ambiguous. Full resolved semantics and declarations are available in the result JSON.`}</p>
      </section>
      <p className="ap-note">Supplied annotations are not verified ground truth. No model performance, representativeness, clustering quality, anomaly correctness, or universal readiness verdict is established.</p>
      <div className="ap-sel__warn ap-co__warn">
        <b>Review the representation</b>
        <label><input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} /> I reviewed the roles, annotation requirements, and representation assumptions.</label>
      </div>
      {saving && <label className="ap-check ap-co__keep"><input type="checkbox" checked={!keep} onChange={(e) => setKeep(!e.target.checked)} /> Don’t save this analysis on this machine</label>}
      <div className="ap-acts">
        {run ? <span className="nk-btn is-run" role="status">Generating the report…</span>
          : <button type="button" className={`nk-btn ${ack ? '' : 'is-off'}`} onClick={go}>Generate reliability report</button>}
        <a className="nk-btn nk-btn--ghost" href={stepHref('configure')} onClick={onLink}>Edit declarations</a>
      </div>
    </div>
  );
}
