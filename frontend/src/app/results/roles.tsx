// The approved M4 Roles layout: a role strip with line-kit connectors, then pair and per-source tiles that
// grow into chapters, then the canonical actions and coverage. Every value is read from the canonical JSON.
import type { ReactNode } from 'react';
import type { M4Analysis, M4Finding } from '../api';
import type { Companion, Dashboard } from './model';
import { type Tone } from './adapter';
import { type Tile } from './Tiles';
import { EvidenceTable } from './charts/EvidenceTable';
import { BarList } from './charts/Bars';
import { buildDashboard, base as baseName } from './compositions/common';
import { resolveComposition } from './resolve';
import { ResultsShell, useCompanion } from './shell/ResultsShell';
import { RankMark } from './shell/Ledger';
import { GuidanceFor } from './shell/Interpretation';
import { recordedRank, scoreOf, type Check } from './normalize';

type Dict = Record<string, unknown>;
const SHADES: [string, boolean][] = [['#163F52', true], ['#D5E4EB', false], ['#2C6E8E', true], ['#FBFAF7', false], ['#BCD3DE', false]];
const PAIR_ORDER = ['split_integrity', 'schema', 'populations', 'material_changes', 'segment_mix'];
const SOURCE_ORDER = ['structure', 'repeated_inputs', 'annotations', 'annotation_cohorts', 'segments', 'missingness_structure', 'dependencies', 'constraints', 'unsupervised_readiness', 'multilabel', 'arithmetic_relationships'];
const NAMES: Record<string, string> = {
  split_integrity: 'Overlap', schema: 'Schema', populations: 'Populations', material_changes: 'Material changes (not findings)', segment_mix: 'Segment mix', overlap_row_unions: 'Overlap across roles',
  structure: 'Structure', repeated_inputs: 'Repeated inputs', annotations: 'Annotations', annotation_cohorts: 'Annotation cohorts', segments: 'Segments',
  missingness_structure: 'Missingness structure', dependencies: 'Dependencies', constraints: 'Constraints', unsupervised_readiness: 'Unsupervised readiness',
  multilabel: 'Multilabel', arithmetic_relationships: 'Arithmetic relationships', blocked_alignment: 'Columns not aligned', before_after: 'Before and after',
};
export const M4_MODE_LABEL: Record<string, string> = { splits: 'Split audit', versions: 'Version comparison', advanced: 'Advanced analysis', before_after: 'Before and after preprocessing' };

const n = (v: unknown) => (typeof v === 'number' ? v.toLocaleString('en-US') : v == null ? '—' : String(v));
const pct = (v: unknown) => (typeof v === 'number' ? `${(v * 100).toLocaleString('en-US', { maximumFractionDigits: 1 })}%` : '—');
const arr = (v: unknown) => (Array.isArray(v) ? (v as Dict[]) : []);
const base = (p: string | undefined | null) => (p ? p.split(/[\\/]/).pop() ?? p : '');

export function rolesOf(a: M4Analysis) {
  const sources = (a.profile.sources ?? {}) as Record<string, Dict>;
  if (a.inputs?.length) return a.inputs.map((i) => ({ id: i.id, role: i.role, file: i.dataset.source_filename ?? base(i.dataset.path), rows: sources[i.id]?.row_count, cols: sources[i.id]?.column_count, sha: (sources[i.id]?.source as Dict | undefined)?.sha256 as string | undefined }));
  return [{ id: 'dataset', role: 'dataset', file: a.dataset?.source_filename ?? base(a.dataset?.path), rows: a.profile.row_count, cols: a.profile.column_count, sha: (a.profile.source as Dict | undefined)?.sha256 as string | undefined }];
}

export function runName(a: M4Analysis) {
  return a.context.dataset_name || a.comparison?.dataset_name || M4_MODE_LABEL[a.comparison?.preset ?? a.comparison?.mode ?? 'advanced'];
}

/** Split a measurement key into its scope ('train', 'a:b', 'dataset', 'comparison') and its check. */
function parse(key: string) { const i = key.lastIndexOf('.'); return i < 0 ? { scope: 'dataset', check: key } : { scope: key.slice(0, i), check: key.slice(i + 1) }; }

/** Declared identity units lead; otherwise identical records. */
function overlapLabel(m: Dict) {
  const unit = arr(m.units).find((u) => Number(u.shared_distinct_groups) > 0) ?? arr(m.units)[0];
  return unit ? `${n(unit.shared_distinct_groups)} shared ${(unit.columns as string[]).join(' + ')}` : `${n(((m.records ?? {}) as Dict).shared_distinct_groups)} shared records`;
}

