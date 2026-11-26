// The supervised workflows (M5 to M9) on one frame: Sources, Configure, Confirm and Report on the shared
// shell, a declarative field renderer that keeps the classic field contract, the running and stopped
// views, and the mosaic page (hero tile, family tiles, actions, coverage) every result uses.
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { reducedMotion } from '../foundation/motion';
import { ApiError, call, type Fields, type SessionInfo } from './api';
import { Chips, SourceCard } from './m4';
import { Viewer } from './parts';
import { ReportBar } from './results/shell/ReportBar';
import { navigate, onLink } from './router';

type Flash = (e: unknown) => void;
export type FlowStep = 'sources' | 'configure' | 'confirm' | 'report';
export const flowSteps: { id: FlowStep; n: number; t: string }[] = [{ id: 'sources', n: 1, t: 'Sources' }, { id: 'configure', n: 2, t: 'Configure' }, { id: 'confirm', n: 3, t: 'Confirm' }, { id: 'report', n: 4, t: 'Report' }];
const RUN_STATES = ['running', 'completed', 'partial', 'failed', 'cancelled'];
const BASE = '/api/datatrust/v1';

export interface FlowSource { id: string; filename: string; format?: string | null; origin: 'upload' | 'local'; headers: string[]; preview: { tokens?: string[] }[]; sha256: string; [k: string]: unknown }
export interface FlowJob {
  state: string; sources: FlowSource[]; fields: Fields; fingerprint: string | null; manifest: Record<string, unknown> | null; configuration: Record<string, unknown> | null;
  effective: Record<string, unknown> | null; progress: Record<string, unknown>; error: string | null; result: { status: string; findings: number } | null; saved_entry: string | null; [k: string]: unknown;
}
export type Doc = Record<string, unknown>;

/** The API for one supervised workflow, under its classic route name (/temporal, /text, /images, /cross). */
export function flowApi(base: string) {
  return {
    job: () => call<{ job: FlowJob | null }>('GET', `${base}/job`),
    start: (f: Fields = {}) => call<{ job: FlowJob }>('POST', `${base}/start`, f),
    upload(file: File, extra: Fields = {}, field = 'dataset') { const f = new FormData(); for (const [k, v] of Object.entries(extra)) f.set(k, v); f.set(field, file); return call<{ job: FlowJob }>('POST', `${base}/sources`, f); },
    local: (body: Fields) => call<{ job: FlowJob }>('POST', `${base}/sources`, body),
    post: (path: string, body: Fields | FormData = {}) => call<{ job: FlowJob } & Doc>('POST', `${base}/${path}`, body),
    configure: (f: Fields) => call<{ job: FlowJob }>('POST', `${base}/configure`, f),
    run: (f: Fields) => call<{ job: FlowJob }>('POST', `${base}/run`, f),
    cancel: () => call<{ job: FlowJob }>('POST', `${base}/cancel`, {}),
    reset: () => call<{ job: null }>('POST', `${base}/new`, {}),
    async analysis(): Promise<Doc> {
      const res = await fetch(`${BASE}${base}/analysis`, { credentials: 'same-origin' });
      const json = await res.json().catch(() => null);
      if (!res.ok) throw new ApiError(json?.error?.message ?? 'The result is not available.', res.status);
      return json;
    },
    report: `${BASE}${base}/report`,
    /** dashboard_companion_v1 for this session's result (an API path for `call`). */
    presentation: `${base}/presentation`,
  };
}
export type FlowApi = ReturnType<typeof flowApi>;

export function flowReachable(j: FlowJob | null): FlowStep[] {
  if (!j) return ['sources'];
  const out: FlowStep[] = ['sources'];
  if (j.sources.length || j.state === 'configure') out.push('configure');
  if (j.fingerprint) out.push('confirm');
  if (RUN_STATES.includes(j.state)) out.push('report');
  return out;
}

/** Moves on once a supervised phase finishes (running → state), never when the user returns to an earlier step. */
export function useAfterRun(job: FlowJob | null, phase: string, state: string, to: string) {
  const prev = useRef(job?.state);
  useEffect(() => { if (prev.current === 'running' && job?.state === state && job.phase === phase) navigate(to); prev.current = job?.state; }, [job?.state, job?.phase]); // eslint-disable-line react-hooks/exhaustive-deps
}

