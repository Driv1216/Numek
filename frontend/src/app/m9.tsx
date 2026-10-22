// M9 · Records ↔ documents: one guided builder over the classic configure actions, a bounded preview,
// a sealed confirmation, and a result mosaic anchored by the Reconciliation hero tile. Evidence excerpts,
// images and review decisions appear only in the live chapter of this session.
import { useEffect, useState, type ReactNode } from 'react';
import { ApiError, csrfToken, type Fields, type SessionInfo } from './api';
import { BoundedTable, ConfirmFrame, FieldSections, Flow, FlowDownloads, LiveOut, MosaicPage, ReportViewer, Running, SHADES, defaults, familyTile, flowApi, scalarFacts, useAfterRun, type Doc, type FlowJob, type FlowStep, type Section } from './flow';
import { READ_ONLY, SeparatorSelect } from './parts';
import type { Tile } from './results/Tiles';
import { navigate, onLink } from './router';

type Flash = (e: unknown) => void;
export const crossApi = flowApi('/cross');
export const M9_PREFIX = '/app/cross';
const RUN = ['running', 'completed', 'failed', 'cancelled'];
const lab = (s: string) => s.replace(/_/g, ' ');
const short = (r: string) => `…${r.slice(-6)}`;

function reach(j: FlowJob | null): FlowStep[] {
  if (!j) return ['sources'];
  const out: FlowStep[] = ['sources'], phase = j.phase as string | undefined, ran = phase === 'run' && RUN.includes(j.state);
  if (j.sources.length || j.state !== 'configure') out.push('configure');
  if (j.state === 'confirm' || ran) out.push('confirm');
  if (ran) out.push('report');
  return out;
}

async function download(path: string, body: Fields, fallback: string) {
  const res = await fetch(`/api/datatrust/v1${path}`, { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken() }, body: JSON.stringify(body) });
  if (!res.ok) throw new ApiError((await res.json().catch(() => null))?.error?.message ?? 'The export could not be prepared.', res.status);
  const url = URL.createObjectURL(await res.blob());
  const a = Object.assign(document.createElement('a'), { href: url, download: /filename="?([^";]+)"?/.exec(res.headers.get('Content-Disposition') ?? '')?.[1] ?? fallback });
  document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/* ——— Sources ——— */

const SOURCE: Section[] = [
  { title: 'Selectors and layout', collapsed: true, note: 'How DataTrust reads identities, text, asset paths and layout families from this source.', fields: [
    { name: 'id_selector', label: 'Logical ID selector', def: 'id' }, { name: 'text_selector', label: 'Text selector', def: 'text' },
    { name: 'path_selector', label: 'Asset path selector', def: 'path' }, { name: 'role', label: 'Source role', def: 'dataset' },
    { name: 'layout', label: 'Layout family' }, { name: 'layout_selector', label: 'Layout selector' },
    { name: 'split_selector', label: 'Split selector' }, { name: 'json_columns', label: 'JSON-valued CSV columns', hint: 'comma-separated' }] },
];

