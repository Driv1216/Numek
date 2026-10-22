// Canonical analysis JSON → the mosaic's tile states. Values are read and formatted, never computed
// into new evidence: findings keep their canonical wording, scores appear only when scoring was computed.
// A tile's state comes from its canonical checks, never from the absence of findings (outcome-map.json).
import type { Analysis, Finding, M3Mode, Mode } from '../api';
import type { ModId } from './modules';
import map from './outcome-map.json';

export type Tone = 'finding' | 'critical' | 'clear' | 'info';
/** finding · no finding within the completed scope · incomplete (a check failed or was cut short) ·
 *  not assessed (nothing completed) · not applicable to this data. */
export type OutcomeState = 'finding' | 'clear' | 'incomplete' | 'not_assessed' | 'not_applicable';
export interface ShownFinding extends Finding { unmapped?: boolean; context?: boolean }
export interface TileRun {
  tone: Tone; state: OutcomeState; label: string; detail: string; findings: ShownFinding[]; facts: [string, string][];
  /** Scope statements: excluded scopes, failed or interrupted checks, planned bounds. Each says which it is. */
  scope: string[]; dim?: boolean; note?: string;
  /** How this module affects the score in this run; replaces the classification-only module note. */
  effect?: string;
}
export type Run = Partial<Record<ModId, TileRun>>;

interface Check { check_id: string; applicability: string; execution: string; scope: string; reason: string | null }

const UNAVAILABLE = 'Unavailable';
const n = (v: unknown) => (typeof v === 'number' ? v.toLocaleString('en-US') : v == null ? UNAVAILABLE : String(v));
const pct = (v: unknown) => (typeof v === 'number' ? `${v}%` : UNAVAILABLE);
const list = (v: unknown) => (Array.isArray(v) ? v.map((x) => (typeof x === 'string' ? x : (x as { name?: string; column?: string })?.name ?? (x as { column?: string })?.column ?? '')).filter(Boolean) : []);
export const date = (iso: string) => { const d = new Date(iso); return Number.isNaN(+d) ? iso : d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }); };

const findingTile = map.findings as Record<string, ModId>;
const checkTiles = map.checks as Partial<Record<ModId, string[]>>;
const reasons = map.reasons as Record<string, string>;
const narrativeOnly = new Set(map.narrative_only);

/** A finding is evidence; "no major issues" is a narrative statement and is never counted as one. */
export const isFinding = (f: { code: string }) => !narrativeOnly.has(f.code);
/** Which tile a canonical finding belongs to, and whether that is an explicit mapping. */
export function tileOf(code: string): { tile: ModId; mapped: boolean } {
  const tile = findingTile[code];
  return tile ? { tile, mapped: true } : { tile: 'reports', mapped: false };
}

/** The tiles a core run's representation covers. Others are drawn dimmed, as in the approved mosaic. */
const UNLABELED: ModId[] = ['score', 'gaps', 'dups', 'outliers', 'local', 'reports'];
const ANNOTATED: ModId[] = ['score', 'gaps', 'dups', 'conflicts', 'outliers', 'local', 'reports'];
const applies: Record<Mode, ModId[]> = {
  classification: ['score', 'gaps', 'dups', 'conflicts', 'imbalance', 'leakage', 'outliers', 'local', 'reports'],
  regression: ['score', 'gaps', 'dups', 'conflicts', 'leakage', 'outliers', 'relations', 'local', 'reports'],
  unlabeled: UNLABELED,
  annotation_classification: ANNOTATED, annotation_regression: ANNOTATED, multilabel_classification: ANNOTATED,
  clustering: UNLABELED, anomaly_detection: UNLABELED, role_profile: UNLABELED,
};
/** An M3 declaration equivalent to a core one runs the core policy; its methodology says which. */
const policyMode: Record<string, Mode> = { classification_legacy_2026_08_13: 'classification', tabular_regression_v1: 'regression', unlabeled_csv_profile_v1: 'unlabeled' };

