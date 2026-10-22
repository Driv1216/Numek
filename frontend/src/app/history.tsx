// Recent analyses: the informed first-use choice, the rail and its saved-report sheet, the History page
// and the saved-report view. Saved analyses are read-only canonical results, verified before they open.
import { useCallback, useEffect, useRef, useState } from 'react';
import { Status } from '../foundation/system';
import { ApiError, api, type Analysis, type Finding, type HistoryState, type JobView, type M3Mode, type M4Analysis, type SavedEntry } from './api';
import { m4Header } from './m4';
import { TemporalPage } from './m5';
import { TextPage } from './m6';
import { ImagePage } from './m7';
import { SavedCross } from './m9';
import { M4_MODE_LABEL, RolesReport } from './results/roles';
import { Corners, MiB, READ_ONLY, Viewer, fmt } from './parts';
import { activeTiles, date, fromAnalysis, governingCap, isFinding, m3Label } from './results/adapter';
import { Mosaic } from './results/Mosaic';
import { ScopeNote } from './results/Tiles';
import { navigate, onLink, stepHref } from './router';

type Flash = (e: unknown) => void;
const sevRank: Record<string, number> = { High: 0, Moderate: 1, Low: 2 };
const WORKFLOW_LABEL: Record<string, string> = { m5: 'Temporal', m6: 'Text', m7: 'Images', m9: 'Records ↔ documents' };
const modeLabel = (e: SavedEntry) => (WORKFLOW_LABEL[e.workflow] ? `${WORKFLOW_LABEL[e.workflow]}${e.mode && e.mode !== e.workflow ? ` · ${e.mode.replace(/_/g, ' ')}` : ''}` : e.workflow === 'm4' ? M4_MODE_LABEL[e.mode] ?? e.mode : e.mode === 'classification' ? `Classification${e.summary.subtype ? ` · ${e.summary.subtype}` : ''}` : e.mode === 'regression' ? 'Regression' : e.mode === 'unlabeled' ? 'Unlabeled' : m3Label[e.mode as M3Mode] ?? e.mode);
const scoreClass = (e: SavedEntry) => (e.score == null ? 'is-none' : e.risk_level === 'Low' ? 'is-low' : 'is-elev');
const retention = (s: HistoryState) => {
  const parts = [s.max_age_days ? `${s.max_age_days} days` : null, s.max_total_bytes ? `${Math.round(s.max_total_bytes / 1048576).toLocaleString('en-US')} MiB in total` : null].filter(Boolean);
  return parts.length ? `Kept for up to ${parts.join(' or ')}, whichever comes first, then removed oldest first` : 'Kept until you delete them';
};
export { READ_ONLY };

/** History state plus the latest saved analyses, refreshed after anything that can change them. */
export function useHistory() {
  const [state, setState] = useState<HistoryState | null>(null);
  const [recent, setRecent] = useState<SavedEntry[]>([]);
  const refresh = useCallback(async () => {
    const s = await api.history.state().catch(() => null);
    setState(s);
    setRecent(s?.enabled && s.access ? (await api.history.list().catch(() => null))?.items.slice(0, 8) ?? [] : []);
  }, []);
  useEffect(() => { refresh(); }, [refresh]);
  return { state, recent, refresh };
}

/* ——— The informed first-use choice ——— */

export function FirstUse({ state, onChange, flash }: { state: HistoryState; onChange: () => void; flash: Flash }) {
  const [busy, setBusy] = useState(false);
  const choose = (v: 'on' | 'off') => { setBusy(true); api.history.choose(v).then(onChange).catch(flash).finally(() => setBusy(false)); };
  return (
    <section className="ap-sec ap-first" aria-labelledby="ap-first-h">
      <div className="ap-co__task"><b id="ap-first-h">Save completed analyses on this machine?</b><span>DataTrust can keep each finished report so you can reopen it later, even after DataTrust restarts. Nothing is saved until you choose.</span></div>
      <dl className="ap-first__list">
        <div><dt>What is saved</dt><dd>The canonical report (HTML), the analysis JSON, and a PDF if you downloaded one. Never your dataset, a copy of it, or private evidence.</dd></div>
        <div><dt>It can still be sensitive</dt><dd>Reports quote values from your data: column, dataset and file names, the purpose you typed, top values and counts, target distributions, and rows cited in findings.</dd></div>
        <div><dt>Where</dt><dd>{state.location}, readable only by your user account. Nothing leaves this machine, and nothing is encrypted beyond what your system provides.</dd></div>
        <div><dt>How long</dt><dd>{retention(state)}. You can delete one analysis, delete everything, or change these limits in History.</dd></div>
      </dl>
      <div className="ap-acts">
        <button type="button" className="nk-btn" disabled={busy} onClick={() => choose('on')}>Save completed analyses on this machine</button>
        <button type="button" className="nk-btn nk-btn--ghost" disabled={busy} onClick={() => choose('off')}>Don’t save</button>
        <span className="ap-acts__hint">You can change this any time in History.</span>
      </div>
    </section>
  );
}

