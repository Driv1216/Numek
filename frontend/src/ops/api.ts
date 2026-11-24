// The operations API (/api/ops/v1). The session cookie is HttpOnly; the CSRF token returned at sign-in is kept
// for this tab only (sessionStorage) and sent on every mutation. Errors keep the API's code and message verbatim.

const BASE = '/api/ops/v1';
const CSRF_KEY = 'numek.ops.csrf';

export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number) { super(message); }
}

function csrf(): string | null {
  try { return sessionStorage.getItem(CSRF_KEY); } catch { return null; }
}

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (method !== 'GET') {
    const token = csrf();
    if (token) headers['X-CSRF-Token'] = token;
  }
  const response = await fetch(BASE + path, { method, headers, credentials: 'same-origin', body: body === undefined ? undefined : JSON.stringify(body) });
  let payload: { data?: T; error?: { code: string; message: string } } = {};
  try { payload = await response.json(); } catch { /* non-JSON body */ }
  if (!response.ok || payload.error) {
    throw new ApiError(payload.error?.code ?? 'http_error', payload.error?.message ?? `The server answered ${response.status}.`, response.status);
  }
  return payload.data as T;
}

export const api = {
  get: <T>(path: string) => call<T>('GET', path),
  post: <T>(path: string, body: unknown = {}) => call<T>('POST', path, body),
  async signIn(name: string, password: string) {
    const data = await call<{ principal: string; csrf: string }>('POST', '/session', { name, password });
    try { sessionStorage.setItem(CSRF_KEY, data.csrf); } catch { /* private mode: mutations will ask to sign in again */ }
    return data;
  },
  async signOut() {
    try { await call('DELETE', '/session'); } finally { try { sessionStorage.removeItem(CSRF_KEY); } catch { /* ignore */ } }
  },
  canMutate: () => csrf() !== null,
  reportUrl: (incident: string, audience: 'shareable' | 'local') => `${BASE}/incidents/${incident}/report?format=html&audience=${audience}`,
};

// Response shapes (as the API returns them) ------------------------------------------------------------------
export type Standing = 'D' | 'F' | 'P' | 'E' | 'X' | 'A' | 'H';
export type Priority = 'P1' | 'P2' | 'P3' | 'P4';

export interface Session { principal: { id: string; name: string; kind: string }; via: string; permissions: string[] }
export interface Deployment { id: string; system_id: string; name: string; tier: number; registered_identity: Record<string, unknown>; created_at: string }

export interface HealthSource { source: string; last_received: string | null; silence_ns: number | null; batches_last_day: number; failed_batches: number; backlog_batches: number; producer_dropped_rows: number; rows_received: number; quarantine_rate: number | null }
export interface HealthDetector { id: string; kind: string; statistic: string; standing: string; power: string | null; units: number; alarms: number; late_excluded: number; cursor: number | null; lag_windows: number | null; reasons: string[] }
export interface Health {
  deployment: string; at: string; statement: string; sources: HealthSource[];
  conditions: { kind: string; severity: string; source?: string; detail?: string; count?: number }[];
  failed_jobs_last_day?: number; untimed_opportunities?: number;
  windows?: { version: number; last_closed: number | null; last_matured: number | null; expected_closed: number; expected_matured: number; maturity_backlog_windows: number; next_maturity: string };
  detectors?: HealthDetector[];
  coverage: Record<string, { status: string; detectors?: string[]; note?: string }>;
}
export interface DetectorRow { detector_id: string; kind: string; standing: string; units: number; alarms: number; plan: { expected_false_alarms_per_30_days?: number | null; false_alarm_statement?: string; statistic?: string } }

export interface IncidentSummary { id: string; number: number; deployment_id: string; state: string; priority: Priority; rule: string; owner: string | null; opened_at: string; resolved_at: string | null; resolution: string | null; escalation_level: number }
export interface IncidentRow {
  id: string; number: number; deployment_id: string; state: string; priority: Priority; revision: number; owner: string | null;
  priority_basis: { table: string; rule: string; why: string; impact?: { affected_units: number; region: string | null; region_share: number | null; region_source_standing: string | null; basis: string } | null; override?: { from: string; to: string; reason: string } };
  resolution: string | null; resolution_detail: Record<string, unknown> | null; catalog_sequence: number; knowledge_revision: number;
  opened_at: string; acknowledged_at: string | null; resolved_at: string | null; escalation_level: number; anchor_condition: string; dossier_digest: string;
}
export interface ConditionRow { id: string; key: string; kind: string; standing: Standing; severity: string; state: string; first_window: number | null; last_window: number | null; windows: number[]; signal_count: number; recovery: { claim?: string; wording?: string; interpretation?: string } | null }
export interface SignalRow { id: string; source: string; source_id: string; window_index: number | null; standing: Standing; severity: string; created_at: string; condition_id: string; payload: { kind?: string; wording?: string; not_established?: string[]; assumptions?: string[]; population?: string } }
export interface Differential { columns: { observation: string; value: boolean | null; standing: Standing }[]; rows: { hypothesis: string; title: string; cells: Record<string, string> }[]; qualification: string }
export interface Knowledge { kind: string; known_at: string; catalog_sequence: number; conditions: ConditionRow[]; signals: SignalRow[]; differential?: Differential; reason?: string }
export interface IncidentView { incident: IncidentRow; members: string[]; events: { seq: number; kind: string; payload: Record<string, unknown>; actor: string; at: string }[]; knowledge: Knowledge; as_known: string }

