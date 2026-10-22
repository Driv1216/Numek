// M4 in the app: Sources, Configure, Confirm and Report, on the same session job as the classic /m4 pages.
// Targets, features, groups and keys are picked as column chips; the request keeps the classic fields.
import { useCallback, useEffect, useRef, useState, type ReactElement } from 'react';
import { Status } from '../foundation/system';
import { reducedMotion } from '../foundation/motion';
import { ApiError, api, type Fields, type M4Analysis, type M4Job, type M4Mode, type SessionInfo } from './api';
import { Corners, SeparatorSelect, Viewer, separatorName } from './parts';
import { date } from './results/adapter';
import { M4_MODE_LABEL, RolesReport, rolesOf, runName } from './results/roles';
import { navigate, onLink } from './router';

type Flash = (e: unknown) => void;
export type M4Step = 'sources' | 'configure' | 'confirm' | 'report';
export const m4Steps: { id: M4Step; n: number; t: string }[] = [{ id: 'sources', n: 1, t: 'Sources' }, { id: 'configure', n: 2, t: 'Configure' }, { id: 'confirm', n: 3, t: 'Confirm' }, { id: 'report', n: 4, t: 'Report' }];
export const m4Href = (s: M4Step) => `/app/m4/${s}`;
const RUN_STATES = ['running', 'completed', 'partial', 'failed', 'cancelled'];

export function m4Reachable(j: M4Job | null): M4Step[] {
  if (!j) return ['sources'];
  const out: M4Step[] = ['sources'];
  if (j.sources.length) out.push('configure');
  if (j.fingerprint) out.push('confirm');
  if (RUN_STATES.includes(j.state)) out.push('report');
  return out;
}

const modeTiles: { id: M4Mode; t: string; d: string; draw: ReactElement }[] = [
  { id: 'splits', t: 'Split audit', d: 'Train, validation and test: overlap, schema and populations.', draw: <svg viewBox="0 0 120 64" aria-hidden="true"><rect x="6" y="18" width="62" height="26" className="ap-d-ink" /><rect x="72" y="18" width="18" height="26" className="ap-d-ln" /><rect x="94" y="18" width="20" height="26" className="ap-d-hot" /></svg> },
  { id: 'versions', t: 'Version comparison', d: 'Reference against current: schema and distributions.', draw: <svg viewBox="0 0 120 64" aria-hidden="true"><rect x="8" y="14" width="42" height="36" className="ap-d-ink" /><path d="M54 32H66" className="ap-d-ln" /><rect x="70" y="14" width="42" height="36" className="ap-d-ln" /><rect x="70" y="38" width="42" height="12" className="ap-d-hot" /></svg> },
  { id: 'before_after', t: 'Before and after preprocessing', d: 'Your file before and after cleaning: reconciliation, lineage and what changed.', draw: <svg viewBox="0 0 120 64" aria-hidden="true"><rect x="8" y="12" width="42" height="40" className="ap-d-ink" /><path d="M54 32H66M62 27L67 32L62 37" className="ap-d-ln" /><rect x="70" y="18" width="42" height="28" className="ap-d-hot" /></svg> },
  { id: 'advanced', t: 'Advanced analysis', d: 'One dataset: dependencies, constraints, segments, readiness.', draw: <svg viewBox="0 0 120 64" aria-hidden="true">{Array.from({ length: 5 }, (_, k) => <rect key={k} x={10 + k * 21} y={12 + (k % 2) * 8} width="14" height={40 - (k % 2) * 8} className={k === 3 ? 'ap-d-hot' : 'ap-d-ln'} />)}</svg> },
];
const ROLES: Record<M4Mode, string[]> = { splits: ['train', 'validation', 'test'], versions: ['reference', 'current'], advanced: ['dataset'], before_after: ['reference', 'current'] };
const ROLE_LABEL: Record<string, string> = { reference: 'reference', current: 'current' };
const TASKS = ['dataset_profile', 'classification', 'regression', 'multilabel_classification', 'clustering', 'anomaly_detection'];
const INTENTS = ['unknown', 'record_disjoint', 'entity_disjoint', 'group_disjoint', 'overlap_permitted'];
const defaultRole = (mode: M4Mode, id: string) => (mode === 'splits' ? (id === 'source1' ? 'train' : id === 'source2' ? 'test' : 'validation') : mode === 'versions' || mode === 'before_after' ? (id === 'source1' ? 'reference' : 'current') : 'dataset');
const split = (v: string | undefined) => (v ?? '').split(',').map((x) => x.trim()).filter(Boolean);