function summary(check: string, m: Dict, role: (id: string) => string, scope: string): { label: string; detail: string; facts: [string, string][] } {
  const [l, r] = scope.split(':').map(role);
  switch (check) {
    case 'split_integrity': {
      const rec = (m.records ?? {}) as Dict, feat = (m.features ?? {}) as Dict, unit = arr(m.units)[0];
      const lead = overlapLabel(m);
      return { label: lead, detail: unit ? `${pct(unit.left_share)} of ${l}, ${pct(unit.right_share)} of ${r}; ${n(rec.shared_distinct_groups)} identical records, ${n(feat.shared_distinct_groups)} identical feature vectors.`
          : `${pct(rec.left_share)} of ${l}, ${pct(rec.right_share)} of ${r}; ${n(feat.shared_distinct_groups)} shared feature vectors.`,
        facts: [...arr(m.units).map((u) => [`Shared ${(u.columns as string[]).join(' + ')} (${u.kind})`, n(u.shared_distinct_groups)] as [string, string]), ['Shared records', n(rec.shared_distinct_groups)], [`${l} rows`, n(rec.left_rows)], [`${r} rows`, n(rec.right_rows)], ['Multiset intersection', n(rec.multiset_intersection)], ['Shared feature vectors', n(feat.shared_distinct_groups)], ['Definition', String(rec.definition ?? '—')]] };
    }
    case 'schema': {
      const add = arr(m.added).length, rem = arr(m.removed).length, ch = arr(m.changes).length;
      return { label: add + rem + ch ? `${add} added · ${rem} removed · ${ch} changed` : 'No change', detail: [...(m.added as string[] ?? []).map((c) => `+${c}`), ...(m.removed as string[] ?? []).map((c) => `−${c}`), ...arr(m.changes).map((c) => `${c.column}: ${c.left_storage ?? '?'} → ${c.right_storage ?? '?'}${c.left_role !== c.right_role ? ` (${c.left_role} → ${c.right_role})` : ''}`)].join(' · ') || `Same columns in ${l} and ${r}.`,
        facts: [['Added', (m.added as string[] ?? []).join(', ') || 'None'], ['Removed', (m.removed as string[] ?? []).join(', ') || 'None'], ['Storage or role changes', n(ch)]] };
    }
    case 'material_changes': {
      const changes = arr(m.changes);
      return { label: `${n(changes.length)} material decrease${changes.length === 1 ? '' : 's'}`, detail: String(m.meaning ?? ''), facts: [] };
    }
    case 'populations': {
      const cols = arr(m.columns), top = [...cols].sort((x, y) => Number(y.cdf_distance ?? 0) - Number(x.cdf_distance ?? 0))[0];
      const review = cols.filter((c) => c.distribution_review || c.missingness_review);
      const t = (m.effect_thresholds ?? {}) as Dict;
      return { label: review.length ? `${review.length} of ${n(cols.length)} columns differ` : `${n(cols.length)} columns, no difference above threshold`,
        detail: top && Number(top.cdf_distance) > 0 ? `Largest CDF distance: ${top.column} (${Number(top.cdf_distance).toPrecision(3)}).` : 'No distribution difference measured.',
        facts: [['Columns compared', n(cols.length)], ['Distribution for review', n(cols.filter((c) => c.distribution_review).length)], ['Missingness for review', n(cols.filter((c) => c.missingness_review).length)],
          ['Review thresholds', `CDF ${n(t.CDF)} · categorical TV ${n(t.categorical_TV)} · W1/IQR ${n(t.W1_reference_IQR)} · missingness ${n(t.missingness)}`], ['Excluded columns', (m.excluded_columns as string[] ?? []).join(', ') || 'None']] };
    }
    case 'annotation_cohorts': {
      const c = arr(m.comparisons), un = arr(m.unsearched).length;
      return { label: `${n(c.length)} cohort comparison${c.length === 1 ? '' : 's'}`, detail: `${un ? `${n(un)} unsearched · ` : ''}stopping: ${String(m.stopping_reason ?? '—').replace(/_/g, ' ')}.`,
        facts: [['Comparisons', n(c.length)], ['Unsearched', n(un)], ['Work · budget', `${n(m.work)} · ${n(m.budget)}`]] };
    }
    case 'overlap_row_unions': {
      const roles = Object.entries(m) as [string, Dict][];
      const rows = roles.flatMap(([id, defs]) => Object.entries(defs).map(([def, v]) => ({ role: role(id), def, affected: Number((v as Dict).affected_rows ?? 0), of: Number((v as Dict).denominator ?? 0) })));
      const worst = [...rows].sort((x, y) => y.affected / Math.max(y.of, 1) - x.affected / Math.max(x.of, 1))[0];
      return { label: worst && worst.affected ? `${n(worst.affected)} of ${n(worst.of)} ${worst.role} rows overlap` : 'No overlapping rows',
        detail: 'Rows that share a record, feature vector, entity or group with another role, per definition.',
        facts: rows.filter((x) => x.of).map((x) => [`${x.role} · ${x.def}`, `${n(x.affected)} of ${n(x.of)}`] as [string, string]) };
    }
    case 'segments': {
      const c = arr(m.comparisons), review = c.filter((x) => x.review || x.candidate_review);
      return { label: `${review.length} of ${n(c.length)} segment comparisons for review`, detail: `Stopping: ${String(m.stopping_reason ?? '—').replace(/_/g, ' ')}.`,
        facts: [['Comparisons', n(c.length)], ['For review', n(review.length)], ['Completed checks · budget', `${n(m.completed_checks)} · ${n(m.budget)}`]] };
    }
    case 'blocked_alignment': {
      const cols = (m.columns as string[] | undefined) ?? [];
      return { label: `${cols.length} column${cols.length === 1 ? '' : 's'} not aligned`, detail: `${cols.join(', ')} · ${String(m.reason ?? '').replace(/_/g, ' ')}.`,
        facts: [['Columns', cols.join(', ') || 'None'], ['Methods that skip them', (m.dependent_methods as string[] ?? []).map((x) => x.replace(/_/g, ' ')).join(', ') || 'None']] };
    }
    case 'before_after': {
      const o = (m.observed ?? {}) as Dict, rows = (o.rows ?? {}) as Dict;
      return { label: `${n(rows.before)} → ${n(rows.after)} rows`, detail: [rows.explanation, m.statement].filter(Boolean).map((x) => String(x).replace(/\.?$/, '.')).join(' '),
        facts: [['Row reconciliation', String(rows.reconciliation ?? '—')], ['Declared transformations', n(arr(m.declared_transformations).length)], ['Declared but not observed', n(arr(o.declared_but_not_observed).length)],
          ['Undeclared changes', n(arr(o.undeclared_changes).length)],
          ['Pipeline use', 'Not observed']] };
    }
    case 'structure': return { label: `${n(m.row_count)} rows · ${n(m.column_count)} columns`, detail: `${n(arr(m.columns).filter((c) => Number(c.missing_count) > 0).length)} columns with missing values.`, facts: [['Rows', n(m.row_count)], ['Columns', n(m.column_count)]] };
    case 'repeated_inputs': return { label: `${n(m.repeated_group_count)} repeated groups`, detail: `${n(m.participating_rows)} participating rows; ${n(m.varying_row_union)} with varying targets.`, facts: [['Distinct input vectors', n(m.distinct_input_vectors)], ['Largest group', n(m.largest_group)]] };
    case 'annotations': { const t = arr(m.targets); return { label: `${n(t.length)} target${t.length === 1 ? '' : 's'}`, detail: t.map((x) => `${x.target}: ${n(x.observed)} observed`).join(' · ') || 'No targets declared.', facts: t.map((x) => [String(x.target), `${n(x.observed)} observed · ${n(x.contradictions)} contradictions`] as [string, string]) }; }
    case 'missingness_structure': return { label: `${n(m.distinct_patterns)} missingness patterns`, detail: `${n(m.review_affected_row_union)} rows in patterns for review.`, facts: [['Retained patterns', n(m.retained_patterns)], ['Unsearched patterns', n(m.unsearched_patterns)]] };
    case 'dependencies': { const p = arr(m.pairs); return { label: `${n(p.filter((x) => x.review).length)} of ${n(p.length)} pairs for review`, detail: p.filter((x) => x.review).map((x) => (x.columns as string[]).join(' ~ ')).slice(0, 3).join(' · ') || 'No dependence above the review threshold.', facts: [['Pairs', n(p.length)]] }; }
    case 'constraints': {
      const d = arr(m.declarations), v = d.reduce((s, x) => s + Number(x.violations ?? 0), 0);
      const rule = (x: Dict) => { const r = (x.declaration ?? {}) as Dict; return `${((r.columns as string[]) ?? []).join(' + ')} ${String(r.rule ?? '')} ${r.value ?? ''}`.trim(); };
      return { label: `${n(m.affected_row_union ?? v)} violating rows`, detail: d.map((x) => `${rule(x)}: ${n(x.violations)}`).slice(0, 2).join(' · ') || 'No requirement declared.',
        facts: d.map((x) => [rule(x), `${n(x.violations)} violating · ${n(x.inconclusive_rows)} inconclusive${x.blocked ? ` · blocked: ${String(x.blocked)}` : ''}`] as [string, string]) };
    }
    case 'unsupervised_readiness': return { label: `${n(arr(m.quantitative_columns).length)} quantitative columns`, detail: `${n(arr(m.excluded_from_geometry).length)} excluded from geometry.`, facts: [['Complete vectors', n(m.complete_quantitative_vectors)]] };
    default: { const lists = Object.entries(m).filter(([, v]) => Array.isArray(v)); return { label: lists.length ? `${n((lists[0][1] as unknown[]).length)} ${lists[0][0].replace(/_/g, ' ')}` : 'Recorded', detail: 'The recorded measurement is in the chapter and the canonical report.', facts: [] }; }
  }
}

