// M7 · Image reliability: presets, local inventory inspection, declarations sealed by a supervised prepare,
// and a result mosaic anchored by the Pairs hero tile. Images appear only in the live chapter, on request.
import { useEffect, useState, type ReactNode } from 'react';
import { ApiError, csrfToken, type Fields, type SessionInfo } from './api';
import { ConfirmFrame, FieldSections, Flow, FlowDownloads, LiveOut, ReportViewer, Running, defaults, flowApi, useAfterRun, viewAnchor, type Doc, type FlowJob, type FlowStep, type Section, type ViewTarget } from './flow';
import { Corners, READ_ONLY } from './parts';
import { imageDashboard, type Pair } from './results/compositions/image';
import { ResultsShell, useCompanion } from './results/shell/ResultsShell';
import { onLink } from './router';

type Flash = (e: unknown) => void;
export const imageApi = flowApi('/images');
export const M7_PREFIX = '/app/images';
const PRESETS: [string, string, string][] = [['directory', 'A folder of images', 'Unlabeled images, read where they are.'], ['classes', 'Images sorted into class folders', 'One subfolder per class.'],
  ['manifest', 'A manifest', 'A JSONL or CSV file listing images and their labels or objects.'], ['multilabel', 'Several labels per image', 'A manifest whose labels field holds a list per image.'],
  ['coco_detection', 'COCO detection', 'COCO boxes.'], ['coco_segmentation', 'COCO segmentation', 'COCO masks.'], ['yolo', 'YOLO', 'YOLO label files.'], ['masks', 'Masks', 'A manifest with mask files.'],
  ['comparison', 'Compare two image sets', 'A reference set against a current one: overlap, duplicates and label differences.']];
const MANIFEST_LIKE = ['manifest', 'masks', 'multilabel', 'comparison'];
const RUN = ['running', 'completed', 'failed', 'cancelled'];

function reach(j: FlowJob | null): FlowStep[] {
  if (!j) return ['sources'];
  const out: FlowStep[] = ['sources'], phase = j.phase as string | undefined;
  if (j.inspected || ['configure', 'confirm'].includes(j.state) || phase === 'prepare' || phase === 'run') out.push('configure');
  if (j.state === 'confirm' || phase === 'run') out.push('confirm');
  if (phase === 'run' && RUN.includes(j.state)) out.push('report');
  return out;
}