/** Multi-select column chips; the request keeps the classic comma-separated field. */
export function Chips({ options, value, onChange, label }: { options: string[]; value: string[]; onChange: (v: string[]) => void; label: string }) {
  return (
    <div className="ap-chips" role="group" aria-label={label}>
      {options.map((c) => { const on = value.includes(c); return <button key={c} type="button" aria-pressed={on} className={on ? 'is-on' : ''} onClick={() => onChange(on ? value.filter((x) => x !== c) : [...value, c])}>{c}</button>; })}
    </div>
  );
}

export function SourceCard({ s, role }: { s: Pick<M4Job['sources'][number], 'id' | 'filename' | 'origin' | 'headers' | 'preview' | 'sha256' | 'delimiter' | 'delimiter_detected'>; role?: string }) {
  return (
    <div className="ap-src">
      <div className="ap-src__h"><span className="ap-strip__role">{role ?? s.id}</span><b>{s.filename}</b><span>{s.origin === 'upload' ? 'uploaded' : 'from a data root'} · {s.headers.length} {s.preview?.length ? 'columns' : 'fields'}{s.sha256 ? ` · ${s.sha256.slice(0, 10)}…` : ''}{s.delimiter && s.delimiter !== ',' ? ` · ${separatorName(s.delimiter)}-separated${s.delimiter_detected ? ' (detected)' : ''}` : ''}</span></div>
      <div className="ap-table" tabIndex={0} aria-label={`${s.filename} raw preview`}>
        <table><thead><tr>{s.headers.map((h) => <th key={h}>{h}</th>)}</tr></thead>
          <tbody>{(s.preview ?? []).map((r, i) => <tr key={i}>{(r.tokens ?? []).map((t, k) => <td key={k}>{t}</td>)}</tr>)}</tbody></table>
      </div>
      <p className="ap-muted">Raw header and preview are provisional. Identifier/key declarations and full-column inference resolve the final interpretation.</p>
    </div>
  );
}

