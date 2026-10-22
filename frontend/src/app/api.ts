// The DataTrust app API (/api/datatrust/v1): the same session-owned jobs as the classic interface.
// Request bodies use the classic form's field names; every mutation carries the session's CSRF header.

export type Fields = Record<string, string>;
export type M3Mode = 'annotation_classification' | 'annotation_regression' | 'multilabel_classification' | 'clustering' | 'anomaly_detection' | 'role_profile';
export type Mode = 'classification' | 'regression' | 'unlabeled' | M3Mode;
export const M3_MODES: M3Mode[] = ['annotation_classification', 'annotation_regression', 'multilabel_classification', 'clustering', 'anomaly_detection', 'role_profile'];
export type M4Mode = 'splits' | 'versions' | 'advanced' | 'before_after';
export type Stage = 'configure' | 'confirm' | 'report';
type Dict = Record<string, unknown>;

export interface SessionInfo { csrf_token: string; upload_limit_bytes: number; upload_limit_mib: number; modes: Mode[]; roots: { id: string; label: string }[] }

export interface TargetOption {
  name: string; dtype: string; group?: string; observed_distinct_count?: number; missing_count?: number;
  finite_count?: number; explanation?: string; selector_explanation?: string; requires_override?: boolean; disabled?: boolean;
}
export interface ParsingWarning { code: string; column: string | null; interpretation: string; observed_count?: number; notice: { title: string; text: string } | null }
export interface ClassTarget {
  target: string; labeled_row_count: number; target_missing_count: number; class_count: number; classification_subtype: 'binary' | 'multiclass' | 'single-class';
  target_distribution: { label: string; count: number; percentage: number }[];
  suitability: { requires_override: boolean; explanation: string };
}
export interface Expectations { kind: string; minimum: number | null; maximum: number | null; units: string | null; nonnegative: boolean | null; integer_required: boolean | null }
export interface Finding { code: string; title: string; severity: 'High' | 'Moderate' | 'Low'; finding: string; evidence?: unknown; modeling_impact?: string; recommendation?: string; score_effect?: string }

/** context_v1 declarations: what you state about the data. They never change parsed values, findings or scores. */
export interface ColumnDecl { availability?: string; placeholders?: Record<string, string>; sentinels?: { value: number; meaning: string }[]; applies_when?: { column: string; op: string; value?: string | number }; unit?: string }
export interface ContextDecl { prediction: { objective: string | null; point: string | null }; columns: Record<string, ColumnDecl>; limits?: Record<string, number> }
export interface ContextCandidate { column: string; value: string | number; kind: 'text_placeholder' | 'numeric_sentinel'; rows: number; rate: number; rule: string }
export interface ContextInfo { candidates: ContextCandidate[]; rules: string; columns: string[]; context: ContextDecl | null; meanings: string[]; availability: string[]; operators: string[] }

export interface JobView {
  mode: Mode; stage: Stage; source_filename: string; file_size: number;
  dataset_name: string | null; purpose: string | null; target: string | null;
  inspection: {
    row_count: number | null; preview_row_count: number | null; column_count: number; columns: string[];
    preview: Record<string, string>[]; target_options: TargetOption[] | null; limits: Dict | null; parsing_warnings: ParsingWarning[];
  };
  config: {
    parsing: { encoding: string; missing_policy: string; na_values: string[]; column_types: Record<string, string>; delimiter: string };
    regression: { expectations: Expectations; feature_availability: Record<string, string> } | null;
    fidelity_inspection: { max_bytes: number; max_records: number; max_cells: number };
    context?: ContextDecl | null;
  };
  target_info: (ClassTarget & Dict) | Dict | null;
  delimiter_detected: boolean;
  summary: (Dict & {
    dataset_name: string; source_filename: string; target?: string; overall?: number; risk_level?: string;
    overall_assessment: string; principal_evidence_summary: string; recommended_action: string; score_explanation?: string;
    risks: Finding[]; parsing_warnings: ParsingWarning[];
    execution: { status: string; analyzed_rows: number; analyzed_columns: number };
    coverage: { completed_applicable_groups: string[]; meaning: string; unavailable_checks: { check_id: string; scope: string; applicability: { value: string } | string; execution: { value: string } | string; reason: string }[]; relationship_search?: { status: string; meaning: string } };
    scoring: { status: string; reason: string | null };
    target_statistics?: { finite_count: number; row_count: number };
  }) | null;
  artifacts: string[];
  /** The saved-history entry for this exact analysis, if it was saved. */
  saved_entry: string | null;
  m3?: {
    task: { targets: string[]; features: string[] | null; metadata: string[]; groups: string[] } | null;
    semantic_types: Record<string, string>; scale_sensitive: boolean | null;
    annotation: { expectation: string; status_column: string | null } | null;
    json: { status_values: string; per_target_annotations: string; expectations_by_target: string; feature_availability: string; multilabel_options: string };
  };
}

