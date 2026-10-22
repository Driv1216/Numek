// M6 · Text reliability: presets, sources and assets, row builders for fields, annotations and assets, and a
// result mosaic anchored by the Candidates hero tile. Text is revealed only on explicit request, live only.
import { useState, type ReactNode } from 'react';
import { ApiError, csrfToken, type Fields, type SessionInfo } from './api';
import { AddSource, ConfirmFrame, FieldSections, Flow, FlowDownloads, LiveOut, MosaicPage, BoundedTable, ReportViewer, SHADES, SourceCard, defaults, familyTile, flowApi, scalarFacts, type Doc, type FlowJob, type FlowStep, type Section } from './flow';
import { Corners, READ_ONLY } from './parts';
import type { Tile } from './results/Tiles';
import { navigate, onLink } from './router';

type Flash = (e: unknown) => void;
export const textApi = flowApi('/text');
export const M6_PREFIX = '/app/text';
const PRESETS = ['corpus', 'classification', 'multilabel', 'token', 'span', 'qa', 'generation', 'conversation', 'retrieval'];
const PRESET_NOTE: Record<string, string> = {
  corpus: 'Integrity, identities, duplicates and vocabulary of a text corpus.', classification: 'Text with a label per record.', multilabel: 'Text with several labels per record.',
  token: 'Token-level tags.', span: 'Character or token spans.', qa: 'Question answering with answer spans.', generation: 'Prompts and completions.',
  conversation: 'Multi-turn conversations, roles and tool calls.', retrieval: 'Documents, chunks, queries and relevance judgments.',
};
const YN = ['no', 'yes'];

/* ——— Row lists, sent as the classic repeated keys ——— */
interface Col { key: string; label: string; kind?: 'text' | 'select' | 'field'; options?: string[]; def?: string }
type Lists = Record<string, string[]>;
function ListRows({ cols, prefix, lists, setLists, fields, label, add }: { cols: Col[]; prefix: string; lists: Lists; setLists: (f: (l: Lists) => Lists) => void; fields: string[]; label: string; add: string }) {
  const n = lists[prefix + cols[0].key]?.length ?? 0;
  const setCell = (i: number, key: string, v: string) => setLists((l) => ({ ...l, [prefix + key]: (l[prefix + key] ?? []).map((x, j) => (j === i ? v : x)) }));
  const remove = (i: number) => setLists((l) => Object.fromEntries(Object.entries(l).map(([k, v]) => [k, cols.some((c) => prefix + c.key === k) ? v.filter((_, j) => j !== i) : v])));
  const append = () => setLists((l) => ({ ...l, ...Object.fromEntries(cols.map((c) => [prefix + c.key, [...(l[prefix + c.key] ?? []), c.def ?? c.options?.[0] ?? '']])) }));
  const listId = `${prefix}${cols[0].key}-fields`;
  return (
    <div className="ap-rows" role="group" aria-label={label}>
      <datalist id={listId}>{fields.map((f) => <option key={f} value={f} />)}</datalist>
      {Array.from({ length: n }, (_, i) => (
        <div key={i} className="ap-rows__r">
          {cols.map((c) => {
            const v = lists[prefix + c.key]?.[i] ?? '';
            return <label key={c.key}>{c.label}{c.kind === 'select' ? <select value={v} onChange={(e) => setCell(i, c.key, e.target.value)}>{c.options!.map((o) => <option key={o} value={o}>{o || '—'}</option>)}</select>
              : <input value={v} list={c.kind === 'field' ? listId : undefined} onChange={(e) => setCell(i, c.key, e.target.value)} />}</label>;
          })}
          <button type="button" className="ap-link" onClick={() => remove(i)}>Remove</button>
        </div>
      ))}
      <button type="button" className="ap-link" onClick={append}>{add}</button>
    </div>
  );
}
const FIELD_COLS: Col[] = [{ key: 'field_name', label: 'Field name' }, { key: 'field_selector', label: 'Column or JSON Pointer', kind: 'field' },
  { key: 'field_kind', label: 'Content kind', kind: 'select', options: ['document', 'chunk', 'query', 'context', 'question', 'prompt', 'completion', 'caption', 'text'] },
  { key: 'field_required', label: 'Required', kind: 'select', options: YN }, { key: 'field_asset', label: 'Local .txt reference', kind: 'select', options: YN }, { key: 'field_checksum', label: 'Checksum selector', kind: 'field' }];
