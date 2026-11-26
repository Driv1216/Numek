// Read the workflows' differing field spellings without changing what they mean: finding identity (code | id), rank
// (severity | priority, or the text and image evidence meaning, kept a different kind), checks (check_id | id, plain or
// {value}), scoring (computed | available → scored) and run status. Nothing here creates evidence.
import type { Companion, Coverage, CoverageItem, LedgerFinding, Rank, ResultState } from './model';

type Doc = Record<string, unknown>;
const NARRATIVE_ONLY = new Set(['no_major_issues']);
const PRIORITY: Record<string, number> = { high: 0, moderate: 1, low: 2 };
const MEANING: Record<string, number> = { deterministic_violation: 0, contextual_observation: 1, heuristic_candidate: 2, model_assisted_candidate: 3 };
const words = (s: unknown) => String(s ?? '').replace(/_/g, ' ');
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
const value = (v: unknown) => (v && typeof v === 'object' && 'value' in (v as Doc) ? String((v as Doc).value) : String(v ?? ''));
export const SCORE_LINE = /\b(composite|universal|overall)\b[^.]*\bscor(?:e|ing)\b|\b(no|not)\b[^.]*\bscor(?:e|ing)\b/i;
/** Recorded statements as a list: some workflows record one string, others a list. */
const lines = (v: unknown): string[] => (Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string' && !!x) : typeof v === 'string' && v ? [v] : []);
const text = (v: unknown) => (Array.isArray(v) ? v.filter(Boolean).map(String).join(' ') : typeof v === 'string' ? v : '');

/** The canonical findings that are findings: "no major issues" is a narrative statement, never one. */
export function canonicalFindings(a: Doc): { index: number; f: Doc }[] {
  return ((a.findings as Doc[] | undefined) ?? []).map((f, index) => ({ index, f })).filter(({ f }) => f && typeof f === 'object' && !NARRATIVE_ONLY.has(String(f.code)));
}

/** The recorded rank. Text and image findings record an evidence meaning, never a priority. */
export function recordedRank(f: Doc): Rank {
  const raw = String(f.priority ?? f.severity ?? '');
  if (!raw && f.meaning) {
    const m = String(f.meaning);
    return { kind: 'evidence_meaning', value: m, label: cap(words(m)), order: MEANING[m] ?? 4 };
  }
  return { kind: 'priority', value: cap(raw.toLowerCase()), label: cap(raw.toLowerCase()), order: PRIORITY[raw.toLowerCase()] ?? 3 };
}

export type Extract = (f: Doc) => Partial<Pick<LedgerFinding, 'scope' | 'statement' | 'nextAction' | 'limitations'>>;

/** The canonical wording every workflow records, under its own field names. */
export const defaultExtract: Extract = (f) => ({
  statement: text(f.finding) || undefined,
  nextAction: text(f.recommendation) || text(f.next_action) || text(f.action) || undefined,
  limitations: text(f.limitations) || undefined,
  scope: [f.scope, f.population, f.measurement, ...(Array.isArray(f.source_ids) ? f.source_ids : [])].filter((x) => typeof x === 'string' && x).map(words).join(' · ') || undefined,
});

/** Every finding, in recorded rank order (priorities High → Low, stable; evidence meanings keep the report's order),
 *  with the companion's report names and verified locators when it is available. */
export function ledger(a: Doc, companion: Companion | null, tileOf: (f: Doc, index: number) => string | null = () => null, extract: Extract = defaultExtract): LedgerFinding[] {
  const named = new Map((companion?.findings ?? []).map((c) => [c.index, c]));
  const rows = canonicalFindings(a).map(({ index, f }) => {
    const c = named.get(index);
    const title = c?.title || String(f.title ?? '') || [f.family, f.meaning].filter(Boolean).map(words).join(' · ') || String(f.code ?? f.id ?? 'Finding');
    return { index, ref: String(f.id ?? f.code ?? '') || null, title, rank: c?.rank ?? recordedRank(f), tile: tileOf(f, index),
             locator: c?.locator ?? { kind: 'none' as const, value: null, reason: 'the report could not be read for this result' }, ...extract(f) };
  });
  const contextual = (((a.contextual as Doc | undefined)?.findings as Doc[] | undefined) ?? []).map((f, i) => ({
    index: 10000 + i, ref: String(f.code ?? ''), title: String(f.title ?? f.code ?? ''), rank: recordedRank(f), tile: tileOf(f, 10000 + i), context: true,
    locator: { kind: 'none' as const, value: null, reason: 'contextual findings are listed in the report’s declarations section' }, ...extract(f) }));
  const all = [...rows, ...contextual];
  return all.every((r) => r.rank.kind === 'priority') ? [...all].sort((x, y) => x.rank.order - y.rank.order) : all;
}

export interface Check { id: string; applicability: string; execution: string; scope: string; reason: string | null }

/** Checks under one shape: core and M3/M4 `check_id`; temporal `t<n>:<family>`; text, image and records `id`/`family`. */
export function checksOf(a: Doc): Check[] {
  return ((a.checks as Doc[] | undefined) ?? []).filter((c) => c && typeof c === 'object').map((c) => ({
    id: String(c.check_id ?? c.family ?? c.id ?? 'check'), applicability: value(c.applicability || 'applicable'), execution: value(c.execution || 'completed'),
    scope: String(c.scope ?? 'dataset'), reason: (c.reason as string | null) ?? null,
  }));
}

const REASONS: Record<string, string> = {
  zero_iqr: 'the middle half has no spread (IQR is zero), so no fences exist',
  floating_resolution: 'values are too close to floating-point resolution to resolve',
  zero_applicable_population: 'nothing in this data was eligible for the check',
};
const why = (r: string | null) => (r ? REASONS[r] ?? words(r) : '');
const label = (c: Check) => `${words(c.id.replace(/^t\d+:/, ''))}${c.scope && !['dataset', 'population', 'full_population'].includes(c.scope) ? ` · ${words(c.scope)}` : ''}`;

/** The recorded reason this workflow has no overall score, once. Null where a score was computed. */
export function noScoreNote(a: Doc, companion: Companion | null): CoverageItem | null {
  const scoring = a.scoring as Doc | undefined;
  if (scoring && ['computed', 'available'].includes(String(scoring.status))) return null;
  const concept = companion?.concepts.find((c) => c.id === 'no_score');
  const recorded = lines((a.narrative as Doc | undefined)?.limitations).find((l) => SCORE_LINE.test(l));
  const reason = (scoring?.reason as string | null) ?? recorded ?? concept?.definition ?? null;
  return { text: 'No overall score', reason: reason ?? 'This workflow records evidence and review findings; it defines no overall score.' };
}

/** The coverage ledger from canonical checks, preferring the analysis's own recorded scope statements
 *  (finding_guidance_v1) where they exist. Bounds, opt-ins and methodology notes come from the composition. */
/** `name` words a recorded check for the ledger; compositions whose check ids carry their scope (M4) pass their own. */
export function coverage(a: Doc, companion: Companion | null, extra: Partial<Coverage> = {}, name: (c: Check) => string = label): Coverage {
  const checks = checksOf(a);
  const recorded = ((a.guidance as Doc | undefined)?.scope as Doc | undefined)?.not_completed as Doc[] | undefined;
  // guidance.scope.not_completed records excluded checks (a method precondition, e.g. zero IQR) next to failed,
  // interrupted and not-assessed ones; only the latter leave part of the analysis incomplete.
  const statement = (c: Doc) => ({ text: `${cap(String(c.state))} · ${name({ id: String(c.check), scope: String(c.scope ?? 'dataset'), applicability: '', execution: '', reason: null })}`, reason: why((c.reason as string) ?? null) });
  const notCompleted: CoverageItem[] = recorded?.length
    ? recorded.filter((c) => String(c.state) !== 'excluded').map(statement)
    : checks.filter((c) => c.applicability !== 'blocked' && ['failed', 'skipped'].includes(c.execution))
        .map((c) => ({ text: `${c.execution === 'skipped' ? 'Interrupted' : 'Failed'} · ${name(c)}`, reason: why(c.reason) }));
  const excluded = recorded?.length
    ? recorded.filter((c) => String(c.state) === 'excluded').map(statement)
    : checks.filter((c) => c.applicability === 'blocked').map((c) => ({ text: `Excluded · ${name(c)}`, reason: why(c.reason) }));
  const notApplicable = checks.filter((c) => c.applicability === 'not_applicable').map((c) => ({ text: name(c), reason: why(c.reason) }));
  const note = noScoreNote(a, companion);
  const completed = checks.filter((c) => c.applicability === 'applicable' && c.execution === 'completed').length;
  return {
    notCompleted: [...notCompleted, ...(extra.notCompleted ?? [])], bounded: extra.bounded ?? [], excluded: [...excluded, ...(extra.excluded ?? [])],
    notApplicable: [...notApplicable, ...(extra.notApplicable ?? [])], notRequested: extra.notRequested ?? [],
    methodology: [...(note ? [note] : []), ...(extra.methodology ?? [])],
    completed: extra.completed ?? (checks.length ? `${completed.toLocaleString('en-US')} of ${checks.length.toLocaleString('en-US')} recorded checks completed` : undefined),
  };
}

/** One state per page. A clean result is never confused with an incomplete one. */
export function resultState(a: Doc, findings: number, cov: Coverage, saved: boolean): ResultState {
  const run = String((a.execution as Doc | undefined)?.status ?? 'completed') === 'partial' ? 'partial' : 'completed';
  const historical = [
    ...(Array.isArray(a.checks) ? [] : ['check outcomes']),
    ...(a.guidance ? [] : ['scope statements (finding guidance)']),
  ];
  return { run, findings, bounded: cov.bounded.length > 0, saved, chip: run === 'partial' || cov.notCompleted.length ? 'partial' : findings ? 'findings' : 'clean', historical };
}

/** The recorded scope conclusion and open questions (finding_guidance_v1), or the narrative's limitations. */
export function unknowns(a: Doc): string[] {
  const scope = (a.guidance as Doc | undefined)?.scope as Doc | undefined;
  const fromScope = lines(scope?.unknowns);
  const fromNarrative = lines((a.narrative as Doc | undefined)?.limitations);
  // A recorded "no score" line is stated once, in the coverage ledger's methodology group (noScoreNote).
  return [...new Set([...fromScope, ...fromNarrative].filter((x) => typeof x === 'string' && x && !SCORE_LINE.test(x)))];
}

export const scoreOf = (a: Doc) => {
  const s = a.scoring as Doc | undefined;
  return s && ['computed', 'available'].includes(String(s.status)) ? (s.values as { overall: number; risk_level: string } | null) : null;
};