/* ——— Rail and sheet ——— */

export function Rail({ job, history, flash }: { job: JobView | null; history: ReturnType<typeof useHistory>; flash: Flash }) {
  const { state, recent, refresh } = history;
  const [open, setOpen] = useState(false);
  const [pick, setPick] = useState<string | null>(null);
  const s = job?.summary;
  const saved = !!(state?.enabled && state.access);
  return (
    <aside className={`ap-recent ${open ? 'is-open' : ''}`} aria-label="Recent analyses">
      <button type="button" className="ap-recent__toggle" aria-expanded={open} onClick={() => setOpen((o) => !o)}>Recent analyses</button>
      <div className="ap-recent__in">
        {job && (
          <>
            <div className="ap-recent__h"><b>This session</b></div>
            <ul><li>
              <a className="ap-recent__it" href={stepHref(job.stage)} onClick={onLink}>
                <b>{s?.dataset_name ?? job.dataset_name ?? job.source_filename}</b>
                <span>{job.source_filename}</span>
                <span className="ap-recent__m"><em>{job.mode}</em>{job.stage !== 'report' ? <i className="is-none">{job.stage}</i> : s?.overall == null ? <i className="is-none">no score defined</i> : <i className={s.risk_level === 'Low' ? 'is-low' : 'is-elev'}>{s.overall.toFixed(1)} · {s.risk_level}</i>}</span>
              </a>
            </li></ul>
          </>
        )}
        <div className="ap-recent__h"><b>Recent analyses</b>{saved && <a className="ap-recent__all" href="/app/history" onClick={onLink}>All →</a>}</div>
        {!state ? null
          : !state.enabled ? <p className="ap-recent__why">Saved analyses are turned off for this run.</p>
          : !state.access ? <p className="ap-recent__why">Open DataTrust from your terminal to see saved analyses.</p>
          : state.saving === 'unset' ? <p className="ap-recent__why">Choose whether to save analyses on this machine.</p>
          : (
            <>
              {state.interrupted?.map((p) => (
                <div key={p.id} className="ap-recent__lost">
                  <b>Not saved: the analysis didn’t finish before DataTrust closed</b>
                  <span>{p.display_name ?? 'Analysis'} · {date(p.started_at)}</span>
                  <button type="button" className="ap-link" onClick={() => api.history.dismiss(p.id).then(refresh).catch(flash)}>Dismiss</button>
                </div>
              ))}
              {recent.length ? (
                <ul>
                  {recent.map((e) => (
                    <li key={e.id}>
                      <button type="button" className={pick === e.id ? 'is-on' : ''} aria-pressed={pick === e.id} onClick={() => setPick(e.id)}>
                        <b>{e.dataset_name ?? e.source_filename}</b>
                        <span>{e.source_filename}</span>
                        <span className="ap-recent__m"><em>{date(e.created_at)}</em>{e.state !== 'ok' ? <i className="is-elev">{e.state === 'missing' ? 'missing' : 'changed on disk'}</i> : e.score == null ? <i className="is-none">no score defined</i> : <i className={scoreClass(e)}>{e.score.toFixed(1)} · {e.risk_level}</i>}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : <p className="ap-recent__why">No saved analyses yet.</p>}
              <p className="ap-recent__foot">{state.saving === 'on' ? 'Saved on this machine. Datasets are never kept.' : 'Saving is off. Turn it on in History.'}</p>
            </>
          )}
      </div>
      {pick && <ReportSheet id={pick} onClose={() => setPick(null)} onDeleted={() => { setPick(null); refresh(); }} flash={flash} />}
    </aside>
  );
}

function SavedDownloads({ e, flash }: { e: SavedEntry; flash?: Flash }) {
  // A saved analysis without a PDF can have one made from its verified saved HTML; the dataset is not needed.
  const [made, setMade] = useState(false), [busy, setBusy] = useState(false);
  const has = (k: string) => e.artifacts.includes(k) || (k === 'pdf' && made);
  const make = () => { setBusy(true); api.history.pdf(e.id).then(() => setMade(true)).catch((x) => flash?.(x)).finally(() => setBusy(false)); };
  return <>
    {(['pdf', 'html', 'json'] as const).filter(has).map((k) => <a key={k} className="ap-sheet__dl" href={api.history.download(e.id, k)}>{k.toUpperCase()} ↓</a>)}
    {!has('pdf') && e.state === 'ok' && e.artifacts.includes('html') && flash && <button type="button" className="ap-sheet__dl" onClick={make} disabled={busy}>{busy ? 'Making PDF…' : 'Make PDF'}</button>}
  </>;
}

function DeleteButton({ id, onDeleted, flash, label = 'Delete' }: { id: string; onDeleted: () => void; flash: Flash; label?: string }) {
  const [sure, setSure] = useState(false);
  return sure
    ? <button type="button" className="ap-sheet__dl ap-del is-sure" onClick={() => api.history.remove(id).then(onDeleted).catch(flash)}>Delete permanently</button>
    : <button type="button" className="ap-sheet__dl ap-del" onClick={() => setSure(true)}>{label}</button>;
}

/** Findings from any workflow's verified canonical JSON; "no major issues" is a statement, not a finding. */
function savedFindings(a: Analysis) {
  type Raw = { code?: string; id?: string; title?: string; family?: string; meaning?: string; severity?: string; priority?: string };
  return ((a.findings ?? []) as unknown as Raw[]).map((f) => ({
    code: String(f.code ?? f.id ?? ''), title: f.title ?? [f.family, f.meaning].filter(Boolean).map((x) => String(x).replace(/_/g, ' ')).join(' · '),
    severity: (f.severity ?? f.priority ?? 'Low') as Finding['severity'],
  })).filter((f) => f.severity in sevRank && isFinding(f));
}
const narrativeOf = (a: Analysis | null) => { const nv = (a as { narrative?: { overall_assessment?: string; summary?: string } } | null)?.narrative; return nv?.overall_assessment ?? nv?.summary ?? null; };

/** A saved analysis, opened from the rail: its verified findings and files. */
function ReportSheet({ id, onClose, onDeleted, flash }: { id: string; onClose: () => void; onDeleted: () => void; flash: Flash }) {
  const close = useRef<HTMLButtonElement>(null);
  const [e, setE] = useState<SavedEntry | null>(null);
  const [a, setA] = useState<Analysis | null>(null);
  // The sheet reads the verified canonical JSON, as the saved and live views do, never the index's copy.
  useEffect(() => {
    close.current?.focus(); setE(null); setA(null);
    api.history.entry(id).then((x) => { setE(x); if (x.state === 'ok') return api.history.analysis(id).then(setA); }).catch((x) => { flash(x); onClose(); });
  }, [id]);
  useEffect(() => { const esc = (k: KeyboardEvent) => { if (k.key === 'Escape') onClose(); }; addEventListener('keydown', esc); return () => removeEventListener('keydown', esc); }, [onClose]);
  const fs = a ? savedFindings(a).sort((x, y) => sevRank[x.severity] - sevRank[y.severity]) : [];
  const values = ['computed', 'available'].includes(a?.scoring?.status ?? '') ? a!.scoring.values : null;
  const cap = governingCap(values);
  return (
    <>
      <div className="ap-sheet__scrim" onClick={onClose} aria-hidden="true" />
      <section className="ap-sheet" role="dialog" aria-modal="true" aria-label={`${e?.dataset_name ?? 'Saved'} report`}>
        <header className="ap-sheet__h">
          <span className="ap-sheet__k">Saved analysis</span>
          <button ref={close} type="button" className="ap-sheet__x" onClick={onClose} aria-label="Close">Close ✕</button>
        </header>
        {!e || (e.state === 'ok' && !a) ? <p className="ap-sheet__note">Verifying the saved files…</p> : (
          <>
            <h2>{e.dataset_name ?? e.source_filename}</h2>
            <p className="ap-sheet__meta">{e.source_filename} · {modeLabel(e)} · {MiB(e.bytes)} MiB · saved {date(e.created_at)}{e.summary.elapsed_seconds != null ? ` · ${e.summary.elapsed_seconds.toFixed(2)} s` : ''}</p>
            {e.state !== 'ok' ? (
              <>
                <p className="ap-note ap-note--warn"><b>{e.state === 'missing' ? 'Files missing' : 'Changed on disk'}</b> {e.state === 'missing' ? 'The saved files for this analysis are no longer in the history folder.' : 'A saved file no longer matches what was recorded, so it is not opened.'}</p>
                <div className="ap-sheet__acts"><DeleteButton id={e.id} onDeleted={onDeleted} flash={flash} label="Remove from history" /></div>
              </>
            ) : (
              <>
                <div className={`ap-sheet__score ${scoreClass(e)}`}>
                  {!values ? <><b>No score</b><span>{a?.scoring?.reason ?? 'No universal score is defined for this kind of data, by design. The report gives evidence.'}</span></> : <><b>{values.overall.toFixed(1)}</b><span>{values.risk_level} risk{cap ? ` · capped at ${cap.cap}` : ''}</span></>}
                </div>
                {narrativeOf(a) && <p className="ap-sheet__lead">{narrativeOf(a)}</p>}
                <h3>{fs.length ? `Findings (${fs.length})` : 'Findings'}</h3>
                <ul className="ap-sheet__fs">
                  {fs.length ? fs.map((f) => <li key={f.code}><span className={`ap-sev is-${f.severity.toLowerCase()}`}>{f.severity}</span><b>{f.title}</b><span>{f.code.replace(/_/g, ' ')}</span></li>)
                    : <li><span className="ap-sev">None</span><b>No review findings</b><span>The completed checks produced no findings.</span></li>}
                </ul>
                <div className="ap-sheet__acts">
                  <a className="nk-btn" href={`/app/history/${e.id}`} onClick={(x) => { onLink(x); onClose(); }}>Open full result</a>
                  {e.live && <a className="nk-btn nk-btn--ghost" href={stepHref('report')} onClick={(x) => { onLink(x); onClose(); }}>Open live result</a>}
                  <SavedDownloads e={e} flash={flash} />
                  <DeleteButton id={e.id} onDeleted={onDeleted} flash={flash} />
                </div>
                <p className="ap-sheet__note">{READ_ONLY}</p>
              </>
            )}
          </>
        )}
      </section>
    </>
  );
}

/** An ISO time with its zone stated; a value without one says so rather than guessing. */
const utc = (iso: string | null | undefined) => {
  if (!iso) return 'at a time not recorded';
  const d = new Date(iso);
  if (Number.isNaN(+d)) return iso;
  return /[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? `${d.toISOString().slice(0, 19).replace('T', ' ')} UTC` : `${iso.replace('T', ' ')} (time zone not recorded)`;
};

/* ——— The saved-report view ——— */

export function SavedReport({ id, onDeleted, flash }: { id: string; onDeleted: () => void; flash: Flash }) {
  const [e, setE] = useState<SavedEntry | null>(null);
  const [a, setA] = useState<Analysis | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [view, setView] = useState(false);
  useEffect(() => {
    let live = true; setE(null); setA(null); setFailed(null);
    api.history.entry(id).then(async (x) => {
      if (!live) return; setE(x);
      if (x.state === 'ok') { const an = await api.history.analysis(id); if (live) setA(an); }
    }).catch((x) => live && setFailed(x instanceof ApiError ? x.message : 'This saved analysis could not be opened.'));
    return () => { live = false; };
  }, [id]);
  if (failed) return <div className="ap-rs"><p className="ap-note ap-note--warn" role="alert">{failed}</p><a className="nk-btn" href="/app/history" onClick={onLink}>← All saved analyses</a></div>;
  if (!e) return <div className="ap-rs"><div className="nk-mosaic nk-mosaic--big nk-mosaic--run ap-rs__wait" aria-busy="true" /></div>;
  const name = e.dataset_name ?? e.source_filename ?? 'Saved analysis';
  const out = (
    <section className="ap-rs__out">
      <div>
        <h2 className="ap-q">Saved on this machine</h2>
        <p className="ap-muted">{e.live ? 'This analysis is still open in this session, so its evidence can be inspected there.' : READ_ONLY}</p>
        <p className="ap-muted">Analysed {utc(e.generated_at)} · saved {utc(e.created_at)}. {e.presentation ? `Rendered by DataTrust ${e.presentation.package_version ?? 'not recorded'}, report templates ${e.presentation.report_templates ?? 'not recorded'}, app build ${e.presentation.app_build ?? 'not recorded'}.` : 'How this report was rendered was not recorded by the version that saved it.'}</p>
      </div>
      <div className="ap-acts">
        {e.state === 'ok' && <button type="button" className="nk-btn" onClick={() => setView(true)}>View full report</button>}
        {e.state === 'ok' && <SavedDownloads e={e} flash={flash} />}
        <DeleteButton id={e.id} onDeleted={onDeleted} flash={flash} label={e.state === 'ok' ? 'Delete' : 'Remove from history'} />
      </div>
    </section>
  );
  const viewer = view && <Viewer name={name} src={api.history.report(e.id)} note="the saved canonical DataTrust report" downloads={<SavedDownloads e={e} flash={flash} />} onClose={() => setView(false)} />;
  if (e.workflow === 'm9' && e.state === 'ok') {
    if (!a) return <div className="ap-rs"><div className="nk-mosaic nk-mosaic--big nk-mosaic--run ap-rs__wait" aria-busy="true" /></div>;
    return <><p className="ap-rs__saved"><Status tone="on">Saved analysis · read-only canonical result</Status></p><SavedCross a={a as unknown as Record<string, unknown>} flash={flash} onOpen={() => setView(true)} out={out} analysisUrl={`/api/datatrust/v1/history/${e.id}/analysis`} />{viewer}</>;
  }
  if (e.workflow === 'm7' && e.state === 'ok') {
    if (!a) return <div className="ap-rs"><div className="nk-mosaic nk-mosaic--big nk-mosaic--run ap-rs__wait" aria-busy="true" /></div>;
    return <><p className="ap-rs__saved"><Status tone="on">Saved analysis · read-only canonical result</Status></p><ImagePage a={a as unknown as Record<string, unknown>} live={false} flash={flash} onOpen={() => setView(true)} out={out} />{viewer}</>;
  }
  if (e.workflow === 'm6' && e.state === 'ok') {
    if (!a) return <div className="ap-rs"><div className="nk-mosaic nk-mosaic--big nk-mosaic--run ap-rs__wait" aria-busy="true" /></div>;
    return <><p className="ap-rs__saved"><Status tone="on">Saved analysis · read-only canonical result</Status></p><TextPage a={a as unknown as Record<string, unknown>} live={false} flash={flash} onOpen={() => setView(true)} out={out} />{viewer}</>;
  }
  if (e.workflow === 'm5' && e.state === 'ok') {
    if (!a) return <div className="ap-rs"><div className="nk-mosaic nk-mosaic--big nk-mosaic--run ap-rs__wait" aria-busy="true" /></div>;
    return <><p className="ap-rs__saved"><Status tone="on">Saved analysis · read-only canonical result</Status></p><TemporalPage a={a as unknown as Record<string, unknown>} live={false} onOpen={() => setView(true)} out={out} />{viewer}</>;
  }
  if (e.workflow === 'm4' && e.state === 'ok') {
    if (!a) return <div className="ap-rs"><div className="nk-mosaic nk-mosaic--big nk-mosaic--run ap-rs__wait" aria-busy="true" /></div>;
    const m4 = a as unknown as M4Analysis;
    return <><RolesReport a={m4} header={<>{m4Header(m4, e.mode, () => setView(true))}<p className="ap-rs__saved"><Status tone="on">Saved analysis · read-only canonical result</Status></p></>} out={out} />{viewer}</>;
  }
  const run = a && e.workflow === 'core' ? fromAnalysis(a, e.mode, e.artifacts) : null;
  return (
    <div className="ap-rs">
      <header className="ap-rs__bar">
        <h1>{name}</h1>
        <p>{e.source_filename} · {modeLabel(e)}<br />{e.generated_at ? `Analysed ${date(e.generated_at)}` : `Saved ${date(e.created_at)}`}{e.summary.elapsed_seconds != null ? ` · ${e.summary.elapsed_seconds.toFixed(2)} s` : ''}{run ? ` · ${activeTiles(run)} of 14 checks apply` : ''}{e.state === 'ok' && <> · <button type="button" className="ap-rs__open" onClick={() => setView(true)}>Open report ↗</button></>}</p>
      </header>
      <p className="ap-rs__saved"><Status tone="on">Saved analysis · read-only canonical result</Status>{e.live && <a href={stepHref('report')} onClick={onLink}>Open the live result</a>}</p>
      {e.state !== 'ok'
        ? <p className="ap-note ap-note--warn"><b>{e.state === 'missing' ? 'Files missing' : 'Changed on disk'}</b> {e.state === 'missing' ? 'The saved files for this analysis are no longer in the history folder.' : 'A saved file no longer matches what was recorded, so it is not opened.'}</p>
        : a && run ? <Mosaic a={a} run={run} runName={name} /> : <div className="nk-mosaic nk-mosaic--big nk-mosaic--run ap-rs__wait" aria-busy="true" />}
      {a && run && <ScopeNote guidance={(a as { guidance?: unknown }).guidance} />}
      {out}
      {viewer}
    </div>
  );
}

/* ——— The History page ——— */

export function HistoryPage({ history, flash }: { history: ReturnType<typeof useHistory>; flash: Flash }) {
  const { state, refresh } = history;
  const [q, setQ] = useState(''); const [risk, setRisk] = useState(''); const [from, setFrom] = useState(''); const [to, setTo] = useState('');
  const [items, setItems] = useState<SavedEntry[]>([]); const [total, setTotal] = useState(0); const [next, setNext] = useState<number | null>(null);
  const [days, setDays] = useState(''); const [mib, setMib] = useState('');
  const [sure, setSure] = useState(false);
  const ready = !!(state?.enabled && state.access);
  const params = () => ({ q, risk, from: from ? `${from}T00:00:00` : '', to: to ? `${to}T23:59:59` : '' });
  const load = useCallback((cursor = 0) => {
    if (!ready) return;
    api.history.list({ ...params(), cursor: String(cursor) }).then((p) => { setItems((x) => (cursor ? [...x, ...p.items] : p.items)); setTotal(p.total); setNext(p.next_cursor); }).catch(flash);
  }, [ready, q, risk, from, to]);
  useEffect(() => { const t = setTimeout(() => load(0), 200); return () => clearTimeout(t); }, [load]);
  useEffect(() => { if (state) { setDays(state.max_age_days ? String(state.max_age_days) : ''); setMib(state.max_total_bytes ? String(Math.round(state.max_total_bytes / 1048576)) : ''); } }, [state]);
  const changed = () => { refresh(); load(0); };
  if (!state) return null;
  return (
    <div className="ap-hist">
      <header className="ap-head"><span className="nk-label">History</span><h1>Saved analyses.</h1><p>Canonical reports kept on this machine. Datasets are never stored.</p></header>
      {!state.enabled ? <p className="ap-note">Saved analyses are turned off for this run (<code>--no-history</code>).</p>
        : !state.access ? <p className="ap-note">Open DataTrust from your terminal to see saved analyses. The link it opens works once, for that browser.</p>
        : (
          <>
            {state.saving === 'unset' && <FirstUse state={state} onChange={changed} flash={flash} />}
            {!!state.interrupted?.length && (
              <section className="ap-sec">{state.interrupted.map((p) => (
                <p key={p.id} className="ap-note ap-note--warn"><b>Not saved: the analysis didn’t finish before DataTrust closed</b> {p.display_name ?? 'Analysis'} · {date(p.started_at)} · <button type="button" className="ap-link" onClick={() => api.history.dismiss(p.id).then(refresh).catch(flash)}>Dismiss</button></p>
              ))}</section>
            )}
            <section className="ap-sec" aria-label="Search saved analyses">
              <div className="ap-fields ap-hist__find">
                <label>Search <span>name, file, target or finding</span><input type="search" value={q} onChange={(x) => setQ(x.target.value)} placeholder="adult, imbalance, credit_risk…" /></label>
                <label>Risk<select value={risk} onChange={(x) => setRisk(x.target.value)}><option value="">Any</option>{['Low', 'Moderate', 'Elevated', 'High'].map((r) => <option key={r}>{r}</option>)}</select></label>
                <label>From<input type="date" value={from} onChange={(x) => setFrom(x.target.value)} /></label>
                <label>To<input type="date" value={to} onChange={(x) => setTo(x.target.value)} /></label>
              </div>
              <p className="ap-sub">{fmt(total)} saved {total === 1 ? 'analysis' : 'analyses'}</p>
              {items.length ? (
                <ul className="ap-hist__list">
                  {items.map((e) => (
                    <li key={e.id}>
                      <a href={`/app/history/${e.id}`} onClick={onLink} className="ap-hist__it">
                        <b>{e.dataset_name ?? e.source_filename}</b>
                        <span>{e.source_filename} · {modeLabel(e)} · {date(e.created_at)}</span>
                        <em className={e.state !== 'ok' ? 'is-elev' : scoreClass(e)}>{e.state !== 'ok' ? (e.state === 'missing' ? 'missing' : 'changed on disk') : e.score == null ? 'no score defined' : `${e.score.toFixed(1)} · ${e.risk_level}`}</em>
                      </a>
                    </li>
                  ))}
                </ul>
              ) : <div className="ap-sel ap-sel--empty"><Corners tone="ghost" /><b>Nothing here yet.</b><p>{q || risk || from || to ? 'No saved analysis matches these filters.' : 'Completed analyses appear here once saving is on.'}</p></div>}
              {next != null && <div className="ap-acts"><button type="button" className="nk-btn nk-btn--ghost" onClick={() => load(next)}>Show more</button></div>}
            </section>
            <section className="ap-sec ap-hist__set" aria-labelledby="ap-set-h">
              <h2 id="ap-set-h" className="ap-q">Saving and retention</h2>
              <div className="ap-acts">
                <Status tone={state.saving === 'on' ? 'on' : 'dev'}>{state.saving === 'on' ? 'Saving completed analyses' : 'Not saving analyses'}</Status>
                <button type="button" className="nk-btn nk-btn--ghost" onClick={() => api.history.choose(state.saving === 'on' ? 'off' : 'on').then(changed).catch(flash)}>{state.saving === 'on' ? 'Stop saving' : 'Start saving'}</button>
              </div>
              <div className="ap-fields ap-fields--two">
                <label>Keep for at most <span>days · empty keeps them until you delete</span><input inputMode="numeric" value={days} onChange={(x) => setDays(x.target.value)} /></label>
                <label>Use at most <span>MiB in total · empty sets no size limit</span><input inputMode="numeric" value={mib} onChange={(x) => setMib(x.target.value)} /></label>
              </div>
              <div className="ap-acts">
                <button type="button" className="nk-btn" onClick={() => api.history.settings({ max_age_days: days, max_total_mib: mib }).then(changed).catch(flash)}>Save retention</button>
                <span className="ap-acts__hint">{retention(state)}. {fmt(state.count)} saved · {MiB(state.bytes ?? 0)} MiB · {state.location}</span>
              </div>
              <div className="ap-acts">
                {sure ? <button type="button" className="ap-sheet__dl ap-del is-sure" onClick={() => api.history.clear().then(() => { setSure(false); changed(); }).catch(flash)}>Delete every saved analysis</button>
                  : <button type="button" className="ap-sheet__dl ap-del" onClick={() => setSure(true)}>Delete all…</button>}
              </div>
            </section>
          </>
        )}
    </div>
  );
}

export const goHistory = () => navigate('/app/history');