const ANNOTATION_COLS: Col[] = [{ key: 'annotation_field', label: 'Content field name' }, { key: 'annotation_selector', label: 'Annotation selector', kind: 'field' },
  { key: 'annotation_kind', label: 'Kind', kind: 'select', options: ['classification', 'multilabel', 'token', 'span', 'qa'] },
  { key: 'annotation_expectation', label: 'Expectation', kind: 'select', options: ['unknown', 'required', 'optional', 'not_applicable'] },
  { key: 'annotation_tokens', label: 'Supplied token selector', kind: 'field' }, { key: 'annotation_unit', label: 'Offsets', kind: 'select', options: ['codepoint', 'utf8', 'utf16', 'token'] },
  { key: 'annotation_scheme', label: 'Tag scheme', kind: 'select', options: ['none', 'BIO', 'BIOES', 'BILOU'] }, { key: 'annotation_overlap', label: 'Overlapping spans', kind: 'select', options: ['yes', 'no'] },
  { key: 'annotation_status', label: 'Status selector', kind: 'field' }, { key: 'annotation_required_statuses', label: 'Required statuses', def: 'complete' },
  { key: 'annotation_answerable', label: 'QA answerability selector', kind: 'field' }, { key: 'annotation_content_source', label: 'Content source ID' }, { key: 'annotation_content_id', label: 'Content ID selector', kind: 'field' }];
const ASSET_COLS: Col[] = [{ key: 'asset_selector', label: 'Asset path selector', kind: 'field' }, { key: 'asset_kind', label: 'Media', kind: 'select', options: ['image', 'text'] },
  { key: 'asset_encoding_row', label: 'Text encoding', def: 'utf-8' }, { key: 'asset_checksum', label: 'Checksum selector', kind: 'field' }];