function Sources({ job, info, setJob, flash }: { job: FlowJob | null; info: SessionInfo; setJob: (j: FlowJob | null) => void; flash: Flash }) {
  const [f, setF] = useState<Fields>(() => ({ source_id: `source${(job?.sources.length ?? 0) + 1}`, kind: 'structured', format: 'csv', delimiter: ',', ...defaults(SOURCE) }));
  const [root, setRoot] = useState(info.roots[0]?.id ?? '');
  const [rel, setRel] = useState('');
  const [assets, setAssets] = useState('');
  const [spec, setSpec] = useState('');
  const [config, setConfig] = useState('{}');
  const [busy, setBusy] = useState(false);
  const set = (k: string, v: string) => setF((x) => ({ ...x, [k]: v }));
  const ensure = async () => job ?? (await crossApi.start()).job;
  const act = (run: () => Promise<{ job: FlowJob | null }>) => { setBusy(true); return run().then((r) => { setJob(r.job); return r.job; }).catch((e) => { flash(e); return null; }).finally(() => setBusy(false)); };
  const added = (j: FlowJob | null) => { if (j) setF((x) => ({ ...x, source_id: `source${j.sources.length + 1}` })); };
  const upload = (file: File) => act(async () => { await ensure(); const d = new FormData(); for (const [k, v] of Object.entries({ ...f, action: 'source' })) d.set(k, v); d.set('source', file); return crossApi.post('action', d); }).then(added);
  const local = () => act(async () => { await ensure(); return crossApi.post('action', { ...f, action: 'source', root_id: root, relative_path: rel.trim(), asset_relative: assets.trim() }); }).then((j) => { added(j); if (j) setRel(''); });
  const remove = (id: string) => act(() => crossApi.post('action', { action: 'remove', collection: 'inputs', identity: id }));
  const imported = () => act(async () => { await ensure(); return crossApi.post('action', { action: 'import', spec_json: spec, config_json: config || '{}' }); }).then((j) => j && navigate(`${M9_PREFIX}/configure`));
  return (
    <div className="ap-up">
      <header className="ap-head"><span className="nk-label">Step 1 · Sources</span><h1>Reconcile records with documents.</h1><p>Structured records checked against supplied PDF and DOCX documents, text and images, read where they are. Mappings are reused across records. No universal score.</p></header>
      {!!job?.sources.length && (
        <section className="ap-sec" aria-labelledby="ap-src-h">
          <h2 id="ap-src-h" className="ap-q">Sources · {job.sources.length}</h2>
          {job.sources.map((s) => <div key={s.id} className="ap-src"><div className="ap-src__h"><span className="ap-strip__role">{String(s.kind ?? '')}</span><b>{s.filename}</b><span>{s.id} · {String(s.format ?? '')} · {s.origin === 'upload' ? 'uploaded' : 'in a data root'}</span><button type="button" className="ap-link" disabled={busy} onClick={() => remove(s.id)}>Remove</button></div></div>)}
        </section>
      )}
      <section className="ap-sec" aria-labelledby="ap-add-h">
        <h2 id="ap-add-h" className="ap-q">Add a source or document manifest</h2>
        <div className="ap-fields ap-fields--two ap-fields--flow">
          <label>Source ID<input value={f.source_id} onChange={(e) => set('source_id', e.target.value)} /></label>
          <label>Kind<select value={f.kind} onChange={(e) => set('kind', e.target.value)}>{['structured', 'document', 'text', 'image'].map((o) => <option key={o}>{o}</option>)}</select></label>
          <label>Format<select value={f.format} onChange={(e) => set('format', e.target.value)}>{['csv', 'jsonl', 'parquet', 'pdf', 'docx', 'txt'].map((o) => <option key={o}>{o}</option>)}</select></label>
          {f.format === 'csv' && <SeparatorSelect value={f.delimiter} auto={false} onChange={(v) => set('delimiter', v)} label="CSV separator" />}
        </div>
        <FieldSections sections={SOURCE} values={f} set={set} />
        {info.roots.length > 0 && (
          <div className="ap-root">
            <b>A file in a data root</b>
            <div className="ap-fields ap-fields--two">
              <label>Data root<select value={root} onChange={(e) => setRoot(e.target.value)}>{info.roots.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}</select></label>
              <label>Path inside it<input value={rel} onChange={(e) => setRel(e.target.value)} placeholder="records.csv" /></label>
              <label>Asset root <span>for documents or images a manifest names; inside the same root</span><input value={assets} onChange={(e) => setAssets(e.target.value)} placeholder="." /></label>
            </div>
            <button type="button" className="nk-btn nk-btn--ghost" disabled={busy || !rel.trim() || !f.source_id.trim()} onClick={local}>Add this source</button>
            <p className="ap-muted">Only files inside the roots DataTrust was started with; links that lead outside are refused.</p>
          </div>
        )}
        <label className="ap-fmt">Or upload a source<input type="file" disabled={busy} onChange={(e) => { const file = e.target.files?.[0]; if (file) upload(file); e.target.value = ''; }} /></label>
        <p className="ap-muted">Up to {info.upload_limit_mib} MiB per upload. A document manifest that names relative files needs those files in a data root.</p>
      </section>
      <details className="ap-more ap-sec">
        <summary>Import complete declarations and work settings</summary>
        <div className="ap-fields ap-fields--flow">
          <label className="ap-fields__wide">Specification <span>JSON</span><textarea rows={8} value={spec} onChange={(e) => setSpec(e.target.value)} /></label>
          <label className="ap-fields__wide">Configuration <span>JSON</span><textarea rows={3} value={config} onChange={(e) => setConfig(e.target.value)} /></label>
        </div>
        <div className="ap-acts"><button type="button" className="nk-btn nk-btn--ghost" disabled={busy || !spec.trim()} onClick={imported}>Import declarations</button>{job && <a className="ap-link" href="/api/datatrust/v1/cross/spec">Export the current specification ↓</a>}</div>
      </details>
      <Reopen setJob={setJob} flash={flash} />
      <div className="ap-acts">
        {job?.sources.length ? <a className="nk-btn" href={`${M9_PREFIX}/configure`} onClick={onLink}>Mappings and rules →</a> : <span className="nk-btn is-off" aria-disabled="true">Mappings and rules →</span>}
      </div>
    </div>
  );
}

/** Reopen completed evidence: the original result JSON and its private manifest, both supplied by the user. */
function Reopen({ setJob, flash, report, title = 'Reopen completed evidence' }: { setJob?: (j: FlowJob | null) => void; flash: Flash; report?: () => Promise<Blob>; title?: string }) {
  const [res, setRes] = useState<File | null>(null);
  const [priv, setPriv] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const go = async () => {
    setBusy(true);
    try {
      const d = new FormData();
      d.set('report', report ? await report() : (res as File), 'analysis.json'); d.set('private', priv as File);
      const r = await crossApi.post('load-result', d);
      setJob?.(r.job); navigate(`${M9_PREFIX}/report`);
    } catch (e) { flash(e); } finally { setBusy(false); }
  };
  return (
    <details className="ap-more ap-sec" open={!!report}>
      <summary>{title}</summary>
      <p className="ap-muted">Live investigation returns only with the matching private manifest you downloaded with this result. DataTrust does not keep it.</p>
      <div className="ap-fields ap-fields--two">
        {!report && <label>Original result JSON<input type="file" accept=".json,application/json" onChange={(e) => setRes(e.target.files?.[0] ?? null)} /></label>}
        <label>Matching private manifest<input type="file" accept=".json,application/json" onChange={(e) => setPriv(e.target.files?.[0] ?? null)} /></label>
      </div>
      <button type="button" className="nk-btn nk-btn--ghost" disabled={busy || !priv || (!report && !res)} onClick={go}>{busy ? 'Verifying…' : 'Load exact completed evidence'}</button>
    </details>
  );
}