function Sources({ job, info, setJob, flash }: { job: FlowJob | null; info: SessionInfo; setJob: (j: FlowJob | null) => void; flash: Flash }) {
  const preset = String(job?.preset ?? '');
  const [root, setRoot] = useState(info.roots[0]?.id ?? '');
  const [rel, setRel] = useState('');
  const [assets, setAssets] = useState('');
  const [role, setRole] = useState('dataset');
  const [fmt, setFmt] = useState('jsonl');
  const [busy, setBusy] = useState(false);
  const act = (p: Promise<{ job: FlowJob | null }>) => { setBusy(true); return p.then((r) => setJob(r.job)).catch(flash).finally(() => setBusy(false)); };
  const count = job?.sources.length ?? 0;
  useEffect(() => { setRole(preset === 'comparison' ? (count ? 'current' : 'reference') : 'dataset'); if (preset === 'comparison' && fmt === 'jsonl' && !count) setFmt('directory'); }, [preset, count]);  // eslint-disable-line react-hooks/exhaustive-deps
  const extra = (): Fields => ({ role, source_id: preset === 'comparison' ? (count ? 'current' : 'reference') : `dataset${count + 1}`, ...(MANIFEST_LIKE.includes(preset) ? { format: fmt } : {}) });
  useAfterRun(job, 'inspect', 'configure', `${M7_PREFIX}/configure`);
  if (job?.state === 'running' && job.phase === 'inspect') return <Running job={job} label="Inspecting the local inventory" api={imageApi} setJob={setJob} flash={flash} />;
  return (
    <div className="ap-up">
      <header className="ap-head"><span className="nk-label">Step 1 · Sources</span><h1>Check image data.</h1><p>Images, annotations and segmentation integrity, read where they are. Optional models are pinned and offline. No universal score.</p></header>
      <section className="ap-sec" aria-labelledby="ap-preset-h">
        <h2 id="ap-preset-h" className="ap-q">What kind of image dataset?</h2>
        <div className="ap-modes ap-modes--compact" role="radiogroup" aria-label="Image preset">
          {PRESETS.map(([p, t, d]) => <button key={p} type="button" role="radio" aria-checked={preset === p} className={`ap-mode ${preset === p ? 'is-on' : ''}`} onClick={() => act(imageApi.start({ preset: p }))}>{preset === p && <Corners />}<b>{t}</b><span>{d}</span></button>)}
        </div>
      </section>
      {job && (
        <section className="ap-sec" aria-labelledby="ap-src-h">
          <h2 id="ap-src-h" className="ap-q">Sources · {job.sources.length}</h2>
          {job.sources.map((s) => <div key={s.id} className="ap-src"><div className="ap-src__h"><span className="ap-strip__role">{String(s.role ?? 'dataset')}</span><b>{s.filename}</b><span>{s.id} · {String(s.format ?? '')}</span></div></div>)}
          <div className="ap-root">
            <b>{preset === 'directory' || preset === 'classes' || (preset === 'comparison' && fmt === 'directory') ? 'A folder in a data root' : 'A manifest in a data root'}</b>
            <div className="ap-fields ap-fields--two">
              <label>Data root<select value={root} onChange={(e) => setRoot(e.target.value)}>{info.roots.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}</select></label>
              <label>Path inside it<input value={rel} onChange={(e) => setRel(e.target.value)} placeholder={preset === 'directory' || preset === 'classes' ? 'images/' : 'annotations.jsonl'} /></label>
              <label>Asset root <span>for relative image or mask paths; inside the same root</span><input value={assets} onChange={(e) => setAssets(e.target.value)} placeholder="." /></label>
              <label>Role<select value={role} onChange={(e) => setRole(e.target.value)}>{['dataset', 'train', 'validation', 'test', 'evaluation', 'reference', 'current'].map((r) => <option key={r}>{r}</option>)}</select></label>
              {MANIFEST_LIKE.includes(preset) && <label>{preset === 'comparison' ? 'Source format' : 'Manifest format'}<select value={fmt} onChange={(e) => setFmt(e.target.value)}>{preset === 'comparison' && <option value="directory">folder</option>}<option>jsonl</option><option>csv</option></select></label>}
              {preset === 'comparison' && <p className="ap-muted ap-fields__wide">Add the reference set first, then the current one. Both use the same format.</p>}
            </div>
            <button type="button" className="nk-btn nk-btn--ghost" disabled={busy || !rel.trim()} onClick={() => act(imageApi.local({ root_id: root, relative_path: rel.trim(), asset_relative: assets.trim(), ...extra() })).then(() => setRel(''))}>Add this source</button>
            {preset !== 'directory' && preset !== 'classes' && <label className="ap-fmt">Or upload a manifest<input type="file" accept=".csv,.jsonl,.json,.yaml,.yml" onChange={(e) => { const f = e.target.files?.[0]; if (f) act(imageApi.upload(f, extra(), 'manifest')); e.target.value = ''; }} /></label>}
            <p className="ap-muted">Directory uploads and archive extraction are unavailable; folders are read where they are, inside the data roots.</p>
          </div>
          <div className="ap-acts">
            {job.sources.length ? <button type="button" className="nk-btn" disabled={busy} onClick={() => act(imageApi.post('inspect'))}>Inspect local inventory →</button> : <span className="nk-btn is-off" aria-disabled="true">Inspect →</span>}
            {!!job.inspected && <a className="nk-btn nk-btn--ghost" href={`${M7_PREFIX}/configure`} onClick={onLink}>Declarations →</a>}
          </div>
        </section>
      )}
    </div>
  );
}

const TASKS = ['unlabeled', 'classification', 'multilabel_classification', 'detection', 'segmentation'];
type Sel = { selector: string; suggestions: { rule: string; role: string; text: string }[]; boxes?: { consistent: string[]; text: string } | null };

/** Manifest column discovery (inspection.discover_selectors over the first records): chips fill the mapping only when
 *  chosen; box values are reported with the formats they are consistent with, never chosen for you. */