const sourceSections = (preset: string): Section[] => [
  { title: 'Source', fields: [
    { name: 'task', label: 'Task', kind: 'select', options: PRESETS, def: preset }, { name: 'role', label: 'Source role', kind: 'select', options: ['corpus', 'train', 'validation', 'test', 'evaluation', 'version', 'documents', 'chunks', 'queries', 'judgments', 'annotations'] },
    { name: 'identity', label: 'Lexical identifier selector', kind: 'column' }, { name: 'namespace', label: 'Identity namespace' }, { name: 'split', label: 'Split selector', kind: 'column' },
    { name: 'task_inputs', label: 'Input field names', hint: 'comma-separated' }, { name: 'task_outputs', label: 'Output field names', hint: 'comma-separated' },
    { name: 'required_outputs', label: 'Require generation outputs', kind: 'select', options: YN }, { name: 'asset_encoding', label: 'Referenced text encoding', def: 'utf-8' }] },
  { title: 'Reading the source', collapsed: true, fields: [
    { name: 'encoding', label: 'Source encoding', def: 'utf-8' }, { name: 'delimiter', label: 'CSV delimiter', def: ',' }, { name: 'quotechar', label: 'CSV quote', def: '"' },
    { name: 'json_columns', label: 'JSON-valued CSV columns', hint: 'comma-separated' }] },
  { title: 'Conversation structure', collapsed: preset !== 'conversation', fields: [
    { name: 'conversation', label: 'Enable conversation checks', kind: 'select', options: YN, def: preset === 'conversation' ? 'yes' : 'no' }, { name: 'message_layout', label: 'Layout', kind: 'select', options: ['nested', 'flat'] },
    { name: 'messages', label: 'Message array selector', def: 'messages' }, { name: 'conversation_id', label: 'Conversation identity selector' }, { name: 'order', label: 'Flat message order selector' },
    { name: 'role_field', label: 'Role selector', def: 'role' }, { name: 'content', label: 'Message content selector', def: 'content' }, { name: 'roles', label: 'Allowed roles', def: 'system,developer,user,assistant,tool' },
    { name: 'calls', label: 'Tool-call array selector', def: 'tool_calls' }, { name: 'call_id', label: 'Tool response ID selector', def: 'tool_call_id' },
    { name: 'tool_closure', label: 'Require tool-call closure', kind: 'select', options: YN }, { name: 'completion', label: 'Require assistant completion', kind: 'select', options: YN }] },
  { title: 'Retrieval and chunk provenance', collapsed: preset !== 'retrieval', fields: [
    { name: 'retrieval', label: 'Entity type', kind: 'select', options: ['', 'document', 'chunk', 'query', 'judgment', 'reference'] }, { name: 'parent_source', label: 'Parent source ID' },
    { name: 'parent_id', label: 'Parent identity selector' }, { name: 'chunk_field', label: 'Chunk content field name' }, { name: 'parent_field', label: 'Parent content field name' },
    { name: 'extractive', label: 'Declare exact extractive chunks', kind: 'select', options: YN }, { name: 'start', label: 'Start selector', def: 'start' }, { name: 'end', label: 'End selector', def: 'end' },
    { name: 'retrieval_unit', label: 'Offset convention', kind: 'select', options: ['codepoint', 'utf8', 'utf16'] }, { name: 'query_source', label: 'Query source ID' },
    { name: 'query_id', label: 'Query reference selector', def: 'query_id' }, { name: 'target_source', label: 'Target source ID' }, { name: 'target_id', label: 'Target reference selector', def: 'document_id' },
    { name: 'grade', label: 'Relevance selector', def: 'relevance' }, { name: 'grade_type', label: 'Positive grade type', kind: 'select', options: ['number', 'string'] }, { name: 'positive_grades', label: 'Positive grades', def: '1' }] },
];
const GLOBAL: Section[] = [
  { title: 'Investigations', fields: [
    { name: 'near_duplicates', label: 'Near-duplicate search', kind: 'select', options: ['yes', 'no'] }, { name: 'passages', label: 'Passage search', kind: 'select', options: ['yes', 'no'] },
    { name: 'vocabulary', label: 'Vocabulary investigation', kind: 'select', options: ['yes', 'no'] }, { name: 'lexical_complete', label: 'Require complete lexical scope', kind: 'select', options: YN },
    { name: 'seed', label: 'Selection seed', def: '0' }, { name: 'near_threshold', label: 'Near-pair review threshold', def: '0.8' }, { name: 'minimum_passage', label: 'Minimum passage graphemes', def: '50' }] },
  { title: 'Optional offline models', collapsed: true, note: 'Model files must already exist locally. Reports distinguish model-assisted observations from deterministic evidence.', fields: [
    { name: 'language', label: 'Language identification', kind: 'select', options: YN }, { name: 'languages', label: 'Declared languages', def: 'ENGLISH,HINDI,SPANISH,FRENCH,GERMAN,CHINESE,ARABIC' },
    { name: 'embedding_directory', label: 'Pinned E5-small local directory' }, { name: 'tokenizer', label: 'Tokenizer vocabulary investigation', kind: 'select', options: YN },
    { name: 'embeddings', label: 'Enable embeddings when a directory is supplied', kind: 'select', options: ['yes', 'no'] }, { name: 'long_documents', label: 'Long-document handling', kind: 'select', options: ['token_windows_v1', 'exclude_long'] }] },
  { title: 'Optional declaration import', collapsed: true, fields: [
    { name: 'spec_json', label: 'Specification', kind: 'area', hint: 'JSON', wide: true, rows: 5 }, { name: 'config_json', label: 'Configuration', kind: 'area', hint: 'JSON', wide: true, rows: 4 }] },
];

