// The DataTrust app (step one of APP_PROPOSAL.md): the shell, Upload and Configure.
// It follows DataTrust's real guided flow (src/datatrust/web.py, templates/ui.html) and shows the
// real inspection of adult.csv (scripts/extract_inspect.py). The "Recent reports" rail is a
// proposal: DataTrust keeps no report history today, and the rail says so.
import '@fontsource-variable/schibsted-grotesk';
import '@fontsource/ibm-plex-mono/400.css';
import '@fontsource/ibm-plex-mono/500.css';
import './nk.css';
import './app.css';
import { useEffect, useRef, useState, type ReactElement } from 'react';
import { runFindings, runs } from '../../fixture';
import { runStates } from '../modules/data';
import { Checks } from './checks';
import './drop.css';
import insp from '../../fixture/inspect.generated.json';
import { useRoute } from '../../shell/router';
import { reducedMotion } from '../../shell/motion';

type Step = 'upload' | 'configure' | 'confirm' | 'report';
type Mode = 'classification' | 'regression' | 'unlabeled';
const steps: { id: Step; n: number; t: string; built: boolean }[] = [
  { id: 'upload', n: 1, t: 'Upload', built: true }, { id: 'configure', n: 2, t: 'Configure', built: true },
  { id: 'confirm', n: 3, t: 'Confirm', built: true }, { id: 'report', n: 4, t: 'Report', built: true },
];
const MiB = (b: number) => (b / 1048576).toFixed(2);
const fmt = (n: number) => n.toLocaleString('en-US');

function appHref(step: Step) {
  const clean = new URLSearchParams(location.hash.split('?')[1] ?? '').has('clean');
  return `#/numek/app?${clean ? 'clean&' : ''}step=${step}`;
}
function siteHref() {
  const clean = new URLSearchParams(location.hash.split('?')[1] ?? '').has('clean');
  return `#/numek/landing?${clean ? 'clean&' : ''}p=datatrust`;
}

/** Four fixed-size corner brackets (Markup's mark). Fixed px, so every corner is identical at any size. */
function Corners({ tone = 'hot' }: { tone?: 'hot' | 'ghost' }) {
  return <span className={`ap-cn ap-cn--${tone}`} aria-hidden="true"><i /><i /><i /><i /></span>;
}

/* ——— Shell ——— */

const workflows = [
  ['Temporal reliability', 'Exact clocks, coverage, availability, revisions', '/temporal'],
  ['Text reliability', 'Corpora, annotation, conversations, retrieval', '/text'],
  ['Image reliability', 'Images, annotations, segmentation integrity', '/images'],
  ['Records ↔ documents', 'Records reconciled against PDF and DOCX', '/cross-representation'],
  ['Split audit · comparison', 'Version comparison and advanced local analysis', '/m4'],
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
          <p>Separate guided workflows in DataTrust. They are not part of this prototype.</p>
          {workflows.map(([t, d, r]) => <div key={r} className="ap-wf__it" role="menuitem" aria-disabled="true"><b>{t}</b><span>{d}</span><code>{r}</code></div>)}
        </div>
      )}
    </div>
  );
}

function AppBar({ step }: { step: Step }) {
  const i = steps.findIndex((s) => s.id === step);
  return (
    <header className="ap-bar">
      <a className="ap-mark" href={siteHref()} aria-label="DataTrust, back to the DataTrust page"><i aria-hidden="true" /><b>DataTrust</b><span>by NUMEK</span></a>
      <nav className="ap-rail" aria-label="Steps">
        <span className="ap-rail__line" aria-hidden="true"><i style={{ transform: `scaleX(${i / (steps.length - 1)})` }} /></span>
        {steps.map((s, k) => {
          const state = k === i ? 'is-on' : k < i ? 'is-done' : '';
          const label = <><b>{k < i ? '✓' : s.n}</b><span>{s.t}</span></>;
          return s.built
            ? <a key={s.id} href={appHref(s.id)} className={`ap-rail__n ${state}`} aria-current={k === i ? 'step' : undefined}>{label}</a>
            : <span key={s.id} className={`ap-rail__n is-later ${state}`} title={`${s.t} is the next build step`}>{label}</span>;
        })}
        <span className="ap-rail__pill" aria-hidden="true">{i + 1}/4 · {steps[i].t}</span>
      </nav>
      <div className="ap-bar__r">
        <Workflows />
        <span className="ap-live"><i aria-hidden="true" />local · 127.0.0.1:8000</span>
      </div>
    </header>
  );
}