/** The first list of records in a measurement, as a sortable, paged evidence table. */
function Table({ m, caption }: { m: Dict; caption: string }) {
  const entry = Object.entries(m).find(([, v]) => Array.isArray(v) && v.length && typeof v[0] === 'object');
  if (!entry) return null;
  return <EvidenceTable rows={entry[1] as Dict[]} caption={`${caption} · ${entry[0].replace(/_/g, ' ')}`} where="the canonical JSON" />;
}

function OverlapViz({ m }: { m: Dict }) {
  const rec = (m.records ?? {}) as Dict, ls = Number(rec.left_share ?? 0), rs = Number(rec.right_share ?? 0);
  return (
    <svg viewBox="0 0 200 60" className="md-viz" preserveAspectRatio="xMidYMax meet">
      <rect x={0} y={8} width={200} height={14} rx={2} className="md-ghost" /><rect x={0} y={8} width={200 * ls} height={14} rx={2} className="md-ink" />
      <rect x={0} y={34} width={200} height={14} rx={2} className="md-ghost" /><rect x={0} y={34} width={200 * rs} height={14} rx={2} className="md-ink" />
    </svg>
  );
}

/** Recorded quantiles (p1, p5, q1, median, q3, p95, p99) of each side on one shared axis per column: left side ghost,
 *  right side ink. With `big`, each row names its column and axis ends. */
