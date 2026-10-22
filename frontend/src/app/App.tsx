// The DataTrust app: the approved concept 22 shell and steps, driven by the local API. Every step reads
// the session's job from the server; the canonical report is DataTrust's own HTML, shown as it is.
import { useEffect, useRef, useState, type ReactElement, type ReactNode } from 'react';
import { reducedMotion } from '../foundation/motion';
import { ApiError, api, files, type Analysis, type ClassTarget, type Fields, type JobView, type Mode, type ParsingWarning, type SaveResult, type SessionInfo, type TargetOption } from './api';
import { Status } from '../foundation/system';
import { FirstUse, HistoryPage, Rail, SavedReport, useHistory } from './history';
import { M3Confirm, M3Configure } from './m3';
import { M4Flow, m4Href, m4Steps, type M4Step } from './m4';
import { flowSteps, type FlowStep } from './flow';
import { M5Flow, M5_PREFIX } from './m5';
import { M6Flow, M6_PREFIX } from './m6';
import { M7Flow, M7_PREFIX } from './m7';
import { M9Flow, M9_PREFIX } from './m9';
import { M3_MODES, type M3Mode } from './api';
import { m3Label } from './results/adapter';
import { navigate, onLink, stepHref, stepOf, steps, usePath, type Step } from './router';
import { activeTiles, date, fromAnalysis, taskLabel } from './results/adapter';
import { Mosaic } from './results/Mosaic';
import { ContextPanel, contextField, emptyContext } from './context';
import { ScopeNote } from './results/Tiles';
import { Corners, MiB, SeparatorHint, SeparatorSelect, Viewer, fmt, separatorName } from './parts';

const subtypeLabel = { binary: 'Binary', multiclass: 'Multiclass', 'single-class': 'Single-class' } as const;
type Flash = (e: unknown) => void;


/** Which steps the server's job state allows. */
function reachable(job: JobView | null): Step[] {
  if (!job) return ['upload'];
  return ['upload', 'configure', ...(job.stage !== 'configure' ? ['confirm' as Step] : []), ...(job.stage === 'report' ? ['report' as Step] : [])];
}

/* ——— Shell ——— */

const workflows = [
  ['Temporal reliability', 'Exact clocks, coverage, availability, revisions', '/app/temporal/sources'],
  ['Text reliability', 'Corpora, annotation, conversations, retrieval', '/app/text/sources'],
  ['Image reliability', 'Images, annotations, segmentation integrity', '/app/images/sources'],
  ['Records ↔ documents', 'Records reconciled against PDF and DOCX', '/app/cross/sources'],
  ['Split audit · comparison', 'Version comparison and advanced local analysis', '/app/m4/sources'],
];

function Workflows() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const off = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    addEventListener('mousedown', off); addEventListener('keydown', esc);
    return () => { removeEventListener('mousedown', off); removeEventListener('keydown', esc); };
  }, [open]);
  return (
    <div ref={ref} className="ap-wf">
      <button type="button" className="ap-wf__btn" aria-expanded={open} aria-label="Other workflows" onClick={() => setOpen((o) => !o)}><span className="ap-wf__long">Other workflows</span><span className="ap-wf__short">More</span> <span aria-hidden="true">▾</span></button>
      {open && (
        <div className="ap-wf__pop" role="menu">
          <p>Separate guided workflows in DataTrust. Those marked classic open in the classic interface for now.</p>
          {workflows.map(([t, d, r]) => <a key={r} href={r} onClick={onLink} className="ap-wf__it" role="menuitem"><b>{t}</b><span>{d}</span><code>{r.startsWith('/app/') ? 'in this app' : `classic · ${r}`}</code></a>)}
        </div>
      )}
    </div>
  );
}

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
        <Workflows />
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

