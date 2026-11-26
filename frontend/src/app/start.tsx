// Step 1 · Start: say what you want to check, or start from a CSV and see which analyses fit it (Guided Analysis
// Stage 4a). Every suggestion comes from the server's advisory input inspection (input_inspection_v1 and
// applicability.py); nothing here ranks, preselects or blocks an analysis, and every analysis stays choosable.
import { useEffect, useRef, useState } from 'react';
import { api, type AnalysisFit, type FitState, type JobView, type Mode, type RegressionTarget, type SessionInfo } from './api';
import { navigate, onLink, stepHref } from './router';
import { Corners, MiB, SeparatorSelect, fmt } from './parts';

type Flash = (e: unknown) => void;

export interface Analysis { key: string; t: string; d: string; mode?: Mode; href?: string }

/** Every analysis, under its user-facing name. Internal identifiers are never shown. */
export const ANALYSES: Analysis[] = [
  { key: 'unlabeled', t: 'Dataset profile', d: 'Missing values, repeats, variation and unusual values in every column. No target needed.', mode: 'unlabeled' },
  { key: 'role_profile', t: 'Profile with chosen columns', d: 'The same profile, over the columns you mark as features.', mode: 'role_profile' },
  { key: 'classification', t: 'Category outcome', d: 'A labelled table for a classifier: target, conflicts, leakage prompts and a review score.', mode: 'classification' },
  { key: 'regression', t: 'Numerical outcome', d: 'A numeric target: its distribution, declared limits, and inputs that reproduce it.', mode: 'regression' },
  { key: 'multioutput', t: 'Several numerical outcomes', d: 'Two or more numeric targets, checked one by one and together.', mode: 'annotation_regression' },
  { key: 'multilabel_classification', t: 'Several labels per row', d: 'Yes/no indicator columns, one per label: completeness, prevalence and support.', mode: 'multilabel_classification' },
  { key: 'annotation_classification', t: 'Partially labelled: category', d: 'A category outcome whose labels may be incomplete or in review.', mode: 'annotation_classification' },
  { key: 'annotation_regression', t: 'Partially labelled: number', d: 'A numerical outcome whose values may be incomplete.', mode: 'annotation_regression' },
  { key: 'clustering', t: 'Clustering readiness', d: 'Prerequisites for distance-based clustering. No model is fitted; no verdict is given.', mode: 'clustering' },
  { key: 'anomaly_detection', t: 'Anomaly-detection readiness', d: 'Prerequisites for distance-based anomaly detection. No model is fitted; no verdict is given.', mode: 'anomaly_detection' },
  { key: 'comparison', t: 'Compare datasets or splits', d: 'Training vs evaluation separation, two versions, before and after preprocessing, or the deeper structure of one large file.', href: '/app/m4/sources' },
  { key: 'temporal', t: 'Data over time', d: 'Clocks, continuity, availability, revisions and folds.', href: '/app/temporal/sources' },
  { key: 'text', t: 'Text and language data', d: 'Corpora, labelled text, question answering, conversations and retrieval. JSONL or CSV.', href: '/app/text/sources' },
  { key: 'images', t: 'Images and annotations', d: 'Folders, manifests, COCO, YOLO and masks.', href: '/app/images/sources' },
  { key: 'cross', t: 'Records and documents', d: 'Records reconciled against PDF and DOCX evidence.', href: '/app/cross/sources' },
];
const byKey = Object.fromEntries(ANALYSES.map((a) => [a.key, a])) as Record<string, Analysis>;