function QuantileViz({ m, big }: { m: Dict; big?: boolean }) {
  const cols = arr(m.columns).filter((c) => Array.isArray(c.left_quantiles) && Array.isArray(c.right_quantiles)).slice(0, big ? 8 : 6);
  if (!cols.length) return null;
  const row = big ? 30 : 22, fmt = (v: number) => (Math.abs(v) >= 1000 ? v.toExponential(1) : Number(v.toPrecision(3)).toString());
  return (
    <figure className="ap-chart">
      <svg viewBox={`0 0 200 ${cols.length * row}`} className="md-viz" preserveAspectRatio="xMidYMax meet" role="img" aria-label="Recorded quantiles of each side per column">
        {cols.map((c, i) => {
          const all = [...(c.left_quantiles as number[]), ...(c.right_quantiles as number[])].filter((v) => typeof v === 'number'), lo = Math.min(...all), hi = Math.max(...all), x = (v: number) => (hi > lo ? ((v - lo) / (hi - lo)) * 190 + 5 : 100);
          const y = big ? 10 : 0;
          return (
            <g key={String(c.column)} transform={`translate(0 ${i * row})`}>
              {big && <text x={5} y={7} className="md-t md-t--s">{String(c.column)} · {fmt(lo)} – {fmt(hi)}</text>}
              <line x1={5} x2={195} y1={y + 11} y2={y + 11} className="md-ghost-l" />
              {(c.left_quantiles as number[]).map((v, k) => typeof v === 'number' && <circle key={`l${k}`} cx={x(v)} cy={y + 7} r={2.4} className="md-ghost" />)}
              {(c.right_quantiles as number[]).map((v, k) => typeof v === 'number' && <circle key={`r${k}`} cx={x(v)} cy={y + 15} r={2.4} className="md-ink" />)}
            </g>
          );
        })}
      </svg>
      {big && <figcaption>Recorded quantiles p1, p5, q1, median, q3, p95, p99 · upper row: first role · lower row: second role · each column on its own axis</figcaption>}
    </figure>
  );
}

/** Row identities kept, dropped and added, by the declared key, against the rows before. Without row-level keys, the
 *  recorded row counts alone. */
function Lineage({ m, max }: { m: Dict; max?: number }) {
  const o = (m.observed ?? {}) as Dict, rows = (o.rows ?? {}) as Dict, lin = (m.lineage ?? {}) as Dict, ids = (lin.identities ?? {}) as Dict;
  const before = Number(rows.before ?? 0) || null;
  if (lin.row_level !== false && ids.retained != null)
    return <BarList max={max} scale="denominator" unit="rows" denominator={before} caption={`Row identities by key ${((lin.key as string[]) ?? []).join(' + ')}, against the rows before`}
      bars={[{ label: 'retained', value: Number(ids.retained) }, { label: 'dropped', value: Number(ids.dropped), hot: false }, { label: 'added', value: Number(ids.added) }]} />;
  return <BarList max={max} scale="max" unit="rows" denominator={before} caption={`Rows before and after${lin.row_level_reason ? ` · identities unavailable: ${String(lin.row_level_reason)}` : ''}`}
    bars={[{ label: 'before', value: Number(rows.before) }, { label: 'after', value: Number(rows.after) }]} />;
}

/** Before and after preprocessing: what the data shows changed, set against what was declared. Nothing was performed,
 *  and fewer findings after does not establish improvement. */