/* ——— Declarative fields: the classic field names, the approved Configure vocabulary ——— */

export interface RowCol { label: string; kind?: 'text' | 'select' | 'column'; options?: string[] }
export interface Field {
  name: string; label: string; kind?: 'text' | 'select' | 'area' | 'chips' | 'rows' | 'column'; options?: string[]; def?: string; hint?: string;
  rows?: number; when?: (v: Fields) => boolean; columns?: RowCol[]; wide?: boolean;
}
export interface Section { title: string; fields: Field[]; collapsed?: boolean; note?: string; when?: (v: Fields) => boolean }

/** Every field's classic default, so the request carries the same fields the classic form submits. */
export function defaults(sections: Section[], prefix = ''): Fields {
  const out: Fields = {};
  for (const s of sections) for (const f of s.fields) out[prefix + f.name] = f.def ?? (f.kind === 'select' ? f.options?.[0] ?? '' : '');
  return out;
}

function Rows({ value, columns, headers, onChange, label }: { value: string; columns: RowCol[]; headers: string[]; onChange: (v: string) => void; label: string }) {
  const rows = value.split('\n').filter((l) => l.trim()).map((l) => { const v = l.split('|').map((x) => x.trim()); while (v.length < columns.length) v.push(''); return v; });
  const set = (r: string[][]) => onChange(r.map((x) => x.join('|')).join('\n'));
  return (
    <div className="ap-rows" role="group" aria-label={label}>
      {rows.map((r, i) => (
        <div key={i} className="ap-rows__r">
          {columns.map((c, k) => {
            const upd = (v: string) => set(rows.map((x, j) => (j === i ? x.map((y, m) => (m === k ? v : y)) : x)));
            const opts = c.kind === 'column' ? ['', ...headers] : c.options;
            return <label key={k}>{c.label}{opts ? <select value={r[k]} onChange={(e) => upd(e.target.value)}>{opts.map((o) => <option key={o} value={o}>{o || '—'}</option>)}</select> : <input value={r[k]} onChange={(e) => upd(e.target.value)} />}</label>;
          })}
          <button type="button" className="ap-link" onClick={() => set(rows.filter((_, j) => j !== i))}>Remove</button>
        </div>
      ))}
      <button type="button" className="ap-link" onClick={() => set([...rows, columns.map((c) => (c.options ? c.options[0] : ''))])}>Add a row</button>
    </div>
  );
}

export function FieldSections({ sections, values, set, prefix = '', headers = [] }: { sections: Section[]; values: Fields; set: (k: string, v: string) => void; prefix?: string; headers?: string[] }) {
  const local: Fields = Object.fromEntries(Object.entries(values).filter(([k]) => k.startsWith(prefix)).map(([k, v]) => [k.slice(prefix.length), v]));
  return (
    <>
      {sections.filter((s) => !s.when || s.when(local)).map((s) => {
        const body = (
          <>
            {s.note && <p className="ap-muted">{s.note}</p>}
            <div className="ap-fields ap-fields--two ap-fields--flow">
              {s.fields.filter((f) => !f.when || f.when(local)).map((f) => {
                const k = prefix + f.name, v = values[k] ?? '';
                const lab = <>{f.label}{f.hint && <span>{f.hint}</span>}</>;
                if (f.kind === 'chips') return <div key={k} className="ap-chipset ap-chipset--field"><span className="ap-chipset__l">{f.label}{f.hint && <em>{f.hint}</em>}</span><Chips options={headers} value={v.split(',').map((x) => x.trim()).filter(Boolean)} label={f.label} onChange={(x) => set(k, x.join(','))} /></div>;
                if (f.kind === 'rows') return <div key={k} className="ap-fields__wide"><span className="ap-chipset__l">{f.label}{f.hint && <em>{f.hint}</em>}</span><Rows value={v} columns={f.columns ?? []} headers={headers} onChange={(x) => set(k, x)} label={f.label} /></div>;
                if (f.kind === 'select' || f.kind === 'column') { const opts = f.kind === 'column' ? ['', ...headers] : f.options ?? []; return <label key={k}>{lab}<select value={v} onChange={(e) => set(k, e.target.value)}>{opts.map((o) => <option key={o} value={o}>{o ? o.replace(/_/g, ' ') : '—'}</option>)}</select></label>; }
                if (f.kind === 'area') return <label key={k} className={f.wide ? 'ap-fields__wide' : ''}>{lab}<textarea rows={f.rows ?? 3} value={v} onChange={(e) => set(k, e.target.value)} /></label>;
                return <label key={k}>{lab}<input value={v} onChange={(e) => set(k, e.target.value)} /></label>;
              })}
            </div>
          </>
        );
        return s.collapsed ? <details key={s.title} className="ap-more ap-sec"><summary>{s.title}</summary>{body}</details> : <section key={s.title} className="ap-sec"><h3 className="ap-sub">{s.title}</h3>{body}</section>;
      })}
    </>
  );
}