/* ——— Configure: the classic guided actions ——— */

const CONTEXT = ['entity', 'period', 'version', 'currency', 'unit'];
function relationship(ids: string[]): Section[] {
  return [
    { title: 'Association', fields: [
      { name: 'relationship_id', label: 'Relationship ID' }, { name: 'left_source', label: 'Structured / left source', kind: 'select', options: ids }, { name: 'right_source', label: 'Evidence / right source', kind: 'select', options: ids.slice(1).concat(ids.slice(0, 1)) },
      { name: 'left_keys', label: 'Left keys', def: 'id' }, { name: 'right_keys', label: 'Right keys', def: 'id' }, { name: 'namespace', label: 'Namespace', def: 'declared' },
      { name: 'key_representation', label: 'Key representation', kind: 'select', options: ['typed', 'lexical', 'nfc', 'numeric'] },
      { name: 'meaning', label: 'Meaning', kind: 'select', options: ['supporting_evidence', 'identity', 'caption', 'version', 'derivation'] },
      { name: 'cardinality', label: 'Cardinality', kind: 'select', options: ['one_to_many', 'one_to_one', 'many_to_one', 'many_to_many'] },
      { name: 'required', label: 'Requiredness', kind: 'select', options: ['required', 'optional', 'unknown'] }] },
    { title: 'Context, clocks and association table', collapsed: true, fields: [
      ...CONTEXT.flatMap((k) => [{ name: `left_${k}`, label: `Left ${k} selector` }, { name: `right_${k}`, label: `Right ${k} selector` }]),
      { name: 'cutoff', label: 'Cutoff clock' }, { name: 'availability', label: 'Evidence availability clock' }, { name: 'timezone', label: 'Timezone for local clocks' },
      { name: 'version_mode', label: 'Version selection', kind: 'select', options: ['all', 'exact', 'latest_as_of'] },
      { name: 'association_source', label: 'Association source ID' }, { name: 'association_left', label: 'Association left selector', def: 'left_id' }, { name: 'association_right', label: 'Association right selector', def: 'right_id' }] },
  ];
}
const MAPPING: Section[] = [
  { title: 'Recipe', note: 'One recipe, reused across every record of a layout family.', fields: [
    { name: 'mapping_id', label: 'Mapping ID' }, { name: 'mapping_layout', label: 'Layout family', def: 'default' }, { name: 'mapping_kind', label: 'Recipe', kind: 'select', options: ['table_field', 'label_value', 'text'] },
    { name: 'row_headers', label: 'Row header aliases', hint: 'comma-separated', when: (v) => v.mapping_kind === 'table_field' }, { name: 'value_headers', label: 'Value header aliases', hint: 'comma-separated', when: (v) => v.mapping_kind === 'table_field' },
    { name: 'row_label', label: 'Row label', when: (v) => v.mapping_kind === 'table_field' }, { name: 'row_selector', label: 'Or row selector', when: (v) => v.mapping_kind === 'table_field' },
    { name: 'period_headers', label: 'Period header aliases', when: (v) => v.mapping_kind === 'table_field' }, { name: 'period_selector', label: 'Period selector', def: 'period', when: (v) => v.mapping_kind === 'table_field' },
    { name: 'labels', label: 'Label aliases', hint: 'comma-separated', when: (v) => v.mapping_kind !== 'table_field' }] },
  { title: 'Section, pages, strategy and units', collapsed: true, fields: [
    { name: 'section', label: 'Section anchor' }, { name: 'pages', label: 'Pages', hint: 'comma-separated page numbers' }, { name: 'pattern', label: 'Value pattern', def: '\\s*:\\s*(?P<value>[^\\n]+)' },
    { name: 'strategy', label: 'PDF table strategy', kind: 'select', options: ['lines', 'text'] }, { name: 'mapping_unit', label: 'Evidence unit' }, { name: 'mapping_currency', label: 'Evidence currency' }] },
];
function rule(rels: string[], maps: string[]): Section[] {
  return [
    { title: 'Comparison', fields: [
      { name: 'rule_id', label: 'Rule ID' }, { name: 'rule_relationship', label: 'Relationship', kind: 'select', options: rels }, { name: 'field', label: 'Structured field' },
      { name: 'mapping', label: 'Evidence mapping', kind: 'select', options: ['', ...maps] }, { name: 'right_field', label: 'Or right field' },
      { name: 'method', label: 'Method', kind: 'select', options: ['decimal', 'string', 'category', 'date', 'nli', 'image_text'] }] },
    { title: 'Representation, tolerance and units', collapsed: true, fields: [
      { name: 'representation', label: 'Representation', kind: 'select', options: ['raw', 'nfc', 'casefold', 'whitespace'] }, { name: 'tolerance', label: 'Tolerance', def: '0' }, { name: 'factor', label: 'Declared conversion factor', def: '1' },
      { name: 'unit', label: 'Unit' }, { name: 'currency', label: 'Currency' }, { name: 'claim_template', label: 'Optional fixed claim template' }] },
  ];
}
const MODELS: Section[] = [
  { title: 'Optional verified local models', collapsed: true, note: 'Pinned and offline. Unqualified methods abstain.', fields: [
    { name: 'nli_directory', label: 'NLI directory' }, { name: 'retrieval_directory', label: 'E5 retrieval directory' }, { name: 'image_text_directory', label: 'Joint image–text directory' }] },
];