function Sources({ job, info, setJob, flash }: { job: M4Job | null; info: SessionInfo; setJob: (j: M4Job | null) => void; flash: Flash }) {
  const input = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState<M4Mode>(job?.mode ?? 'splits');
  const [root, setRoot] = useState(info.roots[0]?.id ?? '');
  const [rel, setRel] = useState('');
  const [sep, setSep] = useState('auto');
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);
  const act = (p: Promise<{ job: M4Job | null }>) => { setBusy(true); return p.then((r) => setJob(r.job)).catch(flash).finally(() => setBusy(false)); };
  const choose = (m: M4Mode) => { setMode(m); if (!job || job.mode !== m) act(api.m4.start(m)); };
  const full = !!job && job.sources.length >= job.limit;
  return (
    <div className="ap-up">
      <header className="ap-head"><span className="nk-label">Step 1 · Sources</span><h1>Compare datasets.</h1><p>Sources are read by this local application. Uploads stay in its temporary workspace; data-root files are read where they are.</p></header>
      <section className="ap-sec" aria-labelledby="ap-m4-h">
        <h2 id="ap-m4-h" className="ap-q">What kind of comparison?</h2>
        <div className="ap-modes" role="radiogroup" aria-label="Comparison mode">
          {modeTiles.map((m) => (
            <button key={m.id} type="button" role="radio" aria-checked={mode === m.id && !!job} disabled={busy} className={`ap-mode ${mode === m.id && job ? 'is-on' : ''}`} onClick={() => choose(m.id)}>
              {mode === m.id && job && <Corners />}
              <span className="ap-mode__draw">{m.draw}</span><b>{m.t}</b><span>{m.d}</span>
            </button>
          ))}
        </div>
        {job && job.sources.length > 0 && <p className="ap-muted ap-co__text">Choosing another mode starts a new comparison and removes these sources.</p>}
      </section>
      {job && (
        <section className="ap-sec" aria-labelledby="ap-src-h">
          <h2 id="ap-src-h" className="ap-q">Sources · {job.sources.length} of {job.limit}</h2>
          {job.sources.map((s, i) => <SourceCard key={s.id} s={s} role={ROLES[job.mode][i] ?? s.id} />)}
          {!full && (
            <div className="ap-add">
              <div className={`ap-drop ap-drop--small ${over ? 'is-over' : ''}`} onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
                onDrop={(e) => { e.preventDefault(); setOver(false); const f = e.dataTransfer.files[0]; if (f) act(api.m4.upload(f, sep)); }}>
                <div className="ap-drop__empty"><b>Drop a CSV for {ROLES[job.mode][job.sources.length] ?? 'the next source'}</b><span>Up to {info.upload_limit_mib} MiB per upload</span>
                  <div className="ap-drop__acts"><button type="button" className="nk-btn" disabled={busy} onClick={() => input.current?.click()}>{busy ? 'Reading…' : 'Choose a file'}</button></div></div>
                <input ref={input} type="file" accept=".csv,text/csv" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) act(api.m4.upload(f, sep)); e.target.value = ''; }} />
              </div>
              <div className="ap-sepbar"><SeparatorSelect value={sep} onChange={setSep} /><span>Applies to the next source you add.</span></div>
              {info.roots.length > 0 && (
                <div className="ap-root">
                  <b>Or a file in a data root</b>
                  <div className="ap-fields ap-fields--two">
                    <label>Data root<select value={root} onChange={(e) => setRoot(e.target.value)}>{info.roots.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}</select></label>
                    <label>Path inside it <span>for example splits/test.csv</span><input value={rel} onChange={(e) => setRel(e.target.value)} placeholder="file.csv" /></label>
                  </div>
                  <button type="button" className="nk-btn nk-btn--ghost" disabled={busy || !rel.trim()} onClick={() => act(api.m4.local(root, rel.trim(), sep)).then(() => setRel(''))}>Add this file</button>
                  <p className="ap-muted">Only files inside the roots DataTrust was started with; links that lead outside are refused.</p>
                </div>
              )}
            </div>
          )}
          <div className="ap-acts">
            {job.sources.length ? <a className="nk-btn" href={m4Href('configure')} onClick={onLink}>Review roles, parsing and alignment →</a> : <span className="nk-btn is-off" aria-disabled="true">Review roles →</span>}
            <span className="ap-acts__hint">{job.mode === 'advanced' ? 'One source.' : `Up to ${job.limit} sources.`} The 1–5 GB combined range is an engineering objective, not guaranteed capacity.</span>
          </div>
        </section>
      )}
    </div>
  );
}

function KeyRows({ value, options, onChange, label }: { value: string; options: string[]; onChange: (v: string) => void; label: string }) {
  const rows = value.split('\n').filter((l) => l.trim()).map(split);
  const set = (r: string[][]) => onChange(r.filter((x) => x.length).map((x) => x.join(',')).join('\n'));
  return (
    <div className="ap-keys">
      <b>{label}</b>
      {rows.map((r, i) => (
        <div key={i} className="ap-keys__row">
          <Chips options={options} value={r} label={`${label}, composite ${i + 1}`} onChange={(v) => set(rows.map((x, k) => (k === i ? v : x)))} />
          <button type="button" className="ap-link" onClick={() => set(rows.filter((_, k) => k !== i))}>Remove</button>
        </div>
      ))}
      <button type="button" className="ap-link" onClick={() => onChange([...rows.map((x) => x.join(',')), options[0] ?? ''].filter(Boolean).join('\n'))}>Add a composite key</button>
    </div>
  );
}