/* ——— Sources ——— */

export function AddSource({ info, onUpload, onLocal, label, accept, extra }: { info: SessionInfo; onUpload: (f: File) => Promise<unknown>; onLocal: (root: string, rel: string) => Promise<unknown>; label: string; accept: string; extra?: ReactNode }) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);
  const [root, setRoot] = useState(info.roots[0]?.id ?? '');
  const [rel, setRel] = useState('');
  const go = (p: Promise<unknown>) => { setBusy(true); p.finally(() => setBusy(false)); };
  return (
    <div className="ap-add">
      <div className={`ap-drop ap-drop--small ${over ? 'is-over' : ''}`} onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); const f = e.dataTransfer.files[0]; if (f) go(onUpload(f)); }}>
        <div className="ap-drop__empty"><b>{label}</b><span>Up to {info.upload_limit_mib} MiB per upload</span>
          {extra}
          <div className="ap-drop__acts"><button type="button" className="nk-btn" disabled={busy} onClick={() => input.current?.click()}>{busy ? 'Reading…' : 'Choose a file'}</button></div></div>
        <input ref={input} type="file" accept={accept} hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) go(onUpload(f)); e.target.value = ''; }} />
      </div>
      {info.roots.length > 0 && (
        <div className="ap-root">
          <b>Or a file in a data root</b>
          <div className="ap-fields ap-fields--two">
            <label>Data root<select value={root} onChange={(e) => setRoot(e.target.value)}>{info.roots.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}</select></label>
            <label>Path inside it <span>relative to the root</span><input value={rel} onChange={(e) => setRel(e.target.value)} placeholder="file.csv" /></label>
          </div>
          <button type="button" className="nk-btn nk-btn--ghost" disabled={busy || !rel.trim()} onClick={() => go(onLocal(root, rel.trim()).then(() => setRel('')))}>Add this file</button>
          <p className="ap-muted">Only files inside the roots DataTrust was started with; links that lead outside are refused.</p>
        </div>
      )}
    </div>
  );
}

export { SourceCard };

/* ——— Confirm, running and stopped ——— */

export function ConfirmFrame({ job, api, flash, saving, prefix, task, children, onRun }: { job: FlowJob; api: FlowApi; flash: Flash; saving: boolean; prefix: string; task: ReactNode; children?: ReactNode; onRun: (j: FlowJob) => void }) {
  const [keep, setKeep] = useState(true);
  const [busy, setBusy] = useState(false);
  const run = () => { setBusy(true); api.run({ fingerprint: job.fingerprint ?? '', save_to_history: saving && keep ? 'yes' : 'no' }).then((r) => { onRun(r.job); navigate(`${prefix}/report`); }).catch(flash).finally(() => setBusy(false)); };
  return (
    <div className="ap-co">
      <header className="ap-head"><span className="nk-label">Step 3 · Confirm</span><h1>Confirm the declarations.</h1></header>
      <div className="ap-co__task">{task}</div>
      {children}
      {job.effective && <details className="ap-more ap-sec"><summary>Effective specification bound by this confirmation</summary><pre className="ap-pre">{JSON.stringify(job.effective, null, 2)}</pre></details>}
      {job.manifest && <details className="ap-more ap-sec"><summary>Declarations</summary><pre className="ap-pre">{JSON.stringify(job.manifest, null, 2)}</pre></details>}
      {saving && <label className="ap-check ap-co__keep"><input type="checkbox" checked={!keep} onChange={(e) => setKeep(!e.target.checked)} /> Don’t save this analysis on this machine</label>}
      <div className="ap-acts">
        <button type="button" className={`nk-btn ${busy ? 'is-run' : ''}`} disabled={busy} onClick={run}>Confirm and analyze locally</button>
        <a className="nk-btn nk-btn--ghost" href={`${prefix}/configure`} onClick={onLink}>Edit declarations</a>
      </div>
    </div>
  );
}