type Decl = { id: string; [k: string]: unknown };
function Builder({ title, n, items, line, collection, sections, action, submit, job, setJob, flash }: {
  title: string; n: number; items: Decl[]; line: (d: Decl) => string; collection: string; sections: Section[]; action: string; submit: string; job: FlowJob; setJob: (j: FlowJob) => void; flash: Flash;
}) {
  const [f, setF] = useState<Fields>(() => ({ ...defaults(sections), ...Object.fromEntries(Object.entries(job.fields as Fields).filter(([k]) => k in defaults(sections))) }));
  const [busy, setBusy] = useState(false);
  const act = (body: Fields) => { setBusy(true); crossApi.post('action', body).then((r) => setJob(r.job)).catch(flash).finally(() => setBusy(false)); };
  return (
    <section className="ap-sec ap-m4src" aria-label={title}>
      <h2 className="ap-q">{n}. {title} · {items.length}</h2>
      {!!items.length && <ul className="ap-more__list">{items.map((d) => <li key={d.id}>{line(d)} <button type="button" className="ap-link" disabled={busy} onClick={() => act({ action: 'remove', collection, identity: d.id })}>Remove</button></li>)}</ul>}
      <FieldSections sections={sections} values={f} set={(k, v) => setF((x) => ({ ...x, [k]: v }))} />
      <div className="ap-acts"><button type="button" className="nk-btn nk-btn--ghost" disabled={busy} onClick={() => act({ ...f, action })}>{submit}</button></div>
    </section>
  );
}

