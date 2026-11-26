// Guided configuration (Guided Analysis Stage 4b): the three layers of each tabular Configure step, availability at
// the prediction point (G0, with a deliberate confirmation for bulk declarations), the role-aware switch, role
// suggestions, and the review panel on Confirm. Wording about what will run comes from the server (`job.review`),
// computed by the same method resolution the analysis uses.
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { api, type JobView, type Mode } from './api';
import { navigate, stepHref } from './router';
import { fmt } from './parts';

type Flash = (e: unknown) => void;
const AVAILABILITY = [['unknown', 'unknown'], ['available_at_prediction', 'available'], ['unavailable_at_prediction', 'not available']] as const;

/* ——— Layers ——— */

const LAYER = { essential: 'Essential', recommended: 'Recommended context', advanced: 'Advanced' } as const;

/** One configuration layer: what it is for (`why`) and what cannot be concluded without it (`ifMissing`). */
export function Layer({ kind, title, why, ifMissing, children, open }: { kind: keyof typeof LAYER; title: string; why?: ReactNode; ifMissing?: ReactNode; children: ReactNode; open?: boolean }) {
  const head = (
    <>
      <span className="ap-layer__k">{LAYER[kind]}</span>
      <span className="ap-layer__t">{title}</span>
    </>
  );
  const body = (
    <>
      {(why || ifMissing) && <dl className="ap-layer__why">{why && <div><dt>Why</dt><dd>{why}</dd></div>}{ifMissing && <div><dt>If you skip it</dt><dd>{ifMissing}</dd></div>}</dl>}
      {children}
    </>
  );
  return kind === 'advanced'
    ? <details className={`ap-layer ap-layer--${kind}`} open={open || undefined}><summary>{head}</summary>{body}</details>
    : <section className={`ap-layer ap-layer--${kind}`}><h2 className="ap-layer__h">{head}</h2>{body}</section>;
}

/* ——— Confirmation dialog ——— */

function Dialog({ open, title, children, confirm, disabled, onConfirm, onClose }: { open: boolean; title: string; children: ReactNode; confirm: string; disabled?: boolean; onConfirm: () => void; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog ref={ref} className="ap-dlg" aria-label={title} onClose={onClose} onCancel={onClose}>
      <h2>{title}</h2>
      {children}
      <div className="ap-acts">
        <button type="button" className={`nk-btn ${disabled ? 'is-off' : ''}`} disabled={disabled} onClick={onConfirm}>{confirm}</button>
        <button type="button" className="nk-btn nk-btn--ghost" onClick={onClose} autoFocus>Cancel</button>
      </div>
    </dialog>
  );
}

/* ——— G0 · Availability at the prediction point ——— */

/** Every column starts unknown. Columns can be declared one by one; declaring several as available at once needs a
 *  deliberate confirmation that lists them and states the consequence. Bulk-declared columns are reported apart. */