export interface M4Source { id: string; filename: string; origin: 'upload' | 'local'; headers: string[]; preview: { tokens?: string[] }[]; sha256: string; delimiter?: string; delimiter_detected?: boolean }
export interface M4Job {
  mode: M4Mode; state: 'sources' | 'configure' | 'confirm' | 'running' | 'completed' | 'partial' | 'failed' | 'cancelled'; limit: number;
  sources: M4Source[]; fields: Fields; fingerprint: string | null; manifest: Record<string, unknown> | null; configuration: Record<string, unknown> | null;
  progress: { stage?: string }; error: string | null; result: { status: string; findings: number } | null; saved_entry: string | null;
}
export interface M4Finding { id: string; title: string; priority: 'High' | 'Moderate' | 'Low'; severity?: string; scope: string; affected_count: number | null; denominator: number | null; evidence_refs: string[]; evidence_type: string; next_action: string; limitations: string }
export type M4Analysis = Record<string, unknown> & {
  methodology_id: string; schema_version: string; generated_at: string;
  inputs?: { id: string; role: string; dataset: { path: string; source_filename: string | null } }[];
  dataset?: { path: string; source_filename: string | null };
  comparison?: { mode: string; identity_keys: string[][]; group_keys: string[][]; evaluation_intent: string; dataset_name: string | null; preset?: string | null };
  context: { dataset_name: string | null; purpose: string | null };
  profile: Record<string, unknown>;
  findings: M4Finding[];
  evidence: { id: string; check_id: string }[];
  coverage: { measurements: Record<string, Record<string, unknown>>; diagnostics: Record<string, { status: string; population: string; reason?: string | null; unsearched_scope?: number; excluded_columns?: string[] }> };
  narrative: { summary: string; limitations: string[] };
  scoring: { status: string; reason?: string | null; values: null | { overall: number; risk_level: string } };
  execution: { status: string; backend: string; elapsed_seconds?: number; [k: string]: unknown };
};

/** The canonical analysis JSON (analysis.json), read-only. */
export type Analysis = Dict & {
  methodology_id: string; schema_version: string; generated_at: string;
  task: Dict; profile: Dict & { columns: (Dict & { name: string; role?: string; is_numeric?: boolean; outlier_count?: number; outlier_rate?: number })[] };
  findings: Finding[];
  scoring: { status: string; reason: string | null; values: null | { sub_scores: Record<string, number>; evidence_score: number; overall: number; risk_level: string; guardrails: { code: string; cap: number; explanation: string }[] } };
  execution: { status: string; analyzed_rows: number; analyzed_columns: number; elapsed_seconds: number; backend?: string };
  coverage: Dict & { completed_applicable_groups: string[] };
  context?: { dataset_name?: string; source_filename?: string };
};

export interface HistoryState {
  enabled: boolean; access?: boolean; saving?: 'unset' | 'on' | 'off'; max_age_days?: number | null; max_total_bytes?: number | null;
  count?: number; bytes?: number; location?: string; interrupted?: { id: string; workflow: string; display_name: string | null; started_at: string }[];
}
export interface SavedEntry {
  id: string; created_at: string; workflow: string; mode: Mode; dataset_name: string | null; source_filename: string | null; generated_at: string | null;
  score: number | null; risk_level: string | null; artifacts: string[]; bytes: number; state: 'ok' | 'altered' | 'missing'; live?: boolean;
  presentation?: { package_version?: string; report_templates?: string; app_build?: string } | null;
  summary: { findings: { code: string; title: string; severity: Finding['severity'] }[]; scoring_status?: string; scoring_reason?: string | null; execution_status?: string;
    rows?: number; columns?: number; elapsed_seconds?: number; subtype?: string; narrative?: { overall_assessment?: string; principal_evidence_summary?: string; recommended_action?: string } };
}
export interface SavedPage { items: SavedEntry[]; total: number; next_cursor: number | null }
export interface SaveResult { saved: boolean; entry?: string; message?: string }

export class ApiError extends Error {
  constructor(message: string, readonly status: number, readonly back?: string) { super(message); }
}

const BASE = '/api/datatrust/v1';
let csrf = '';
/** The session's API CSRF token, for the few downloads made with fetch. */
export const csrfToken = () => csrf;

export async function call<T>(method: 'GET' | 'POST', path: string, body?: Fields | FormData): Promise<T> {
  const headers: Record<string, string> = {};
  if (method !== 'GET') headers['X-CSRF-Token'] = csrf;
  if (body && !(body instanceof FormData)) headers['Content-Type'] = 'application/json';
  const res = await fetch(BASE + path, { method, headers, credentials: 'same-origin', body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined });
  const json = await res.json().catch(() => null);
  if (!res.ok || !json) throw new ApiError(json?.error?.message ?? 'DataTrust could not complete the request.', res.status, json?.error?.back);
  return json.data as T;
}