function BeforeAfter({ m }: { m: Dict }) {
  const o = (m.observed ?? {}) as Dict, cols = (o.columns ?? {}) as Dict, lin = (m.lineage ?? {}) as Dict;
  const cov = (o.target_coverage ?? null) as Dict | null, risks = (m.remaining_risks ?? {}) as Dict;
  const list = (v: unknown) => ((v as string[] | undefined) ?? []).join(', ') || 'None';
  return <>
    {arr(o.missingness).length > 0 && <EvidenceTable caption="Missing values in declared or changed columns, before and after" rows={arr(o.missingness).map((c) => ({ column: String(c.column), before_missing: (c.before_missing as number) ?? null, after_missing: (c.after_missing as number) ?? null }))} />}
    <dl>{([['Identity reconciliation', lin.identity_reconciliation ? `${String(lin.identity_reconciliation)} · ${lin.identity_reconciles ? 'reconciles' : 'does not reconcile'}` : 'Unavailable without identity keys'],
      ['Columns', `${n(cols.before)} → ${n(cols.after)} · removed ${list(cols.removed)} · added ${list(cols.added)}`], ['Imputation still missing', n(arr(o.declared_imputation_remaining).length)],
      ['Findings still present', list(risks.still_present)], ['New findings', list(risks.new)], ['No longer flagged', list(risks.no_longer_flagged)]] as [string, string][]).map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
    <EvidenceTable caption="Declared transformations" rows={arr(m.declared_transformations).map((t) => ({ kind: String(t.kind ?? '').replace(/_/g, ' '), columns: ((t.columns as string[]) ?? []).join(', ') || null, description: (t.description as string) || null }))} />
    {cov && <EvidenceTable caption={`Target ${String(cov.target ?? '')} by class, before and after`} rows={arr(cov.classes).map((c) => ({ class: String(c.class), before: (c.before as number) ?? null, after: (c.after as number) ?? null, share_change_points: (c.share_change_points as number) ?? null }))} />}
    <p className="nk-ch__not">{String(risks.meaning ?? '')}</p>
  </>;
}

/** Every column of either side: unchanged ghost, added ink, changed ring, removed dashed outline. Coral is not used:
 *  a schema change is a recorded difference, not by itself a finding. */
function SchemaViz({ m }: { m: Dict }) {
  const removed = (m.removed as string[] | undefined) ?? [];
  const order = [...((m.right_order as string[] | undefined) ?? []), ...removed], added = new Set(m.added as string[] ?? []), gone = new Set(removed), changed = new Set(arr(m.changes).map((c) => String(c.column)));
  return (
    <svg viewBox={`0 0 200 ${Math.ceil(Math.max(order.length, 1) / 5) * 16}`} className="md-viz" preserveAspectRatio="xMidYMax meet" role="img" aria-label={`${added.size} added, ${gone.size} removed, ${changed.size} changed of ${order.length} columns`}>
      {order.map((c, i) => <rect key={c} x={(i % 5) * 40 + 1} y={Math.floor(i / 5) * 16 + 2} width={36} height={10} rx={2} className={added.has(c) ? 'md-ink' : changed.has(c) ? 'md-ring' : gone.has(c) ? 'md-ghost-l' : 'md-ghost'} strokeDasharray={gone.has(c) ? '2 2' : undefined} fill={gone.has(c) ? 'none' : undefined} />)}
    </svg>
  );
}

/** Columns ranked by recorded CDF distance; coral only where a finding cites this comparison and the column carries
 *  its own recorded review flag. */
function PopulationBars({ m, cited, max = 6 }: { m: Dict; cited: boolean; max?: number }) {
  const measures = [['cdf_distance', 'CDF distance per quantitative column'], ['total_variation', 'Total variation per categorical column']] as const;
  const lists = measures.map(([key, what]) => [what, [...arr(m.columns)].filter((c) => typeof c[key] === 'number').sort((x, y) => Number(y[key]) - Number(x[key]))
    .map((c) => ({ label: String(c.column), value: Number(Number(c[key]).toFixed(3)), hot: cited && !!c.distribution_review, note: c.distribution_review ? 'review' : undefined }))] as const).filter(([, bars]) => bars.length);
  // The face shows the first measure recorded; the chapter shows each, never mixed in one ranking.
  return <>{(max > 6 ? lists : lists.slice(0, 1)).map(([what, bars]) => <BarList key={what} bounded max={max} scale="denominator" unit="" denominator={1}
    caption={`${what} (0 = identical, 1 = disjoint), largest first`} bars={bars} more="the populations table" />)}</>;
}

/** Recorded missing rate per column, highest first; columns with none are counted, not drawn. */
function MissingBars({ m, max }: { m: Dict; max: number }) {
  const cols = arr(m.columns), gaps = cols.filter((c) => Number(c.missing_count ?? 0) > 0).sort((x, y) => Number(y.missing_rate) - Number(x.missing_rate));
  if (!gaps.length) {
    // Nothing missing: the recorded columns by role instead, so the lead tile still shows this dataset's shape.
    const roles = new Map<string, number>();
    for (const c of cols) roles.set(String(c.role ?? 'unrecorded'), (roles.get(String(c.role ?? 'unrecorded')) ?? 0) + 1);
    return <BarList max={max} scale="denominator" unit="columns" denominator={cols.length || null} caption="Columns by recorded role · no column has a missing value"
      bars={[...roles].sort((x, y) => y[1] - x[1]).map(([label, value]) => ({ label, value }))} />;
  }
  return <BarList max={max} scale="percent" unit="%" denominator={100} caption={`Missing rate per column, ${n(gaps.length)} of ${n(cols.length)} columns with missing values`}
    bars={gaps.map((c) => ({ label: String(c.column), value: Number(c.missing_rate) }))} more="the structure table" />;
}

function StructureViz({ m }: { m: Dict }) {
  const cols = arr(m.columns).slice(0, 24), W = 196, bw = W / Math.max(cols.length, 1);
  return (
    <svg viewBox="0 0 196 60" className="md-viz" preserveAspectRatio="xMidYMax meet">
      {cols.map((c, i) => { const h = 6 + 50 * Number(c.missing_rate ?? 0) / 100; return <rect key={i} x={i * bw + 1} y={58 - h} width={bw - 2} height={h} className={Number(c.missing_count) > 0 ? 'md-ink' : 'md-ghost'} />; })}
    </svg>
  );
}

/** Role frames joined by line-kit connectors; coral where a finding for that pair is High or a declared violation. */
function RolesViz({ roles, links, big }: { roles: { role: string; file: string }[]; links: { hot: boolean; text: string }[]; big?: boolean }) {
  const W = 300, H = big ? 170 : 130, k = roles.length, gap = k > 1 ? (W - 20 - k * 96) / (k - 1) : 0, x = (i: number) => 10 + i * (96 + gap), y = H / 2 - 34;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="md-viz" preserveAspectRatio="xMidYMid meet">
      {links.map((l, i) => (
        <g key={i}>
          <line x1={x(i) + 96} x2={x(i + 1)} y1={y + 34} y2={y + 34} className={l.hot ? 'md-cap' : 'md-ghost-l'} />
          <circle cx={x(i) + 96} cy={y + 34} r={3} className={l.hot ? 'md-hot' : 'md-ink'} /><circle cx={x(i + 1)} cy={y + 34} r={3} className={l.hot ? 'md-hot' : 'md-ink'} />
          {big && <text x={(x(i) + 96 + x(i + 1)) / 2} y={y + 26} className="md-t md-t--c md-t--s">{l.text}</text>}
        </g>
      ))}
      {roles.map((r, i) => (
        <g key={i} transform={`translate(${x(i)} ${y})`} className="md-grow" style={{ ['--i' as string]: i }}>
          <rect width={96} height={68} rx={4} className="md-page" />
          <rect width={96} height={6} rx={2} className="md-ink" />
          <text x={8} y={26} className="md-t">{r.role}</text>
          {big && <text x={8} y={44} className="md-t md-t--s">{r.file.length > 14 ? `${r.file.slice(0, 13)}…` : r.file}</text>}
        </g>
      ))}
    </svg>
  );
}

