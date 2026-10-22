// The optional Context section of Configure (context_v1): the prediction objective and point, meanings for
// suggested codes, availability, and advanced conditions and units. Suggestions are never applied until you choose
// a meaning. Declarations change no parsed value, finding or score; they add a separate interpreted view.
import { useEffect, useState } from 'react';
import { api, type ColumnDecl, type ContextDecl, type ContextInfo, type JobView } from './api';

const label = (v: string) => v.replace(/_/g, ' ');
export const emptyContext = (): ContextDecl => ({ prediction: { objective: null, point: null }, columns: {} });

/** The context to submit, or '' when nothing is declared (an empty declaration clears the context). */
export function contextField(c: ContextDecl): string {
  const columns = Object.fromEntries(Object.entries(c.columns).map(([k, v]) => [k, Object.fromEntries(Object.entries(v).filter(([, x]) => x != null && !(typeof x === 'object' && !Array.isArray(x) && !Object.keys(x).length) && !(Array.isArray(x) && !x.length)))]).filter(([, v]) => Object.keys(v as object).length));
  const declared = c.prediction.objective || c.prediction.point || Object.keys(columns).length;
  return declared ? JSON.stringify({ prediction: c.prediction, columns, ...(c.limits ? { limits: c.limits } : {}) }) : '';
}

export function ContextPanel({ job, value, onChange, availability = true }: { job: JobView; value: ContextDecl; onChange: (c: ContextDecl) => void; availability?: boolean }) {
  const [info, setInfo] = useState<ContextInfo | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [advanced, setAdvanced] = useState(() => JSON.stringify(Object.fromEntries(Object.entries(value.columns).filter(([, d]) => d.applies_when || d.unit).map(([k, d]) => [k, { ...(d.applies_when ? { applies_when: d.applies_when } : {}), ...(d.unit ? { unit: d.unit } : {}) }])), null, 1));
  const [advancedError, setAdvancedError] = useState<string | null>(null);
  useEffect(() => { let live = true; api.context().then((x) => live && setInfo(x)).catch((x) => live && setFailed(String(x?.message ?? x))); return () => { live = false; }; }, [job.source_filename, job.config.parsing.delimiter]);
  const column = (name: string, change: (d: ColumnDecl) => ColumnDecl) => onChange({ ...value, columns: { ...value.columns, [name]: change({ ...(value.columns[name] ?? {}) }) } });
  const meaningOf = (c: ContextInfo['candidates'][number]) => {
    const d = value.columns[c.column];
    return c.kind === 'numeric_sentinel' ? d?.sentinels?.find((s) => s.value === c.value)?.meaning ?? '' : d?.placeholders?.[String(c.value)] ?? '';
  };
  const setMeaning = (c: ContextInfo['candidates'][number], meaning: string) => column(c.column, (d) => {
    if (c.kind === 'numeric_sentinel') {
      const rest = (d.sentinels ?? []).filter((s) => s.value !== c.value);
      return { ...d, sentinels: meaning ? [...rest, { value: Number(c.value), meaning }] : rest };
    }
    const placeholders = { ...(d.placeholders ?? {}) };
    if (meaning) placeholders[String(c.value)] = meaning; else delete placeholders[String(c.value)];
    return { ...d, placeholders };
  });
  const applyAdvanced = (text: string) => {
    setAdvanced(text);
    try {
      const parsed = text.trim() ? JSON.parse(text) as Record<string, { applies_when?: ColumnDecl['applies_when']; unit?: string }> : {};
      if (typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('Use an object of column names.');
      const columns: Record<string, ColumnDecl> = Object.fromEntries(Object.entries(value.columns).map(([k, d]) => [k, { ...d, applies_when: undefined, unit: undefined } as ColumnDecl]));
      for (const [k, d] of Object.entries(parsed)) columns[k] = { ...(columns[k] ?? {}), ...(d.applies_when ? { applies_when: d.applies_when } : {}), ...(d.unit ? { unit: d.unit } : {}) };
      setAdvancedError(null); onChange({ ...value, columns });
    } catch (x) { setAdvancedError(x instanceof Error ? x.message : 'Not valid JSON.'); }
  };
  const target = job.target;
  const suggested = info?.candidates.length ?? 0;
  const declared = Object.values(value.columns).filter((d) => Object.values(d).some((x) => x != null && (typeof x !== 'object' || Object.keys(x).length))).length;
  return (
    <details className="ap-more ap-sec" open={declared > 0 || undefined}>
      <summary>Context (optional){suggested ? ` · ${suggested} suggested code${suggested === 1 ? '' : 's'}` : ''}{declared ? ` · ${declared} column${declared === 1 ? '' : 's'} declared` : ''}</summary>
      <p className="ap-muted">What you know about the data and its use. Declarations never change parsed values, findings or the score: they add a separate interpreted view, and a bounded search checks whether any feature determines the target.</p>
      <div className="ap-fields ap-fields--two">
        <label>Prediction objective <span>optional</span><input maxLength={500} value={value.prediction.objective ?? ''} onChange={(x) => onChange({ ...value, prediction: { ...value.prediction, objective: x.target.value || null } })} placeholder="For example: decide which clients to call" /></label>
        <label>Prediction point <span>when the prediction is made</span><input maxLength={500} value={value.prediction.point ?? ''} onChange={(x) => onChange({ ...value, prediction: { ...value.prediction, point: x.target.value || null } })} placeholder="For example: before the first contact" /></label>
      </div>
      <h3 className="ap-q ap-q--sub">Suggested codes</h3>
      {failed ? <p className="ap-note ap-note--warn">Suggestions are unavailable: {failed}</p>
        : !info ? <p className="ap-muted">Reading the file for suggestions…</p>
        : !info.candidates.length ? <p className="ap-muted">No value matched the suggestion rules ({info.rules}). You can still declare codes under Advanced.</p>
        : (
          <>
            <p className="ap-muted">Values that often stand for absent or special cases ({info.rules}). Nothing is applied until you choose a meaning.</p>
            <div className="ap-avail">
              {info.candidates.map((c) => (
                <label key={`${c.column}=${c.value}`}><span>{c.column} = <b>{String(c.value)}</b> · {c.rows.toLocaleString('en-US')} rows ({c.rate}%)</span>
                  <select value={meaningOf(c)} onChange={(x) => setMeaning(c, x.target.value)}><option value="">not applied</option>{info.meanings.map((m) => <option key={m} value={m}>{m === 'category' ? 'a real category' : label(m)}</option>)}</select>
                </label>
              ))}
            </div>
          </>
        )}
      {availability && info && (
        <>
          <h3 className="ap-q ap-q--sub">Availability at the prediction point</h3>
          <div className="ap-avail">{info.columns.filter((c) => c !== target).map((c) => (
            <label key={c}><span>{c}</span><select value={value.columns[c]?.availability ?? 'unknown'} onChange={(x) => column(c, (d) => ({ ...d, availability: x.target.value === 'unknown' ? undefined : x.target.value }))}>
              {info.availability.map((v) => <option key={v} value={v}>{label(v)}</option>)}</select></label>
          ))}</div>
        </>
      )}
      <label className="ap-fields__wide">Advanced: conditions and units <span>JSON, for example {'{"pdays": {"applies_when": {"column": "previous", "op": ">", "value": 0}, "unit": "days"}}'}</span>
        <textarea rows={3} value={advanced} onChange={(x) => applyAdvanced(x.target.value)} aria-invalid={!!advancedError} /></label>
      {advancedError && <p className="ap-note ap-note--warn" role="alert">{advancedError}</p>}
    </details>
  );
}