function Sources({ job, info, setJob, flash }: { job: FlowJob | null; info: SessionInfo; setJob: (j: FlowJob | null) => void; flash: Flash }) {
  const [preset, setPreset] = useState('corpus');
  const [fmt, setFmt] = useState('jsonl');
  const add = (p: Promise<{ job: FlowJob }>) => p.then((r) => setJob(r.job)).catch(flash);
  const assets = (job?.assets as string[] | undefined) ?? [];
  return (
    <div className="ap-up">
      <header className="ap-head"><span className="nk-label">Step 1 · Sources</span><h1>Check text data.</h1><p>Corpus integrity, annotations, conversations and retrieval provenance. Bounded similarity candidates with exact local evidence. No universal score.</p></header>
      <section className="ap-sec" aria-labelledby="ap-preset-h">
        <h2 id="ap-preset-h" className="ap-q">What kind of text dataset?</h2>
        <div className="ap-modes ap-modes--compact" role="radiogroup" aria-label="Dataset task">
          {PRESETS.map((p) => { const on = (job?.preset ?? preset) === p; return (
            <button key={p} type="button" role="radio" aria-checked={on} className={`ap-mode ${on ? 'is-on' : ''}`} onClick={() => { setPreset(p); add(textApi.start({ preset: p })); }}>
              {on && <Corners />}<b>{p}</b><span>{PRESET_NOTE[p]}</span>
            </button>); })}
        </div>
        {job && job.sources.length > 0 && <p className="ap-muted ap-co__text">Choosing another task starts a new text audit.</p>}
      </section>
      {job && (
        <section className="ap-sec" aria-labelledby="ap-src-h">
          <h2 id="ap-src-h" className="ap-q">Sources · {job.sources.length}</h2>
          {job.sources.map((s) => <SourceCard key={s.id} s={s} role={`${s.id} · ${String(s.format ?? '').toUpperCase()}`} />)}
          <AddSource info={info} label="Drop a JSONL or CSV source" accept=".jsonl,.csv"
            extra={<label className="ap-fmt">Format<select value={fmt} onChange={(e) => setFmt(e.target.value)}><option value="jsonl">JSONL</option><option value="csv">CSV</option></select></label>}
            onUpload={(f) => add(textApi.upload(f, { format: fmt }))} onLocal={(root, rel) => add(textApi.local({ root_id: root, relative_path: rel, format: fmt }))} />
          <details className="ap-more ap-sec"><summary>Referenced text or image assets{assets.length ? ` · ${assets.length}` : ''}</summary>
            <p className="ap-muted">Asset filenames must match references relative to uploaded sources. Existing filenames are preserved.</p>
            {assets.length > 0 && <ul className="ap-more__list">{assets.map((a) => <li key={a}>{a}</li>)}</ul>}
            <label className="ap-fmt">Upload an asset<input type="file" accept=".txt,.png,.jpg,.jpeg" onChange={(e) => { const f = e.target.files?.[0]; if (f) add(textApi.upload(f, { asset_upload: 'yes' })); e.target.value = ''; }} /></label>
          </details>
          <div className="ap-acts">{job.sources.length ? <a className="nk-btn" href={`${M6_PREFIX}/configure`} onClick={onLink}>Map fields and semantics →</a> : <span className="nk-btn is-off" aria-disabled="true">Map fields →</span>}</div>
        </section>
      )}
    </div>
  );
}