/** Signed change with its direction (m4_local_2026_11_25): a decrease beyond the threshold is a material change, not a defect. */
function direction(c: Dict, measure: 'missingness' | 'nonfinite'): string {
  const d = String(c[`${measure}_direction`] ?? 'none'), pts = (100 * Number(c[`${measure}_magnitude`] ?? 0)).toFixed(1);
  return d === 'none' ? 'no change' : `${d === 'increase' ? '↑' : '↓'} ${pts} pts${c[`${measure}_material_decrease`] ? ' · material change' : ''}`;
}

const VIZ: Record<string, (p: { m: Dict }) => ReactNode> = { split_integrity: OverlapViz, populations: QuantileViz, schema: SchemaViz, structure: StructureViz };

export function RolesReport({ a, out, onOpen, presentation, saved }: { a: M4Analysis; out: ReactNode; onOpen: (anchor?: string) => void; presentation: string | null; saved?: boolean }) {
  const companion = useCompanion(presentation);
  if (companion === undefined) return <div className="ap-rs"><div className="nk-mosaic nk-mosaic--big nk-mosaic--run ap-rs__wait" aria-busy="true" /></div>;
  const d = m4Dashboard(a, companion, !!saved);
  return <ResultsShell d={d} label={d.composition === 'comparison' ? 'Comparison checks' : 'Advanced analysis checks'} out={out} onOpenReport={onOpen} live={!saved} />;
}