function Configure({ job, setJob, flash }: { job: FlowJob; setJob: (j: FlowJob) => void; flash: Flash }) {
  const spec = (job.spec as Doc | undefined) ?? {}, list = (k: string) => ((spec[k] as Decl[]) ?? []);
  const ids = job.sources.map((s) => s.id), rels = list('relationships').map((r) => r.id), maps = list('mappings').map((m) => m.id);
  const preview = (job.preview as Doc | null) ?? null, phase = job.phase as string | undefined;
  const [busy, setBusy] = useState(false);
  useAfterRun(job, 'seal', 'confirm', `${M9_PREFIX}/confirm`);
  if (job.state === 'running' && phase === 'preview') return <Running job={job} label="Previewing up to 20 documents and recipe matches" api={crossApi} setJob={setJob} flash={flash} />;
  if (job.state === 'running' && phase === 'seal') return <Running job={job} label="Sealing declarations, source evidence and models" api={crossApi} setJob={setJob} flash={flash} />;
  const step = (path: string) => { setBusy(true); crossApi.post(path).then((r) => setJob(r.job)).catch(flash).finally(() => setBusy(false)); };
  const common = { job, setJob, flash };
  return (
    <div className="ap-cf">
      <header className="ap-head"><span className="nk-label">Step 2 · Configure</span><h1>Declare how records meet documents.</h1><p>Associations, reusable mappings and reconciliation rules, then a bounded preview. Partial declarations stay editable; a complete set is validated on every change.</p></header>
      {job.state === 'failed' && job.error && <p className="ap-note ap-note--warn">{job.error}</p>}
      <section className="ap-sec" aria-label="Sources">
        <h2 className="ap-q">1. Sources · {job.sources.length}</h2>
        <ul className="ap-more__list">{job.sources.map((s) => <li key={s.id}>{s.id} · {String(s.kind ?? '')} · {String(s.format ?? '')} · {s.filename}</li>)}</ul>
        <a className="ap-link" href={`${M9_PREFIX}/sources`} onClick={onLink}>Add or remove sources</a>
      </section>
      <Builder key={`r${ids.join()}`} title="Associations and context" n={2} items={list('relationships')} line={(r) => `${r.id} · ${r.left_source} → ${r.right_source} · ${lab(String(r.cardinality))}`} collection="relationships" sections={relationship(ids)} action="relationship" submit="Declare this relationship" {...common} />
      <Builder title="Reusable mappings" n={3} items={list('mappings')} line={(m) => `${m.id} · ${lab(String(m.kind))} · ${m.layout}`} collection="mappings" sections={MAPPING} action="mapping" submit="Save this recipe" {...common} />
      <Builder key={`u${rels.join()}${maps.join()}`} title="Reconciliation rules" n={4} items={list('rules')} line={(r) => `${r.id} · ${r.field} · ${r.method} · ${r.mapping ?? r.right_field ?? ''}`} collection="rules" sections={rule(rels, maps)} action="rule" submit="Map this field to evidence" {...common} />
      <Builder title="Models" n={5} items={[]} line={() => ''} collection="" sections={MODELS} action="models" submit="Set optional models" {...common} />
      <section className="ap-sec" aria-labelledby="ap-pv-h">
        <h2 id="ap-pv-h" className="ap-q">6. Preview and confirmation</h2>
        {preview ? (
          <>
            <p className="ap-muted"><b>Sample only</b> · {String(preview.sample_documents ?? preview.documents ?? '—')} documents. Preview findings describe a bounded sample; the audit evaluates all admitted records and declared associations.</p>
            <dl className="ap-dl">{scalarFacts(preview, 8).map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
            <details className="ap-more"><summary>Preview detail</summary><pre className="ap-pre">{JSON.stringify(preview, null, 2)}</pre></details>
          </>
        ) : <p className="ap-muted">Preview reads up to 20 documents and shows how the recipes match before anything is sealed.</p>}
        <div className="ap-acts">
          <button type="button" className="nk-btn nk-btn--ghost" disabled={busy || !ids.length} onClick={() => step('preview')}>Preview up to 20 documents</button>
          <button type="button" className="nk-btn" disabled={busy || !ids.length} onClick={() => step('seal')}>Review the confirmation →</button>
        </div>
      </section>
    </div>
  );
}

function Confirm({ job, saving, setJob, flash }: { job: FlowJob; saving: boolean; setJob: (j: FlowJob) => void; flash: Flash }) {
  const models = Object.entries((job.sealed_models as Record<string, Doc> | null) ?? {}).filter(([k]) => k !== 'retrieval');
  const config = (job.config as Doc | undefined) ?? {}, exec = (config.execution as Doc | undefined) ?? {};
  return (
    <ConfirmFrame job={job} api={crossApi} flash={flash} saving={saving} prefix={M9_PREFIX} onRun={setJob}
      task={<><b>Records ↔ documents · {job.sources.length} source{job.sources.length === 1 ? '' : 's'}</b><span>Confirmation binds declarations, source evidence and model artifacts. The audit evaluates all admitted records and declared associations.</span></>}>
      <section className="ap-sec" aria-labelledby="ap-cpu-h">
        <h2 id="ap-cpu-h" className="ap-q">CPU allocation and model scope</h2>
        {models.length ? <ul className="ap-more__list">{models.map(([k, m]) => { const q = (m.qualification as Doc | undefined) ?? {}; return <li key={k}>{k} · {String(m.model ?? '—')} · qualified: {String(m.qualified)} · {String(q.scope ?? q.status ?? '')}</li>; })}</ul>
          : <p className="ap-muted">No optional judgment model selected.</p>}
        <dl className="ap-dl">{scalarFacts(exec, 6).map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
        <p className="ap-muted">Optional models require measured qualification. CPU work ceilings do not promise complete investigation coverage.</p>
        <details className="ap-more"><summary>Frozen declarations</summary><pre className="ap-pre">{JSON.stringify(job.spec, null, 2)}</pre></details>
        <details className="ap-more"><summary>Effective work settings</summary><pre className="ap-pre">{JSON.stringify(config, null, 2)}</pre></details>
      </section>
    </ConfirmFrame>
  );
}

/* ——— Result ——— */

type XE = { id: string; family: string; population: string; data: Doc; references: string[]; scope: string };
type XF = { id: string; family: string; title: string; priority: string; population: string; counts: Doc; references: string[] };
type Target = { kind: string; population: string; evidence_refs?: string[]; detail?: Doc; semantic?: Doc };
const STATUS = ['satisfied', 'violated', 'conflicting_evidence', 'inconclusive', 'incomplete', 'unassessed'];
const targetLabel = (t: Target) => lab(String(t.semantic?.status ?? t.detail?.reason ?? t.detail?.status ?? t.kind));

function rulesOf(a: Doc) {
  const fams = (((a.coverage as Doc | undefined)?.families as Record<string, Doc> | undefined) ?? {});
  return ((a.evidence as XE[]) ?? []).filter((e) => e.family === 'reconciliation').map((e) => {
    const d = e.data, records = Number(d.records ?? 0), n = (k: string) => Number(d[k] ?? 0);
    return { id: e.population, method: String(fams[e.population]?.method ?? ''), records, counts: STATUS.map((k) => [k, n(k)] as [string, number]).filter(([, v]) => v > 0), satisfied: n('satisfied'), assessed: records - n('unassessed'), incomplete: n('incomplete_records') };
  });
}

function RuleBars({ a, big }: { a: Doc; big?: boolean }) {
  const rules = rulesOf(a);
  if (!rules.length) return null;
  const cls: Record<string, string> = { satisfied: 'md-ink', violated: 'md-hot-l', conflicting_evidence: 'md-hot', unassessed: 'md-ghost', incomplete: 'md-ghost-l', inconclusive: 'md-ghost-l' };
  return (
    <svg viewBox={`0 0 300 ${rules.length * 34 + 6}`} className="md-viz" preserveAspectRatio="xMidYMid meet">
      {rules.map((r, i) => {
        let x = 0;
        return (
          <g key={r.id} transform={`translate(0 ${i * 34 + 4})`} className="md-grow" style={{ ['--i' as string]: i }}>
            <text x={0} y={8} className="md-t md-t--s">{lab(r.id)}{r.method ? ` · ${r.method}` : ''} · {r.assessed ? `${r.satisfied} of ${r.records} reconcile` : 'unassessed'}</text>
            {r.counts.map(([k, v]) => { const w = r.records ? (v / r.records) * 296 : 0, at = x; x += w; return <rect key={k} x={at + 2} y={12} width={Math.max(1.5, w - 1)} height={14} rx={1.5} className={cls[k] ?? 'md-ghost'}><title>{lab(k)} {v}</title></rect>; })}
            {big && <text x={298} y={8} className="md-t md-t--s md-t--r">{r.counts.map(([k, v]) => `${lab(k)} ${v}`).join(' · ')}</text>}
          </g>
        );
      })}
    </svg>
  );
}

function Evidence({ e }: { e: Doc }) {
  const loc = (e.location as Doc | undefined) ?? {};
  const where = [loc.page != null && `PDF page ${loc.page}`, loc.row != null && `row ${loc.row} · column ${loc.column}`, loc.line_start != null && `line ${loc.line_start}`].filter(Boolean).join(' · ');
  return (
    <div className="ap-reveal__r">
      <b>{lab(String(e.status ?? ''))}</b><code>{String(e.selector ?? '')}{e.selector ? ' · ' : ''}{String(e.asset_path ?? e.source_path ?? '')}</code>{where && <span>{where}</span>}
      <div className="ap-reveal__v">
        {e.excerpt != null && <blockquote>{String(e.excerpt)}</blockquote>}
        {typeof e.image === 'string' && <div className="ap-pairs__img"><figure><img src={e.image} alt="Verified local image" /></figure></div>}
        <details className="ap-more"><summary>Exact source location</summary><pre className="ap-pre">{JSON.stringify(Object.keys(loc).length ? loc : e.reference, null, 2)}</pre></details>
      </div>
    </div>
  );
}

function Investigate({ target, t, reviews, setJob, flash }: { target: string; t: Target; reviews: Record<string, Doc>; setJob: (j: FlowJob) => void; flash: Flash }) {
  const [shown, setShown] = useState<Doc | string | null>(null);
  const [disposition, setDisposition] = useState(String(reviews[target]?.disposition ?? 'confirm'));
  const [note, setNote] = useState(String(reviews[target]?.note ?? ''));
  const [pick, setPick] = useState<string[]>([]);
  useEffect(() => { setShown(null); setPick([]); crossApi.post('investigate', { target }).then((r) => setShown(r as Doc)).catch((e) => setShown(e instanceof ApiError ? e.message : 'Unavailable.')); }, [target]);
  const ev = typeof shown === 'object' && shown ? ((shown.evidence as Doc[]) ?? []) : [];
  const rule = typeof shown === 'object' && shown ? (shown.rule as Doc | null) : null;
  const ctx = typeof shown === 'object' && shown ? ((shown.context as Doc[] | null) ?? []) : [];
  const resolved = ev.filter((e) => e.status === 'resolved');
  const disclose = () => download('/cross/disclose', { excerpt_refs: pick.filter((r) => !resolved.find((e) => e.reference === r)?.image).join(','), image_refs: pick.filter((r) => resolved.find((e) => e.reference === r)?.image).join(',') }, 'evidence-disclosure.html').catch(flash);
  return (
    <div className="ap-reveal" aria-live="polite">
      {rule && <><b>{String(rule.field)} · {String(rule.method)}</b><details className="ap-more"><summary>Frozen comparison rule</summary><pre className="ap-pre">{JSON.stringify(rule, null, 2)}</pre></details></>}
      <p>{targetLabel(t)} · {lab(t.population)} · <code>{short(target)}</code></p>
      <details className="ap-more"><summary>Judgment, scores and evidence references</summary><pre className="ap-pre">{JSON.stringify(t, null, 2)}</pre></details>
      {typeof shown === 'string' ? <p className="ap-reveal__err">{shown}</p> : !shown ? <p className="nk-ch__not">Reading exact local evidence…</p> : (
        <>
          {ctx.map((c, i) => <p key={i} className="nk-ch__not">Association context · eligible: {String(c.eligible)} · excluded: {((c.excluded as string[]) ?? []).join(', ') || 'none'} · unknown: {((c.unknown as string[]) ?? []).join(', ') || 'none'}</p>)}
          {ev.map((e, i) => <Evidence key={i} e={e} />)}
          <div className="ap-fields ap-fields--two">
            <label>Disposition<select value={disposition} onChange={(e) => setDisposition(e.target.value)}>{['confirm', 'dismiss', 'unresolved'].map((o) => <option key={o}>{o}</option>)}</select></label>
            <label>Optional note<textarea rows={2} maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)} /></label>
          </div>
          <div className="ap-acts"><button type="button" className="ap-sheet__dl" onClick={() => crossApi.post('review', { target, disposition, note }).then((r) => setJob(r.job)).catch(flash)}>Save separate review decision</button></div>
          {!!resolved.length && (
            <div className="ap-acts">
              {resolved.map((e) => { const r = String(e.reference); return <label key={r} className="ap-check"><input type="checkbox" checked={pick.includes(r)} onChange={(x) => setPick(x.target.checked ? [...pick, r] : pick.filter((y) => y !== r))} /> Disclose <code>{short(r)}</code></label>; })}
              <button type="button" className="ap-sheet__dl" disabled={!pick.length} onClick={disclose}>Export selected evidence variant ↓</button>
            </div>
          )}
        </>
      )}
      <p className="nk-ch__not">Excerpts and images are read locally on request and are not added to history.</p>
    </div>
  );
}