function ManifestSuggestions({ s, i, f, set, task }: { s: FlowJob['sources'][number]; i: number; f: Fields; set: (k: string, v: string) => void; task: string }) {
  const d = s.discovery as { error?: string; statement?: string; selectors?: Sel[] } | null | undefined;
  if (!d || d.error || !d.selectors) return null;
  const p = `s${i}_`;
  const pick = (role: string) => d.selectors!.filter((x) => x.suggestions.some((y) => y.role === role));
  const rows: [string, string, string][] = [['path', 'path', 'Image path'], ['logical_id', 'identifier', 'Logical identity'], ['split', 'split', 'Split'],
    ['labels', task === 'multilabel_classification' ? 'labels' : 'label', 'Labels'], ['objects', 'objects', 'Objects']];
  const boxes = pick('objects').find((x) => x.boxes)?.boxes;
  const shown = rows.map(([field, role, label]) => [field, label, role, pick(role).filter((x) => f[p + field] !== x.selector)] as const).filter(([, , , list]) => list.length);
  return (
    <div className="ap-suggestbox">
      <p className="ap-muted">{d.statement}</p>
      {shown.map(([field, label, role, list]) => (
        <p key={field} className="ap-suggest">{label}: {list.map((x) => (
          <button key={x.selector} type="button" className="ap-chip" title={x.suggestions.map((y) => y.text).join(' ')} onClick={() => set(p + field, x.selector)}>{x.selector}? <code>{x.suggestions.find((y) => y.role === role)?.rule}</code></button>))}</p>
      ))}
      {boxes && <p className="ap-suggest">{boxes.text} {boxes.consistent.map((b) => f[p + 'box_format'] === b
        ? <span key={b} className="ap-chip is-done">{b} ✓</span>
        : <button key={b} type="button" className="ap-chip" onClick={() => set(p + 'box_format', b)}>{b}?</button>)}</p>}
    </div>
  );
}
function Configure({ job, setJob, flash }: { job: FlowJob; setJob: (j: FlowJob) => void; flash: Flash }) {
  const preview = (job.preview as Doc | undefined) ?? {};
  const sourceSections = (s: FlowJob['sources'][number]): Section[] => {
    const mapping = (s.mapping as Doc | undefined) ?? {}, ann = (s.annotations as Doc | undefined) ?? {};
    return [
      { title: 'Task and mapping', note: 'Mapping fields may be JSON Pointers.', fields: [
        { name: 'task', label: 'Task', kind: 'select', options: TASKS, def: String((s.task as Doc | undefined)?.kind ?? 'unlabeled') },
        ...Object.entries(mapping).map(([k, v]) => ({ name: k, label: k.replace(/_/g, ' '), def: Array.isArray(v) ? v.join(',') : v == null ? '' : String(v) }))] },
      { title: 'Annotations', fields: [
        { name: 'categories', label: 'Categories', hint: 'explicit IDs, comma-separated', def: ((ann.categories as unknown[]) ?? []).join(',') },
        { name: 'expectation', label: 'Annotation expectation', kind: 'select', options: ['unknown', 'required', 'optional', 'not_applicable'], def: String(ann.expectation ?? 'unknown') },
        { name: 'box_format', label: 'Box coordinates', kind: 'select', options: ['xyxy', 'xywh', 'normalized_cxcywh'], def: String(ann.box_format ?? 'xyxy') },
        { name: 'frame', label: 'Coordinate frame', kind: 'select', options: ['encoded', 'oriented', 'unknown'], def: String(ann.coordinate_frame ?? 'encoded') },
        { name: 'mask_encoding', label: 'Mask representation', kind: 'select', options: ['semantic_png', 'binary_png', 'rgb_png', 'coco'], def: String(ann.mask_encoding ?? 'semantic_png') },
        { name: 'color_mapping', label: 'RGB mask mapping', hint: 'JSON: "r,g,b" to explicit category', def: JSON.stringify(ann.color_mapping ?? {}) },
        { name: 'missing_negative', label: 'YOLO missing label files are annotated negatives', kind: 'select', options: ['no', 'yes'], def: ann.missing_yolo_labels_are_negative ? 'yes' : 'no' },
        { name: 'json_columns', label: 'CSV fields containing JSON arrays or objects', def: (((s.source as Doc | undefined)?.json_columns as string[]) ?? []).join(',') }] },
    ];
  };
  const GLOBAL: Section[] = [
    { title: 'Dataset', fields: [{ name: 'dataset_name', label: 'Dataset name' }, { name: 'model_directory', label: 'Verified local model directory', hint: 'opt-in CPU embeddings; no downloads' }] },
    { title: 'Advanced comparisons, transforms and resource settings', collapsed: true, fields: [
      { name: 'advanced', label: 'Use strict declarations below', kind: 'select', options: ['no', 'yes'] },
      ...(job.preset === 'comparison' ? [{ name: 'align_logical_keys', label: 'Align the two sets by logical identity', kind: 'select' as const, options: ['yes', 'no'] }] : []),
      { name: 'spec_json', label: 'Audit specification', kind: 'area', hint: 'JSON', wide: true, rows: 6 }, { name: 'config_json', label: 'Analysis configuration', kind: 'area', hint: 'JSON', wide: true, rows: 4, def: '{}' }] },
  ];
  const [f, setF] = useState<Fields>(() => ({ ...defaults(GLOBAL), ...Object.assign({}, ...job.sources.map((s, i) => defaults(sourceSections(s), `s${i}_`))), ...(job.fields as Fields) }));
  const set = (k: string, v: string) => setF((x) => ({ ...x, [k]: v }));
  useAfterRun(job, 'prepare', 'confirm', `${M7_PREFIX}/confirm`);
  if (job.state === 'running' && job.phase === 'prepare') return <Running job={job} label="Sealing declarations, models and inventory" api={imageApi} setJob={setJob} flash={flash} />;
  const submit = () => { const body = { ...f }; if (body.advanced !== 'yes') delete body.advanced; imageApi.configure(body).then((r) => setJob(r.job)).catch(flash); };
  return (
    <div className="ap-cf">
      <header className="ap-head"><span className="nk-label">Step 2 · Configure</span><h1>Declare what the images mean.</h1><p>{Number(preview.occurrences ?? 0).toLocaleString('en-US')} occurrences in the inspected inventory. Standard presets declare encoded-image coordinates; missing annotations stay unknown unless declared.</p></header>
      {job.state === 'failed' && <p className="ap-note ap-note--warn">{job.error}</p>}
      {job.preset === 'comparison' && job.sources.length === 2 && <p className="ap-note">Compares <b>{String(job.sources.find((x) => x.role === 'reference')?.id ?? job.sources[0].id)}</b> (reference) against <b>{String(job.sources.find((x) => x.role === 'current')?.id ?? job.sources[1].id)}</b> (current).</p>}
      <FieldSections sections={GLOBAL.slice(0, 1)} values={f} set={set} />
      {job.sources.map((s, i) => (
        <section key={s.id} className="ap-sec ap-m4src" aria-label={`${s.id} declarations`}>
          <h2 className="ap-q">{s.id} · {String(s.format ?? '')}</h2>
          <ManifestSuggestions s={s} i={i} f={f} set={set} task={f[`s${i}_task`]} />
          <FieldSections sections={sourceSections(s)} values={f} set={set} prefix={`s${i}_`} />
        </section>
      ))}
      <FieldSections sections={GLOBAL.slice(1)} values={f} set={set} />
      <div className="ap-acts">
        <button type="button" className="nk-btn" onClick={submit}>Review effective declarations →</button>
        <a className="nk-btn nk-btn--ghost" href={`${M7_PREFIX}/sources`} onClick={onLink}>Back to sources</a>
      </div>
    </div>
  );
}

