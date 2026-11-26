// The DataTrust app: the approved concept 22 shell and steps, driven by the local API. Every step reads
// the session's job from the server; the canonical report is DataTrust's own HTML, shown as it is.
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { reducedMotion } from '../foundation/motion';
import { ApiError, api, files, type Analysis, type ClassTarget, type Fields, type ContextDecl, type JobView, type ParsingWarning, type SaveResult, type SessionInfo, type TargetOption } from './api';
import { FirstUse, HistoryPage, Rail, SavedReport, useHistory } from './history';
import { M3Confirm, M3Configure } from './m3';
import { M4Flow, m4Href, m4Steps, type M4Step } from './m4';
import { flowSteps, type FlowStep } from './flow';
import { M5Flow, M5_PREFIX } from './m5';
import { M6Flow, M6_PREFIX } from './m6';
import { M7Flow, M7_PREFIX } from './m7';
import { M9Flow, M9_PREFIX } from './m9';
import { M3_MODES, type M3Mode } from './api';
import { ResultError } from './flow';
import { TabularPage } from './results/compositions/index';
import { navigate, onLink, stepHref, stepOf, steps, usePath, type Step } from './router';
import { ContextPanel, contextField, emptyContext } from './context';
import { AllAnalysesLink, AnalysisBar, RegressionTargets, Start } from './start';
import { Availability, Layer, ReviewPanel, RoleNotes } from './configure';
import { ReportBar } from './results/shell/ReportBar';
import { Corners, MiB, SeparatorHint, SeparatorSelect, Viewer, fmt, separatorName } from './parts';

const subtypeLabel = { binary: 'Binary', multiclass: 'Multiclass', 'single-class': 'Single-class' } as const;
type Flash = (e: unknown) => void;


/** Which steps the server's job state allows. */
function reachable(job: JobView | null): Step[] {
  if (!job || job.stage === 'choose') return ['upload'];  // uploaded, analysis not chosen yet (the Start page chooses it)
  return ['upload', 'configure', ...(job.stage !== 'configure' ? ['confirm' as Step] : []), ...(job.stage === 'report' ? ['report' as Step] : [])];
}

/* ——— Shell ——— */

interface RailItem { id: string; n: number; t: string; href: string }
function AppBar({ items, current, ok }: { items: RailItem[]; current: string | null; ok: string[] }) {
  const i = items.findIndex((s) => s.id === current);
  return (
    <header className="ap-bar">
      <a className="ap-mark" href="/app/" onClick={onLink} aria-label="DataTrust home"><i aria-hidden="true" /><b>DataTrust</b><span>by NUMEK</span></a>
      <nav className="ap-rail" aria-label="Steps">
        <span className="ap-rail__line" aria-hidden="true"><i style={{ transform: `scaleX(${Math.max(i, 0) / (items.length - 1)})` }} /></span>
        {items.map((s, k) => {
          const state = k === i ? 'is-on' : k < i ? 'is-done' : '';
          const label = <><b>{k < i ? '✓' : s.n}</b><span>{s.t}</span></>;
          return ok.includes(s.id)
            ? <a key={s.id} href={s.href} onClick={onLink} className={`ap-rail__n ${state}`} aria-current={k === i ? 'step' : undefined}>{label}</a>
            : <span key={s.id} className={`ap-rail__n is-later ${state}`} aria-disabled="true" title="Complete the earlier steps first">{label}</span>;
        })}
        <span className="ap-rail__pill" aria-hidden="true">{i < 0 ? 'History' : `${i + 1}/4 · ${items[i].t}`}</span>
      </nav>
      <div className="ap-bar__r">
        <AllAnalysesLink />
        <span className="ap-live"><i aria-hidden="true" />local · {location.host}</span>
      </div>
    </header>
  );
}

/** PDF is rendered on demand from the canonical HTML; a rendering failure comes back as the API's error message. */
async function downloadPdf() {
  const res = await fetch(files.pdf, { credentials: 'same-origin' });
  if (res.ok && (res.headers.get('Content-Type') ?? '').includes('application/pdf')) {
    const name = /filename="?([^";]+)"?/.exec(res.headers.get('Content-Disposition') ?? '')?.[1] ?? 'datatrust-reliability-report.pdf';
    const url = URL.createObjectURL(await res.blob());
    const a = Object.assign(document.createElement('a'), { href: url, download: name });
    document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    return;
  }
  const body = await res.json().catch(() => null);
  throw new ApiError(body?.error?.message ?? 'The PDF report could not be generated.', res.status);
}

function Downloads({ flash }: { flash: Flash }) {
  const [busy, setBusy] = useState(false);
  return (
    <>
      <button type="button" className="ap-sheet__dl" disabled={busy} onClick={() => { setBusy(true); downloadPdf().catch(flash).finally(() => setBusy(false)); }}>{busy ? 'Rendering PDF…' : 'Download PDF ↓'}</button>
      <a className="ap-sheet__dl" href={files.html}>Download HTML ↓</a>
      <a className="ap-sheet__dl" href={files.json}>Download JSON ↓</a>
    </>
  );
}

function Warnings({ list, full = false }: { list: ParsingWarning[]; full?: boolean }) {
  if (!list.length) return null;
  return (
    <ul className="ap-warns">
      {list.map((w, k) => w.notice
        ? <li key={k} className="ap-note"><b>{w.notice.title}</b> {w.notice.text}</li>
        : <li key={k} className="ap-note ap-note--warn"><b>Parsing review: {w.code}{w.column ? ` · ${w.column}` : ''}</b> {w.interpretation}{full && w.observed_count != null && <span className="ap-warns__n">{w.observed_count} observed occurrences within bounded inspection; not dataset incidence.</span>}</li>)}
    </ul>
  );
}