interface Intent { id: string; t: string; d: string; keys?: string[]; href?: string }
const INTENTS: Intent[] = [
  { id: 'understand', t: 'Understand a dataset', d: 'No prediction target needed.', keys: ['unlabeled', 'role_profile'] },
  { id: 'predict', t: 'Prepare data for prediction', d: 'Which outcome will a model predict?', keys: ['classification', 'regression', 'multioutput', 'multilabel_classification', 'annotation_classification', 'annotation_regression'] },
  { id: 'readiness', t: 'Readiness for clustering or anomaly detection', d: 'No model is fitted and no verdict is given.', keys: ['clustering', 'anomaly_detection'] },
  { id: 'compare', t: 'Compare datasets or splits', d: 'Two or three files, or one large file.', href: '/app/m4/sources' },
  { id: 'time', t: 'Data over time', d: 'Needs a time column.', href: '/app/temporal/sources' },
  { id: 'text', t: 'Text and language data', d: 'JSONL or CSV.', href: '/app/text/sources' },
  { id: 'images', t: 'Images and annotations', d: 'A local folder or manifest.', href: '/app/images/sources' },
  { id: 'records', t: 'Records and documents', d: 'Records plus PDF or DOCX.', href: '/app/cross/sources' },
];

const FIT: { state: FitState; h: string; d: string }[] = [
  { state: 'can_run', h: 'Can run now', d: 'The file has what these analyses need. You still choose the columns.' },
  { state: 'needs_input', h: 'Needs more input', d: 'These need something the file alone does not give, such as a second file or a confirmed clock.' },
  { state: 'unlikely', h: 'Probably not useful', d: 'The file lacks what these analyses look at. You can still choose one.' },
];

const LAST = 'datatrust.last-analysis';
const lastUsed = (): string | null => { try { return localStorage.getItem(LAST); } catch { return null; } };
const remember = (key: string) => { try { localStorage.setItem(LAST, key); } catch { /* per-viewer convenience only */ } };

/** The header's "All analyses" link: opens the list on the Start page from anywhere in the app. */
export const ALL_EVENT = 'datatrust:all-analyses';
export function AllAnalysesLink() {
  return <a className="ap-wf__btn" href="/app/" onClick={(e) => { e.preventDefault(); navigate('/app/'); setTimeout(() => dispatchEvent(new Event(ALL_EVENT)), 0); }}>
    <span className="ap-wf__long">All analyses</span><span className="ap-wf__short">Analyses</span></a>;
}

/** Which analysis the job runs now, under its user-facing key. */
function currentKey(job: JobView | null): string | null {
  if (!job?.mode) return null;
  if (job.mode === 'annotation_regression') return (job.m3?.task?.targets.length ?? 0) > 1 ? 'multioutput' : 'annotation_regression';
  return job.mode;
}