function Downloads({ mode, flash }: { mode: Mode; flash: Flash }) {
  const [busy, setBusy] = useState(false);
  return (
    <>
      <button type="button" className="ap-sheet__dl" disabled={busy} onClick={() => { setBusy(true); downloadPdf().catch(flash).finally(() => setBusy(false)); }}>{busy ? 'Rendering PDF…' : 'Download PDF ↓'}</button>
      {mode !== 'classification' && <a className="ap-sheet__dl" href={files.html}>Download HTML ↓</a>}
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

/* ——— 1 · Upload ——— */

const modes: { id: Mode; t: string; d: string; draw: ReactElement }[] = [
  { id: 'classification', t: 'Classification', d: 'Explicit target. Scores, sub-scores and guardrails.', draw: <svg viewBox="0 0 120 64" aria-hidden="true"><rect x="6" y="20" width="80" height="22" className="ap-d-ink" /><rect x="86" y="20" width="28" height="22" className="ap-d-hot" /><path d="M6 50V54H114V50" className="ap-d-ln" /></svg> },
  { id: 'regression', t: 'Regression', d: 'Numerical target. Evidence, no universal score.', draw: <svg viewBox="0 0 120 64" aria-hidden="true">{[[12, 48], [24, 44], [34, 40], [46, 38], [58, 30], [68, 28], [80, 22], [94, 18], [106, 12]].map(([x, y], k) => <circle key={k} cx={x} cy={y} r="3" className="ap-d-ink" />)}<path d="M6 52L114 10" className="ap-d-ln" /></svg> },
  { id: 'unlabeled', t: 'Unlabeled', d: 'No target. Every column is profiled.', draw: <svg viewBox="0 0 120 64" aria-hidden="true">{Array.from({ length: 6 }, (_, k) => <rect key={k} x={8 + k * 18} y="10" width="12" height="44" className="ap-d-ln" />)}<rect x="44" y="40" width="12" height="14" className="ap-d-ink" /></svg> },
];

function Upload({ info, onJob, flash }: { info: SessionInfo; onJob: (j: JobView) => void; flash: Flash }) {
  const input = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState<Mode>('classification');
  const [file, setFile] = useState<File | null>(null);
  const [sep, setSep] = useState('auto');
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const inspect = () => {
    if (!file || busy) return;
    setBusy(true);
    api.upload(mode, file, sep).then((r) => { onJob(r.job); navigate(stepHref('configure')); }).catch(flash).finally(() => setBusy(false));
  };
  return (
    <div className="ap-up">
      <header className="ap-head">
        <span className="nk-label">Step 1 · Upload</span>
        <h1>Generate a reliability report.</h1>
        <p>Your CSV is processed by this local application and is not sent to DataTrust or a cloud service.</p>
      </header>

      <section className="ap-sec" aria-labelledby="ap-mode-h">
        <h2 id="ap-mode-h" className="ap-q">What kind of analysis?</h2>
        <div className="ap-modes" role="radiogroup" aria-label="Analysis mode">
          {modes.map((m) => (
            <button key={m.id} type="button" role="radio" aria-checked={mode === m.id} className={`ap-mode ${mode === m.id ? 'is-on' : ''}`} onClick={() => setMode(m.id)}>
              {mode === m.id && <Corners />}
              <span className="ap-mode__draw">{m.draw}</span>
              <b>{m.t}</b><span>{m.d}</span>
            </button>
          ))}
        </div>
        <details className="ap-more" open={M3_MODES.includes(mode as M3Mode) || undefined}><summary>Six more modes</summary>
          <ul role="radiogroup" aria-label="More analysis modes">{M3_MODES.map((m) => <li key={m}><button type="button" role="radio" aria-checked={mode === m} className={mode === m ? 'is-on' : ''} onClick={() => setMode(m)}>{m3Label[m]}</button></li>)}</ul>
          <p>They use the same Upload step, then ask for column roles and annotation declarations in Configure.</p></details>
      </section>

      <section className="ap-sec" aria-labelledby="ap-file-h">
        <h2 id="ap-file-h" className="ap-q">Which dataset?</h2>
        <div className={`ap-drop ${over ? 'is-over' : ''} ${file ? 'is-ready' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
          onDrop={(e) => { e.preventDefault(); setOver(false); const f = e.dataTransfer.files[0]; if (f) setFile(f); }}>
          {!file ? (
            <div className="ap-drop__empty">
              <svg viewBox="0 0 40 40" aria-hidden="true"><path d="M20 6V24M12 16L20 24L28 16" /><path d="M6 26V33H34V26" /></svg>
              <b>Drop a CSV here</b>
              <span>CSV with a header row · up to {info.upload_limit_mib} MiB</span>
              <div className="ap-drop__acts"><button type="button" className="nk-btn" onClick={() => input.current?.click()}>Choose a file</button></div>
            </div>
          ) : (
            <div className="ap-drop__file">
              <div className="ap-file">
                <span className="ap-file__fold" aria-hidden="true" />
                <b>{file.name}</b>
                <span>{MiB(file.size)} MiB · chosen on this machine</span>
              </div>
              <button type="button" className="ap-link" onClick={() => { setFile(null); if (input.current) input.current.value = ''; }}>Choose a different file</button>
            </div>
          )}
          <input ref={input} type="file" accept=".csv,text/csv" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) setFile(f); }} />
        </div>
        <div className="ap-sepbar"><SeparatorSelect value={sep} onChange={setSep} /><span>Commas, semicolons, tabs and vertical bars are read. Detection applies a separator only when exactly one fits; if several fit, you choose.</span></div>
      </section>

      <div className="ap-acts">
        {file ? <button type="button" className={`nk-btn ${busy ? 'is-run' : ''}`} onClick={inspect} disabled={busy}>{busy ? 'Inspecting…' : 'Inspect dataset →'}</button> : <span className="nk-btn is-off" aria-disabled="true">Inspect dataset →</span>}
        <span className="ap-acts__hint">{file ? 'Next: preview the rows and choose what to check.' : 'Choose a CSV with a header row.'}</span>
      </div>
    </div>
  );
}

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

function ClassConfigure({ job, submit, busy, separator }: { job: JobView; submit: (f: Fields) => void; busy: boolean; separator?: ReactNode }) {
  const [target, setTarget] = useState<string | null>(job.target);
  const [name, setName] = useState(job.dataset_name ?? '');
  const [purpose, setPurpose] = useState(job.purpose ?? '');
  const [infos, setInfos] = useState<Record<string, ClassTarget>>({});
  const [msg, setMsg] = useState(false);
  const [ctx, setCtx] = useState(() => job.config.context ?? emptyContext());
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
  return (
    <div className="ap-cf">
      <header className="ap-head"><span className="nk-label">Step 2 · Configure</span><h1>Configure the analysis.</h1></header>
      {separator}
      <Cards items={[['File', job.source_filename], ['Size', `${MiB(job.file_size)} MiB`], ['Rows', fmt(i.row_count)], ['Columns', fmt(i.column_count)]]} />
      <Preview job={job} target={target} />
      <section className="ap-target" aria-labelledby="ap-target-h">
        <div className="ap-target__l">
          <h2 id="ap-target-h" className="ap-q">What outcome is this dataset meant to predict?</h2>
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
          <NameFields name={name} setName={setName} purpose={purpose} setPurpose={setPurpose} />
          <ContextPanel job={{ ...job, target }} value={ctx} onChange={setCtx} />
          <div className="ap-acts">
            <button type="button" className={`nk-btn ${target ? '' : 'is-off'} ${busy ? 'is-run' : ''}`} disabled={busy} onClick={() => { if (!target) { setMsg(true); return; } submit({ target, dataset_name: name, purpose, context: contextField(ctx) }); }}>{busy ? 'Checking the target…' : 'Review selection →'}</button>
            <a className="nk-btn nk-btn--ghost" href="/app/" onClick={onLink}>Back</a>
            {msg && !target && <span className="ap-acts__hint ap-acts__hint--stop" role="status">Choose a target column from the uploaded dataset.</span>}
          </div>
        </div>
        <div className="ap-target__r"><Selection name={target} t={target ? infos[target] : undefined} /></div>
      </section>
    </div>
  );
}

const policies = ['pandas_default', 'empty_only', 'custom'];
const availability = ['unknown', 'available_at_prediction', 'unavailable_at_prediction'];

/** Regression and unlabeled profiling: the classic form's CSV interpretation and declarations. */
function TabularConfigure({ job, submit, busy, separator }: { job: JobView; submit: (f: Fields) => void; busy: boolean; separator?: ReactNode }) {
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
  const [avail, setAvail] = useState<Record<string, string>>(() => Object.fromEntries(job.inspection.columns.map((c) => [c, job.config.regression?.feature_availability[c] ?? 'unknown'])));
  const [name, setName] = useState(job.dataset_name ?? '');
  const [purpose, setPurpose] = useState(job.purpose ?? '');
  const [msg, setMsg] = useState(false);
  const [ctx, setCtx] = useState(() => job.config.context ?? emptyContext());
  const fields = (action?: 'preview'): Fields => {
    const f: Fields = { encoding, missing_policy: policy, na_values: na, column_types: types, dataset_name: name, purpose, context: contextField(ctx) };
    if (reg) {
      Object.assign(f, { regression_options_submitted: '1', target_kind: kind, target_units: units, target_minimum: min, target_maximum: max });
      if (target) f.target = target;
      if (nonneg) f.target_nonnegative = 'on';
      if (integer) f.target_integer = 'on';
      for (const c of job.inspection.columns) f[`availability_${c}`] = avail[c];
    }
    if (action) f.action = action;
    return f;
  };
  const i = job.inspection;
  return (
    <div className="ap-cf">
      <header className="ap-head"><span className="nk-label">Step 2 · Configure</span><h1>Configure the analysis.</h1></header>
      {separator}
      <Cards items={[['File', job.source_filename], ['Size', `${MiB(job.file_size)} MiB`], ['Preview rows', fmt(i.preview_row_count)], ['Columns', fmt(i.column_count)]]} />
      <Preview job={job} target={target} />

      <section className="ap-sec" aria-labelledby="ap-csv-h">
        <h2 id="ap-csv-h" className="ap-q">How should the CSV be read?</h2>
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
        <div className="ap-acts"><button type="button" className="nk-btn nk-btn--ghost" disabled={busy} onClick={() => submit(fields('preview'))}>Refresh parsing preview</button></div>
      </section>

      {reg && (
        <section className="ap-target" aria-labelledby="ap-target-h">
          <div className="ap-target__l">
            <h2 id="ap-target-h" className="ap-q">Which numerical outcome should be reviewed?</h2>
            <p className="ap-muted">Preview assessments are provisional. Select the intended outcome explicitly; full confirmation verifies numeric compatibility.</p>
            <div className="ap-opts">
              {(i.target_options ?? []).map((o) => (
                <label key={o.name} className={`ap-opt ${target === o.name ? 'is-on' : ''} ${o.disabled ? 'is-off' : ''}`}>
                  <input type="radio" name="target" checked={target === o.name} onChange={() => setTarget(o.name)} disabled={o.disabled} />
                  <span className="ap-opt__r" aria-hidden="true" />
                  <span className="ap-opt__t"><b>{o.name}</b><span>{o.dtype} · {fmt(o.finite_count ?? 0)} preview finite values · {o.explanation} {o.selector_explanation}</span></span>
                </label>
              ))}
            </div>
          </div>
          <div className="ap-target__r">
            <div className="ap-sel ap-fields ap-fields--panel">
              <span className="ap-sel__k">Declared expectations</span>
              <label>Target intent<select value={kind} onChange={(x) => setKind(x.target.value)}>{['unspecified', 'continuous', 'count'].map((v) => <option key={v} value={v}>{v}</option>)}</select></label>
              <p className="ap-sel__ok">Count declares nonnegative integer values. Observed integers alone do not establish count semantics.</p>
              <label>Units <span>optional · display only</span><input maxLength={80} value={units} onChange={(x) => setUnits(x.target.value)} /></label>
              <div className="ap-fields--two">
                <label>Inclusive minimum <span>optional</span><input type="number" step="any" value={min} onChange={(x) => setMin(x.target.value)} /></label>
                <label>Inclusive maximum <span>optional</span><input type="number" step="any" value={max} onChange={(x) => setMax(x.target.value)} /></label>
              </div>
              <label className="ap-check"><input type="checkbox" checked={nonneg} onChange={(x) => setNonneg(x.target.checked)} /> Require nonnegative values</label>
              <label className="ap-check"><input type="checkbox" checked={integer} onChange={(x) => setInteger(x.target.checked)} /> Require integer values</label>
            </div>
          </div>
        </section>
      )}
      {reg && (
        <details className="ap-more ap-sec">
          <summary>Optional feature availability at the intended prediction time</summary>
          <p className="ap-muted">User-declared context; unknown is the default. The selected target’s entry is ignored.</p>
          <div className="ap-avail">{i.columns.map((c) => <label key={c}><span>{c}</span><select value={avail[c]} onChange={(x) => setAvail((m) => ({ ...m, [c]: x.target.value }))}>{availability.map((v) => <option key={v} value={v}>{v.replace(/_/g, ' ')}</option>)}</select></label>)}</div>
        </details>
      )}

      <ContextPanel job={{ ...job, target }} value={ctx} onChange={setCtx} availability={!reg} />
      <NameFields name={name} setName={setName} purpose={purpose} setPurpose={setPurpose} />
      <div className="ap-acts">
        <button type="button" className={`nk-btn ${reg && !target ? 'is-off' : ''} ${busy ? 'is-run' : ''}`} disabled={busy} onClick={() => { if (reg && !target) { setMsg(true); return; } submit(fields()); }}>{busy ? 'Checking…' : 'Review selection →'}</button>
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
  const separator = <SeparatorBar job={job} onJob={onJob} flash={flash} />;
  if (M3_MODES.includes(job.mode as M3Mode)) return <M3Configure key={job.config.parsing.delimiter} job={job} submit={submit} busy={busy} separator={separator} />;
  return job.mode === 'classification' ? <ClassConfigure key={job.config.parsing.delimiter} job={job} submit={submit} busy={busy} separator={separator} /> : <TabularConfigure key={JSON.stringify(job.config.parsing)} job={job} submit={submit} busy={busy} separator={separator} />;
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
  const [view, setView] = useState(false);
  const [a, setA] = useState<Analysis | null>(null);
  useEffect(() => { let live = true; api.analysis().then((x) => { if (live) setA(x); }).catch(flash); return () => { live = false; }; }, [job]);
  const s = job.summary!;
  const run = a ? fromAnalysis(a, job.mode, job.artifacts) : null;
  const applies = run ? activeTiles(run) : 0;
  return (
    <div className="ap-rs">
      <header className="ap-rs__bar">
        <h1>{s.dataset_name}</h1>
        <p>{s.source_filename} · {a ? taskLabel(a, job.mode) : job.mode}<br />{a ? `${date(a.generated_at)} · ${a.execution.elapsed_seconds.toFixed(2)} s · ${applies} of 14 checks apply · ` : ''}<button type="button" className="ap-rs__open" onClick={() => setView(true)}>Open report ↗</button></p>
      </header>
      {s.execution.status === 'partial' && <p className="ap-note ap-note--warn"><b>Analysis incomplete</b> Review unavailable checks; completed evidence remains available.</p>}

      {a && run ? <Mosaic a={a} run={run} runName={s.dataset_name} /> : <div className="nk-mosaic nk-mosaic--big nk-mosaic--run ap-rs__wait" aria-busy="true" />}
      {a && <ScopeNote guidance={(a as { guidance?: unknown }).guidance} />}

      <section className="ap-rs__out">
        <div>
          <h2 className="ap-q">Take it with you</h2>
          {save?.saved
            ? <p className="ap-muted ap-rs__savedline"><Status tone="on">Saved on this machine · <a href="/app/history" onClick={onLink}>manage in History</a></Status>A PDF you download now is added to the saved copy.</p>
            : <p className="ap-muted">The same evidence as a canonical report, a PDF and strict JSON. {save?.message ? `This analysis wasn’t saved: ${save.message} ` : ''}This result lasts for this session, so download it before starting a new analysis.</p>}
        </div>
        <div className="ap-acts">
          <button type="button" className="nk-btn" onClick={() => setView(true)}>View full report</button>
          <Downloads mode={job.mode} flash={flash} />
          <button type="button" className="nk-btn nk-btn--ghost" onClick={onNew}>New analysis</button>
        </div>
      </section>

      <details className="ap-more ap-rs__cov">
        <summary>Parsing review and coverage</summary>
        <p className="ap-muted">Analysis status: {s.execution.status} · {fmt(s.execution.analyzed_rows)} rows · {fmt(s.execution.analyzed_columns)} columns.</p>
        {job.mode === 'regression' && <>
          {s.scoring.reason && <p className="ap-muted">{s.scoring.reason}</p>}
          {s.target_statistics && <p className="ap-muted">Finite targets: {fmt(s.target_statistics.finite_count)} / {fmt(s.target_statistics.row_count)}.</p>}
          {s.coverage.relationship_search && <p className="ap-note"><b>Relationship search: {s.coverage.relationship_search.status.replace(/_/g, ' ')}</b> {s.coverage.relationship_search.meaning}{s.coverage.relationship_search.status === 'bounded' ? ' Planned pool/work limits are coverage limitations, not diagnostic failures.' : ''}</p>}
        </>}
        {s.parsing_warnings.length ? <Warnings list={s.parsing_warnings} full /> : <p className="ap-muted">No parsing warnings observed within the inspected scope. This does not establish losslessness.</p>}
        <p className="ap-muted">Completed groups: {s.coverage.completed_applicable_groups.join(', ')}. {s.coverage.meaning}</p>
        {s.coverage.unavailable_checks.map((c, k) => { const v = (x: { value: string } | string) => (typeof x === 'string' ? x : x.value); return <p key={k} className="ap-muted">{c.check_id} · {c.scope}: {v(c.applicability)} / {v(c.execution)} — {c.reason}</p>; })}
      </details>
      {view && <Viewer name={s.dataset_name} src={files.report} note="the canonical DataTrust report" downloads={<Downloads mode={job.mode} flash={flash} />} onClose={() => setView(false)} />}
    </div>
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
              {info && step === 'upload' && <Upload info={info} onJob={onJob} flash={flash} />}
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