/* ——— 1 · Start: start.tsx ——— */

/* ——— 2 · Configure ——— */

function Preview({ job, target }: { job: JobView; target: string | null }) {
  const i = job.inspection;
  return (
    <section className="ap-sec" aria-labelledby="ap-prev-h">
      <h2 id="ap-prev-h" className="ap-sub">First 10 rows</h2>
      {job.mode !== 'classification' && <p className="ap-muted">Bounded provisional preview. Final types and row counts are determined during full analysis. Names such as label do not establish roles.</p>}
      <div className="ap-table" tabIndex={0} aria-label={`First 10 rows of ${job.source_filename}, scrollable`}>
        <table>
          <thead><tr>{i.columns.map((c) => <th key={c} className={c === target ? 'is-t' : ''}>{c}</th>)}</tr></thead>
          <tbody>{i.preview.map((r, k) => <tr key={k}>{i.columns.map((c) => <td key={c} className={c === target ? 'is-t' : ''}>{r[c]}</td>)}</tr>)}</tbody>
        </table>
      </div>
    </section>
  );
}

function Cards({ items }: { items: [string, string][] }) {
  return <dl className="ap-cards">{items.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>;
}

function NameFields({ name, setName, purpose, setPurpose }: { name: string; setName: (s: string) => void; purpose: string; setPurpose: (s: string) => void }) {
  return (
    <div className="ap-fields">
      <label>Dataset/report name <span>optional · 120 characters</span><input type="text" maxLength={120} placeholder="Defaults to the filename" value={name} onChange={(e) => setName(e.target.value)} /></label>
      <label>Purpose <span>optional · 1,000 characters</span><textarea maxLength={1000} rows={3} placeholder="What prediction or decision will this dataset support?" value={purpose} onChange={(e) => setPurpose(e.target.value)} /></label>
    </div>
  );
}

const groups: { id: string; h: string; d: string }[] = [
  { id: 'outcome_word', h: 'Outcome-word candidates', d: 'These names contain outcome-style wording and have a small observed value set.' },
  { id: 'small_class_set', h: 'Other small-set candidates', d: 'These columns have a small observed value set, but their names do not establish the intended outcome.' },
];

function Pick({ o, on, set, info }: { o: TargetOption; on: boolean; set: () => void; info?: ClassTarget }) {
  return (
    <label className={`ap-opt ${on ? 'is-on' : ''} ${o.group === 'advanced' ? 'is-adv' : ''} ${o.disabled ? 'is-off' : ''}`}>
      <input type="radio" name="target" checked={on} onChange={set} disabled={o.disabled} />
      <span className="ap-opt__r" aria-hidden="true" />
      <span className="ap-opt__t"><b>{o.name}</b><span>{o.disabled ? `Unavailable · ${o.selector_explanation}` : `${fmt(o.observed_distinct_count ?? 0)} distinct values · ${fmt(o.missing_count ?? 0)} missing · ${o.selector_explanation}`}</span></span>
      {on && info && <span className="ap-opt__mini"><Mini t={info} /></span>}
    </label>
  );
}

/** Compact version of the selection panel, shown under the chosen option on narrow screens. */
function Mini({ t }: { t: ClassTarget }) {
  return (
    <>
      <b>{subtypeLabel[t.classification_subtype]} · {fmt(t.class_count)} classes · {fmt(t.labeled_row_count)} labelled</b>
      <span>{t.target_distribution.slice(0, 3).map((d) => `${d.label} ${d.percentage}%`).join(' · ')}{t.target_distribution.length > 3 ? ' · …' : ''}</span>
      {t.suitability.requires_override && <em>Needs an extra confirmation in the next step.</em>}
    </>
  );
}

function Selection({ name, t }: { name: string | null; t?: ClassTarget }) {
  if (!name) return (
    <div className="ap-sel ap-sel--empty">
      <Corners tone="ghost" />
      <b>Choose the outcome.</b>
      <p>DataTrust won’t choose it for you: only you know what the data is meant to predict.</p>
    </div>
  );
  if (!t) return <div className="ap-sel" key={name}><span className="ap-sel__k">Selected outcome</span><b className="ap-sel__n">{name}</b><span className="ap-sel__task">Reading the target…</span></div>;
  const shown = t.target_distribution.slice(0, 12);
  const max = Math.max(...shown.map((d) => d.percentage), 1);
  const more = t.class_count - shown.length;
  return (
    <div className="ap-sel" key={name}>
      <span className="ap-sel__k">Selected outcome</span>
      <b className="ap-sel__n">{name}</b>
      <span className="ap-sel__task">{subtypeLabel[t.classification_subtype]} classification · {fmt(t.class_count)} classes</span>
      <dl className="ap-sel__kv"><div><dt>Labelled rows</dt><dd>{fmt(t.labeled_row_count)}</dd></div><div><dt>Missing labels</dt><dd>{fmt(t.target_missing_count)}</dd></div></dl>
      <ul className="ap-sel__dist">
        {shown.map((d, k) => <li key={d.label}><span>{d.label}</span><i style={{ width: `${(d.percentage / max) * 100}%` }} className={k === 0 ? 'is-top' : ''} /><em>{d.percentage}%</em></li>)}
        {more > 0 && <li className="ap-sel__more">+ {fmt(more)} more classes</li>}
      </ul>
      {t.suitability.requires_override
        ? <div className="ap-sel__warn"><b>Needs an extra confirmation</b><p>{t.suitability.explanation}</p><p>You can still use it on purpose; DataTrust will ask you to confirm in the next step.</p></div>
        : <p className="ap-sel__ok">{t.suitability.explanation}</p>}
    </div>
  );
}

/** Availability declared in context (classification), as a column → value map for the G0 control. */
const ctxAvailability = (ctx: ContextDecl, cols: string[]) => Object.fromEntries(cols.map((c) => [c, ctx.columns[c]?.availability ?? 'unknown']));
const withAvailability = (ctx: ContextDecl, m: Record<string, string>): ContextDecl => ({
  ...ctx, columns: { ...ctx.columns, ...Object.fromEntries(Object.entries(m).map(([c, v]) => [c, { ...(ctx.columns[c] ?? {}), availability: v === 'unknown' ? undefined : v }])) },
});
const withoutTarget = (ctx: ContextDecl, target: string | null): ContextDecl => (target && ctx.columns[target]?.availability ? { ...ctx, columns: { ...ctx.columns, [target]: { ...ctx.columns[target], availability: undefined } } } : ctx);

const WHY_POINT = 'A column is a fair input only if it is known when the prediction is made. Declaring the prediction point and which columns are known then lets DataTrust tell leakage apart from legitimate predictors.';
const IF_NO_POINT = 'Availability is not verified. Leakage is checked by column name and a bounded dependency search only, and a column known only after the outcome (such as a call’s duration) cannot be detected from the data.';

interface ConfigureProps { job: JobView; submit: (f: Fields) => void; busy: boolean; separator?: ReactNode; onJob: (j: JobView) => void; flash: Flash }

function ClassConfigure({ job, submit, busy, separator, onJob, flash }: ConfigureProps) {
  const [target, setTarget] = useState<string | null>(job.target);
  const [name, setName] = useState(job.dataset_name ?? '');
  const [purpose, setPurpose] = useState(job.purpose ?? '');
  const [infos, setInfos] = useState<Record<string, ClassTarget>>({});
  const [msg, setMsg] = useState(false);
  const [ctx, setCtx] = useState(() => job.config.context ?? emptyContext());
  const [bulk, setBulk] = useState<string[]>([]);
  useEffect(() => {
    if (!target || infos[target]) return;
    let live = true;
    api.targetPreview(target).then((r) => { if (live) setInfos((m) => ({ ...m, [target]: r.target_info })); }).catch(() => {});
    return () => { live = false; };
  }, [target, infos]);
  const opts = job.inspection.target_options ?? [];
  const adv = opts.filter((o) => o.group === 'advanced' || o.group === 'disabled');
  const advOpen = !!target && adv.some((o) => o.name === target);
  const i = job.inspection;
  const inputs = i.columns.filter((c) => c !== target);
  return (
    <div className="ap-cf">
      <header className="ap-head"><span className="nk-label">Step 2 · Configure</span><h1>Configure the analysis.</h1></header>
      {separator}
      <Cards items={[['File', job.source_filename], ['Size', `${MiB(job.file_size)} MiB`], ['Rows', fmt(i.row_count)], ['Columns', fmt(i.column_count)]]} />
      <Preview job={job} target={target} />
      <Layer kind="essential" title="What outcome is this dataset meant to predict?" why="The outcome decides which rows are labelled, how the classes are balanced, and which columns are checked for leakage." ifMissing="Nothing can run without it.">
        <section className="ap-target" aria-label="Outcome">
          <div className="ap-target__l">
            <p className="ap-muted">DataTrust groups structurally plausible choices and explains why. It does not choose or preselect the business outcome.</p>
            {groups.map((g) => {
              const list = opts.filter((o) => o.group === g.id);
              if (!list.length) return null;
              return (
                <fieldset key={g.id} className="ap-group">
                  <legend>{g.h}</legend>
                  <p className="ap-muted">{g.d}</p>
                  <div className="ap-opts">{list.map((o) => <Pick key={o.name} o={o} on={target === o.name} set={() => setTarget(o.name)} info={infos[o.name]} />)}</div>
                </fieldset>
              );
            })}
            {adv.length > 0 && (
              <details className="ap-group ap-group--adv" open={advOpen || undefined}>
                <summary>Advanced choices ({opts.filter((o) => o.group === 'advanced').length})</summary>
                <p className="ap-muted">These choices look single-class, identifier-like, continuous, or highly categorical. You can still use one intentionally after an extra confirmation.</p>
                <div className="ap-opts">{adv.map((o) => <Pick key={o.name} o={o} on={target === o.name} set={() => setTarget(o.name)} info={infos[o.name]} />)}</div>
              </details>
            )}
            <RoleNotes job={job} target={target} onJob={onJob} flash={flash} />
          </div>
          <div className="ap-target__r"><Selection name={target} t={target ? infos[target] : undefined} /></div>
        </section>
      </Layer>
      <Layer kind="recommended" title="When will predictions be made, and what is known then?" why={WHY_POINT} ifMissing={IF_NO_POINT}>
        <ContextPanel bare parts={['prediction', 'codes']} availability={false} job={{ ...job, target }} value={ctx} onChange={setCtx} />
        <h3 className="ap-q ap-q--sub">Known at the prediction point?</h3>
        <Availability columns={inputs} value={ctxAvailability(ctx, inputs)} onChange={(m) => setCtx(withAvailability(ctx, m))} bulk={bulk} setBulk={setBulk} />
      </Layer>
      <Layer kind="advanced" title="Name, purpose, conditions and units">
        <NameFields name={name} setName={setName} purpose={purpose} setPurpose={setPurpose} />
        <ContextPanel bare parts={['advanced']} availability={false} job={{ ...job, target }} value={ctx} onChange={setCtx} />
      </Layer>
      <div className="ap-acts">
        <button type="button" className={`nk-btn ${target ? '' : 'is-off'} ${busy ? 'is-run' : ''}`} disabled={busy} onClick={() => { if (!target) { setMsg(true); return; } submit({ target, dataset_name: name, purpose, context: contextField(withoutTarget(ctx, target)), availability_bulk: JSON.stringify(bulk) }); }}>{busy ? 'Checking the target…' : 'Review selection →'}</button>
        <a className="nk-btn nk-btn--ghost" href="/app/" onClick={onLink}>Back</a>
        {msg && !target && <span className="ap-acts__hint ap-acts__hint--stop" role="status">Choose a target column from the uploaded dataset.</span>}
      </div>
    </div>
  );
}

const policies = ['pandas_default', 'empty_only', 'custom'];

/** Regression and unlabeled profiling: the classic form's CSV interpretation and declarations, in three layers. */
function TabularConfigure({ job, submit, busy, separator, onJob, flash }: ConfigureProps) {
  const p = job.config.parsing, reg = job.mode === 'regression';
  const e = job.config.regression?.expectations;
  const [encoding, setEncoding] = useState(p.encoding);
  const [policy, setPolicy] = useState(p.missing_policy);
  const [na, setNa] = useState(JSON.stringify(p.na_values));
  const [types, setTypes] = useState(JSON.stringify(p.column_types));
  const [target, setTarget] = useState<string | null>(job.target);
  const [kind, setKind] = useState(e?.kind ?? 'unspecified');
  const [units, setUnits] = useState(e?.units ?? '');
  const [min, setMin] = useState(e?.minimum != null ? String(e.minimum) : '');
  const [max, setMax] = useState(e?.maximum != null ? String(e.maximum) : '');
  const [nonneg, setNonneg] = useState(!!e?.nonnegative);
  const [integer, setInteger] = useState(!!e?.integer_required);
  const [dependency, setDependency] = useState(!!job.config.regression?.dependency_search);
  const [avail, setAvail] = useState<Record<string, string>>(() => Object.fromEntries(job.inspection.columns.map((c) => [c, job.config.regression?.feature_availability[c] ?? 'unknown'])));
  const [bulk, setBulk] = useState<string[]>([]);
  const [name, setName] = useState(job.dataset_name ?? '');
  const [purpose, setPurpose] = useState(job.purpose ?? '');
  const [msg, setMsg] = useState(false);
  const [ctx, setCtx] = useState(() => job.config.context ?? emptyContext());
  const fields = (action?: 'preview'): Fields => {
    const f: Fields = { encoding, missing_policy: policy, na_values: na, column_types: types, dataset_name: name, purpose, context: contextField(ctx), availability_bulk: JSON.stringify(bulk) };
    if (reg) {
      Object.assign(f, { regression_options_submitted: '1', target_kind: kind, target_units: units, target_minimum: min, target_maximum: max });
      if (target) f.target = target;
      if (nonneg) f.target_nonnegative = 'on';
      if (integer) f.target_integer = 'on';
      if (dependency) f.regression_dependency_search = 'on';
      for (const c of job.inspection.columns) f[`availability_${c}`] = avail[c];
    }
    if (action) f.action = action;
    return f;
  };
  const i = job.inspection;
  const csv = (
    <>
      <h3 className="ap-q ap-q--sub">How the CSV is read</h3>
      <div className="ap-fields ap-fields--two">
        <label>Text encoding<input value={encoding} onChange={(x) => setEncoding(x.target.value)} required /></label>
        <label>Missing-value policy<select value={policy} onChange={(x) => setPolicy(x.target.value)}>{policies.map((v) => <option key={v} value={v}>{v}</option>)}</select></label>
      </div>
      <p className="ap-muted">pandas_default recognizes pandas NA tokens. empty_only preserves nonempty tokens, including whitespace and NA. custom recognizes exactly the listed tokens.</p>
      <div className="ap-fields ap-fields--two">
        <label>Custom missing tokens <span>JSON list · custom policy only</span><textarea rows={2} value={na} onChange={(x) => setNa(x.target.value)} /></label>
        <label>Explicit column types <span>JSON object of resolved names to string or numeric</span><textarea rows={2} value={types} onChange={(x) => setTypes(x.target.value)} /></label>
      </div>
      <p className="ap-muted">Use string to preserve numeric-looking codes; numeric requires valid conversion. Source data stays unchanged.</p>
      <Warnings list={i.parsing_warnings} />
      <div className="ap-acts"><button type="button" className="nk-btn nk-btn--ghost" disabled={busy} onClick={() => submit(fields('preview'))}>Read the file again with these settings</button></div>
    </>
  );
  return (
    <div className="ap-cf">
      <header className="ap-head"><span className="nk-label">Step 2 · Configure</span><h1>Configure the analysis.</h1></header>
      {separator}
      <Cards items={[['File', job.source_filename], ['Size', `${MiB(job.file_size)} MiB`], ['Preview rows', fmt(i.preview_row_count)], ['Columns', fmt(i.column_count)]]} />
      <Preview job={job} target={target} />

      {reg ? (
        <Layer kind="essential" title="Which numerical outcome should be reviewed?" why="The outcome decides which relations are searched for (inputs that reproduce it) and which declared limits are checked." ifMissing="Nothing can run without it.">
          <section className="ap-target" aria-label="Outcome">
            <div className="ap-target__l">
              {job.suggestions ? <RegressionTargets job={job} target={target} setTarget={setTarget} /> : <>
                <p className="ap-muted">Preview assessments are provisional. Select the intended outcome explicitly; full confirmation verifies numeric compatibility.</p>
                <div className="ap-opts">
                  {(i.target_options ?? []).map((o) => (
                    <label key={o.name} className={`ap-opt ${target === o.name ? 'is-on' : ''} ${o.disabled ? 'is-off' : ''}`}>
                      <input type="radio" name="target" checked={target === o.name} onChange={() => setTarget(o.name)} disabled={o.disabled} />
                      <span className="ap-opt__r" aria-hidden="true" />
                      <span className="ap-opt__t"><b>{o.name}</b><span>{o.dtype} · {fmt(o.finite_count ?? 0)} preview finite values · {o.explanation} {o.selector_explanation}</span></span>
                    </label>
                  ))}
                </div></>}
              <RoleNotes job={job} target={target} onJob={onJob} flash={flash} />
            </div>
            <div className="ap-target__expectations">
              <div className="ap-sel ap-fields ap-fields--panel">
                <span className="ap-sel__k">What the outcome should look like · recommended</span>
                <label>Target intent<select value={kind} onChange={(x) => setKind(x.target.value)}>{['unspecified', 'continuous', 'count'].map((v) => <option key={v} value={v}>{v}</option>)}</select></label>
                <p className="ap-sel__ok">Count declares nonnegative integer values. Observed integers alone do not establish count semantics.</p>
                <label>Units <span>optional · display only</span><input maxLength={80} value={units} onChange={(x) => setUnits(x.target.value)} /></label>
                <div className="ap-fields--two">
                  <label>Inclusive minimum <span>optional</span><input type="number" step="any" value={min} onChange={(x) => setMin(x.target.value)} /></label>
                  <label>Inclusive maximum <span>optional</span><input type="number" step="any" value={max} onChange={(x) => setMax(x.target.value)} /></label>
                </div>
                <label className="ap-check"><input type="checkbox" checked={nonneg} onChange={(x) => setNonneg(x.target.checked)} /> Require nonnegative values</label>
                <label className="ap-check"><input type="checkbox" checked={integer} onChange={(x) => setInteger(x.target.checked)} /> Require integer values</label>
                <p className="ap-sel__ok">Without a declared range, values outside a plausible range are described, not called violations.</p>
              </div>
            </div>
          </section>
        </Layer>
      ) : (
        <Layer kind="essential" title="Nothing else is required." why="Every column is profiled: missing values, repeats, variation, categories and unusual values. No target is needed.">
          <RoleNotes job={job} target={null} onJob={onJob} flash={flash} />
        </Layer>
      )}

      {reg ? (
        <Layer kind="recommended" title="When will predictions be made, and what is known then?" why={WHY_POINT} ifMissing="A column that reproduces the target is reported for review, not as leakage or as a legitimate predictor, because its availability is unknown.">
          <ContextPanel bare parts={['prediction', 'codes']} availability={false} job={{ ...job, target }} value={ctx} onChange={setCtx} />
          <h3 className="ap-q ap-q--sub">Known at the prediction point?</h3>
          <Availability columns={i.columns.filter((c) => c !== target)} value={avail} onChange={setAvail} bulk={bulk} setBulk={setBulk} />
        </Layer>
      ) : (
        <Layer kind="recommended" title="What do special codes mean?" why="Values such as -1, 999 or “unknown” often stand for absent or special cases. Declaring them adds an interpreted view next to the values as recorded." ifMissing="Codes are profiled as ordinary values.">
          <ContextPanel bare parts={['codes']} job={{ ...job, target }} value={ctx} onChange={setCtx} />
        </Layer>
      )}

      <Layer kind="advanced" title="CSV interpretation, name, purpose, conditions and units">
        {reg && (
          <div className="ap-dep">
            <h3 className="ap-q ap-q--sub">Dependency search</h3>
            <label className="ap-check"><input type="checkbox" checked={dependency} onChange={(x) => setDependency(x.target.checked)} /> Also search for features that determine the target (regression_dependency_v1)</label>
            <p className="ap-muted">Looks for a lookup (a code that fixes the value), a binned copy of the target, or a monotone mapping, in addition to exact copies, rescalings and sums. Bounded to 64 features and 128 checks; evidence only, and no relationship is called leakage unless you declare the feature unavailable at the prediction point.</p>
          </div>
        )}
        {csv}
        <NameFields name={name} setName={setName} purpose={purpose} setPurpose={setPurpose} />
        <ContextPanel bare parts={['advanced']} availability={false} job={{ ...job, target }} value={ctx} onChange={setCtx} />
      </Layer>
      <div className="ap-acts">
        <button type="button" className={`nk-btn ${reg && !target ? 'is-off' : ''} ${busy ? 'is-run' : ''}`} disabled={busy} onClick={() => { if (reg && !target) { setMsg(true); return; } submit(fields()); }}>{busy ? 'Checking…' : reg ? 'Review selection →' : 'Review the profile →'}</button>
        <a className="nk-btn nk-btn--ghost" href="/app/" onClick={onLink}>Back</a>
        {msg && reg && !target && <span className="ap-acts__hint ap-acts__hint--stop" role="status">Choose a target column from the uploaded dataset.</span>}
      </div>
    </div>
  );
}

function Configure({ job, onJob, flash }: { job: JobView; onJob: (j: JobView) => void; flash: Flash }) {
  const [busy, setBusy] = useState(false);
  const submit = (f: Fields) => {
    setBusy(true);
    api.configure(f).then((r) => { onJob(r.job); if (r.next === 'confirm') navigate(stepHref('confirm')); }).catch(flash).finally(() => setBusy(false));
  };
  const separator = <><AnalysisBar job={job} /><SeparatorBar job={job} onJob={onJob} flash={flash} /></>;
  if (M3_MODES.includes(job.mode as M3Mode)) return <M3Configure key={job.config.parsing.delimiter} job={job} submit={submit} busy={busy} separator={separator} />;
  return job.mode === 'classification' ? <ClassConfigure key={job.config.parsing.delimiter} job={job} submit={submit} busy={busy} separator={separator} onJob={onJob} flash={flash} /> : <TabularConfigure key={JSON.stringify(job.config.parsing)} job={job} submit={submit} busy={busy} separator={separator} onJob={onJob} flash={flash} />;
}

/** The separator the file was read with; changing it reads the file again and clears declarations for the old columns. */
function SeparatorBar({ job, onJob, flash }: { job: JobView; onJob: (j: JobView) => void; flash: Flash }) {
  const d = job.config.parsing.delimiter ?? ',';
  const [busy, setBusy] = useState(false);
  const change = (v: string) => { setBusy(true); api.delimiter(v).then((r) => onJob(r.job)).catch(flash).finally(() => setBusy(false)); };
  return (
    <>
      <div className="ap-sepbar">
        <SeparatorSelect value={d} auto={false} disabled={busy} onChange={change} label="CSV separator" />
        <span>{busy ? 'Reading the file again…' : job.delimiter_detected ? `Detected: this file is ${separatorName(d)}-separated. Change it if that is wrong.` : `Read as ${separatorName(d)}-separated.`}</span>
      </div>
      {d === ',' && <SeparatorHint inspection={job.inspection} />}
    </>
  );
}

/* ——— 3 · Confirm ——— */

const planned: Record<'classification' | 'regression' | 'unlabeled', { list: string[]; text: string }> = {
  classification: { list: ['Missing values', 'Repeated rows', 'Contradicting labels', 'Unusual values', 'Leaked answers', 'Lopsided target'], text: 'Planned checks retain classification profiling, target evidence, conflicts, leakage heuristics, and scoring.' },
  regression: { list: ['Target distribution', 'Declared constraints', 'Arithmetic relationships', 'Repeated rows', 'Repeated inputs, varying target', 'Feature evidence'], text: 'Planned checks: finite target distributions, declared constraints, qualified arithmetic relationships, exact repetition, repeated-input target variation, feature evidence, and parsing review. Relationship searches have configured work and pool limits.' },
  unlabeled: { list: ['Schema', 'Missing values', 'Repeated rows', 'Observed variation', 'Category cardinality', 'Unusual values'], text: 'Planned checks: schema, cell/column/row missingness, exact duplicates, observed variation, categorical cardinality, finite numeric summaries, eligible 1.5-IQR evidence, and bounded parsing review.' },
};

function Confirm(props: { job: JobView; onJob: (j: JobView) => void; flash: Flash; saving: boolean; onSaved: (r: SaveResult) => void }) {
  return M3_MODES.includes(props.job.mode as M3Mode) ? <M3Confirm {...props} /> : <CoreConfirm {...props} />;
}

function CoreConfirm({ job, onJob, flash, saving, onSaved }: { job: JobView; onJob: (j: JobView) => void; flash: Flash; saving: boolean; onSaved: (r: SaveResult) => void }) {
  const [ack, setAck] = useState(false);
  const [keep, setKeep] = useState(true);
  const [run, setRun] = useState(false);
  const t = (job.target_info ?? {}) as Record<string, unknown> & Partial<ClassTarget>;
  const needsAck = job.mode !== 'unlabeled' && !!t.suitability?.requires_override;
  const limits = JSON.stringify(job.inspection.limits);
  const fi = job.config.fidelity_inspection;
  const go = () => {
    if (run || (needsAck && !ack)) return;
    setRun(true);
    api.generate({ ...(needsAck ? { advanced_target_ack: 'confirmed' } : {}), save_to_history: saving && keep ? 'yes' : 'no' }).then((r) => { onJob(r.job); onSaved(r.history); navigate(stepHref('report')); })
      .catch((e) => { setRun(false); flash(e); }).finally(() => scrollTo({ top: 0, behavior: reducedMotion() ? 'auto' : 'smooth' }));
  };
  let task: ReactNode, cards: [string, string][] = [], extra: ReactNode = null;
  if (job.mode === 'classification') {
    const ct = t as ClassTarget;
    task = <><b>Detected task: {subtypeLabel[ct.classification_subtype]} classification</b><span>Based on {fmt(ct.class_count)} observed target {ct.class_count === 1 ? 'class' : 'classes'}. Missing labels are excluded.</span></>;
    cards = [['Dataset', job.dataset_name || job.source_filename], ['Target', job.target ?? ''], ['Labelled rows', fmt(ct.labeled_row_count)], ['Missing labels', fmt(ct.target_missing_count)]];
    extra = <div className="ap-co__split" aria-label="Target classes">{ct.target_distribution.slice(0, 6).map((d, k) => <i key={d.label} style={{ flex: d.percentage }} className={k === 0 ? 'is-top' : ''}><span>{d.label} · {d.percentage}%</span></i>)}</div>;
  } else if (job.mode === 'regression') {
    const s = t.statistics as Record<string, number>, c = t.constraints as Record<string, number>;
    const e = job.config.regression?.expectations;
    task = <><b>Single-target regression · {job.target}</b><span>No overall score, sub-scores, or readiness verdict.</span></>;
    cards = [['Finite targets', `${fmt(s.finite_count)} / ${fmt(s.row_count)}`], ['Missing', fmt(s.missing_count)], ['Non-finite', fmt(s.positive_infinity_count + s.negative_infinity_count)], ['Distinct finite values', fmt(s.distinct_count)]];
    extra = (
      <div className="ap-sec ap-co__facts">
        <p>Observed range: {String(s.min)} to {String(s.max)}. Constraints: {fmt(c.violation_union_count)} violating finite targets. All finite targets remain in distribution evidence.</p>
        <p>Declared expectations: {e?.kind}{e?.units ? ` · ${e.units}` : ''}. Inclusive minimum: {e?.minimum ?? 'Not declared'}; inclusive maximum: {e?.maximum ?? 'Not declared'}. Nonnegative: {String(e?.nonnegative ?? false)}; integer required: {String(e?.integer_required ?? false)}. Feature availability is user-declared context.</p>
      </div>
    );
  } else {
    const pp = job.config.parsing;
    task = <><b>Unlabeled CSV profiling</b><span>All columns participate. No overall score, sub-scores, or readiness verdict will be generated.</span></>;
    cards = [['Dataset', job.dataset_name || job.source_filename], ['Encoding', pp.encoding], ['Missing policy', pp.missing_policy], ['Columns', fmt(job.inspection.column_count)]];
    extra = <p className="ap-muted">Tokens: {JSON.stringify(pp.na_values)}. Column overrides: {JSON.stringify(pp.column_types)}.</p>;
  }
  return (
    <div className="ap-co">
      <header className="ap-head"><span className="nk-label">Step 3 · Confirm</span><h1>Confirm the analysis.</h1></header>
      <div className="ap-co__task">{task}</div>
      <Cards items={cards} />
      {extra}
      <ReviewPanel job={job} />
      <section className="ap-sec">
        <h2 className="ap-sub">Planned checks</h2>
        <ol className={`ap-co__checks ${run ? 'is-run' : ''}`}>{planned[job.mode as keyof typeof planned].list.map((c, k) => <li key={c} style={{ ['--k' as string]: k }}><i aria-hidden="true" />{c}</li>)}</ol>
        <p className="ap-muted ap-co__text">{planned[job.mode as keyof typeof planned].text}</p>
      </section>
      <Warnings list={job.inspection.parsing_warnings} />
      {job.config.parsing.delimiter !== ',' && <p className="ap-note"><b>CSV separator: {separatorName(job.config.parsing.delimiter)}.</b> The report records it, and any change after confirming reads the file again.</p>}
      <details className="ap-more ap-sec">
        <summary>Parsing and safeguards</summary>
        {job.mode === 'classification' && <p className="ap-muted">Parsing: existing pandas NA/type defaults, UTF-8, {separatorName(job.config.parsing.delimiter)} separator, inferred header. Analysis safeguards: {limits}; the configured upload cap also applies.</p>}
        {job.mode === 'regression' && <p className="ap-muted">Operational safeguards: {limits}. Post-load frame measurement and cooperative deadlines are not hard memory or execution guarantees.</p>}
        {job.mode === 'unlabeled' && <p className="ap-muted">Operational safeguards: {limits}. Source/header preflight, bounded row read, post-load frame measurement, and cooperative deadlines are safeguards, not hard memory or execution guarantees.</p>}
        <p className="ap-muted">Token inspection bounds: {fi.max_bytes} bytes, {fi.max_records} data records, {fi.max_cells} comparable cells. Preview inspection is limited to preview rows. Warnings are review prompts; absence within this scope does not establish losslessness.</p>
      </details>
      {needsAck && (
        <div className="ap-sel__warn ap-co__warn">
          <b>Review this outcome choice</b>
          <p>{t.suitability!.explanation}</p>
          <label><input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} /> I still want to use <strong>{job.target}</strong> as the prediction outcome.</label>
        </div>
      )}
      {saving && <label className="ap-check ap-co__keep"><input type="checkbox" checked={!keep} onChange={(e) => setKeep(!e.target.checked)} /> Don’t save this analysis on this machine</label>}
      <div className="ap-acts">
        {run
          ? <span className="nk-btn is-run" role="status">Generating the report…</span>
          : <button type="button" className={`nk-btn ${needsAck && !ack ? 'is-off' : ''}`} onClick={go}>Generate reliability report</button>}
        <a className="nk-btn nk-btn--ghost" href={stepHref('configure')} onClick={onLink}>Change selection</a>
      </div>
    </div>
  );
}