export function Start({ info, job, onJob, flash }: { info: SessionInfo; job: JobView | null; onJob: (j: JobView) => void; flash: Flash }) {
  const input = useRef<HTMLInputElement>(null);
  const drop = useRef<HTMLDivElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [sep, setSep] = useState('auto');
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [replacing, setReplacing] = useState(false);
  const [intent, setIntent] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [choosing, setChoosing] = useState<string | null>(null);
  const last = lastUsed();
  const hasFile = !!job && !replacing;

  const choose = (a: Analysis, j: JobView | null = job) => {
    if (a.href) { navigate(a.href); return; }
    if (!j || replacing) { setPending(a.key); drop.current?.scrollIntoView({ block: 'center' }); return; }
    setChoosing(a.key);
    api.chooseAnalysis(a.mode!).then((r) => { remember(a.key); onJob(r.job); navigate(stepHref('configure')); }).catch(flash).finally(() => setChoosing(null));
  };
  const read = () => {
    if (!file || busy) return;
    setBusy(true);
    api.uploadOnly(file, sep).then((r) => {
      onJob(r.job); setReplacing(false); setFile(null);
      if (pending) { const a = byKey[pending]; setPending(null); choose(a, r.job); }
    }).catch(flash).finally(() => setBusy(false));
  };
  const pickIntent = (x: Intent) => {
    if (x.href) { navigate(x.href); return; }
    setIntent((v) => (v === x.id ? null : x.id));
    if (!hasFile) drop.current?.scrollIntoView({ block: 'center' });
  };

  const dropZone = (
    <div ref={drop} className={`ap-drop ${over ? 'is-over' : ''} ${file ? 'is-ready' : ''}`}
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
          <div className="ap-file"><span className="ap-file__fold" aria-hidden="true" /><b>{file.name}</b><span>{MiB(file.size)} MiB · chosen on this machine</span></div>
          <button type="button" className="ap-link" onClick={() => { setFile(null); if (input.current) input.current.value = ''; }}>Choose a different file</button>
        </div>
      )}
      <input ref={input} type="file" accept=".csv,text/csv" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) setFile(f); }} />
    </div>
  );

  return (
    <div className="ap-up ap-start">
      <header className="ap-head">
        <span className="nk-label">Step 1 · Start</span>
        <h1>What do you want to check?</h1>
        <p>Files are processed by this local application and are not sent to DataTrust or a cloud service.</p>
      </header>

      {hasFile ? (
        <>
          <FileFacts job={job!} onReplace={() => setReplacing(true)} />
          <nav className="ap-filter" aria-label="Filter the analyses by what you want to check">
            <span className="ap-sub">I want to</span>
            <button type="button" className={!intent ? 'is-on' : ''} aria-pressed={!intent} onClick={() => setIntent(null)}>see everything</button>
            {INTENTS.map((x) => x.href
              ? <a key={x.id} href={x.href} onClick={onLink}>{x.t.toLowerCase()} ↗</a>
              : <button key={x.id} type="button" className={intent === x.id ? 'is-on' : ''} aria-pressed={intent === x.id} onClick={() => pickIntent(x)}>{x.t.toLowerCase()}</button>)}
          </nav>
        </>
      ) : (
      <div className="ap-start__grid">
        <section className="ap-sec ap-start__csv" aria-labelledby="ap-csv-start-h">
          <h2 id="ap-csv-start-h" className="ap-q">Start from a CSV</h2>
          <p className="ap-muted">DataTrust reads the file on this machine, then shows which analyses fit it. You choose.</p>
          {pending && <p className="ap-note"><b>{byKey[pending].t}</b> opens once the file is read.</p>}
          {dropZone}
          <div className="ap-sepbar"><SeparatorSelect value={sep} onChange={setSep} /><span>Commas, semicolons, tabs and vertical bars are read. Detection applies a separator only when exactly one fits; if several fit, you choose.</span></div>
          <div className="ap-acts">
            {file ? <button type="button" className={`nk-btn ${busy ? 'is-run' : ''}`} onClick={read} disabled={busy}>{busy ? 'Reading the file…' : 'Read the file →'}</button> : <span className="nk-btn is-off" aria-disabled="true">Read the file →</span>}
            {replacing && <button type="button" className="nk-btn nk-btn--ghost" onClick={() => { setReplacing(false); setFile(null); setPending(null); }}>Keep {job!.source_filename}</button>}
          </div>
        </section>

        <nav className="ap-sec ap-intents" aria-labelledby="ap-intents-h">
          <h2 id="ap-intents-h" className="ap-sub">I know what I need</h2>
          <ul>
            {INTENTS.map((x) => (
              <li key={x.id}>
                <button type="button" className={`ap-intent ${intent === x.id ? 'is-on' : ''}`} aria-pressed={x.href ? undefined : intent === x.id} onClick={() => pickIntent(x)}>
                  {intent === x.id && <Corners />}
                  <b>{x.t}</b><span>{x.d}</span><i aria-hidden="true">{x.href ? '↗' : '→'}</i>
                </button>
              </li>
            ))}
          </ul>
        </nav>
      </div>
      )}

      {hasFile && <Fits job={job!} intent={intent} clear={() => setIntent(null)} choose={choose} choosing={choosing} last={last} />}
      {!hasFile && intent && <IntentPreview intent={INTENTS.find((x) => x.id === intent)!} choose={choose} pending={pending} />}
      <AllAnalyses choose={choose} choosing={choosing} current={currentKey(job)} last={last} />
    </div>
  );
}

function FileFacts({ job, onReplace }: { job: JobView; onReplace: () => void }) {
  const ii = job.input_inspection, cov = ii?.coverage;
  return (
    <section className="ap-start__file" aria-label="Your file">
      <div className="ap-file"><span className="ap-file__fold" aria-hidden="true" /><b>{job.source_filename}</b>
        <span>{MiB(job.file_size)} MiB{cov ? ` · ${fmt(cov.columns_total)} columns` : ''}</span></div>
      <div className="ap-start__about">
        <p>{ii?.error ? `The file could not be inspected for suggestions (${ii.error}). Every analysis can still be chosen.` : cov?.statement}</p>
        {job.stage === 'report' && <p className="ap-note">Choosing an analysis replaces this session’s report. A report saved to History stays there.</p>}
        <button type="button" className="ap-link" onClick={onReplace}>Use a different file</button>
      </div>
    </section>
  );
}