const FILTERS = ['all', 'unreviewed', 'confirm', 'dismiss', 'unresolved'];
function Reconciliation({ a, live, job, setJob, flash }: { a: Doc; live: boolean; job?: FlowJob; setJob?: (j: FlowJob) => void; flash: Flash }) {
  const targets = Object.entries(((a.profile as Doc)?.review_targets as Record<string, Target>) ?? {});
  const reviews = (job?.reviews as Record<string, Doc> | undefined) ?? {};
  const [filter, setFilter] = useState('all');
  const [open, setOpen] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const rows = targets.filter(([id]) => filter === 'all' || String(reviews[id]?.disposition ?? 'unreviewed') === filter);
  const importReview = (file: File) => { const d = new FormData(); d.set('review', file); setBusy(true); crossApi.post('import-review', d).then((r) => setJob?.(r.job)).catch(flash).finally(() => setBusy(false)); };
  return (
    <>
      {live && <div className="ap-chips" role="group" aria-label="Filter by review disposition">{FILTERS.map((f) => <button key={f} type="button" className={filter === f ? 'is-on' : ''} aria-pressed={filter === f} onClick={() => setFilter(f)}>{f}</button>)}</div>}
      <div className="ap-chtab">
        <table><thead><tr><th>Population</th><th>Target</th><th>Status</th><th>Candidates</th>{live && <th>Review</th>}{live && <th />}</tr></thead>
          <tbody>{rows.slice(0, 60).map(([id, t]) => (
            <tr key={id} className={open === id ? 'is-on' : ''}><td>{lab(t.population)}</td><td>{short(id)}</td><td>{targetLabel(t)}</td><td>{String(t.detail?.candidate_count ?? '—')}</td>
              {live && <td>{String(reviews[id]?.disposition ?? 'unreviewed')}</td>}
              {live && <td><button type="button" className="ap-link" onClick={() => setOpen(open === id ? null : id)}>{open === id ? 'Close' : 'Inspect'}</button></td>}</tr>
          ))}</tbody></table>
        {rows.length > 60 && <p>{rows.length - 60} more review targets in the canonical JSON.</p>}
      </div>
      {live && open && setJob && <Investigate key={open} target={open} t={targets.find(([id]) => id === open)![1]} reviews={reviews} setJob={setJob} flash={flash} />}
      {live ? (
        <div className="ap-acts">
          <span className="nk-ch__not">{Object.keys(reviews).length} reviewed / {targets.length} retained targets. Aggregate dispositions do not establish individual record inspection.</span>
          <a className="ap-sheet__dl" href="/api/datatrust/v1/cross/download/review">Review JSON ↓</a>
          <label className="ap-sheet__dl">Import review JSON<input type="file" hidden disabled={busy} accept=".json,application/json" onChange={(e) => { const f = e.target.files?.[0]; if (f) importReview(f); e.target.value = ''; }} /></label>
        </div>
      ) : <p className="nk-ch__lim">{READ_ONLY}</p>}
    </>
  );
}