/** The comparison (splits, versions, before and after) or advanced single-dataset dashboard, from recorded values only. */
export function m4Dashboard(a: M4Analysis, companion: Companion | null, saved: boolean): Dashboard {
  const roles = rolesOf(a);
  const role = (id: string) => roles.find((r) => r.id === id)?.role ?? id;
  const scopeLabel = (scope: string) => (scope.includes(':') ? scope.split(':').slice(0, 2).map(role).join(' ↔ ') : scope === 'comparison' ? 'all roles' : role(scope));
  const checkOf = new Map(a.evidence.map((e) => [e.id, e.check_id]));
  const byCheck = new Map<string, M4Finding[]>();
  for (const f of a.findings) for (const ref of f.evidence_refs ?? []) { const k = checkOf.get(ref); if (k) byCheck.set(k, [...(byCheck.get(k) ?? []), f]); }
  const rank = { High: 0, Moderate: 1, Low: 2 } as const;
  const keys = Object.keys(a.coverage.measurements).filter((k) => parse(k).scope.split(':').length <= 2);
  const order = (k: string) => { const { scope, check } = parse(k); const pair = scope.includes(':'); const roleIdx = roles.findIndex((r) => r.id === scope.split(':')[0]);
    return [pair ? 0 : scope === 'comparison' ? 1 : 2, pair ? PAIR_ORDER.indexOf(check) : roleIdx, pair ? 0 : SOURCE_ORDER.indexOf(check)]; };
  keys.sort((x, y) => { const a1 = order(x), b1 = order(y); return a1[0] - b1[0] || a1[1] - b1[1] || a1[2] - b1[2]; });

  const tiles: Tile[] = keys.map((key, i) => {
    const { scope, check } = parse(key), m = a.coverage.measurements[key], diag = a.coverage.diagnostics[key];
    const fs = [...(byCheck.get(key) ?? [])].sort((x, y) => rank[x.priority] - rank[y.priority]);
    const s = summary(check, m, role, scope);
    const tone: Tone = fs.some((f) => f.priority === 'High' || f.evidence_type === 'declared_violation') ? 'critical' : fs.length ? 'finding' : 'info';
    const label = fs.length ? `${fs[0].priority} · ${fs[0].evidence_type === 'declared_violation' ? 'declared requirement violated' : `${fs.length} finding${fs.length === 1 ? '' : 's'}`}` : diag && diag.status !== 'completed' ? diag.status.replace(/_/g, ' ') : s.label;
    const detail = fs.length ? fs[0].title : s.detail;
    const [bg, light] = scope.includes(':') ? SHADES[i % 3] : SHADES[3 + (i % 2)];
    const V = VIZ[check];
    return {
      id: key, name: NAMES[check] ?? check.replace(/_/g, ' '), n: String(i + 2).padStart(2, '0'), kicker: scopeLabel(scope), bg, light, wide: scope.includes(':'), tone, label, detail,
      viz: check === 'populations' ? <PopulationBars m={m} cited={fs.length > 0} /> : V ? <V m={m} /> : undefined,
      bigViz: check === 'populations' ? <><PopulationBars m={m} cited={fs.length > 0} max={16} /><QuantileViz m={m} big /></> : undefined,
      chapter: (
        <>
          <h3>{NAMES[check] ?? check}</h3>
          <div className="nk-ch__run"><span>{scopeLabel(scope)}</span><b>{fs.length ? `${fs.length} finding${fs.length > 1 ? 's' : ''}` : s.label}</b><p>{s.detail}</p></div>
          {fs.map((f) => (
            <div key={f.id} className="nk-ch__f" data-ref={f.id}>
              <b>{f.title} <RankMark rank={recordedRank(f as unknown as Dict)} /></b>
              <p>{f.next_action}{f.affected_count != null ? ` ${n(f.affected_count)} affected${f.denominator ? ` of ${n(f.denominator)} rows` : ''}.` : ''}</p>
              <p className="nk-ch__lim">{f.limitations}</p>
              <GuidanceFor refKey={f.id} />
            </div>
          ))}
          {!!s.facts.length && <dl>{s.facts.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>}
          {check === 'populations'
            ? <EvidenceTable caption="Columns compared" where="the report’s populations table" rows={arr(m.columns).map((c) => ({ column: String(c.column), cdf_distance: typeof c.cdf_distance === 'number' ? Number(Number(c.cdf_distance).toFixed(3)) : null,
                total_variation: typeof c.total_variation === 'number' ? Number(Number(c.total_variation).toFixed(3)) : null,
                normalized_w1: typeof c.normalized_wasserstein === 'number' ? Number(Number(c.normalized_wasserstein).toFixed(3)) : null, median_shift: (c.median_shift as number) ?? null,
                missingness_change: (c.missingness_change as number) ?? null, ...(c.missingness_direction ? { missingness_direction: direction(c, 'missingness') } : {}),
                distribution_review: !!c.distribution_review, missingness_review: !!c.missingness_review }))} />
            : check === 'before_after' ? <BeforeAfter m={m} /> : <Table m={m} caption={NAMES[check] ?? check} />}
          {diag && <p className="nk-ch__not">{diag.status.replace(/_/g, ' ')} · {diag.population}{diag.unsearched_scope ? ` · ${n(diag.unsearched_scope)} unsearched` : ''}</p>}
        </>
      ),
    };
  });

  const pairFinding = (x: string, y: string) => a.findings.filter((f) => f.scope === `${x}:${y}` || f.scope === `${y}:${x}`);
  const integrity = (x: string, y: string) => (a.coverage.measurements[`${x}:${y}.split_integrity`] ?? a.coverage.measurements[`${y}:${x}.split_integrity`]) as Dict | undefined;
  const schema = (x: string, y: string) => (a.coverage.measurements[`${x}:${y}.schema`] ?? a.coverage.measurements[`${y}:${x}.schema`]) as Dict | undefined;
  const links = roles.slice(0, -1).map((r, i) => {
    const next = roles[i + 1], si = integrity(r.id, next.id), sc = schema(r.id, next.id);
    const hot = pairFinding(r.id, next.id).some((f) => f.priority === 'High' || f.evidence_type === 'declared_violation');
    return { hot, text: `${si ? overlapLabel(si) : sc ? `${arr(sc.added).length + arr(sc.removed).length + arr(sc.changes).length} schema changes` : 'compared'}${hot ? ' · review' : ''}` };
  });
  const intent = a.comparison?.evaluation_intent && a.comparison.evaluation_intent !== 'unknown'
    ? `Declared intent: ${a.comparison.evaluation_intent.replace(/_/g, ' ')}${a.comparison.identity_keys?.length ? ` · identity keys ${a.comparison.identity_keys.map((k) => k.join(' + ')).join('; ')}` : ''}` : null;
  const pairFindings = a.findings.filter((f) => f.scope.includes(':')).sort((x, y) => rank[x.priority] - rank[y.priority]);
  const mode = M4_MODE_LABEL[a.comparison?.preset ?? a.comparison?.mode ?? 'advanced'];
  const hero: Tile = {
    id: 'roles', hero: true, name: 'Roles', n: '01', kicker: mode, bg: '#163F52', light: true,
    tone: links.some((l) => l.hot) ? 'critical' : pairFindings.length ? 'finding' : 'info',
    label: `${roles.length} role${roles.length === 1 ? '' : 's'}`,
    detail: intent ?? (roles.length > 1 ? 'No evaluation intent declared.' : 'One dataset, analysed on its own.'),
    viz: <RolesViz roles={roles} links={links} />, bigViz: <RolesViz roles={roles} links={links} big />,
    chapter: (
      <>
        <h3>Roles</h3>
        <div className="nk-ch__run"><span>{mode}</span><b>{roles.map((r) => r.role).join(' · ')}</b><p>{intent ?? 'No evaluation intent declared.'}</p></div>
        <ul className="ap-rolecards">
          {roles.map((r, i) => (
            <li key={r.id}>
              <span className="ap-strip__role">{r.role}</span><b>{r.file}</b><span>{n(r.rows)} rows · {n(r.cols)} columns{r.sha ? ` · ${r.sha.slice(0, 16)}…` : ''}</span>
              {links[i] && <em className={links[i].hot ? 'is-hot' : ''}>↓ {links[i].text}</em>}
            </li>
          ))}
        </ul>
        {pairFindings.map((f) => (
          <div key={f.id} className="nk-ch__f" data-ref={f.id}><b>{f.title} <RankMark rank={recordedRank(f as unknown as Dict)} /></b><p>{scopeLabel(f.scope)} · {f.next_action}</p><p className="nk-ch__lim">{f.limitations}</p><GuidanceFor refKey={f.id} /></div>
        ))}
      </>
    ),
  };
  const score = scoreOf(a as unknown as Dict);
  const scored: Tile[] = score ? [{
    id: 'standalone-score', name: 'Classification score', n: String(tiles.length + 2).padStart(2, '0'), kicker: 'existing policy', bg: '#FBFAF7', light: false, tone: 'info',
    label: `${score.overall} · ${score.risk_level}`, detail: 'Existing classification policy, scoped to this parsed dataset.',
    chapter: <><h3>Classification score</h3><div className="nk-ch__run"><span>Standalone, from the existing classification policy</span><b>{score.overall} · {score.risk_level}</b><p>{String((a.scoring as Dict).interpretation ?? 'Scoped to this parsed dataset. Comparisons themselves have no composite score.')}</p></div></>,
  }] : [];
  const { composition, variant } = resolveComposition(a as unknown as Dict);
  // Before and after: the lineage of the rows leads; the roles become an ordinary tile.
  // A single dataset: its structure leads, as the one role needs no diagram.
  const lead = variant === 'before_after' ? tiles.find((t) => t.id.endsWith('.before_after'))
    : composition === 'structure' ? tiles.find((t) => t.id === `${roles[0]?.id}.structure`) : undefined;
  if (lead) {
    const m = a.coverage.measurements[lead.id];
    if (variant === 'before_after') {
      const rows = (((m.observed ?? {}) as Dict).rows ?? {}) as Dict;
      Object.assign(lead, { label: `${n(rows.before)} → ${n(rows.after)} rows`, detail: String(rows.explanation ?? rows.reconciliation ?? ''), viz: <Lineage m={m} /> });
    } else Object.assign(lead, { viz: <MissingBars m={m} max={8} />, bigViz: <MissingBars m={m} max={24} /> });
    Object.assign(lead, { hero: true, wide: false, bg: '#163F52', light: true });
    Object.assign(hero, { hero: false, wide: roles.length > 1 });
  }
  const all = lead ? [lead, hero, ...tiles.filter((t) => t !== lead), ...scored] : [hero, ...tiles, ...scored];
  const tileOf = (f: Dict) => { const key = ((f.evidence_refs as string[] | undefined) ?? []).map((r) => checkOf.get(r)).find((k) => k && keys.includes(k)); return key ?? 'roles'; };
  const bounded = Object.entries(a.coverage.diagnostics).filter(([, d]) => (d.unsearched_scope ?? 0) > 0 || /bound/.test(d.status))
    .map(([k, d]) => ({ text: `${scopeLabel(parse(k).scope)} · ${NAMES[parse(k).check] ?? parse(k).check.replace(/_/g, ' ')}${d.unsearched_scope ? `: ${n(d.unsearched_scope)} unsearched` : ''}`, reason: d.population }));
  // Recorded check outcomes (failed, interrupted, blocked) come from the checks; worded with their roles here.
  const checkName = (c: Check) => { const { scope, check } = c.id.includes('.') ? parse(c.id) : { scope: c.scope, check: c.id };
    return `${NAMES[check] ?? check.replace(/_/g, ' ')}${scope && scope !== 'dataset' ? ` · ${scopeLabel(scope)}` : ''}`; };
  return buildDashboard(a as unknown as Dict, companion, {
    composition, variant: mode, saved,
    identity: { name: runName(a), sources: roles.map((r) => baseName(r.file)).join(' ↔ '), workflow: composition === 'comparison' ? 'Comparison' : 'Advanced analysis', variant: mode,
                when: a.generated_at, methodology: a.methodology_id, schema: a.schema_version, scale: `${roles.length} role${roles.length === 1 ? '' : 's'}` },
    statement: a.narrative?.summary || undefined, tiles: all, tileOf,
    extract: (f) => ({ scope: scopeLabel(String(f.scope ?? '')), statement: String(f.next_action ?? '') || undefined, limitations: String(f.limitations ?? '') || undefined,
                       nextAction: f.affected_count != null ? `${n(f.affected_count)} affected${f.denominator ? ` of ${n(f.denominator)} rows` : ''}` : undefined }),
    coverage: { bounded }, checkName,
  });
}