function Configure({ job, setJob, flash }: { job: M4Job; setJob: (j: M4Job) => void; flash: Flash }) {
  const [f, setF] = useState<Fields>(() => {
    const out: Fields = { identity_keys: '', group_keys: '', evaluation_intent: 'unknown', configuration: '{}', ...job.fields };
    for (const s of job.sources) {
      out[`${s.id}_role`] ??= defaultRole(job.mode, s.id); out[`${s.id}_task`] ??= 'dataset_profile';
      for (const k of ['targets', 'features', 'groups']) out[`${s.id}_${k}`] ??= '';
      out[`${s.id}_parsing`] ??= '{}'; out[`${s.id}_mapping`] ??= '{}';
    }
    return out;
  });
  const [busy, setBusy] = useState(false);
  const set = (k: string, v: string) => setF((x) => ({ ...x, [k]: v }));
  const aligned = [...new Set(job.sources.flatMap((s) => { try { const m = JSON.parse(f[`${s.id}_mapping`] || '{}') as Record<string, string>; return s.headers.map((h) => m[h] ?? h); } catch { return s.headers; } }))];
  const submit = () => { setBusy(true); api.m4.configure(f).then((r) => { setJob(r.job); navigate(m4Href('confirm')); }).catch(flash).finally(() => setBusy(false)); };
  return (
    <div className="ap-cf">
      <header className="ap-head"><span className="nk-label">Step 2 · Configure</span><h1>Roles, parsing and alignment.</h1><p>{M4_MODE_LABEL[job.mode]}. No silent feature intersection or inferred renaming occurs.</p></header>
      {job.sources.map((s) => (
        <section key={s.id} className="ap-sec ap-m4src" aria-label={`${s.filename} declarations`}>
          <h2 className="ap-q">{s.filename}</h2>
          <div className="ap-fields ap-fields--two">
            {job.mode === 'before_after'
              ? <label>Source role<input readOnly value={s.id === 'source1' ? 'Before (the first source)' : 'After (the second source)'} /></label>
              : <label>Source role<select value={f[`${s.id}_role`]} onChange={(e) => set(`${s.id}_role`, e.target.value)}>{ROLES[job.mode].map((r) => <option key={r} value={r}>{ROLE_LABEL[r] ?? r}</option>)}</select></label>}
            <label>Task<select value={f[`${s.id}_task`]} onChange={(e) => set(`${s.id}_task`, e.target.value)}>{TASKS.map((t) => <option key={t}>{t}</option>)}</select></label>
          </div>
          {([['targets', 'Targets', 'leave empty for target-free sources'], ['features', 'Selected features', 'none selected uses every eligible feature'], ['groups', 'Within-source group columns', '']] as const).map(([k, l, hint]) => (
            <div key={k} className="ap-chipset"><span className="ap-chipset__l">{l}{hint && <em>{hint}</em>}</span><Chips options={s.headers} value={split(f[`${s.id}_${k}`])} label={`${l} for ${s.filename}`} onChange={(v) => set(`${s.id}_${k}`, v.join(','))} /></div>
          ))}
          <details className="ap-more">
            <summary>Parsing, analytical declarations and name mapping</summary>
            <div className="ap-fields ap-fields--two">
              <label>Per-source parsing and analytical declarations <span>AnalysisConfig JSON</span><textarea rows={4} value={f[`${s.id}_parsing`]} onChange={(e) => set(`${s.id}_parsing`, e.target.value)} /></label>
              <label>Source-name → aligned-name mapping <span>JSON; exact names otherwise</span><textarea rows={4} value={f[`${s.id}_mapping`]} onChange={(e) => set(`${s.id}_mapping`, e.target.value)} /></label>
            </div>
            <p className="ap-muted">Example: {'{"parsing":{"column_types":{"id":"string"}},"features":{"semantic_types":{"id":"identifier"}}}'}. Declared identifiers and keys default to exact strings and empty-only missingness.</p>
          </details>
        </section>
      ))}
      {job.mode !== 'advanced' && (
        <section className="ap-sec" aria-labelledby="ap-cmp-h">
          <h2 id="ap-cmp-h" className="ap-q">How the sources relate</h2>
          <KeyRows label="Identity keys" value={f.identity_keys} options={aligned} onChange={(v) => set('identity_keys', v)} />
          <KeyRows label="Comparison group keys" value={f.group_keys} options={aligned} onChange={(v) => set('group_keys', v)} />
          {job.mode === 'before_after' && (
            <div className="ap-fields">
              <label>Declared transformations <span>JSON list · kinds: impute, drop_rows, drop_columns, cap, transform, encode, rename, deduplicate, filter, resample, other</span>
                <textarea rows={4} value={f.transformations ?? '[]'} onChange={(e) => set('transformations', e.target.value)} /></label>
              <p className="ap-muted">For example {'[{"kind": "drop_columns", "columns": ["telephone"]}, {"kind": "impute", "columns": ["age"]}, {"kind": "filter", "description": "credit_amount < 10000"}]'}. Declared steps are compared with what the data shows; nothing is performed. Identity keys above make record-level lineage possible.</p>
            </div>
          )}
{job.mode !== 'before_after' &&           <div className="ap-fields"><label>Evaluation intent<select value={f.evaluation_intent} onChange={(e) => set('evaluation_intent', e.target.value)}>{INTENTS.map((i) => <option key={i} value={i}>{i.replace(/_/g, ' ')}</option>)}</select></label></div>}
        </section>
      )}
      <details className="ap-more ap-sec">
        <summary>Job execution and advanced diagnostics</summary>
        <div className="ap-fields"><label>Configuration <span>JSON</span><textarea rows={5} value={f.configuration} onChange={(e) => set('configuration', e.target.value)} /></label></div>
        <p className="ap-muted">Use execution for job limits and advanced for constraints, requested_pairs, spearman_pairs, and segments. Version comparisons optionally accept inference:true with sampling:"independent_rows". Budgets remain bounded and coverage is reported explicitly.</p>
      </details>
      <div className="ap-acts">
        <button type="button" className={`nk-btn ${busy ? 'is-run' : ''}`} disabled={busy} onClick={submit}>{busy ? 'Binding the specification…' : 'Review effective specification →'}</button>
        <a className="nk-btn nk-btn--ghost" href={m4Href('sources')} onClick={onLink}>Back to sources</a>
      </div>
    </div>
  );
}