/** Tiles this run's representation covers, in mosaic order: used for the planned-checks ticker too. */
export const appliesTo = (mode: Mode) => applies[mode];
/** Tiles that say something about this run: every tile except dimmed ones. */
export const activeTiles = (run: Run) => Object.values(run).filter((t) => t && !t.dim).length;
const subOf: Partial<Record<ModId, [string, string]>> = {
  gaps: ['completeness', 'Completeness'], dups: ['uniqueness', 'Uniqueness'], imbalance: ['target_balance', 'Target balance'],
  outliers: ['feature_usability', 'Feature usability'], leakage: ['leakage_risk', 'Name-check sub-score'],
};
const rank = { High: 0, Moderate: 1, Low: 2 } as const;
const value = (v: unknown) => (typeof v === 'object' && v && 'value' in v ? String((v as { value: unknown }).value) : String(v));
const why = (c: Check) => { const r = c.reason ?? ''; return reasons[r] ?? r.replace(/_/g, ' '); };
const where = (c: Check) => (c.scope && c.scope !== 'dataset' ? `${c.scope}: ` : '');

/** The governing guardrail cap: the overall score is capped by the lowest triggered cap. */
export function governingCap(values: { guardrails?: { code: string; cap: number; explanation: string }[] } | null | undefined) {
  if (!values?.guardrails?.length) return null;
  const cap = Math.min(...values.guardrails.map((g) => g.cap));
  return { cap, governing: values.guardrails.filter((g) => g.cap === cap), also: values.guardrails.filter((g) => g.cap !== cap) };
}

/** One tile's outcome from its canonical checks. Precedence: findings first (with any incompleteness kept
 *  alongside); then failed or interrupted checks (incomplete if anything completed, else not assessed);
 *  then completed checks (no finding within the completed scope, naming excluded scopes); then checks
 *  blocked for every scope (not assessed); then not applicable. Excluded scopes (a method precondition such
 *  as zero IQR) are not failures, and planned search bounds never change the state. */
function outcome(checks: Check[]) {
  const status = (c: Check) => [value(c.applicability), value(c.execution)] as const;
  const completed = checks.filter((c) => status(c)[0] === 'applicable' && status(c)[1] === 'completed');
  const failed = checks.filter((c) => status(c)[0] !== 'blocked' && ['failed', 'skipped'].includes(status(c)[1]));
  const blocked = checks.filter((c) => status(c)[0] === 'blocked');
  const notApplicable = checks.filter((c) => status(c)[0] === 'not_applicable');
  const scope = [
    ...failed.map((c) => `${status(c)[1] === 'skipped' ? 'Interrupted' : 'Failed'} · ${where(c)}${c.check_id.replace(/_/g, ' ')}: ${why(c)}`),
    ...blocked.map((c) => `Excluded · ${where(c)}${why(c)}`),
  ];
  const state: OutcomeState = failed.length ? (completed.length ? 'incomplete' : 'not_assessed')
    : completed.length ? 'clear' : blocked.length ? 'not_assessed' : notApplicable.length ? 'not_applicable' : 'not_assessed';
  return { state, scope, completed, failed, blocked, reason: [...failed, ...blocked, ...notApplicable].map(why).find(Boolean) };
}

/** Statements for every canonical check that did not complete: failed, interrupted, or excluded for a scope.
 *  Used by the supervised workflows' pages, whose tiles are built from evidence, so an incomplete check is never silent. */
export function scopeStatements(checks: unknown): string[] {
  const list = Array.isArray(checks) ? (checks as Check[]).filter((c) => c && typeof c === 'object' && 'check_id' in c) : [];
  return [...new Set(outcome(list).scope)];
}

interface Contextual {
  status?: string; reason?: string; findings?: Finding[]; candidates?: { column: string; value: unknown }[];
  interpreted?: Record<string, { applicable_rows?: number; declared_missing_rows?: number; structural_absence_rows?: number; applicable_numeric?: { outlier_count?: number; outlier_rate?: number | null; outlier_unavailable_reason?: string | null } }>;
  prediction?: { objective?: string | null; point?: string | null; declared?: boolean }; availability?: Record<string, string>;
  dependency_search?: { status: string; reason?: string; checks?: unknown[]; unsearched_features?: string[]; flagged?: string[] };
}