export function crossTiles(a: Doc, live: boolean, flash: Flash, job?: FlowJob, setJob?: (j: FlowJob) => void): Tile[] {
  const ev = (a.evidence as XE[]) ?? [], fs = (a.findings as XF[]) ?? [], profile = (a.profile as Doc) ?? {};
  const rules = rulesOf(a), assessed = rules.filter((r) => r.assessed > 0);
  const sat = assessed.reduce((s, r) => s + r.satisfied, 0), of = assessed.reduce((s, r) => s + r.records, 0);
  const flagged = rules.some((r) => r.counts.some(([k]) => k === 'violated' || k === 'conflicting_evidence'));
  const label = !assessed.length ? 'No rule could be assessed' : `${sat.toLocaleString('en-US')} of ${of.toLocaleString('en-US')} ${assessed.length === 1 ? 'records' : 'record checks'} reconcile`;
  const n = (k: string) => Number(profile[k] ?? 0).toLocaleString('en-US');
  const hero: Tile = {
    id: 'reconciliation', hero: true, name: 'Reconciliation', n: '01', kicker: `${rules.length} rule${rules.length === 1 ? '' : 's'}`, bg: '#163F52', light: true,
    tone: flagged ? 'finding' : 'info', label, detail: `${n('records')} records · ${n('documents')} documents · ${n('pages')} pages`,
    viz: <RuleBars a={a} />, bigViz: <RuleBars a={a} big />,
    chapter: (
      <>
        <h3>Reconciliation</h3>
        <div className="nk-ch__run"><span>Records against supplied evidence, per declared rule</span><b>{label}</b><p>Agreement is judged on examined evidence only. A satisfied rule does not certify a document, and an unassessed rule makes no claim.</p></div>
        <Reconciliation a={a} live={live} job={job} setJob={setJob} flash={flash} />
      </>
    ),
  };
  const families = [...new Set(ev.map((e) => e.family))].filter((f) => f !== 'reconciliation');
  return [hero, ...families.map((fam, i) => {
    const recs = ev.filter((e) => e.family === fam), ffs = fs.filter((f) => f.family === fam), data = recs[0]?.data ?? {}, facts = scalarFacts(data, 6);
    return familyTile({ id: fam, name: lab(fam), n: i + 2, kicker: `${recs.length} population${recs.length === 1 ? '' : 's'}`, shade: SHADES[i % SHADES.length], tone: ffs.length ? 'finding' : 'info',
      label: ffs.length ? ffs[0].title : facts[0] ? `${facts[0][1]} ${facts[0][0]}` : 'Measured', detail: recs.map((e) => lab(e.population)).join(' · '),
      body: <><h3>{lab(fam)}</h3><div className="nk-ch__run"><span>{recs.map((e) => lab(e.population)).join(' · ')} · {recs[0]?.scope}</span><b>{ffs.length ? `${ffs.length} finding${ffs.length === 1 ? '' : 's'}` : 'No finding'}</b><p>{ffs[0]?.title ?? 'Evidence for review within its examined scope.'}</p></div>
        {recs.map((e) => { const f = scalarFacts(e.data, 8); return <div key={e.id}>{recs.length > 1 && <b>{lab(e.population)}</b>}{!!f.length && <dl>{f.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>}<BoundedTable data={e.data} /></div>; })}</> });
  })];
}

export function CrossPage({ a, out, live, flash, onOpen, job, setJob }: { a: Doc; out: ReactNode; live: boolean; flash: Flash; onOpen: () => void; job?: FlowJob; setJob?: (j: FlowJob) => void }) {
  const fs = (a.findings as XF[]) ?? [], profile = (a.profile as Doc) ?? {};
  const counts = (f: XF) => Object.entries(f.counts ?? {}).filter(([k, v]) => typeof v === 'number' && k !== 'records' && v > 0).map(([k, v]) => `${lab(k)} ${v}`).join(' · ');
  return (
    <MosaicPage checks={a.checks} guidance={a.guidance} name={String(profile.dataset_name ?? 'Records ↔ documents')} sub={`${Number(profile.source_count ?? 0)} sources · Records ↔ documents`} when={String(a.generated_at)} findings={fs.length}
      status="No score: reconciliation reports evidence and review targets." partial={(a.execution as Doc)?.status === 'partial'} label="Reconciliation checks"
      tiles={crossTiles(a, live, flash, job, setJob)} actions={fs.map((f) => ({ id: f.id, title: f.title, priority: f.priority, text: counts(f), scope: lab(f.population) }))}
      summary={String(profile.summary ?? '')} out={out} onOpen={onOpen} coverage={<p className="ap-muted">Analytical downloads omit source content and use opaque references. The private manifest and review JSON are separate files; review JSON includes your notes.</p>} />
  );
}

/** A saved Records ↔ documents entry: read-only, with an explicit reopen using the user's own private manifest. */
export function SavedCross({ a, out, flash, onOpen, analysisUrl }: { a: Doc; out: ReactNode; flash: Flash; onOpen: () => void; analysisUrl: string }) {
  const report = async () => { const r = await fetch(analysisUrl, { credentials: 'same-origin' }); if (!r.ok) throw new ApiError('The saved result could not be read.', r.status); return r.blob(); };
  return (
    <>
      <CrossPage a={a} live={false} flash={flash} onOpen={onOpen} out={<>{out}<Reopen flash={flash} report={report} title="Reopen with your private manifest" /></>} />
    </>
  );
}

export function M9Flow({ path, info, flash, saving, onRail, onSaved }: { path: string; info: SessionInfo; flash: Flash; saving: boolean; onRail: (s: FlowStep, ok: FlowStep[]) => void; onSaved: () => void }) {
  const [view, setView] = useState(false);
  const dl = <FlowDownloads route="/api/datatrust/v1/cross/download" kinds={['pdf', 'html', 'json', 'private', 'review']} flash={flash} />;
  return (
    <Flow path={path} prefix={M9_PREFIX} api={crossApi} info={info} flash={flash} onRail={onRail} onSaved={onSaved} label="Records ↔ documents" reachable={reach}
      render={({ step, job, setJob, analysis, onNew }) => (
        <>
          {step === 'sources' && <Sources job={job} info={info} setJob={setJob} flash={flash} />}
          {job && step === 'configure' && <Configure job={job} setJob={setJob} flash={flash} />}
          {job && step === 'confirm' && <Confirm job={job} saving={saving} setJob={setJob} flash={flash} />}
          {job && step === 'report' && analysis && (
            <>
              <CrossPage a={analysis} live flash={flash} job={job} setJob={setJob} onOpen={() => setView(true)} out={<LiveOut saved={!!job.saved_entry} onView={() => setView(true)} onNew={onNew} newLabel="New reconciliation" downloads={dl} />} />
              {view && <ReportViewer name="Records ↔ documents" src={crossApi.report} downloads={dl} onClose={() => setView(false)} />}
            </>
          )}
        </>
      )} />
  );
}