export function Availability({ columns, value, onChange, bulk, setBulk }: { columns: string[]; value: Record<string, string>; onChange: (v: Record<string, string>) => void; bulk: string[]; setBulk: (b: string[]) => void }) {
  const [picked, setPicked] = useState<string[]>([]);
  const [asking, setAsking] = useState(false);
  const [checked, setChecked] = useState(false);
  const get = (c: string) => value[c] ?? 'unknown';
  const counts = AVAILABILITY.map(([v, l]) => [l, columns.filter((c) => get(c) === v).length] as const);
  const set = (c: string, v: string) => { onChange({ ...value, [c]: v }); if (bulk.includes(c)) setBulk(bulk.filter((x) => x !== c)); };
  const apply = () => {
    onChange({ ...value, ...Object.fromEntries(picked.map((c) => [c, 'available_at_prediction'])) });
    setBulk([...new Set([...bulk, ...picked])]);
    setPicked([]); setAsking(false); setChecked(false);
  };
  const toggle = (c: string) => setPicked((p) => (p.includes(c) ? p.filter((x) => x !== c) : [...p, c]));
  return (
    <div className="ap-av">
      <p className="ap-av__n">{counts.map(([l, n]) => `${fmt(n)} ${l}`).join(' · ')}{bulk.length ? ` · ${fmt(bulk.length)} declared in bulk` : ''}</p>
      <div className="ap-av__list" role="group" aria-label="Availability of each column at the prediction point">
        {columns.map((c) => (
          <div key={c} className={`ap-av__row is-${get(c)}`}>
            <label className="ap-av__pick"><input type="checkbox" checked={picked.includes(c)} onChange={() => toggle(c)} aria-label={`Select ${c}`} /></label>
            <span className="ap-av__c">{c}{bulk.includes(c) && <em>bulk</em>}</span>
            <select aria-label={`Availability of ${c}`} value={get(c)} onChange={(e) => set(c, e.target.value)}>
              {AVAILABILITY.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>
        ))}
      </div>
      <div className="ap-av__bulk">
        <button type="button" className={`nk-btn nk-btn--ghost ${picked.length ? '' : 'is-off'}`} disabled={!picked.length} onClick={() => setAsking(true)}>Mark {picked.length ? fmt(picked.length) : ''} selected as available…</button>
        {picked.length > 0 && <button type="button" className="ap-link" onClick={() => setPicked([])}>Clear selection</button>}
        {!picked.length && <span className="ap-muted">Tick columns to declare several at once.</span>}
      </div>
      <Dialog open={asking} title={`Declare ${fmt(picked.length)} ${picked.length === 1 ? 'column' : 'columns'} available?`} confirm="Declare available" disabled={!checked} onConfirm={apply} onClose={() => { setAsking(false); setChecked(false); }}>
        <p>Declaring a column available tells DataTrust it is known <b>before</b> the prediction is made.</p>
        <p>If one of these is only known after the outcome (for example a call’s duration, a final status or a settlement amount), DataTrust treats its relation to the target as legitimate: a column that reproduces the target is then reported as Low (“deterministic predictor declared available”) instead of a leakage review, and the leakage concern does not appear. Leave a column <b>unknown</b> if you are not sure.</p>
        <ul className="ap-dlg__list">{picked.map((c) => <li key={c}>{c}</li>)}</ul>
        <label className="ap-check"><input type="checkbox" checked={checked} onChange={(e) => setChecked(e.target.checked)} /> I checked each listed column against the prediction point.</label>
      </Dialog>
    </div>
  );
}

/* ——— Role information and the role-aware switch ——— */

const SWITCH: Partial<Record<Mode, { to: Mode; label: string; text: string; carry: boolean }>> = {
  classification: { to: 'annotation_classification', label: 'Switch to role-aware classification', carry: true,
    text: 'It opens “Partially labelled: category”, the analysis that takes column roles. Role-aware classification lets you mark columns as metadata, grouping keys or ignored, and declare label expectations. Once you declare anything beyond the scored method’s defaults it runs as tabular_partial_classification_v1, and no composite review score is computed.' },
  regression: { to: 'annotation_regression', label: 'Switch to role-aware numerical outcome', carry: true,
    text: 'It opens “Partially labelled: number”, the analysis that takes column roles. The role-aware numerical outcome lets you mark columns as metadata, grouping keys or ignored, and declare expectations per target. Once you declare roles or expectations it runs as tabular_annotation_regression_v1.' },
  unlabeled: { to: 'role_profile', label: 'Switch to profile with chosen columns', carry: false,
    text: 'Profile with chosen columns lets you mark columns as features, metadata or ignored. Once you do, it runs as tabular_role_profile_v1 over the features only.' },
};

const NOTICED: Record<string, string> = { identifier: 'looks like an identifier', clock: 'may hold times', annotation_status: 'looks like a labelling status' };

/** What inspection noticed about roles. On the scored path this is information only: every non-target column is
 *  analysed as a feature. Assigning roles needs the explicit switch, which states the method that will then run. */
export function RoleNotes({ job, target, onJob, flash }: { job: JobView; target: string | null; onJob: (j: JobView) => void; flash: Flash }) {
  const sw = SWITCH[job.mode];
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  if (!sw) return null;
  const noticed = (job.input_inspection?.columns ?? []).filter((c) => c.name !== target).flatMap((c) => {
    const s = ['clock', 'annotation_status', 'identifier'].map((r) => c.suggestions.find((x) => x.role === r)).find(Boolean);  // a unique date reads as a time first
    return s ? [{ name: c.name, role: s.role, rule: s.rule }] : [];
  });
  const go = () => {
    setBusy(true);
    api.chooseAnalysis(sw.to, sw.carry ? target : null).then((r) => { setAsking(false); onJob(r.job); navigate(stepHref('configure')); }).catch(flash).finally(() => setBusy(false));
  };
  return (
    <div className="ap-roles-note">
      {noticed.length > 0 && (
        <>
          <p><b>Columns DataTrust noticed.</b> {job.mode === 'unlabeled' ? 'Every column is profiled.' : 'In this method every column other than the target is analysed as a feature.'} Nothing below is applied.</p>
          <ul>{noticed.slice(0, 8).map((n) => <li key={n.name}><code>{n.name}</code> {NOTICED[n.role]} <span className="ap-fit__rules"><code>{n.rule}</code></span></li>)}{noticed.length > 8 && <li>and {fmt(noticed.length - 8)} more</li>}</ul>
        </>
      )}
      <button type="button" className="ap-link" onClick={() => setAsking(true)}>{sw.label}</button>
      <Dialog open={asking} title={sw.label} confirm={busy ? 'Switching…' : 'Switch'} disabled={busy} onConfirm={go} onClose={() => setAsking(false)}>
        <p>{sw.text}</p>
        <p>{sw.carry && target ? <>Your outcome <b>{target}</b> stays selected as the target. </> : null}Other declarations made on this page are cleared. The file is kept. The review step names the method that will run before anything is generated.</p>
      </Dialog>
    </div>
  );
}

/** M3 role suggestions, from the input inspection, as chips accepted one at a time. Nothing is preselected. */
export function suggestedRole(job: JobView, column: string): { role: string; rule: string; why: string } | null {
  const c = job.input_inspection?.columns?.find((x) => x.name === column);
  if (!c) return null;
  const has = (r: string) => c.suggestions.find((s) => s.rule === r);
  const readiness = job.mode === 'clustering' || job.mode === 'anomaly_detection' || job.mode === 'role_profile';
  const time = has('R-TIME-1') ?? has('R-TIME-2');
  if (time) return { role: 'metadata', rule: time.rule, why: 'may hold times' };
  const id = has('R-ID-1') ?? has('R-ID-2');
  if (id) return { role: readiness ? 'ignored' : 'metadata', rule: id.rule, why: 'looks like an identifier' };
  const status = has('R-STATUS-1');
  if (status && !readiness) return { role: 'metadata', rule: status.rule, why: 'looks like a labelling status' };
  if (job.mode === 'multilabel_classification' && job.input_inspection?.table?.[0]?.columns.includes(column)) return { role: 'target', rule: 'R-MULTI-1', why: 'a yes/no indicator' };
  if (readiness && has('R-TEXT-1')) return { role: 'ignored', rule: 'R-TEXT-1', why: 'free text carries no distance' };
  return null;
}

/* ——— Review panel (Confirm) ——— */

export function ReviewPanel({ job }: { job: JobView }) {
  const r = job.review;
  if (!r) return null;
  const a = r.availability;
  return (
    <section className="ap-sec ap-review" aria-labelledby="ap-review-h">
      <h2 id="ap-review-h" className="ap-sub">What will run</h2>
      <div className="ap-review__m">
        <b>{r.name}</b>
        <code>{r.methodology}</code>
        <span>{r.scored ? 'Computes the composite review score (a review-policy score, not a probability).' : 'No composite score is computed.'}</span>
      </div>
      <dl className="ap-review__kv">
        {r.targets.length > 0 && <div><dt>{r.targets.length === 1 ? 'Target' : 'Targets'}</dt><dd>{r.targets.join(', ')}</dd></div>}
        {a && <div><dt>Prediction point</dt><dd>{r.prediction_point ?? 'Not declared'}</dd></div>}
        {a && <div><dt>Availability</dt><dd>{fmt(a.available.length)} available · {fmt(a.unavailable.length)} not available · {fmt(a.unknown)} unknown</dd></div>}
        <div><dt>Code meanings</dt><dd>{r.codes_declared ? `${fmt(r.codes_declared)} declared` : 'None declared'}</dd></div>
      </dl>
      {a?.bulk.length ? <div className="ap-note"><b>Declared available in bulk:</b> {a.bulk.join(', ')}. {a.consequence}</div> : null}
      {r.unknowns.length > 0 && <><h3 className="ap-q ap-q--sub">Not established by this run</h3><ul className="ap-review__u">{r.unknowns.map((u) => <li key={u}>{u}</li>)}</ul></>}
    </section>
  );
}