/** artifacts: the canonical files that exist now (live job or saved entry), so Reports shows actual states. */
export function fromAnalysis(a: Analysis, declared: Mode, artifacts?: string[]): Run {
  const mode = policyMode[a.methodology_id] ?? declared;
  const p = a.profile as Record<string, unknown> & Analysis['profile'];
  const values = a.scoring.status === 'computed' ? a.scoring.values : null;
  const sub = values?.sub_scores ?? {};
  const checks = ((a as { checks?: Check[] }).checks ?? []);
  const byTile = new Map<ModId, ShownFinding[]>();
  for (const f of (a.findings ?? []).filter(isFinding)) {
    const { tile, mapped } = tileOf(f.code);
    byTile.set(tile, [...(byTile.get(tile) ?? []), mapped ? f : { ...f, unmapped: true }]);
  }
  // Contextual findings (context_v1) follow your declarations and the dependency search; they never change a score.
  const ctx = (a as { contextual?: Contextual }).contextual;
  for (const f of ctx?.findings ?? []) {
    const { tile, mapped } = tileOf(f.code);
    byTile.set(tile, [...(byTile.get(tile) ?? []), { ...f, context: true, ...(mapped ? {} : { unmapped: true }) }]);
  }
  // Numeric feature columns only: the legacy profile also records a 0 rate on text columns, which were never assessed.
  const numeric = p.columns.filter((c) => typeof c.outlier_rate === 'number' && c.is_numeric !== false && c.role !== 'target');
  const topOut = [...numeric].sort((x, y) => (y.outlier_rate ?? 0) - (x.outlier_rate ?? 0))[0];
  const exec = a.execution;
  const search = (a.coverage as { relationship_search?: { status?: string; meaning?: string } }).relationship_search;
  const legacy = a.methodology_id === 'classification_legacy_2026_08_13';
  const parsing = (a as { parsing?: { options?: { missing_policy?: string; na_values?: string[] } } }).parsing?.options;
  const policy = parsing?.missing_policy === 'empty_only' ? 'Empty cells only' : parsing?.missing_policy === 'custom' ? `Custom tokens: ${(parsing.na_values ?? []).join(', ') || 'none'}` : 'pandas default missing tokens';
  const zeroIqr = p.columns.filter((c) => { const q = (c as { numeric_summary?: { q1?: number; q3?: number } }).numeric_summary; return c.role !== 'target' && typeof q?.q1 === 'number' && q.q1 === q.q3; }).map((c) => c.name);
  const usability = (a as { guidance?: { scoring?: { feature_usability?: { contributors: { column: string; rules: { rule: string; points: number }[] }[]; raw_points: number; feature_count: number; sub_score: number } } } }).guidance?.scoring?.feature_usability;
  const classes = (p.target_distribution as { label: string; count: number; percentage: number }[] | undefined) ?? [];
  const limits = Object.entries((exec as { limits?: Record<string, unknown> }).limits ?? {}).filter(([, v]) => v != null);

  const facts: Partial<Record<ModId, [string, string][]>> = {
    score: values ? [['Evidence score', `${values.evidence_score} (mean of ${Object.keys(sub).length} sub-scores)`], ['Governing cap', governingCap(values) ? String(governingCap(values)!.cap) : 'None triggered'], ['Final score', `${values.overall} · ${values.risk_level}`], ['Nature', 'Heuristic review policy, not a validated probability']] : [],
    gaps: [['Missing-value rule', policy], ['Missing cells', n(p.missing_cells)], ['Missing rate', pct(p.missing_rate)], ['Rows with a gap', n(p.missing_feature_row_count)], ['Severely missing columns', list(p.severe_missing_columns).join(', ') || 'None']],
    dups: [['Equality', 'Whole parsed rows, target included; missing equals missing'], ['Duplicate groups', n(p.duplicate_group_count)], ['Repeated rows', n(p.duplicate_rows)], ['Largest group', n(p.largest_duplicate_group_size)], ['Duplicate rate', pct(p.duplicate_rate)]],
    conflicts: mode === 'classification' ? [['Definition', 'Feature-identical rows with more than one non-missing label'], ['Groups', n(p.conflicting_label_group_count)], ['Rows', n(p.conflicting_label_row_count)]] : [],
    imbalance: mode === 'classification' ? [...classes.slice(0, 8).map((c) => [`Class ${c.label}`, `${n(c.count)} · ${c.percentage}%`] as [string, string]), ...(classes.length > 8 ? [['Other classes', `${classes.length - 8} more in the report`] as [string, string]] : []), ['Majority : minority', p.majority_to_minority_ratio == null ? UNAVAILABLE : `${p.majority_to_minority_ratio} : 1`], ['Labelled rows', n(p.labeled_row_count)]] : [],
    leakage: mode === 'classification' ? [['Method', 'Column names only'], ['Review-only prompts', list(p.review_only_leakage_candidates).join(', ') || 'None'], ['Strong candidates', list(p.strong_leakage_candidates).join(', ') || 'None'], ['Not verified', 'When each feature becomes available']]
      : mode === 'regression' ? [['Method', 'Declared availability and bounded relationship search'], ['Not verified', 'Availability of undeclared features']] : [],
    outliers: [['Population', legacy ? 'All rows; non-finite values counted outside the fences' : 'Finite values per column'], ['Numeric columns', n(p.numeric_feature_count)], ['Assessed for IQR candidates', n(numeric.length - (legacy ? zeroIqr.filter((z) => numeric.some((c) => c.name === z)).length : 0))], ['With IQR candidates', n(numeric.filter((c) => (c.outlier_count ?? 0) > 0).length)], ['Highest rate', topOut ? `${topOut.name} · ${topOut.outlier_rate}%` : UNAVAILABLE],
      ...(zeroIqr.length ? [['IQR is zero (fences undefined)', zeroIqr.join(', ')] as [string, string]] : []),
      ...(usability ? [['Usability points', `${usability.raw_points} across ${usability.feature_count} feature${usability.feature_count === 1 ? '' : 's'} → ${usability.sub_score}`] as [string, string], ...usability.contributors.slice(0, 6).map((c) => [c.column, c.rules.map((r) => `${r.rule} · ${r.points}`).join('; ')] as [string, string])] : [])],
    relations: search ? [['Search', String(search.status ?? UNAVAILABLE).replace(/_/g, ' ')], ['Meaning', search.meaning ?? UNAVAILABLE]] : [],
    local: [['Status', String(exec.status ?? UNAVAILABLE)], ['Rows analysed', n(exec.analyzed_rows)], ['Columns', n(exec.analyzed_columns)], ['Elapsed', typeof exec.elapsed_seconds === 'number' ? `${exec.elapsed_seconds.toFixed(2)} s` : UNAVAILABLE], ['Backend', String(exec.backend ?? UNAVAILABLE).replace(/_/g, ' ')],
      ['Materialisation', String((exec as { materialization?: string }).materialization ?? UNAVAILABLE).replace(/_/g, ' ')], ['Configured limits', limits.length ? limits.map(([k, v]) => `${k.replace(/_/g, ' ')} ${n(v)}`).join('; ') : 'None set']],
    reports: [['Methodology', a.methodology_id], ['Schema', a.schema_version], ['Generated', date(a.generated_at)], ['Files', artifactLine(artifacts)], ['Guidance', (a as { guidance?: { version?: string } }).guidance?.version ?? 'Not recorded by this version']],
  };
  for (const [id, [key, label]] of Object.entries(subOf) as [ModId, [string, string]][]) if (key in sub) facts[id] = [...(facts[id] ?? []), [label, n(sub[key])]];
  if (ctx?.status === 'completed') {
    const interpreted = Object.entries(ctx.interpreted ?? {});
    const declaredMissing = interpreted.reduce((t, [, r]) => t + (r.declared_missing_rows ?? 0), 0), structural = interpreted.reduce((t, [, r]) => t + (r.structural_absence_rows ?? 0), 0);
    facts.gaps = [...(facts.gaps ?? []), ['Suggested codes (not applied)', ctx.candidates?.length ? ctx.candidates.slice(0, 4).map((c) => `${c.column} = ${c.value}`).join(', ') + (ctx.candidates.length > 4 ? ` +${ctx.candidates.length - 4}` : '') : 'None'],
      ...(interpreted.length ? [['Declared missing cells', n(declaredMissing)] as [string, string], ['Declared not-applicable cells', n(structural)] as [string, string]] : [])];
    for (const [name, r] of interpreted.slice(0, 3)) {
      const q = r.applicable_numeric;
      if (q) facts.outliers = [...(facts.outliers ?? []), [`${name} · applicable rows`, `${n(r.applicable_rows)}${q.outlier_rate != null ? ` · ${n(q.outlier_count)} outside fences (${q.outlier_rate}%)` : ` · ${String(q.outlier_unavailable_reason ?? 'not assessable').replace(/_/g, ' ')}`}`]];
    }
    const search = ctx.dependency_search;
    facts.leakage = [...(facts.leakage ?? []), ['Prediction point', ctx.prediction?.point ?? ctx.prediction?.objective ?? 'Not declared'],
      ['Availability declared', `${Object.keys(ctx.availability ?? {}).length} columns`],
      ...(search && search.status !== 'not_applicable' ? [['Dependency search', search.status === 'not_assessable' ? `Not assessable: ${search.reason ?? ''}` : `${search.checks?.length ?? 0} features checked${search.unsearched_features?.length ? `, ${search.unsearched_features.length} unsearched` : ''}; ${search.flagged?.length ? `flagged ${search.flagged.join(', ')}` : 'none flagged'}`] as [string, string]] : [])];
  } else if (ctx?.status === 'not_completed') {
    facts.leakage = [...(facts.leakage ?? []), ['Contextual evidence', `Not completed: ${ctx.reason ?? ''}`]];
  }

  // What a check measured when it found nothing to report, from the same profile.
  const quiet: Partial<Record<ModId, string>> = {
    gaps: typeof p.missing_cells === 'number' ? `${n(p.missing_cells)} missing cells under ${policy}; ${pct(p.missing_feature_row_rate)} of rows have a gap. Text such as 'unknown' counts as a value unless declared; its meaning was not assessed.` : undefined,
    dups: typeof p.duplicate_group_count === 'number' ? `${n(p.duplicate_group_count)} groups, ${n(p.duplicate_rows)} repeated rows.` : undefined,
    conflicts: mode === 'classification' ? `${n(p.conflicting_label_group_count)} feature-identical groups disagree.` : undefined,
    imbalance: mode === 'classification' ? `Majority class ${pct(p.majority_class_baseline)}.` : undefined,
    leakage: mode === 'classification' ? `No outcome-like names among ${n(p.feature_count)} features. When each feature becomes available was not verified.`
      : mode === 'regression' ? 'Nothing to review among declared availability and the bounded relationship search. Undeclared features were not verified.' : undefined,
    outliers: topOut ? `Highest IQR rate: ${topOut.name}, ${topOut.outlier_rate}%.${zeroIqr.length ? ` IQR is zero for ${zeroIqr.join(', ')}, so fences are undefined there.` : ''}` : undefined,
  };

  const run: Run = {};
  const tiles = [...applies[mode], ...[...byTile.keys()].filter((t) => !applies[mode].includes(t))]; // every finding stays reachable
  for (const id of tiles) {
    const fs = [...(byTile.get(id) ?? [])].sort((x, y) => rank[x.severity] - rank[y.severity]);
    const key = subOf[id]?.[0], s = key && key in sub ? sub[key] : undefined;
    const critical = (s !== undefined && s <= 50) || fs.some((f) => f.severity === 'High');
    const o = outcome(checks.filter((c) => checkTiles[id]?.includes(c.check_id)));
    const bounds = id === 'relations' && search?.status === 'bounded' ? [`Planned bound · the relationship search is bounded${search.meaning ? `: ${search.meaning}` : ''}`] : [];
    let state: Omit<TileRun, 'findings' | 'facts' | 'scope'>;
    if (id === 'score') {
      const cap = governingCap(values);
      state = values
        ? { state: 'clear', tone: values.guardrails.length ? 'critical' : values.risk_level === 'Low' ? 'clear' : 'finding', label: `${values.overall.toFixed(1)} · ${values.risk_level}`,
            detail: `Evidence ${values.evidence_score}. ${cap ? `Capped at ${cap.cap}: ${cap.governing.map((g) => g.explanation).join(' ')}` : 'No guardrail applied.'}` }
        : a.scoring.status === 'not_defined' || !a.scoring.status
          ? { state: 'not_applicable', tone: 'info', label: 'No score defined', detail: a.scoring.reason ?? 'No validated scoring policy is defined for this kind of data.' }
          : { state: 'not_assessed', tone: 'info', label: 'Not assessed', detail: a.scoring.reason ?? `Scoring ${a.scoring.status.replace(/_/g, ' ')}.` };
    } else if (id === 'local') {
      state = exec.status === 'completed' ? { state: 'clear', tone: 'info', label: typeof exec.elapsed_seconds === 'number' ? `${exec.elapsed_seconds.toFixed(2)} s` : 'Completed', detail: `${n(exec.analyzed_rows)} rows, on this machine. An execution property, not a data check.` }
        : { state: 'incomplete', tone: 'finding', label: 'Partial', detail: 'Analysis incomplete. Completed evidence remains available.' };
    } else if (id === 'reports' && !fs.length) {
      state = { state: 'clear', tone: 'info', label: artifactLine(artifacts), detail: `Canonical report · ${date(a.generated_at)}. Report files, not a data check.` };
    } else if (fs.length) {
      const partly = o.state === 'incomplete' || o.state === 'not_assessed' ? ' · incomplete' : '';
      state = { state: 'finding', tone: critical ? 'critical' : 'finding', label: `${fs[0].severity} priority${fs.length > 1 ? ` · ${fs.length} findings` : ''}${partly}`, detail: fs[0].finding };
    } else if (o.state === 'clear') {
      const excluded = o.blocked.length ? ` Excluded from this check: ${o.blocked.map((c) => (c.scope && c.scope !== 'dataset' ? c.scope : why(c))).join(', ')}.` : '';
      state = { state: 'clear', tone: s !== undefined && s <= 50 ? 'critical' : 'info', label: s !== undefined ? `${subOf[id]![1]} ${s}` : 'No finding',
                detail: `${quiet[id] ?? 'Nothing in the completed scope met this check’s finding threshold.'} No finding within the completed scope.${excluded}` };
    } else if (o.state === 'incomplete') {
      state = { state: 'incomplete', tone: 'finding', label: 'Incomplete', detail: `No finding in the completed part; ${o.failed.length} check${o.failed.length > 1 ? 's' : ''} did not finish, so that part is unknown.` };
    } else if (o.state === 'not_applicable') {
      state = { state: 'not_applicable', tone: 'info', label: 'Not applicable', detail: o.reason ?? 'This check does not apply to this data.', dim: true };
    } else {
      state = { state: 'not_assessed', tone: 'info', label: 'Not assessed', detail: o.reason ? `Not assessed: ${o.reason}.` : 'No check for this module completed in this analysis.' };
    }
    const policyFact: [string, string][] = s !== undefined && s <= 50 ? [['Scoring policy', `${subOf[id]![1]} ${s} ≤ 50 triggers the critical-sub-score guardrail (cap 69)`]] : [];
    const effect = values || !['gaps', 'dups', 'outliers', 'imbalance', 'leakage'].includes(id) ? undefined : 'Evidence only: no score is defined for this task.';
    run[id] = { ...state, findings: fs, facts: [...(facts[id] ?? []), ...policyFact], scope: [...o.scope, ...bounds], ...(effect ? { effect } : {}) };
  }
  return run;
}

/** Which canonical files exist: live job artifacts or a saved entry's. Unknown when the caller cannot say. */
function artifactLine(artifacts?: string[]) {
  if (!artifacts) return 'HTML · JSON · PDF on request';
  const has = (k: string) => artifacts.includes(k);
  return `${has('html') ? 'HTML ready' : 'HTML missing'} · ${has('json') ? 'JSON ready' : 'JSON missing'} · ${has('pdf') ? 'PDF ready' : 'PDF on request'}`;
}

export const m3Label: Record<M3Mode, string> = {
  annotation_classification: 'Classification · annotation expectations', annotation_regression: 'Regression · annotations or multiple outputs',
  multilabel_classification: 'Multilabel binary indicators', clustering: 'Clustering readiness', anomaly_detection: 'Anomaly-detection readiness', role_profile: 'Profiling with explicit roles',
};
export const taskLabel = (a: Analysis, mode: Mode) =>
  mode === 'classification' ? `Classification · ${String(a.profile.classification_subtype ?? '')}` : mode === 'regression' ? `Regression · ${String(a.profile.target ?? '')}`
    : mode === 'unlabeled' ? 'Unlabeled · all columns' : m3Label[mode];