function Recent() {
  const [open, setOpen] = useState(false);
  const [pick, setPick] = useState<string | null>(null);
  return (
    <aside className={`ap-recent ${open ? 'is-open' : ''}`} aria-label="Recent reports (proposed)">
      <button type="button" className="ap-recent__toggle" aria-expanded={open} onClick={() => setOpen((o) => !o)}>Recent reports <em>proposed</em></button>
      <div className="ap-recent__in">
        <div className="ap-recent__h"><b>Recent reports</b><em>Proposed</em></div>
        <p className="ap-recent__why">Not in DataTrust today: a result lasts one session. This rail shows how saved reports could look.</p>
        <ul>
          {runs.map((r) => (
            <li key={r.id}>
              <button type="button" className={pick === r.id ? 'is-on' : ''} aria-pressed={pick === r.id} onClick={() => setPick(r.id)}>
                <b>{r.name}</b>
                <span>{r.file}</span>
                <span className="ap-recent__m"><em>{r.when}</em>{r.score == null ? <i className="is-none">no score defined</i> : <i className={r.score >= 85 ? 'is-low' : 'is-elev'}>{r.score.toFixed(1)} · {r.band}</i>}</span>
              </button>
            </li>
          ))}
        </ul>
        <p className="ap-recent__foot">Today: download HTML, PDF or JSON before starting a new analysis.</p>
      </div>
      {pick && <ReportSheet id={pick} onClose={() => setPick(null)} />}
    </aside>
  );
}

const sevRank: Record<string, number> = { High: 0, Moderate: 1, Low: 2 };
// Real reports in public/reports: the classification runs were generated with DataTrust's own CLI
// for this prototype; Bike and SMS are copies of the recorded validation reports.
const reportFiles: Record<string, { stem: string; ext: string[] } | undefined> = {
  adult: { stem: 'adult', ext: ['html', 'pdf', 'json'] }, german: { stem: 'german_credit', ext: ['html', 'pdf', 'json'] },
  bank: { stem: 'bank_marketing', ext: ['html', 'pdf', 'json'] }, bike: { stem: 'bike_hour', ext: ['html', 'json'] }, sms: { stem: 'sms', ext: ['html', 'json'] },
};