type Input = { id: string; role: string; dataset: { path: string; source_filename: string | null }; task: { kind: string; targets: string[] } };
function Confirm({ job, setJob, flash, saving }: { job: M4Job; setJob: (j: M4Job) => void; flash: Flash; saving: boolean }) {
  const [keep, setKeep] = useState(true);
  const [busy, setBusy] = useState(false);
  const m = job.manifest as Record<string, unknown>;
  const inputs = (job.mode === 'advanced' ? [m] : (m.inputs as unknown[])) as Input[];
  const run = () => { setBusy(true); api.m4.run({ fingerprint: job.fingerprint ?? '', save_to_history: saving && keep ? 'yes' : 'no' }).then((r) => { setJob(r.job); navigate(m4Href('report')); }).catch(flash).finally(() => setBusy(false)); };
  return (
    <div className="ap-co">
      <header className="ap-head"><span className="nk-label">Step 3 · Confirm</span><h1>Confirm the declarations.</h1></header>
      <div className="ap-co__task"><b>{M4_MODE_LABEL[job.mode]} · {inputs.length} source{inputs.length > 1 ? 's' : ''}</b><span>This confirmation binds every source hash, parsing/key representation, mapping and effective declaration. Raw previews remain provisional until full-column inference completes.</span></div>
      <dl className="ap-cards">{inputs.map((i) => <div key={i.id}><dt>{i.role}</dt><dd className="ap-cards__small">{i.dataset.source_filename ?? i.dataset.path}<br />{i.task.kind}{i.task.targets?.length ? ` · ${i.task.targets.join(', ')}` : ''}</dd></div>)}</dl>
      {job.mode !== 'advanced' && <p className="ap-muted">Identity keys: {(m.identity_keys as string[][] | undefined)?.map((k) => k.join(' + ')).join('; ') || 'none'} · group keys: {(m.group_keys as string[][] | undefined)?.map((k) => k.join(' + ')).join('; ') || 'none'} · evaluation intent: {String(m.evaluation_intent ?? 'unknown').replace(/_/g, ' ')}.</p>}
      <details className="ap-more ap-sec"><summary>Effective source and task specification</summary><pre className="ap-pre">{JSON.stringify(job.manifest, null, 2)}</pre></details>
      <details className="ap-more ap-sec"><summary>Execution, diagnostic bounds and parsing settings</summary><pre className="ap-pre">{JSON.stringify(job.configuration, null, 2)}</pre></details>
      <p className="ap-note">Lexical identifiers preserve leading zeros, whitespace, case, punctuation and Unicode sequences. Numeric keys require finite, exact compatible equality. No silent feature intersection or inferred renaming occurs.</p>
      {saving && <label className="ap-check ap-co__keep"><input type="checkbox" checked={!keep} onChange={(e) => setKeep(!e.target.checked)} /> Don’t save this comparison on this machine</label>}
      <div className="ap-acts">
        <button type="button" className={`nk-btn ${busy ? 'is-run' : ''}`} disabled={busy} onClick={run}>Confirm and analyze locally</button>
        <a className="nk-btn nk-btn--ghost" href={m4Href('configure')} onClick={onLink}>Edit declarations (retain sources)</a>
      </div>
    </div>
  );
}