export function Running({ job, label, api, setJob, flash }: { job: FlowJob; label: string; api: FlowApi; setJob: (j: FlowJob) => void; flash: Flash }) {
  const stage = typeof job.progress.stage === 'string' ? job.progress.stage : Object.entries(job.progress).filter(([, v]) => typeof v !== 'object').map(([k, v]) => `${k.replace(/_/g, ' ')} ${v}`).join(' · ');
  return (
    <div className="ap-co">
      <header className="ap-head"><span className="nk-label">Step 4 · Analyze</span><h1>Analyzing locally.</h1><p>One supervised worker on this machine. You can leave this page; the result stays in this session.</p></header>
      <div className="ap-co__task ap-run"><b role="status">{stage || 'Starting'}</b><span>{label} · {job.sources.map((s) => s.filename).join(' · ')}</span><i className="ap-run__bar" aria-hidden="true" /></div>
      <div className="ap-acts"><button type="button" className="nk-btn nk-btn--ghost" onClick={() => api.cancel().then((r) => setJob(r.job)).catch(flash)}>Cancel analysis</button></div>
    </div>
  );
}

export function Stopped({ job, prefix }: { job: FlowJob; prefix: string }) {
  return (
    <div className="ap-co">
      <header className="ap-head"><span className="nk-label">Step 4 · Report</span><h1>{job.state === 'cancelled' ? 'Analysis cancelled.' : 'Analysis stopped.'}</h1></header>
      <p className="ap-note ap-note--warn">{job.error ?? 'No completed result was published.'}</p>
      <div className="ap-acts"><a className="nk-btn" href={`${prefix}/confirm`} onClick={onLink}>Back to confirm</a><a className="nk-btn nk-btn--ghost" href={`${prefix}/configure`} onClick={onLink}>Edit declarations</a></div>
    </div>
  );
}