function Rules({ list }: { list: string[] }) {
  return list.length ? <span className="ap-fit__rules">{list.map((r) => <code key={r}>{r}</code>)}</span> : null;
}

function Fits({ job, intent, clear, choose, choosing, last }: { job: JobView; intent: string | null; clear: () => void; choose: (a: Analysis) => void; choosing: string | null; last: string | null }) {
  const fits: AnalysisFit[] = job.suggestions?.analyses ?? ANALYSES.filter((a) => a.mode).map((a) => ({ analysis: a.key, state: 'can_run' as FitState, reason: a.d, rules: [] }));
  const keys = intent ? INTENTS.find((x) => x.id === intent)?.keys ?? null : null;
  const shown = fits.filter((f) => byKey[f.analysis] && (!keys || keys.includes(f.analysis)));
  const now = currentKey(job);
  return (
    <section className="ap-sec ap-fits" aria-labelledby="ap-fits-h">
      <h2 id="ap-fits-h" className="ap-q">Analyses for this file</h2>
      <p className="ap-muted">{job.suggestions ? 'Sorted by what the file contains, not ranked. The reasons name the inspection rules behind them; none is applied for you.' : 'No suggestions are available for this file.'}
        {intent && <> Showing {INTENTS.find((x) => x.id === intent)!.t.toLowerCase()}. <button type="button" className="ap-link" onClick={clear}>Show all</button></>}</p>
      {FIT.map((g) => {
        const list = shown.filter((f) => f.state === g.state);
        if (!list.length) return null;
        const body = <ul className="ap-fit">{list.map((f) => {
          const a = byKey[f.analysis];
          return (
            <li key={f.analysis}>
              <button type="button" className={`ap-fit__it ${now === a.key ? 'is-now' : ''}`} disabled={!!choosing} onClick={() => choose(a)}>
                <b>{a.t}{now === a.key && <em>current</em>}{last === a.key && now !== a.key && <em className="is-last">last used</em>}</b>
                <span>{f.reason}</span>
                <Rules list={f.rules} />
                <i aria-hidden="true">{choosing === a.key ? '…' : a.href ? '↗' : '→'}</i>
              </button>
            </li>
          );
        })}</ul>;
        return g.state === 'unlikely'
          ? <details key={g.state} className="ap-group ap-group--adv ap-fit__g"><summary>{g.h} ({list.length})</summary><p className="ap-muted">{g.d}</p>{body}</details>
          : <div key={g.state} className="ap-fit__g"><h3 className="ap-sub">{g.h}</h3><p className="ap-muted">{g.d}</p>{body}</div>;
      })}
    </section>
  );
}

/** Before a file is read: the chosen intent's analyses, each of which asks for the file. */
function IntentPreview({ intent, choose, pending }: { intent: Intent; choose: (a: Analysis) => void; pending: string | null }) {
  return (
    <section className="ap-sec ap-fits" aria-labelledby="ap-intent-h">
      <h2 id="ap-intent-h" className="ap-q">{intent.t}</h2>
      <p className="ap-muted">Choose one to open it as soon as the file is read, or read the file first to see which fit.</p>
      <ul className="ap-fit">{intent.keys!.map((k) => (
        <li key={k}><button type="button" className={`ap-fit__it ${pending === k ? 'is-now' : ''}`} onClick={() => choose(byKey[k])} aria-pressed={pending === k}>
          <b>{byKey[k].t}</b><span>{byKey[k].d}</span><i aria-hidden="true">→</i></button></li>
      ))}</ul>
    </section>
  );
}