async function downloadM4Pdf() {
  const res = await fetch(api.m4.download('pdf'), { credentials: 'same-origin' });
  if (!res.ok || !(res.headers.get('Content-Type') ?? '').includes('application/pdf')) throw new ApiError((await res.json().catch(() => null))?.error?.message ?? 'The PDF report could not be generated.', res.status);
  const url = URL.createObjectURL(await res.blob());
  const a = Object.assign(document.createElement('a'), { href: url, download: 'numek-m4-review.pdf' });
  document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function M4Downloads({ flash }: { flash: Flash }) {
  const [busy, setBusy] = useState(false);
  return (
    <>
      <button type="button" className="ap-sheet__dl" disabled={busy} onClick={() => { setBusy(true); downloadM4Pdf().catch(flash).finally(() => setBusy(false)); }}>{busy ? 'Rendering PDF…' : 'Download PDF ↓'}</button>
      <a className="ap-sheet__dl" href={api.m4.download('html')}>Download HTML ↓</a>
      <a className="ap-sheet__dl" href={api.m4.download('json')}>Download JSON ↓</a>
    </>
  );
}

export function m4Header(a: M4Analysis, mode: string, open: () => void) {
  const roles = rolesOf(a);
  return (
    <header className="ap-rs__bar">
      <h1>{runName(a)}</h1>
      <p>{roles.map((r) => r.file).join(' ↔ ')} · {M4_MODE_LABEL[mode] ?? mode}<br />{date(a.generated_at)} · {a.findings.length} finding{a.findings.length === 1 ? '' : 's'} · <button type="button" className="ap-rs__open" onClick={open}>Open report ↗</button></p>
    </header>
  );
}

function Report({ job, setJob, flash, onNew }: { job: M4Job; setJob: (j: M4Job) => void; flash: Flash; onNew: () => void }) {
  const [a, setA] = useState<M4Analysis | null>(null);
  const [view, setView] = useState(false);
  const running = job.state === 'running';
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => { api.m4.job().then((r) => r.job && setJob(r.job)).catch(() => {}); }, 1000);
    return () => clearInterval(t);
  }, [running, setJob]);
  useEffect(() => { if (job.result) api.m4.analysis().then(setA).catch(flash); }, [job.result?.status]);
  if (running) return (
    <div className="ap-co">
      <header className="ap-head"><span className="nk-label">Step 4 · Analyze</span><h1>Analyzing locally.</h1><p>One supervised worker on this machine. You can leave this page; the result stays in this session.</p></header>
      <div className="ap-co__task ap-run"><b role="status">{job.progress.stage ?? 'Starting'}</b><span>{M4_MODE_LABEL[job.mode]} · {job.sources.map((s) => s.filename).join(' ↔ ')}</span><i className="ap-run__bar" aria-hidden="true" /></div>
      <div className="ap-acts"><button type="button" className="nk-btn nk-btn--ghost" onClick={() => api.m4.cancel().then((r) => setJob(r.job)).catch(flash)}>Cancel analysis</button></div>
    </div>
  );
  if (job.state === 'failed' || job.state === 'cancelled') return (
    <div className="ap-co">
      <header className="ap-head"><span className="nk-label">Step 4 · Report</span><h1>{job.state === 'cancelled' ? 'Analysis cancelled.' : 'Analysis stopped.'}</h1></header>
      <p className="ap-note ap-note--warn">{job.error ?? 'No completed result was published.'}</p>
      <div className="ap-acts"><a className="nk-btn" href={m4Href('confirm')} onClick={onLink}>Back to confirm</a><a className="nk-btn nk-btn--ghost" href={m4Href('configure')} onClick={onLink}>Edit declarations</a></div>
    </div>
  );
  if (!a) return <div className="ap-rs"><div className="nk-mosaic nk-mosaic--big nk-mosaic--run ap-rs__wait" aria-busy="true" /></div>;
  return (
    <>
      <RolesReport a={a} header={m4Header(a, job.mode, () => setView(true))} out={
        <section className="ap-rs__out">
          <div><h2 className="ap-q">Take it with you</h2>
            {job.saved_entry ? <p className="ap-muted ap-rs__savedline"><Status tone="on">Saved on this machine · <a href="/app/history" onClick={onLink}>manage in History</a></Status>A PDF you download now is added to the saved copy.</p>
              : <p className="ap-muted">Exports use completed evidence and do not reanalyze. This result lasts for this session.</p>}</div>
          <div className="ap-acts"><button type="button" className="nk-btn" onClick={() => setView(true)}>View full report</button><M4Downloads flash={flash} /><button type="button" className="nk-btn nk-btn--ghost" onClick={onNew}>New comparison</button></div>
        </section>} />
      {view && <Viewer name={runName(a)} src={api.m4.report} note="the canonical DataTrust comparison report" downloads={<M4Downloads flash={flash} />} onClose={() => setView(false)} />}
    </>
  );
}