/** Downloads through the classic ownership-checked route; the PDF is rendered on request. */
export function FlowDownloads({ route, kinds, flash }: { route: string; kinds: string[]; flash: Flash }) {
  const [busy, setBusy] = useState(false);
  const pdf = async () => {
    const res = await fetch(`${route}/pdf`, { credentials: 'same-origin' });
    if (!res.ok || !(res.headers.get('Content-Type') ?? '').includes('application/pdf')) throw new ApiError((await res.json().catch(() => null))?.error?.message ?? 'The PDF report could not be generated.', res.status);
    const url = URL.createObjectURL(await res.blob());
    const a = Object.assign(document.createElement('a'), { href: url, download: /filename="?([^";]+)"?/.exec(res.headers.get('Content-Disposition') ?? '')?.[1] ?? 'report.pdf' });
    document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return (
    <>
      {kinds.includes('pdf') && <button type="button" className="ap-sheet__dl" disabled={busy} onClick={() => { setBusy(true); pdf().catch(flash).finally(() => setBusy(false)); }}>{busy ? 'Rendering PDF…' : 'Download PDF ↓'}</button>}
      {kinds.filter((k) => k !== 'pdf').map((k) => <a key={k} className="ap-sheet__dl" href={`${route}/${k}`}>Download {k.toUpperCase()} ↓</a>)}
    </>
  );
}

/** A family tile: canonical counts on its face, canonical wording and bounded data in its chapter. */

/** Scalar facts of an evidence object, for a chapter's definition list. */
export function scalarFacts(data: Doc, limit = 8): [string, string][] {
  return Object.entries(data).filter(([, v]) => ['string', 'number', 'boolean'].includes(typeof v)).slice(0, limit)
    .map(([k, v]) => [k.replace(/_/g, ' '), typeof v === 'number' ? v.toLocaleString('en-US', Number.isInteger(v) ? {} : { maximumSignificantDigits: 7 }) : String(v)]);
}

/* ——— The workflow: steps, polling and routing ——— */

export function Flow({ path, prefix, api, info, flash, onRail, onSaved, label, render, reachable = flowReachable }: {
  path: string; prefix: string; api: FlowApi; info: SessionInfo; flash: Flash; onRail: (s: FlowStep, ok: FlowStep[]) => void; onSaved: () => void; label: string;
  reachable?: (j: FlowJob | null) => FlowStep[];
  render: (p: { step: FlowStep; job: FlowJob | null; setJob: (j: FlowJob | null) => void; analysis: Doc | null; info: SessionInfo; onNew: () => void }) => ReactNode;
}) {
  const [job, setJobState] = useState<FlowJob | null | undefined>(undefined);
  const [analysis, setAnalysis] = useState<Doc | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const setJob = useCallback((j: FlowJob | null) => setJobState(j), []);
  useEffect(() => { api.job().then((r) => setJobState(r.job)).catch((e) => { setJobState(null); flash(e); }); }, [api]); // eslint-disable-line react-hooks/exhaustive-deps
  const requested = (new RegExp(`^${prefix}/(sources|configure|confirm|report)/?$`).exec(path)?.[1] ?? 'sources') as FlowStep;
  const ok = reachable(job ?? null);
  const step = ok.includes(requested) ? requested : ok[ok.length - 1];
  useEffect(() => { if (job !== undefined && step !== requested) navigate(`${prefix}/${step}`, true); }, [job, step, requested, prefix]);
  useEffect(() => { onRail(step, ok); }, [step, ok.join()]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (job?.saved_entry) onSaved(); }, [job?.saved_entry]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { scrollTo({ top: 0, behavior: reducedMotion() ? 'auto' : 'smooth' }); }, [step]);
  const running = job?.state === 'running';
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => { api.job().then((r) => r.job && setJobState(r.job)).catch(() => {}); }, 1000);
    return () => clearInterval(t);
  }, [running, api]);
  useEffect(() => {
    setAnalysis(null); setFailed(null);
    if (job?.result) api.analysis().then(setAnalysis).catch((e) => setFailed(e instanceof Error ? e.message : 'The result could not be read.'));
  }, [job?.result?.status, job?.fingerprint, attempt]); // eslint-disable-line react-hooks/exhaustive-deps
  if (job === undefined) return null;
  const onNew = () => { api.reset().then(() => { setJobState(null); navigate(`${prefix}/sources`); }).catch(flash); };
  if (step === 'report' && job) {
    if (running) return <Running job={job} label={label} api={api} setJob={setJob} flash={flash} />;
    if (job.state === 'failed' || job.state === 'cancelled') return <Stopped job={job} prefix={prefix} />;
    if (failed) return <ResultError message={failed} onRetry={() => setAttempt((n) => n + 1)} />;
    if (!analysis) return <div className="ap-rs"><div className="nk-mosaic nk-mosaic--big nk-mosaic--run ap-rs__wait" aria-busy="true" /></div>;
  }
  return <>{render({ step, job, setJob, analysis, info, onNew })}</>;
}

/** The reports-and-files section of a live result. */
export function LiveOut({ saved, downloads, onView, onNew, newLabel }: { saved: boolean; downloads: ReactNode; onView: () => void; onNew: () => void; newLabel: string }) {
  return <ReportBar saved={saved} downloads={downloads} onView={onView} extra={<button type="button" className="nk-btn nk-btn--ghost" onClick={onNew}>{newLabel}</button>} />;
}

/** The canonical report, opened at a verified anchor when the dashboard asks for one. */
export function ReportViewer({ name, src, downloads, onClose, anchor }: { name: string; src: string; downloads: ReactNode; onClose: () => void; anchor?: string | null }) {
  return <Viewer name={name} src={anchor ? `${src}#${encodeURIComponent(anchor)}` : src} note="the canonical DataTrust report" downloads={downloads} onClose={onClose} />;
}

/** A completed result that could not be read: say so, and offer to try again, never an endless wait. */
export function ResultError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="ap-rs">
      <p className="ap-note ap-note--warn" role="alert"><b>The result could not be read.</b> {message}</p>
      <div className="ap-acts"><button type="button" className="nk-btn" onClick={onRetry}>Try again</button></div>
    </div>
  );
}

/** What a page asks for when it opens the report: `true` for the top, or a verified anchor. */
export type ViewTarget = false | true | string;
export const viewAnchor = (v: ViewTarget) => (typeof v === 'string' ? v : null);