/** The real DataTrust HTML report, full screen inside the app. */
function Viewer({ stem, name, ext, onClose }: { stem: string; name: string; ext: string[]; onClose: () => void }) {
  return (
    <div className="ap-view" role="dialog" aria-modal="true" aria-label={`${name}: full DataTrust report`}>
      <header className="ap-view__h">
        <button type="button" className="ap-sheet__x" onClick={onClose}>← Back</button>
        <b>{stem}.html</b><span>the real DataTrust report</span>
        <div className="ap-view__dl">{ext.map((x) => <a key={x} className="ap-sheet__dl" href={`/reports/${stem}.${x}`} download={`${stem}.${x}`}>{x.toUpperCase()} ↓</a>)}</div>
      </header>
      <iframe title={`${name} report`} src={`/reports/${stem}.html`} />
    </div>
  );
}
/** A saved report, opened from the proposed rail: the run's real summary, findings and evidence. */
function ReportSheet({ id, onClose }: { id: string; onClose: () => void }) {
  const r = runs.find((x) => x.id === id)!;
  const close = useRef<HTMLButtonElement>(null);
  const files = reportFiles[id];
  const [view, setView] = useState(false);
  useEffect(() => { close.current?.focus(); setView(false); }, [id]);
  useEffect(() => { const esc = (e: KeyboardEvent) => { if (e.key !== 'Escape') return; if (view) setView(false); else onClose(); }; addEventListener('keydown', esc); return () => removeEventListener('keydown', esc); }, [view, onClose]);
  const fs = [...(runFindings[id] ?? [])].sort((a, b) => sevRank[a.severity] - sevRank[b.severity]);
  const states = Object.entries(runStates[id] ?? {}).filter(([k, v]) => v && k !== 'local' && k !== 'reports' && k !== 'score');
  return (
    <>
      <div className="ap-sheet__scrim" onClick={onClose} aria-hidden="true" />
      <section className="ap-sheet" role="dialog" aria-modal="true" aria-label={`${r.name} report`}>
        <header className="ap-sheet__h">
          <span className="ap-sheet__k">Saved report · <em>proposed</em></span>
          <button ref={close} type="button" className="ap-sheet__x" onClick={onClose} aria-label="Close">Close ✕</button>
        </header>
        <h2>{r.name}</h2>
        <p className="ap-sheet__meta">{r.file} · {r.task} · {r.size} · {r.when} · {r.runtime}</p>
        <div className={`ap-sheet__score ${r.score == null ? 'is-none' : r.score >= 85 ? 'is-low' : 'is-elev'}`}>
          {r.score == null ? <><b>No score</b><span>No universal score is defined for this kind of data, by design. The report gives evidence.</span></> : <><b>{r.score.toFixed(1)}</b><span>{r.band} risk</span></>}
        </div>
        <p className="ap-sheet__lead">{r.lead}.</p>
        <h3>{fs.length ? `Findings (${fs.length})` : 'Evidence'}</h3>
        <ul className="ap-sheet__fs">
          {fs.length
            ? fs.map((f) => <li key={f.title}><span className={`ap-sev is-${f.severity.toLowerCase()}`}>{f.severity}</span><b>{f.title}</b><span>{f.evidence}</span></li>)
            : states.map(([k, v]) => <li key={k}><span className="ap-sev is-low">{v!.label}</span><b>{k[0].toUpperCase() + k.slice(1)}</b><span>{v!.detail}</span></li>)}
        </ul>
        {files ? (
          <>
            <div className="ap-sheet__acts">
              <button type="button" className="nk-btn" onClick={() => setView(true)}>Open full result</button>
              {files.ext.map((x) => <a key={x} className="ap-sheet__dl" href={`/reports/${files.stem}.${x}`} download={`${files.stem}.${x}`}>{x.toUpperCase()} ↓</a>)}
            </div>
            <p className="ap-sheet__note">These are the real reports DataTrust produced for this run. Keeping them in a list like this is the proposal: DataTrust keeps no history today.</p>
          </>
        ) : <p className="ap-sheet__note ap-sheet__note--none">No report file for this run is included in this prototype, so there is nothing to open or download here.</p>}
      </section>
      {view && files && <Viewer stem={files.stem} name={r.name} ext={files.ext} onClose={() => setView(false)} />}
    </>
  );
}

/* ——— 1 · Upload ——— */

const modes: { id: Mode; t: string; d: string; draw: ReactElement }[] = [
  { id: 'classification', t: 'Classification', d: 'Explicit target. Scores, sub-scores and guardrails.', draw: <svg viewBox="0 0 120 64" aria-hidden="true"><rect x="6" y="20" width="80" height="22" className="ap-d-ink" /><rect x="86" y="20" width="28" height="22" className="ap-d-hot" /><path d="M6 50V54H114V50" className="ap-d-ln" /></svg> },
  { id: 'regression', t: 'Regression', d: 'Numerical target. Evidence, no universal score.', draw: <svg viewBox="0 0 120 64" aria-hidden="true">{[[12, 48], [24, 44], [34, 40], [46, 38], [58, 30], [68, 28], [80, 22], [94, 18], [106, 12]].map(([x, y], k) => <circle key={k} cx={x} cy={y} r="3" className="ap-d-ink" />)}<path d="M6 52L114 10" className="ap-d-ln" /></svg> },
  { id: 'unlabeled', t: 'Unlabeled', d: 'No target. Every column is profiled.', draw: <svg viewBox="0 0 120 64" aria-hidden="true">{Array.from({ length: 6 }, (_, k) => <rect key={k} x={8 + k * 18} y="10" width="12" height="44" className="ap-d-ln" />)}<rect x="44" y="40" width="12" height="14" className="ap-d-ink" /></svg> },
];
const moreModes = ['Classification with annotation expectations', 'Regression with annotations or multiple outputs', 'Multilabel binary indicators', 'Clustering readiness', 'Anomaly-detection readiness', 'Profiling with explicit roles'];