/* ——— Result ——— */

const lab = (s: string) => s.replace(/_/g, ' ');
const measure = (p: Pair) => (p.hamming_distance != null ? `distance ${p.hamming_distance}` : p.cosine != null ? `cosine ${p.cosine.toFixed(3)}` : '');
const short = (r: string) => `…${r.slice(-6)}`;

function PairViewer({ pairs, flash }: { pairs: Pair[]; flash: Flash }) {
  const [i, setI] = useState(0);
  const [overlays, setOverlays] = useState(false);
  const [labels, setLabels] = useState(false);
  const [shown, setShown] = useState<Doc[] | string | null>(null);
  const p = pairs[i];
  const view = () => { setShown(null); imageApi.post('resolve', { references: `${p.left},${p.right}`, overlays: overlays ? 'yes' : 'no', labels: labels ? 'yes' : 'no' })
    .then((r) => setShown((r.resolved as Doc[]) ?? [])).catch((e) => setShown(e instanceof ApiError ? e.message : 'Unavailable.')); };
  const exportPair = async () => {
    try {
      const res = await fetch('/api/datatrust/v1/images/export-examples', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken() }, body: JSON.stringify({ references: `${p.left},${p.right}`, overlays: overlays ? 'yes' : 'no', labels: labels ? 'yes' : 'no' }) });
      if (!res.ok) { const j = await res.json().catch(() => null); throw new ApiError(j?.error?.message ?? 'The examples could not be exported.', res.status); }
      const url = URL.createObjectURL(await res.blob()); const a = Object.assign(document.createElement('a'), { href: url, download: 'image-examples.html' }); document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) { flash(e); }
  };
  if (!p) return <p className="nk-ch__not">No retained pairs to view.</p>;
  return (
    <div className="ap-pairs">
      <div className="ap-acts">
        <button type="button" className="ap-sheet__dl" onClick={() => { setI((i - 1 + pairs.length) % pairs.length); setShown(null); }}>←</button>
        <b>{i + 1} / {pairs.length} · {lab(p.family)}{measure(p) ? ` · ${measure(p)}` : ''}</b>
        <button type="button" className="ap-sheet__dl" onClick={() => { setI((i + 1) % pairs.length); setShown(null); }}>→</button>
      </div>
      <div className="ap-acts">
        <label className="ap-check"><input type="checkbox" checked={overlays} onChange={(e) => setOverlays(e.target.checked)} /> Show compatible supplied overlays</label>
        <label className="ap-check"><input type="checkbox" checked={labels} onChange={(e) => setLabels(e.target.checked)} /> Reveal supplied labels locally</label>
        <button type="button" className="ap-sheet__dl" onClick={view}>View this pair locally</button>
        <button type="button" className="ap-sheet__dl" onClick={exportPair}>Export examples ↓</button>
      </div>
      {typeof shown === 'string' ? <p className="ap-reveal__err">{shown}</p> : shown && (
        <div className="ap-pairs__img">{shown.map((e, k) => (
          <figure key={k}>{typeof e.image_data_uri === 'string' ? <img src={e.image_data_uri} alt={`Verified local image, ${k ? 'right' : 'left'}`} /> : <p className="nk-ch__not">No image for this reference.</p>}
            <figcaption><code>{short(String(e.reference ?? (k ? p.right : p.left)))}</code> Annotation: {String(e.annotation_state ?? '—')}. Frame compatible: {String(e.frame_compatible ?? '—')}.{e.labels ? ` ${typeof e.labels === 'string' ? e.labels : JSON.stringify(e.labels)}` : ''}</figcaption></figure>
        ))}</div>
      )}
      <p className="nk-ch__not">Local viewing does not add images to exports or history. Hold an image to zoom.</p>
    </div>
  );
}