/* ——— 4 · Report ——— */

function Result({ job, onNew, flash, save }: { job: JobView; onNew: () => void; flash: Flash; save: SaveResult | null }) {
  const [view, setView] = useState<false | true | string>(false);
  const [a, setA] = useState<Analysis | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let live = true; setFailed(null);
    api.analysis().then((x) => { if (live) setA(x); }).catch((e) => live && setFailed(e instanceof Error ? e.message : 'The result could not be read.'));
    return () => { live = false; };
  }, [job, attempt]);
  const s = job.summary!;
  if (failed) return <ResultError message={failed} onRetry={() => setAttempt((x) => x + 1)} />;
  if (!a) return <div className="ap-rs"><div className="nk-mosaic nk-mosaic--big nk-mosaic--run ap-rs__wait" aria-busy="true" /></div>;
  const out = <ReportBar saved={!!save?.saved} note={save?.message ? `This analysis wasn’t saved: ${save.message} This result lasts for this session, so download it before starting a new analysis.` : undefined}
    downloads={<Downloads flash={flash} />} onView={() => setView(true)} extra={<button type="button" className="nk-btn nk-btn--ghost" onClick={onNew}>New analysis</button>} />;
  return (
    <>
      <TabularPage a={a as unknown as Record<string, unknown>} out={out} onOpen={(x) => setView(x ?? true)} presentation="/core/job/presentation" live fallbackName={s.dataset_name} />
      {view && <Viewer name={s.dataset_name} src={typeof view === 'string' ? `${files.report}#${encodeURIComponent(view)}` : files.report} note="the canonical DataTrust report" downloads={<Downloads flash={flash} />} onClose={() => setView(false)} />}
    </>
  );
}