/** The M4 workflow: its own steps on the shared shell. */
export function M4Flow({ path, info, flash, saving, onRail, onSaved }: { path: string; info: SessionInfo; flash: Flash; saving: boolean; onRail: (s: M4Step, ok: M4Step[]) => void; onSaved: () => void }) {
  const [job, setJobState] = useState<M4Job | null | undefined>(undefined);
  const setJob = useCallback((j: M4Job | null) => setJobState(j), []);
  useEffect(() => { api.m4.job().then((r) => setJobState(r.job)).catch((e) => { setJobState(null); flash(e); }); }, []);
  const requested = (/^\/app\/m4\/(sources|configure|confirm|report)\/?$/.exec(path)?.[1] ?? 'sources') as M4Step;
  const ok = m4Reachable(job ?? null);
  const step = ok.includes(requested) ? requested : ok[ok.length - 1];
  useEffect(() => { if (job !== undefined && step !== requested) navigate(m4Href(step), true); }, [job, step, requested]);
  useEffect(() => { onRail(step, ok); }, [step, ok.join()]);
  useEffect(() => { if (job?.saved_entry) onSaved(); }, [job?.saved_entry]);
  useEffect(() => { scrollTo({ top: 0, behavior: reducedMotion() ? 'auto' : 'smooth' }); }, [step]);
  if (job === undefined) return null;
  const onNew = () => api.m4.reset().then(() => { setJob(null); navigate(m4Href('sources')); }).catch(flash);
  return (
    <>
      {step === 'sources' && <Sources job={job} info={info} setJob={setJob} flash={flash} />}
      {job && step === 'configure' && <Configure key={job.sources.map((s) => s.id).join()} job={job} setJob={setJob} flash={flash} />}
      {job && step === 'confirm' && <Confirm job={job} setJob={setJob} flash={flash} saving={saving} />}
      {job && step === 'report' && <Report job={job} setJob={setJob} flash={flash} onNew={onNew} />}
    </>
  );
}