export function ImagePage({ a, out, live, flash, onOpen, presentation, saved }: { a: Doc; out: ReactNode; live: boolean; flash: Flash; onOpen: (anchor?: string) => void; presentation: string | null; saved?: boolean }) {
  const companion = useCompanion(presentation);
  if (companion === undefined) return <div className="ap-rs"><div className="nk-mosaic nk-mosaic--big nk-mosaic--run ap-rs__wait" aria-busy="true" /></div>;
  const d = imageDashboard(a, companion, !!saved, { pairs: live ? (pairs) => <PairViewer pairs={pairs} flash={flash} /> : undefined, readOnly: READ_ONLY });
  return <ResultsShell d={d} label="Image checks" out={out} onOpenReport={onOpen} live={live} />;
}

export function M7Flow({ path, info, flash, saving, onRail, onSaved }: { path: string; info: SessionInfo; flash: Flash; saving: boolean; onRail: (s: FlowStep, ok: FlowStep[]) => void; onSaved: () => void }) {
  const [view, setView] = useState<ViewTarget>(false);
  const dl = <FlowDownloads route="/api/datatrust/v1/images/download" kinds={['pdf', 'html', 'json', 'private']} flash={flash} />;
  return (
    <Flow path={path} prefix={M7_PREFIX} api={imageApi} info={info} flash={flash} onRail={onRail} onSaved={onSaved} label="Image audit" reachable={reach}
      render={({ step, job, setJob, analysis, onNew }) => (
        <>
          {step === 'sources' && <Sources job={job} info={info} setJob={setJob} flash={flash} />}
          {job && step === 'configure' && <Configure key={job.sources.map((s) => s.id).join()} job={job} setJob={setJob} flash={flash} />}
          {job && step === 'confirm' && <ConfirmFrame job={job} api={imageApi} flash={flash} saving={saving} prefix={M7_PREFIX} onRun={setJob}
            task={<><b>Image audit · {String(job.preset ?? '').replace(/_/g, ' ')} · {job.sources.length} source{job.sources.length === 1 ? '' : 's'}</b><span>Confirm these meanings once. Source bytes and directory membership are verified before publication. Execution: {String(job.max_seconds ?? '—')} seconds; perceptual search prioritizes eligible cross-split queries, and work limits stay visible.</span></>} />}
          {job && step === 'report' && analysis && (
            <>
              <ImagePage a={analysis} live flash={flash} presentation={imageApi.presentation} onOpen={(x) => setView(x ?? true)} out={<LiveOut saved={!!job.saved_entry} onView={() => setView(true)} onNew={onNew} newLabel="New image audit" downloads={dl} />} />
              {view && <ReportViewer name="Image audit" src={imageApi.report} anchor={viewAnchor(view)} downloads={dl} onClose={() => setView(false)} />}
            </>
          )}
        </>
      )} />
  );
}