function Configure({ job, setJob, flash }: { job: FlowJob; setJob: (j: FlowJob) => void; flash: Flash }) {
  const preset = String(job.preset ?? 'corpus');
  const exec = (job.execution_defaults as Record<string, number> | undefined) ?? {}, lim = (job.limit_defaults as Record<string, number> | undefined) ?? {};
  const budgets: Section[] = [{ title: 'Execution and investigation budgets', collapsed: true, fields: [
    ...Object.entries(exec).map(([k, v]) => ({ name: `execution_${k}`, label: k.replace(/_/g, ' '), def: String(v) })),
    ...Object.entries(lim).map(([k, v]) => ({ name: `limit_${k}`, label: k.replace(/_/g, ' '), def: String(v) }))] }];
  const [f, setF] = useState<Fields>(() => ({ ...defaults([...GLOBAL, ...budgets]), ...Object.assign({}, ...job.sources.map((s, i) => ({ ...defaults(sourceSections(preset), `s${i}_`), [`s${i}_encoding`]: String(s.encoding ?? 'utf-8'), [`s${i}_delimiter`]: String(s.delimiter ?? ','), [`s${i}_quotechar`]: String(s.quotechar ?? '"') }))) }));
  const [lists, setLists] = useState<Lists>(() => Object.assign({ compare_left: [], compare_right: [], representation: ['raw', 'nfc'] }, ...job.sources.map((s, i) => {
    const p = `s${i}_`, initial = s.headers.includes('text') ? 'text' : '';
    return { ...Object.fromEntries(FIELD_COLS.map((c) => [p + c.key, [c.key === 'field_name' || c.key === 'field_selector' ? initial : c.def ?? c.options?.[0] ?? '']])),
      ...Object.fromEntries([...ANNOTATION_COLS, ...ASSET_COLS].map((c) => [p + c.key, []])) };
  })));
  const [busy, setBusy] = useState(false);
  const set = (k: string, v: string) => setF((x) => ({ ...x, [k]: v }));
  const reps = lists.representation ?? [];
  const submit = () => {
    setBusy(true);
    textApi.post('configure', { ...f, ...lists } as unknown as Fields).then((r) => { setJob(r.job); navigate(`${M6_PREFIX}/confirm`); }).catch(flash).finally(() => setBusy(false));
  };
  return (
    <div className="ap-cf">
      <header className="ap-head"><span className="nk-label">Step 2 · Configure</span><h1>Fields, relationships and semantics.</h1><p>Nested mappings use JSON Pointers; nested CSV cells need a JSON-valued column declaration.</p></header>
      {job.sources.map((s, i) => (
        <section key={s.id} className="ap-sec ap-m4src" aria-label={`${s.id} declarations`}>
          <h2 className="ap-q">{s.id} · {String(s.format ?? '')}</h2>
          <p className="ap-muted">Fields: {s.headers.join(', ') || 'none detected in the first records'}.</p>
          <FieldSections sections={sourceSections(preset).slice(0, 1)} values={f} set={set} prefix={`s${i}_`} headers={s.headers} />
          <h3 className="ap-sub">Content fields</h3>
          <ListRows cols={FIELD_COLS} prefix={`s${i}_`} lists={lists} setLists={setLists} fields={s.headers} label={`Content fields for ${s.id}`} add="Add content field" />
          <details className="ap-more ap-sec"><summary>Tokens, spans, labels and QA annotations</summary><ListRows cols={ANNOTATION_COLS} prefix={`s${i}_`} lists={lists} setLists={setLists} fields={s.headers} label={`Annotations for ${s.id}`} add="Add annotation binding" /></details>
          <details className="ap-more ap-sec"><summary>Additional text–image or content assets</summary><ListRows cols={ASSET_COLS} prefix={`s${i}_`} lists={lists} setLists={setLists} fields={s.headers} label={`Assets for ${s.id}`} add="Add asset binding" /></details>
          <FieldSections sections={sourceSections(preset).slice(1)} values={f} set={set} prefix={`s${i}_`} headers={s.headers} />
        </section>
      ))}
      {job.sources.length > 1 && (
        <section className="ap-sec"><h3 className="ap-sub">Evaluation and version comparisons</h3>
          <ListRows cols={[{ key: 'compare_left', label: 'Left source ID', kind: 'select', options: ['', ...job.sources.map((s) => s.id)] }, { key: 'compare_right', label: 'Right source ID', kind: 'select', options: ['', ...job.sources.map((s) => s.id)] }]}
            prefix="" lists={lists} setLists={setLists} fields={[]} label="Comparisons" add="Add comparison" /></section>
      )}
      <section className="ap-sec"><h3 className="ap-sub">Representations</h3>
        <div className="ap-chips" role="group" aria-label="Representations">{['raw', 'nfc', 'casefold', 'whitespace'].map((r) => <button key={r} type="button" aria-pressed={reps.includes(r)} className={reps.includes(r) ? 'is-on' : ''} onClick={() => setLists((l) => ({ ...l, representation: reps.includes(r) ? reps.filter((x) => x !== r) : [...reps, r] }))}>{r}</button>)}</div>
      </section>
      <FieldSections sections={[...GLOBAL, ...budgets]} values={f} set={set} />
      <p className="ap-muted">Exports contain aggregates and opaque references by default. Local evidence reveal and bounded excerpt export are explicit actions after completion.</p>
      <div className="ap-acts">
        <button type="button" className={`nk-btn ${busy ? 'is-run' : ''}`} disabled={busy} onClick={submit}>{busy ? 'Sealing sources, assets and models…' : 'Confirm interpretation →'}</button>
        <a className="nk-btn nk-btn--ghost" href={`${M6_PREFIX}/sources`} onClick={onLink}>Back to sources</a>
      </div>
    </div>
  );
}