export interface Hypothesis { hypothesis_id: string; state: string; reason: string | null; evidence: { supporting: { observation: string; standing: Standing }[]; contradicting: { observation: string; standing: Standing }[]; missing: { observation: string; reason: string | null; eta: string | null; action: string | null }[] }; knowledge_revision: number }
export interface Requirement { observation: string; status: string; reason: string; eta: string | null; action: string | null; hypotheses: string[]; template: string | null; triggered_run: string | null }
export interface Run { id: string; template: string; tier: 'auto' | 'confirm' | 'restricted'; state: string; value: number; cost_minutes: number; reasoning: { movable?: { hypothesis: string; weight: number }[]; note?: string }; reused_from: string | null; stale_fraction: number | null; approved_by: string | null; result: { observations?: Record<string, { value: boolean; standing: Standing }> } | null; error: { code: string; message: string } | null; created_at: string }
export interface ProposalCard { proposal: string; kind: string; title: string; state: string; evidence_basis: string[]; strongest_basis: string | null; effects: { metric: string; expected: number; interval?: [number, number]; basis: string }[]; prerequisites: { kind: string; pass: boolean; reason: string | null }[]; risks: string[]; required_role: string; verification_plan: { claims: { id: string; claim: string; statistic?: string }[] }; causal_claim: string }
export interface Comparison { proposals: ProposalCard[]; prior_mitigations: { jaccard: number; title: string; state: string }[]; qualification: string }
export interface ProposalDetail { proposal: { id: string; revision: number; author: string; state: string }; standings: Record<string, { outcome: string; evidence_kind: string }>; verification: { claim_id: string; claim: string; state: string; start_window: number | null; result: { wording?: string; interpretation?: string } | null }[] }

export interface RunListItem extends Run { incident_id: string; incident_number: number; priority: Priority; deployment_id: string; finished_at: string | null }
export interface ProposalListItem { id: string; incident_id: string; incident_number: number; priority: Priority; deployment_id: string; kind: string; title: string; state: string; author: string; required_role: string; evidence_basis: string[]; revision: number; created_at: string; updated_at: string }
export interface SourceFunnel { batches: number; by_state: Record<string, number>; rows_received: number; rows_accepted: number; rows_quarantined: number; facts_new: number; facts_duplicate: number; facts_quarantined: number; values_dropped: number; producer_dropped: number; late_rows: number; reconciled: boolean }
export interface SourceBatch { batch_id: string; state: string; mode: string; contract_version: number; raw_bytes: number; producer_dropped: number; catalog_sequence: number | null; counts: Record<string, number | Record<string, number>>; error: string | null; received_at: string; finished_at: string | null }
export interface SourceView { source: string; contract_version: number; contract_digest: string; registered_at: string; format: string; event_time: string; fields: Record<string, { type: string; required?: boolean; identity?: boolean; probability?: boolean }>; watermark: { through_tick: string; updated_at: string } | null; funnel: SourceFunnel; quarantine_reasons: { reason: string; rows: number; fields: string[] | null }[]; batches: SourceBatch[] }
export interface SourcesView { deployment: string; allowed_lateness_ns: string | null; sources: SourceView[]; qualification: string }
export interface IdentityView { ladder: string[]; latest: { standing: string; outcome: string; evidence: Record<string, unknown>; recorded_at: string }[]; history: { standing: string; outcome: string; recorded_at: string }[]; registered_identity: Record<string, unknown> | null; qualification: string }
export interface EstimateWindow { window: number; value: number | null; population: number; matched_estimate: number | null; realized: number | null; realized_interval: [number, number] | null; coverage: number | null; exceedance: boolean | null }
export interface EstimatesView { estimators: Record<string, { assumption: string; summary: { matched_windows: number; mean_signed_bias?: number; mean_absolute_error?: number; exceedances?: number; mean_coverage?: number }; windows: EstimateWindow[] }>; qualification: string }
export interface WindowPhase { units: number; revision: number; closure: string; reproducibility: string; label_availability_rate: number | null; region_shares: Record<string, { members: number; defined: number; share: number | null; source_standing: string }>; start: number | null; end: number | null }
export interface WindowsView { windows: ({ window: number } & { close?: WindowPhase; maturity?: WindowPhase })[] }
export interface DetectorPlan {
  id: string; statistic: string; kind: string; admitted: boolean; refusal?: string; standing?: string; phase?: string; m0?: number; m1?: number; alpha?: number; delta?: number;
  reference_upper?: number | null; reference_mean?: number | null; reference_n?: number; reference_design?: string | null; included_units_per_day?: number | null;
  planner?: { expected_delay_units: number; expected_delay_days?: number }; expected_total_delay_days?: number | null; max_useful_delay_days?: number; power?: string;
  expected_false_alarms_per_30_days?: number | null; reasons?: string[]; region?: string; region_source_standing?: string; false_alarm_statement?: string; conditional_on_reference?: string;
}
export interface Inspection {
  version: number; inspection_digest: string; deployment: string; variant: string; catalog_sequence: number;
  reference: { id: string; rule_digest: string; units: number; inclusion: Record<string, number | null>; evidence_use: string };
  windows: { start: string; length_ns: string; allowed_lateness_ns: string; maturity: Record<string, string> };
  detectors: DetectorPlan[]; estimators: string[]; family: { expected_false_alarms_per_30_days: number }; refusals: { id: string; reason: string }[]; qualifications: string[];
}
export interface DefinitionVersion { version: number; state: string; spec: Record<string, unknown>; spec_digest: string; inspection: Inspection; inspection_digest: string; created_at: string; confirmed_at: string | null; confirmed_by: string | null }