function Upload({ mode, setMode, picked, setPicked }: { mode: Mode; setMode: (m: Mode) => void; picked: 'none' | 'adult' | { name: string; size: number }; setPicked: (p: 'none' | 'adult' | { name: string; size: number }) => void }) {
  const file = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const ready = picked !== 'none';
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
        <details className="ap-more"><summary>Six more modes</summary><ul>{moreModes.map((x) => <li key={x}>{x}</li>)}</ul><p>They use the same Upload step, then add their own declarations in Configure.</p></details>
        {mode !== 'classification' && <p className="ap-note">This prototype follows a classification run on Adult. In DataTrust, {mode} changes what Configure asks.</p>}
      </section>

      <section className="ap-sec" aria-labelledby="ap-file-h">
        <h2 id="ap-file-h" className="ap-q">Which dataset?</h2>
        <div className={`ap-drop ${over ? 'is-over' : ''} ${ready ? 'is-ready' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
          onDrop={(e) => { e.preventDefault(); setOver(false); const f = e.dataTransfer.files[0]; if (f) setPicked({ name: f.name, size: f.size }); }}>
          {!ready ? (
            <div className="ap-drop__empty">
              <svg viewBox="0 0 40 40" aria-hidden="true"><path d="M20 6V24M12 16L20 24L28 16" /><path d="M6 26V33H34V26" /></svg>
              <b>Drop a CSV here</b>
              <span>Comma-delimited · header required · up to 100 MiB</span>
              <div className="ap-drop__acts">
                <button type="button" className="nk-btn nk-btn--ghost" onClick={() => file.current?.click()}>Choose a file</button>
                <button type="button" className="nk-btn" onClick={() => setPicked('adult')}>Try it with Adult</button>
              </div>
              <input ref={file} type="file" accept=".csv,text/csv" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) setPicked({ name: f.name, size: f.size }); }} />
            </div>
          ) : (
            <div className="ap-drop__file">
              <div className="ap-file">
                <span className="ap-file__fold" aria-hidden="true" />
                <b>{picked === 'adult' ? insp.file : picked.name}</b>
                <span>{picked === 'adult' ? `${MiB(insp.file_size)} MiB · ${fmt(insp.row_count)} rows · ${insp.column_count} columns` : `${MiB(picked.size)} MiB · chosen on this machine`}</span>
              </div>
              {picked !== 'adult' && <p className="ap-note">This prototype can’t read your file. In DataTrust it would be inspected right here, locally. The prototype continues with Adult.</p>}
              <button type="button" className="ap-link" onClick={() => setPicked('none')}>Choose a different file</button>
            </div>
          )}
        </div>
      </section>

      <div className="ap-acts">
        {ready ? <a className="nk-btn" href={appHref('configure')}>{picked === 'adult' ? 'Inspect dataset' : 'Continue with Adult'} →</a> : <span className="nk-btn is-off" aria-disabled="true">Inspect dataset →</span>}
        <span className="ap-acts__hint">{ready ? 'Next: preview the rows and choose the outcome.' : 'Choose a file, or try it with Adult.'}</span>
      </div>
    </div>
  );
}

/* ——— 2 · Configure ——— */

type Opt = (typeof insp.target_options)[number];
type TInfo = { subtype: string; class_count: number; labeled: number; missing: number; distribution: { label: string; count: number; percentage: number }[]; more_classes: number; explanation: string; requires_override: boolean };
const targets = insp.targets as unknown as Record<string, TInfo>;
const groups: { id: string; h: string; d: string }[] = [
  { id: 'outcome_word', h: 'Outcome-word candidates', d: 'These names contain outcome-style wording and have a small observed value set.' },
  { id: 'small_class_set', h: 'Other small-set candidates', d: 'These columns have a small observed value set, but their names do not establish the intended outcome.' },
];

function Pick({ o, on, set }: { o: Opt; on: boolean; set: () => void }) {
  return (
    <label className={`ap-opt ${on ? 'is-on' : ''} ${o.group === 'advanced' ? 'is-adv' : ''}`}>
      <input type="radio" name="target" checked={on} onChange={set} />
      <span className="ap-opt__r" aria-hidden="true" />
      <span className="ap-opt__t"><b>{o.name}</b><span>{fmt(o.observed_distinct_count ?? 0)} distinct values · {fmt(o.missing_count ?? 0)} missing · {o.selector_explanation}</span></span>
      {on && <span className="ap-opt__mini"><Mini name={o.name} /></span>}
    </label>
  );
}

/** Compact version of the selection panel, shown under the chosen option on narrow screens. */
function Mini({ name }: { name: string }) {
  const t = targets[name];
  return (
    <>
      <b>{t.subtype === 'binary' ? 'Binary' : t.subtype === 'multiclass' ? 'Multiclass' : 'Single-class'} · {fmt(t.class_count)} classes · {fmt(t.labeled)} labelled</b>
      <span>{t.distribution.slice(0, 3).map((d) => `${d.label} ${d.percentage}%`).join(' · ')}{t.distribution.length > 3 || t.more_classes ? ' · …' : ''}</span>
      {t.requires_override && <em>Needs an extra confirmation in the next step.</em>}
    </>
  );
}

function Selection({ name }: { name: string | null }) {
  if (!name) return (
    <div className="ap-sel ap-sel--empty">
      <Corners tone="ghost" />
      <b>Choose the outcome.</b>
      <p>DataTrust won’t choose it for you: only you know what the data is meant to predict.</p>
    </div>
  );
  const t = targets[name];
  const max = Math.max(...t.distribution.map((d) => d.percentage));
  return (
    <div className="ap-sel" key={name}>
      <span className="ap-sel__k">Selected outcome</span>
      <b className="ap-sel__n">{name}</b>
      <span className="ap-sel__task">{t.subtype === 'binary' ? 'Binary' : t.subtype === 'multiclass' ? 'Multiclass' : 'Single-class'} classification · {fmt(t.class_count)} classes</span>
      <dl className="ap-sel__kv"><div><dt>Labelled rows</dt><dd>{fmt(t.labeled)}</dd></div><div><dt>Missing labels</dt><dd>{fmt(t.missing)}</dd></div></dl>
      <ul className="ap-sel__dist">
        {t.distribution.map((d, k) => <li key={d.label}><span>{d.label}</span><i style={{ width: `${(d.percentage / max) * 100}%` }} className={k === 0 ? 'is-top' : ''} /><em>{d.percentage}%</em></li>)}
        {t.more_classes > 0 && <li className="ap-sel__more">+ {fmt(t.more_classes)} more classes</li>}
      </ul>
      {t.requires_override
        ? <div className="ap-sel__warn"><b>Needs an extra confirmation</b><p>{t.explanation}</p><p>You can still use it on purpose; DataTrust will ask you to confirm in the next step.</p></div>
        : <p className="ap-sel__ok">{t.explanation}</p>}
    </div>
  );
}

function Configure({ target, setTarget, name, setName, purpose, setPurpose }: { target: string | null; setTarget: (t: string) => void; name: string; setName: (s: string) => void; purpose: string; setPurpose: (s: string) => void }) {
  const [msg, setMsg] = useState(false);
  const adv = insp.target_options.filter((o) => o.group === 'advanced');
  const advOpen = !!target && adv.some((o) => o.name === target);
  return (
    <div className="ap-cf">
      <header className="ap-head">
        <span className="nk-label">Step 2 · Configure</span>
        <h1>Configure the analysis.</h1>
      </header>
      <dl className="ap-cards">
        {[['File', insp.file], ['Size', `${MiB(insp.file_size)} MiB`], ['Rows', fmt(insp.row_count)], ['Columns', String(insp.column_count)]].map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}
      </dl>

      <section className="ap-sec" aria-labelledby="ap-prev-h">
        <h2 id="ap-prev-h" className="ap-sub">First 10 rows</h2>
        <div className="ap-table" tabIndex={0} aria-label="First 10 rows of adult.csv, scrollable">
          <table>
            <thead><tr>{insp.columns.map((c) => <th key={c} className={c === target ? 'is-t' : ''}>{c}</th>)}</tr></thead>
            <tbody>{insp.preview.map((r, i) => <tr key={i}>{r.map((v, j) => <td key={j} className={insp.columns[j] === target ? 'is-t' : ''}>{v}</td>)}</tr>)}</tbody>
          </table>
        </div>
      </section>

      <section className="ap-target" aria-labelledby="ap-target-h">
        <div className="ap-target__l">
          <h2 id="ap-target-h" className="ap-q">What outcome is this dataset meant to predict?</h2>
          <p className="ap-muted">DataTrust groups structurally plausible choices and explains why. It does not choose or preselect the business outcome.</p>
          {groups.map((g) => {
            const list = insp.target_options.filter((o) => o.group === g.id);
            if (!list.length) return null;
            return (
              <fieldset key={g.id} className="ap-group">
                <legend>{g.h}</legend>
                <p className="ap-muted">{g.d}</p>
                <div className="ap-opts">{list.map((o) => <Pick key={o.name} o={o} on={target === o.name} set={() => setTarget(o.name)} />)}</div>
              </fieldset>
            );
          })}
          <details className="ap-group ap-group--adv" open={advOpen || undefined}>
            <summary>Advanced choices ({adv.length})</summary>
            <p className="ap-muted">These choices look single-class, identifier-like, continuous, or highly categorical. You can still use one intentionally after an extra confirmation.</p>
            <div className="ap-opts">{adv.map((o) => <Pick key={o.name} o={o} on={target === o.name} set={() => setTarget(o.name)} />)}</div>
          </details>

          <div className="ap-fields">
            <label>Dataset/report name <span>optional · 120 characters</span><input type="text" maxLength={120} placeholder="Defaults to the filename" value={name} onChange={(e) => setName(e.target.value)} /></label>
            <label>Purpose <span>optional · 1,000 characters</span><textarea maxLength={1000} rows={3} placeholder="What prediction or decision will this dataset support?" value={purpose} onChange={(e) => setPurpose(e.target.value)} /></label>
          </div>
          <div className="ap-acts">
            {target ? <a className="nk-btn" href={appHref('confirm')}>Review selection →</a> : <button type="button" className="nk-btn is-off" onClick={() => setMsg(true)}>Review selection →</button>}
            <a className="nk-btn nk-btn--ghost" href={appHref('upload')}>Back</a>
            {msg && !target && <span className="ap-acts__hint ap-acts__hint--stop" role="status">Choose a target column from the uploaded dataset.</span>}
          </div>
        </div>
        <div className="ap-target__r"><Selection name={target} /></div>
      </section>
    </div>
  );
}

/* ——— 3 · Confirm ——— */

const planned = ['Missing values', 'Repeated rows', 'Contradicting labels', 'Unusual values', 'Leaked answers', 'Lopsided target'];

function Confirm({ target, name }: { target: string | null; name: string }) {
  const [ack, setAck] = useState(false);
  const [run, setRun] = useState(false);
  useEffect(() => {
    if (!run) return;
    const t = setTimeout(() => { location.hash = appHref('report'); }, reducedMotion() ? 0 : 2600);
    return () => clearTimeout(t);
  }, [run]);
  if (!target) return (
    <div className="ap-cf"><header className="ap-head"><span className="nk-label">Step 3 · Confirm</span><h1>Choose an outcome first.</h1><p>Confirm needs the target you picked in Configure.</p></header><a className="nk-btn" href={appHref('configure')}>← Back to Configure</a></div>
  );
  const t = targets[target];
  const over = t.requires_override;
  return (
    <div className="ap-co">
      <header className="ap-head">
        <span className="nk-label">Step 3 · Confirm</span>
        <h1>Confirm the analysis.</h1>
      </header>
      <div className="ap-co__task"><b>Detected task: {t.subtype === 'binary' ? 'Binary' : 'Multiclass'} classification</b><span>Based on {fmt(t.class_count)} observed target classes. Missing labels are excluded.</span></div>
      <dl className="ap-cards">
        {[['Dataset', name || insp.file], ['Target', target], ['Labelled rows', fmt(t.labeled)], ['Missing labels', fmt(t.missing)]].map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}
      </dl>
      <div className="ap-co__split" aria-label="Target classes">
        {t.distribution.slice(0, 6).map((d, k) => <i key={d.label} style={{ flex: d.percentage }} className={k === 0 ? 'is-top' : ''}><span>{d.label} · {d.percentage}%</span></i>)}
      </div>
      <section className="ap-sec">
        <h2 className="ap-sub">Planned checks</h2>
        <ol className={`ap-co__checks ${run ? 'is-run' : ''}`}>{planned.map((c, k) => <li key={c} style={{ ['--k' as string]: k }}><i aria-hidden="true" />{c}</li>)}</ol>
      </section>
      {over && (
        <div className="ap-sel__warn ap-co__warn">
          <b>Review this outcome choice</b>
          <p>{t.explanation}</p>
          <label><input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} /> I still want to use <strong>{target}</strong> as the prediction outcome.</label>
        </div>
      )}
      <div className="ap-acts">
        {run
          ? <span className="nk-btn is-run" role="status">Generating the report…</span>
          : <button type="button" className={`nk-btn ${over && !ack ? 'is-off' : ''}`} onClick={() => { if (!over || ack) setRun(true); }}>Generate reliability report</button>}
        <a className="nk-btn nk-btn--ghost" href={appHref('configure')}>Change selection</a>
      </div>
    </div>
  );
}

/* ——— 4 · Report ——— */

function Result({ name, onNew }: { target: string | null; name: string; onNew: () => void }) {
  const [view, setView] = useState(false);
  return (
    <div className="ap-rs">
      <header className="ap-rs__bar">
        <h1>{name || 'Adult'}</h1>
        <p>adult.csv · Classification · binary<br />13 Aug 2026 · 0.18 s · 9 of 14 checks apply · <button type="button" className="ap-rs__open" onClick={() => setView(true)}>Open report ↗</button></p>
      </header>

      <Checks result />

      <section className="ap-rs__out">
        <div>
          <h2 className="ap-q">Take it with you</h2>
          <p className="ap-muted">The same evidence in three files. This result lasts for this session, so download it before starting a new analysis.</p>
        </div>
        <div className="ap-acts">
          <button type="button" className="nk-btn" onClick={() => setView(true)}>View full report</button>
          {['pdf', 'json'].map((x) => <a key={x} className="ap-sheet__dl" href={`/reports/adult.${x}`} download={`adult.${x}`}>Download {x.toUpperCase()} ↓</a>)}
          <a className="nk-btn nk-btn--ghost" href={appHref('upload')} onClick={onNew}>New analysis</a>
        </div>
      </section>
      {view && <Viewer stem="adult" name="Adult" ext={['html', 'pdf', 'json']} onClose={() => setView(false)} />}
    </div>
  );
}

/* ——— App ——— */

function useSession<T>(key: string, init: T) {
  const [v, setV] = useState<T>(() => { try { const s = sessionStorage.getItem(key); return s ? (JSON.parse(s) as T) : init; } catch { return init; } });
  useEffect(() => { try { sessionStorage.setItem(key, JSON.stringify(v)); } catch { /* storage unavailable */ } }, [key, v]);
  return [v, setV] as const;
}

export default function App() {
  const { params } = useRoute();
  const step = (['upload', 'configure', 'confirm', 'report'].includes(params.get('step') ?? '') ? params.get('step') : 'upload') as Step;
  const [mode, setMode] = useSession<Mode>('nk-app-mode', 'classification');
  const [picked, setPicked] = useSession<'none' | 'adult' | { name: string; size: number }>('nk-app-picked', 'none');
  const [target, setTarget] = useSession<string | null>('nk-app-target', null);
  const [name, setName] = useSession('nk-app-name', '');
  const [purpose, setPurpose] = useSession('nk-app-purpose', '');
  useEffect(() => { scrollTo({ top: 0, behavior: reducedMotion() ? 'auto' : 'smooth' }); }, [step]);
  return (
    <div className="nk ap">
      <AppBar step={step} />
      <div className="ap-body">
        <Recent />
        <main className="ap-main">
          {step === 'upload' && <Upload mode={mode} setMode={setMode} picked={picked} setPicked={setPicked} />}
          {step === 'configure' && <Configure target={target} setTarget={setTarget} name={name} setName={setName} purpose={purpose} setPurpose={setPurpose} />}
          {step === 'confirm' && <Confirm target={target} name={name} />}
          {step === 'report' && <Result target={target} name={name} onNew={() => { setPicked('none'); setTarget(null); setName(''); setPurpose(''); }} />}
        </main>
      </div>
    </div>
  );
}