/* ——— App ——— */

export default function App() {
  const path = usePath();
  const saved = /^\/app\/history(?:\/([0-9a-f]{32}))?\/?$/.exec(path);
  const inM4 = path.startsWith('/app/m4');
  const flowPrefix = [M5_PREFIX, M6_PREFIX, M7_PREFIX, M9_PREFIX].find((x) => path.startsWith(x)) ?? null;
  const [flowRail, setFlowRail] = useState<{ step: FlowStep; ok: FlowStep[] }>({ step: 'sources', ok: ['sources'] });
  const [m4Rail, setM4Rail] = useState<{ step: M4Step; ok: M4Step[] }>({ step: 'sources', ok: ['sources'] });
  const requested = stepOf(path);
  const history = useHistory();
  const [info, setInfo] = useState<SessionInfo | null>(null);
  const [job, setJob] = useState<JobView | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [fatal, setFatal] = useState<string | null>(null);
  const [save, setSave] = useState<SaveResult | null>(null);
  const keep = useRef(false); // a redirect made by the app itself keeps the message it carries

  useEffect(() => {
    // Session and job arrive together, so the step guard never judges a reload before the job is known.
    api.session().then(async (s) => { const r = await api.job(); setJob(r.job); setInfo(s); })
      .catch((e) => setFatal(e instanceof Error ? e.message : 'DataTrust is not reachable.'));
  }, []);

  const flash: Flash = (e) => {
    const err = e instanceof ApiError ? e : new ApiError('DataTrust could not complete the request.', 0);
    setNotice(err.message);
    keep.current = true;
    if (err.status === 404 && /no longer available/.test(err.message)) { setJob(null); navigate('/app/', true); return; }
    api.job().then((r) => setJob(r.job)).catch(() => {});
    if (flowPrefix || inM4) { /* those flows keep their own step; the notice is enough */ }
    else if (err.back === 'index') navigate('/app/');
    else if (err.back === 'configure' || err.back === 'confirm') navigate(stepHref(err.back));
    scrollTo({ top: 0, behavior: reducedMotion() ? 'auto' : 'smooth' });
  };

  // The server's job decides which step is reachable. History pages sit outside the steps.
  const ok = reachable(job);
  const step: Step = ok.includes(requested) ? requested : ok[ok.length - 1];
  useEffect(() => { if (info && !saved && !inM4 && !flowPrefix && step !== requested) { keep.current = true; navigate(stepHref(step), true); } }, [info, saved, inM4, flowPrefix, step, requested]);
  useEffect(() => { scrollTo({ top: 0, behavior: reducedMotion() ? 'auto' : 'smooth' }); }, [step, path]);
  useEffect(() => { if (keep.current) keep.current = false; else setNotice(null); }, [path]);

  const onJob = (j: JobView) => { setJob(j); setNotice(null); };
  const onSaved = (r: SaveResult) => { setSave(r); history.refresh(); };
  const onNew = () => { api.reset().then(() => { setJob(null); setSave(null); navigate('/app/'); }).catch(flash); };
  const hs = history.state;
  const saving = !!(hs?.enabled && hs.access && hs.saving === 'on');
  const savedNow: SaveResult | null = job?.saved_entry ? { saved: true, entry: job.saved_entry } : save;

  return (
    <div className="nk ap">
      {flowPrefix
        ? <AppBar items={flowSteps.map((x) => ({ ...x, href: `${flowPrefix}/${x.id}` }))} current={flowRail.step} ok={flowRail.ok} />
        : inM4
        ? <AppBar items={m4Steps.map((x) => ({ ...x, href: m4Href(x.id) }))} current={m4Rail.step} ok={m4Rail.ok} />
        : <AppBar items={steps.map((x) => ({ ...x, href: stepHref(x.id) }))} current={saved ? null : step} ok={reachable(job)} />}
      <div className="ap-body">
        <Rail job={job} history={history} flash={flash} />
        <main className="ap-main">
          {fatal && <p className="ap-note ap-note--warn" role="alert">{fatal}</p>}
          {notice && <p className="ap-note ap-note--warn" role="alert">{notice}</p>}
          {flowPrefix === M5_PREFIX ? (info && <M5Flow path={path} info={info} flash={flash} saving={saving} onRail={(st, o) => setFlowRail({ step: st, ok: o })} onSaved={history.refresh} />)
          : flowPrefix === M7_PREFIX ? (info && <M7Flow path={path} info={info} flash={flash} saving={saving} onRail={(st, o) => setFlowRail({ step: st, ok: o })} onSaved={history.refresh} />)
          : flowPrefix === M9_PREFIX ? (info && <M9Flow path={path} info={info} flash={flash} saving={saving} onRail={(st, o) => setFlowRail({ step: st, ok: o })} onSaved={history.refresh} />)
          : flowPrefix === M6_PREFIX ? (info && <M6Flow path={path} info={info} flash={flash} saving={saving} onRail={(st, o) => setFlowRail({ step: st, ok: o })} onSaved={history.refresh} />)
          : inM4 ? (info && <M4Flow path={path} info={info} flash={flash} saving={saving} onRail={(st, o) => setM4Rail({ step: st, ok: o })} onSaved={history.refresh} />)
          : saved ? (saved[1]
            ? <SavedReport key={saved[1]} id={saved[1]} flash={flash} onDeleted={() => { history.refresh(); navigate('/app/history'); }} />
            : <HistoryPage history={history} flash={flash} />) : (
            <>
              {hs?.enabled && hs.access && hs.saving === 'unset' && step === 'upload' && <FirstUse state={hs} onChange={history.refresh} flash={flash} />}
              {info && step === 'upload' && <Start info={info} job={job} onJob={onJob} flash={flash} />}
              {job && step === 'configure' && <Configure key={job.source_filename + job.mode} job={job} onJob={onJob} flash={flash} />}
              {job && step === 'confirm' && <Confirm job={job} onJob={onJob} flash={flash} saving={saving} onSaved={onSaved} />}
              {job && step === 'report' && <Result job={job} onNew={onNew} flash={flash} save={savedNow} />}
            </>
          )}
        </main>
      </div>
    </div>
  );
}