/* ——— Result ——— */

type TF = { id: string; family: string; meaning: string; count: number; references: string[]; action: string };
type TE = { id: string; family: string; meaning: string; data: Doc; references: string[]; scope: string };
const CANDIDATES = ['exact_duplicates', 'near_duplicates', 'passages', 'repetition'];
const label = (s: string) => s.replace(/_/g, ' ');
const short = (r: string) => `…${r.slice(-6)}`;

function CandidateBars({ a, big }: { a: Doc; big?: boolean }) {
  const fs = (a.findings as TF[]) ?? [], ev = (a.evidence as TE[]) ?? [];
  const rows = CANDIDATES.map((fam) => ({ fam, n: fs.filter((f) => f.family === fam).reduce((s, f) => s + (f.count ?? 0), 0), ghost: Number((ev.find((e) => e.family === fam)?.data as Doc | undefined)?.subthreshold_candidates ?? 0) }))
    .filter((r) => r.n || r.ghost || ev.some((e) => e.family === r.fam));
  if (!rows.length) return null;
  const max = Math.max(1, ...rows.map((r) => Math.max(r.n, r.ghost)));
  return (
    <svg viewBox={`0 0 300 ${rows.length * 30 + 6}`} className="md-viz" preserveAspectRatio="xMidYMid meet">
      {rows.map((r, i) => (
        <g key={r.fam} transform={`translate(0 ${i * 30 + 4})`} className="md-grow" style={{ ['--i' as string]: i }}>
          {r.ghost > 0 && <rect x={0} y={10} width={Math.max(2, (r.ghost / max) * 290)} height={12} rx={2} className="md-ghost" />}
          <rect x={0} y={10} width={Math.max(r.n ? 3 : 0, (r.n / max) * 290)} height={12} rx={2} className={r.n ? 'md-hot' : 'md-ghost'} />
          <text x={0} y={7} className="md-t md-t--s">{label(r.fam)} · {r.n.toLocaleString('en-US')}{big && r.ghost ? ` (${r.ghost.toLocaleString('en-US')} below threshold)` : ''}</text>
        </g>
      ))}
    </svg>
  );
}

function Reveal({ refs, flash }: { refs: string[]; flash: Flash }) {
  const [shown, setShown] = useState<Record<string, Doc | string>>({});
  const [pick, setPick] = useState<string[]>([]);
  const reveal = (ref: string, yes: boolean) => textApi.post('evidence', { reference: ref, reveal: yes ? 'yes' : 'no' })
    .then((r) => setShown((m) => ({ ...m, [ref]: (r.resolved as Doc) ?? {} })))
    .catch((e) => setShown((m) => ({ ...m, [ref]: e instanceof ApiError ? e.message : 'Unavailable.' })));
  return (
    <div className="ap-reveal">
      {refs.slice(0, 12).map((ref) => {
        const v = shown[ref];
        return (
          <div key={ref} className="ap-reveal__r">
            <label className="ap-check"><input type="checkbox" checked={pick.includes(ref)} onChange={(e) => setPick((p) => (e.target.checked ? [...p, ref] : p.filter((x) => x !== ref)))} /> <code>{short(ref)}</code></label>
            <button type="button" className="ap-link" onClick={() => reveal(ref, false)}>Locate</button>
            <button type="button" className="ap-link" onClick={() => reveal(ref, true)}>Reveal text</button>
            {typeof v === 'string' ? <p className="ap-reveal__err">{v}</p> : v && (
              <div className="ap-reveal__v">{typeof v.excerpt === 'string' && <blockquote>{v.excerpt}</blockquote>}<dl>{scalarFacts(v, 6).filter(([k]) => k !== 'excerpt').map(([k, x]) => <div key={k}><dt>{k}</dt><dd>{x}</dd></div>)}</dl></div>
            )}
          </div>
        );
      })}
      {refs.length > 12 && <p className="nk-ch__not">{refs.length - 12} more references in the canonical JSON.</p>}
      <ExportExcerpts refs={pick} flash={flash} />
      <p className="nk-ch__not">Revealed text is shown only here, on this machine. It is never saved to history or added to exports.</p>
    </div>
  );
}