function AllAnalyses({ choose, choosing, current, last }: { choose: (a: Analysis) => void; choosing: string | null; current: string | null; last: string | null }) {
  const ref = useRef<HTMLDetailsElement>(null);
  const [q, setQ] = useState('');
  useEffect(() => {
    const open = () => { if (ref.current) { ref.current.open = true; ref.current.scrollIntoView({ block: 'start' }); ref.current.querySelector('input')?.focus(); } };
    addEventListener(ALL_EVENT, open);
    return () => removeEventListener(ALL_EVENT, open);
  }, []);
  const words = q.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const list = ANALYSES.filter((a) => words.every((w) => `${a.t} ${a.d}`.toLowerCase().includes(w)));
  return (
    <details ref={ref} id="all-analyses" className="ap-more ap-sec ap-all">
      <summary>All analyses ({ANALYSES.length})</summary>
      <label className="ap-all__q">Search<input type="search" value={q} placeholder="e.g. labels, time, images" onChange={(e) => setQ(e.target.value)} /></label>
      <ul className="ap-fit">{list.map((a) => (
        <li key={a.key}><button type="button" className={`ap-fit__it ${current === a.key ? 'is-now' : ''}`} disabled={!!choosing} onClick={() => choose(a)}>
          <b>{a.t}{current === a.key && <em>current</em>}{last === a.key && current !== a.key && <em className="is-last">last used</em>}</b><span>{a.d}</span>
          <i aria-hidden="true">{a.href ? '↗' : '→'}</i></button></li>
      ))}</ul>
      {!list.length && <p className="ap-muted">No analysis matches “{q}”.</p>}
    </details>
  );
}

/* ——— Numerical outcome picker (Configure) ——— */

const REG_GROUPS: { id: RegressionTarget['group']; h: string; open: boolean }[] = [
  { id: 'outcome_word', h: 'Outcome-word candidates', open: true },
  { id: 'numeric', h: 'Other numeric columns', open: true },
  { id: 'review', h: 'Review needed', open: false },
  { id: 'unavailable', h: 'Not available as a number', open: false },
];

/** Grouped from the full-file input inspection; nothing is preselected (target_guidance.regression_target_groups). */
export function RegressionTargets({ job, target, setTarget }: { job: JobView; target: string | null; setTarget: (t: string) => void }) {
  const g = job.suggestions?.regression_targets;
  if (!g) return null;
  return (
    <>
      <p className="ap-muted">DataTrust groups the numeric columns and explains why. It does not choose or preselect the outcome. {g.coverage}</p>
      {REG_GROUPS.map((x) => {
        const list = g.options.filter((o) => o.group === x.id);
        if (!list.length) return null;
        const opts = <div className="ap-opts">{list.map((o) => (
          <label key={o.name} className={`ap-opt ${target === o.name ? 'is-on' : ''} ${x.id === 'review' ? 'is-adv' : ''} ${x.id === 'unavailable' ? 'is-off' : ''}`}>
            <input type="radio" name="target" checked={target === o.name} onChange={() => setTarget(o.name)} disabled={x.id === 'unavailable'} />
            <span className="ap-opt__r" aria-hidden="true" />
            <span className="ap-opt__t"><b>{o.name}</b><span>{o.text}{o.missing ? ` · ${fmt(o.missing)} missing` : ''}</span></span>
          </label>
        ))}</div>;
        const open = x.open || list.some((o) => o.name === target);
        return x.open
          ? <fieldset key={x.id} className="ap-group"><legend>{x.h}</legend><p className="ap-muted">{g.groups[x.id]}</p>{opts}</fieldset>
          : <details key={x.id} className="ap-group ap-group--adv" open={open || undefined}><summary>{x.h} ({list.length})</summary><p className="ap-muted">{g.groups[x.id]}</p>{opts}</details>;
      })}
    </>
  );
}

/** Configure's link back to the analysis list; the file is kept. */
export function AnalysisBar({ job }: { job: JobView }) {
  const a = byKey[currentKey(job) ?? ''];
  if (!a) return null;
  return <p className="ap-anbar"><span>Analysis: <b>{a.t}</b></span><a className="ap-link" href="/app/" onClick={onLink}>Change analysis</a></p>;
}