export const api = {
  async session() { const s = await call<SessionInfo>('GET', '/session'); csrf = s.csrf_token; return s; },
  job: () => call<{ job: JobView | null; classic_job?: string }>('GET', '/core/job'),
  upload(mode: Mode, file: File, delimiter = 'auto') { const f = new FormData(); f.set('mode', mode); f.set('delimiter', delimiter); f.set('dataset', file); return call<{ job: JobView }>('POST', '/core/jobs', f); },
  delimiter: (delimiter: string) => call<{ job: JobView }>('POST', '/core/job/delimiter', { delimiter }),
  context: () => call<ContextInfo>('GET', '/core/job/context'),
  targetPreview: (target: string) => call<{ target_info: ClassTarget }>('GET', `/core/job/target-preview?target=${encodeURIComponent(target)}`),
  configure: (fields: Fields) => call<{ next: 'configure' | 'confirm'; job: JobView }>('POST', '/core/job/configure', fields),
  generate: (fields: Fields) => call<{ job: JobView; history: SaveResult }>('POST', '/core/job/generate', fields),
  async analysis(): Promise<Analysis> {
    const res = await fetch(`${BASE}/core/job/analysis`, { credentials: 'same-origin' });
    if (!res.ok) throw new ApiError('The canonical analysis is not available for this session.', res.status);
    return res.json();
  },
  reset: () => call<{ job: null }>('POST', '/core/job/new', {}),
  m4: {
    job: () => call<{ job: M4Job | null }>('GET', '/m4/job'),
    start: (mode: M4Mode) => call<{ job: M4Job }>('POST', '/m4/start', { mode }),
    upload(file: File, delimiter = 'auto') { const f = new FormData(); f.set('delimiter', delimiter); f.set('dataset', file); return call<{ job: M4Job }>('POST', '/m4/sources', f); },
    local: (root_id: string, relative_path: string, delimiter = 'auto') => call<{ job: M4Job }>('POST', '/m4/sources', { root_id, relative_path, delimiter }),
    configure: (fields: Fields) => call<{ job: M4Job }>('POST', '/m4/configure', fields),
    run: (fields: Fields) => call<{ job: M4Job }>('POST', '/m4/run', fields),
    cancel: () => call<{ job: M4Job }>('POST', '/m4/cancel', {}),
    reset: () => call<{ job: null }>('POST', '/m4/new', {}),
    async analysis(): Promise<M4Analysis> {
      const res = await fetch(`${BASE}/m4/analysis`, { credentials: 'same-origin' });
      const json = await res.json().catch(() => null);
      if (!res.ok) throw new ApiError(json?.error?.message ?? 'The comparison result is not available.', res.status);
      return json;
    },
    report: `${BASE}/m4/report`,
    download: (kind: string) => `${BASE}/m4/download/${kind}`,
  },
  history: {
    state: () => call<HistoryState>('GET', '/history/state'),
    choose: (saving: 'on' | 'off') => call<HistoryState>('POST', '/history/choice', { saving }),
    settings: (f: Fields) => call<HistoryState>('POST', '/history/settings', f),
    list(params: Record<string, string> = {}) { const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v)).toString(); return call<SavedPage>('GET', `/history${q ? `?${q}` : ''}`); },
    entry: (id: string) => call<SavedEntry>('GET', `/history/${id}`),
    async analysis(id: string): Promise<Analysis> {
      const res = await fetch(`${BASE}/history/${id}/analysis`, { credentials: 'same-origin' });
      const json = await res.json().catch(() => null);
      if (!res.ok) throw new ApiError(json?.error?.message ?? 'This saved analysis could not be opened.', res.status);
      return json;
    },
    pdf: (id: string) => call<SavedEntry>('POST', `/history/${id}/pdf`, {}),
    remove: (id: string) => call<{ deleted: string }>('POST', `/history/${id}/delete`, {}),
    clear: () => call<{ deleted: number }>('POST', '/history/clear', { confirm: 'delete-all' }),
    dismiss: (id: string) => call<{ dismissed: string }>('POST', `/history/pending/${id}/dismiss`, {}),
    report: (id: string) => `${BASE}/history/${id}/report`,
    download: (id: string, kind: string) => `${BASE}/history/${id}/download/${kind}`,
  },
};

/** Existing ownership-checked artifact routes of the classic interface. */
export const files = { report: `${BASE}/core/job/report`, html: `${BASE}/core/job/download/html`, pdf: `${BASE}/core/job/download/pdf`, json: `${BASE}/core/job/download/json` };