function ExportExcerpts({ refs, flash }: { refs: string[]; flash: Flash }) {
  const [busy, setBusy] = useState(false);
  const go = async () => {
    setBusy(true);
    try {
      const res = await fetch('/api/datatrust/v1/text/export-excerpts', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken() }, body: JSON.stringify({ references: refs.join(',') }) });
      if (!res.ok) { const j = await res.json().catch(() => null); throw new ApiError(j?.error?.message ?? 'The excerpts could not be exported.', res.status); }
      const url = URL.createObjectURL(await res.blob());
      const a = Object.assign(document.createElement('a'), { href: url, download: 'text-excerpts.html' }); document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) { flash(e); } finally { setBusy(false); }
  };
  return <button type="button" className="ap-sheet__dl" disabled={!refs.length || busy} onClick={go}>{busy ? 'Exporting…' : `Export excerpts${refs.length ? ` (${refs.length})` : ''} ↓`}</button>;
}

export function textTiles(a: Doc, live: boolean, flash: Flash): Tile[] {
  const fs = (a.findings as TF[]) ?? [], ev = (a.evidence as TE[]) ?? [];
  const cand = fs.filter((f) => CANDIDATES.includes(f.family));
  const near = ev.find((e) => e.family === 'near_duplicates')?.data as Doc | undefined;
  const provenance = near ? `near duplicates: ${Number(near.qualifying_pairs ?? 0).toLocaleString('en-US')} qualifying, ${Number(near.subthreshold_candidates ?? 0).toLocaleString('en-US')} below ${near.threshold ?? '—'}${near.not_transitive ? ', not transitive' : ''}` : 'Near-duplicate search was not part of this audit.';
  const hero: Tile = {
    id: 'candidates', hero: true, name: 'Candidates', n: '01', kicker: 'review items', bg: '#163F52', light: true,
    tone: cand.length ? 'finding' : 'info', label: `${cand.length} candidate finding${cand.length === 1 ? '' : 's'}`, detail: provenance,
    viz: <CandidateBars a={a} />, bigViz: <CandidateBars a={a} big />,
    chapter: (
      <>
        <h3>Candidates</h3>
        <div className="nk-ch__run"><span>Bounded, calibrated searches</span><b>{cand.length} candidate finding{cand.length === 1 ? '' : 's'}</b><p>{provenance}. Candidates are review items, not verdicts.</p></div>
        {cand.map((f) => (
          <div key={f.id} className="nk-ch__f">
            <b>{label(f.family)} <em>{label(f.meaning)}</em></b>
            <p>{f.count.toLocaleString('en-US')} · {f.action}</p>
            {f.references.length > 0 && (live ? <Reveal refs={f.references} flash={flash} /> : <p className="nk-ch__lim">References {f.references.slice(0, 6).map(short).join(' · ')}{f.references.length > 6 ? ` · ${f.references.length - 6} more` : ''}. {READ_ONLY}</p>)}
          </div>
        ))}
      </>
    ),
  };
  const families = [...new Set(ev.map((e) => e.family))];
  const tiles = families.map((fam, i) => {
    const recs = ev.filter((e) => e.family === fam), ffs = fs.filter((f) => f.family === fam), data = recs[0]?.data ?? {};
    const facts = scalarFacts(data, 6);
    return familyTile({ id: fam, name: label(fam), n: i + 2, kicker: recs[0]?.scope?.replace(/_/g, ' ') ?? '', shade: SHADES[i % SHADES.length], tone: ffs.length ? 'finding' : 'info',
      label: ffs.length ? `${ffs.reduce((s, f) => s + (f.count ?? 0), 0).toLocaleString('en-US')} · ${label(ffs[0].meaning)}` : facts[0] ? `${facts[0][1]} ${facts[0][0]}` : 'Measured',
      detail: ffs[0]?.action ?? label(recs[0]?.meaning ?? ''),
      body: <><h3>{label(fam)}</h3><div className="nk-ch__run"><span>{label(recs[0]?.meaning ?? '')} · {recs[0]?.scope}</span><b>{ffs.length ? `${ffs.length} finding${ffs.length === 1 ? '' : 's'}` : 'No finding'}</b><p>{ffs[0]?.action ?? 'Evidence for review within its examined scope.'}</p></div>
        {!!facts.length && <dl>{facts.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>}<BoundedTable data={data} /></> });
  });
  return [hero, ...tiles];
}

export function TextPage({ a, out, live, flash, onOpen }: { a: Doc; out: ReactNode; live: boolean; flash: Flash; onOpen: () => void }) {
  const fs = (a.findings as TF[]) ?? [], profile = (a.profile as Doc) ?? {};
  return (
    <MosaicPage checks={a.checks} guidance={a.guidance} name={String(profile.dataset_name ?? 'Text audit')} sub={`${Number(profile.source_count ?? 0)} source${profile.source_count === 1 ? '' : 's'} · Text`} when={String(a.generated_at)} findings={fs.length}
      status="No score: text runs report evidence and review candidates." partial={(a.execution as Doc)?.status === 'partial'} label="Text checks"
      tiles={textTiles(a, live, flash)} actions={fs.map((f) => ({ id: f.id, title: label(f.family), priority: f.meaning === 'heuristic_candidate' ? 'Moderate' : 'Low', text: f.action, scope: `${f.count.toLocaleString('en-US')} · ${label(f.meaning)}` }))}
      summary={String(profile.summary ?? '')} out={out} onOpen={onOpen} coverage={<p className="ap-muted">{String(profile.summary ?? '')}</p>} />
  );
}

export function M6Flow({ path, info, flash, saving, onRail, onSaved }: { path: string; info: SessionInfo; flash: Flash; saving: boolean; onRail: (s: FlowStep, ok: FlowStep[]) => void; onSaved: () => void }) {
  const [view, setView] = useState(false);
  const dl = <FlowDownloads route="/api/datatrust/v1/text/download" kinds={['pdf', 'html', 'json', 'private']} flash={flash} />;
  return (
    <Flow path={path} prefix={M6_PREFIX} api={textApi} info={info} flash={flash} onRail={onRail} onSaved={onSaved} label="Text audit"
      render={({ step, job, setJob, analysis, onNew }) => (
        <>
          {step === 'sources' && <Sources job={job} info={info} setJob={setJob} flash={flash} />}
          {job && step === 'configure' && <Configure key={job.sources.map((s) => s.id).join()} job={job} setJob={setJob} flash={flash} />}
          {job && step === 'confirm' && <ConfirmFrame job={job} api={textApi} flash={flash} saving={saving} prefix={M6_PREFIX} onRun={setJob}
            task={<><b>Text audit · {String(job.preset)} · {job.sources.length} source{job.sources.length === 1 ? '' : 's'}</b><span>Confirmation seals sources, referenced assets and any model files. The worker re-checks them before publishing.</span></>} />}
          {job && step === 'report' && analysis && (
            <>
              <TextPage a={analysis} live flash={flash} onOpen={() => setView(true)} out={<LiveOut saved={!!job.saved_entry} onView={() => setView(true)} onNew={onNew} newLabel="New text audit" downloads={dl} />} />
              {view && <ReportViewer name="Text audit" src={textApi.report} downloads={dl} onClose={() => setView(false)} />}
            </>
          )}
        </>
      )} />
  );
}
