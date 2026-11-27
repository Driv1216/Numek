// Tiles every tabular composition shares (classification, dataset profile; regression and M3 in Stage 3): missing
// values, repeated rows, column variation, numeric evidence, the columns ledger and parsing review. Each reads recorded
// profile fields only, states its denominator, and lists the findings routed to it with the same data-ref the ledger uses.
import type { ReactNode } from 'react';
import { BarList, ProportionBar } from '../charts/Bars';
import { EvidenceTable } from '../charts/EvidenceTable';
import { RankMark } from '../shell/Ledger';
import { GuidanceFor } from '../shell/Interpretation';
import { SCORE_LINE, canonicalFindings, recordedRank } from '../normalize';
import type { Tile } from '../Tiles';
import type { Tone } from '../adapter';
import routes from '../finding-routes.json';

export type Doc = Record<string, unknown>;
export interface Column {
  name: string; role?: string; dtype?: string; is_numeric?: boolean; missing_count?: number; missing_rate?: number; unique_count?: number; unique_rate?: number;
  constant?: boolean; near_constant?: boolean; high_cardinality?: boolean; top_value?: string | null; top_value_rate?: number; top_value_hidden?: boolean;
  outlier_count?: number | null; outlier_rate?: number | null; outlier_denominator?: number | null; outlier_unavailable_reason?: string | null;
  numeric_summary?: { q1?: number; q3?: number; min?: number; max?: number; median?: number } | null;
}

export const SHADE = { deep: ['#163F52', true], blue: ['#2C6E8E', true], pale: ['#D5E4EB', false], mist: ['#BCD3DE', false], card: ['#FBFAF7', false] } as const;
export const n = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) ? v.toLocaleString('en-US') : 'Unavailable');
export const pct = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) ? `${v.toLocaleString('en-US')}%` : 'Unavailable');
const words = (s: unknown) => String(s ?? '').replace(/_/g, ' ');

/** The composition's explicit route for a finding code; findings no route names go to "Other findings". */
export function routeOf(composition: keyof typeof routes, f: Doc): string {
  const map = routes[composition] as Record<string, string>;
  return map[String(f.code)] ?? 'other';
}

/** The recorded statement the outcome band leads with. Where no score is defined, a sentence about scoring is left to
 *  the coverage ledger's methodology group, so the reason is stated once. */
export function statementOf(a: Doc, scored: boolean): string | undefined {
  const nv = (a.narrative as Doc | undefined) ?? {};
  const lines = [nv.overall_assessment, nv.principal_evidence_summary].filter((x): x is string => typeof x === 'string' && !!x);
  return scored ? lines[0] : lines.find((l) => !SCORE_LINE.test(l));
}

/** Findings routed to a tile, as chapter blocks the ledger can focus. */
export function FindingBlocks({ a, tile, route }: { a: Doc; tile: string; route: (f: Doc) => string }) {
  const contextual = ((a.contextual as Doc | undefined)?.findings as Doc[] | undefined) ?? [];
  const list = canonicalFindings(a).map(({ f }) => f).concat(contextual).filter((f) => route(f) === tile);
  return <>{list.map((f, i) => (
    <div key={`${String(f.code)}:${i}`} className="nk-ch__f" data-ref={String(f.code ?? f.id ?? '')}>
      <b>{String(f.title ?? words(f.code))} <RankMark rank={recordedRank(f)} /></b>
      {typeof f.finding === 'string' && <p>{f.finding}</p>}
      {typeof f.evidence === 'string' && f.evidence && <p>{f.evidence}</p>}
      {typeof f.recommendation === 'string' && <p>{f.recommendation}</p>}
      {typeof f.score_effect === 'string' && f.score_effect && <span className="nk-ch__eff">{f.score_effect}</span>}
      <GuidanceFor refKey={String(f.id ?? f.code ?? '')} context={contextual.includes(f)} />
    </div>
  ))}</>;
}

export function Facts({ rows }: { rows: [string, ReactNode][] }) {
  return <dl>{rows.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>;
}

/** Tone from routed findings only: High is critical, any other finding is a finding, none is informational. */
export function toneOf(a: Doc, tile: string, route: (f: Doc) => string): { tone: Tone; count: number; top?: Doc } {
  const contextual = ((a.contextual as Doc | undefined)?.findings as Doc[] | undefined) ?? [];
  const fs = [...canonicalFindings(a).map(({ f }) => f), ...contextual].filter((f) => route(f) === tile);
  const ranked = [...fs].sort((x, y) => recordedRank(x).order - recordedRank(y).order);
  return { tone: fs.some((f) => String(f.severity).toLowerCase() === 'high') ? 'critical' : fs.length ? 'finding' : 'info', count: fs.length, top: ranked[0] };
}

function faceOf(a: Doc, tile: string, route: (f: Doc) => string, quiet: string) {
  const t = toneOf(a, tile, route);
  return { tone: t.tone, label: t.count ? `${t.count} finding${t.count === 1 ? '' : 's'} · ${recordedRank(t.top!).label}` : quiet };
}

const columnsOf = (a: Doc) => (((a.profile as Doc)?.columns as Column[] | undefined) ?? []);
const zeroIqr = (c: Column) => typeof c.numeric_summary?.q1 === 'number' && c.numeric_summary.q1 === c.numeric_summary.q3;

export function missingTile(a: Doc, route: (f: Doc) => string, i: number): Tile {
  // Feature columns only: a target's absent values are label or annotation coverage, shown with the target.
  const p = (a.profile as Doc) ?? {}, cols = columnsOf(a).filter((c) => c.role !== 'target' && (c.missing_count ?? 0) > 0).sort((x, y) => (y.missing_rate ?? 0) - (x.missing_rate ?? 0));
  const targetGaps = columnsOf(a).filter((c) => c.role === 'target' && (c.missing_count ?? 0) > 0).length;
  const rows = p.row_count as number | undefined;
  const face = faceOf(a, 'missing', route, `${pct(p.missing_rate)} of cells`);
  const proportion = <ProportionBar count={(p.missing_feature_row_count as number) ?? null} denominator={rows ?? null} caption="rows with at least one missing feature value" />;
  return {
    id: 'missing', name: 'Missing values', n: String(i).padStart(2, '0'), kicker: `${n(p.missing_cells)} cells`, bg: SHADE.pale[0], light: SHADE.pale[1], ...face,
    detail: `${n(p.missing_feature_row_count)} of ${n(rows)} rows have a missing feature value; ${cols.length} feature column${cols.length === 1 ? '' : 's'} have any.`,
    viz: proportion,
    chapter: <>
      <h3>Missing values</h3>
      <div className="nk-ch__run"><span>Cells parsed as missing under the recorded missing-value policy</span><b>{pct(p.missing_rate)} of all cells</b><p>Text such as “unknown” counts as a value unless it was declared missing; its meaning is not assessed.</p></div>
      <FindingBlocks a={a} tile="missing" route={route} />
      {proportion}
      {cols.length
        ? <BarList bars={cols.map((c) => ({ label: c.name, value: c.missing_rate ?? null, note: `${n(c.missing_count)} rows` }))} denominator={rows ?? null} unit="%" scale="percent" caption="missing share per column, most missing first" max={16} more="the columns table" />
        : <p className="nk-ch__not">No feature column has a missing value under the recorded policy.</p>}
      {targetGaps > 0 && <p className="nk-ch__not">{targetGaps} target column{targetGaps === 1 ? ' has' : 's have'} absent values; they are counted in the cell total above and shown with the target’s label or annotation evidence.</p>}
      <Facts rows={[['Missing cells', n(p.missing_cells)], ['Rows with 1 missing feature', n(p.rows_with_1_missing_feature)], ['Rows with 2', n(p.rows_with_2_missing_features)], ['Rows with 3 or more', n(p.rows_with_3_plus_missing_features)],
        ['Severely missing columns', (p.severe_missing_columns as string[] | undefined)?.join(', ') || 'None']]} />
    </>,
  };
}

export function repeatsTile(a: Doc, route: (f: Doc) => string, i: number, labels: boolean): Tile {
  const p = (a.profile as Doc) ?? {};
  const face = faceOf(a, 'repeats', route, `${n(p.duplicate_rows)} repeated rows`);
  return {
    id: 'repeats', name: labels ? 'Repeated rows · label disagreement' : 'Repeated rows', n: String(i).padStart(2, '0'), kicker: 'whole rows', bg: SHADE.card[0], light: SHADE.card[1], ...face,
    detail: `${n(p.duplicate_group_count)} duplicate groups${labels ? ` · ${n(p.conflicting_label_group_count)} feature-identical groups with different labels` : ''}.`,
    chapter: <>
      <h3>{labels ? 'Repeated rows and label disagreement' : 'Repeated rows'}</h3>
      <div className="nk-ch__run"><span>Whole parsed rows{labels ? ', target included' : ''}; missing equals missing</span><b>{n(p.duplicate_rows)} repeated rows</b><p>Duplicates are reported, never removed.{labels ? ' A disagreement group has identical features and more than one label; it cannot say which label is right.' : ''}</p></div>
      <FindingBlocks a={a} tile="repeats" route={route} />
      <Facts rows={[['Duplicate groups', n(p.duplicate_group_count)], ['Repeated rows', n(p.duplicate_rows)],
        ...('rows_in_duplicate_groups' in p ? [['Rows in duplicate groups', n(p.rows_in_duplicate_groups)]] as [string, string][] : []), ['Largest group', n(p.largest_duplicate_group_size)], ['Duplicate rate', pct(p.duplicate_rate)],
        ...(labels ? [['Label disagreement groups', n(p.conflicting_label_group_count)], ['Rows in them', n(p.conflicting_label_row_count)]] as [string, string][] : [])]} />
    </>,
  };
}

export function variationTile(a: Doc, route: (f: Doc) => string, i: number): Tile {
  const cols = columnsOf(a).filter((c) => c.role !== 'target');
  const constant = cols.filter((c) => c.constant), near = cols.filter((c) => c.near_constant), high = cols.filter((c) => c.high_cardinality);
  const face = faceOf(a, 'variation', route, `${constant.length + near.length + high.length} columns flagged`);
  const list = (xs: Column[]) => xs.map((c) => c.name).join(', ') || 'None';
  return {
    id: 'variation', name: 'Variation and cardinality', n: String(i).padStart(2, '0'), kicker: `${cols.length} columns`, bg: SHADE.mist[0], light: SHADE.mist[1], ...face,
    detail: `${constant.length} constant · ${near.length} near-constant · ${high.length} high-cardinality.`,
    chapter: <>
      <h3>Variation and cardinality</h3>
      <div className="nk-ch__run"><span>Observed value sets per column</span><b>{constant.length + near.length + high.length} flags</b><p>A flag is a review prompt; rarity or many categories can be legitimate.</p></div>
      <FindingBlocks a={a} tile="variation" route={route} />
      <Facts rows={[['Constant', list(constant)], ['Near-constant (top value ≥ 95%)', list(near)], ['High cardinality', list(high)]]} />
      <EvidenceTable caption="Top value per column (hidden where the profile hides it)" where="the canonical JSON"
        rows={cols.map((c) => ({ column: c.name, top_value: c.top_value_hidden ? 'hidden' : c.top_value ?? null, top_share: c.top_value_rate ?? null, distinct: c.unique_count ?? null }))} />
    </>,
  };
}

export function numericTile(a: Doc, route: (f: Doc) => string, i: number, opts: { legacy: boolean; usability?: Doc | null }): Tile {
  const cols = columnsOf(a).filter((c) => (c.role == null || c.role === 'feature') && c.is_numeric !== false && (typeof c.outlier_rate === 'number' || zeroIqr(c)));
  const ranked = [...cols].filter((c) => typeof c.outlier_rate === 'number').sort((x, y) => (y.outlier_rate ?? 0) - (x.outlier_rate ?? 0));
  const zero = cols.filter(zeroIqr);
  const rows = (a.profile as Doc)?.row_count as number | undefined;
  const face = faceOf(a, 'numeric', route, ranked[0] ? `Highest ${ranked[0].name} · ${pct(ranked[0].outlier_rate)}` : 'No numeric features');
  const usability = opts.usability as { contributors?: { column: string; rules: { rule: string; points: number }[] }[]; raw_points?: number; feature_count?: number; method?: string } | null | undefined;
  const bars = <BarList bars={ranked.map((c) => ({ label: c.name, value: c.outlier_rate ?? null, note: `${n(c.outlier_count)}` }))} denominator={opts.legacy ? rows ?? null : 100} unit="%"
    caption={`share of ${opts.legacy ? 'all rows' : 'finite values'} outside 1.5 × IQR fences, per numeric feature`} max={12} more="the columns table" />;
  return {
    id: 'numeric', name: opts.usability ? 'Feature usability' : 'Numeric values', n: String(i).padStart(2, '0'), kicker: `${cols.length} numeric`, bg: SHADE.blue[0], light: SHADE.blue[1], ...face,
    detail: `${ranked.filter((c) => (c.outlier_count ?? 0) > 0).length} of ${cols.length} numeric features have IQR candidates${zero.length ? `; IQR is zero for ${zero.length}` : ''}.`,
    viz: bars,
    chapter: <>
      <h3>{opts.usability ? 'Feature usability' : 'Numeric values'}</h3>
      <div className="nk-ch__run"><span>{opts.legacy ? 'All rows; non-finite values count outside the fences' : 'Finite values per column'}</span><b>{ranked.filter((c) => (c.outlier_count ?? 0) > 0).length} features with IQR candidates</b><p>An IQR flag does not prove an error; extreme values can be legitimate. Nothing is deleted or clipped.</p></div>
      <FindingBlocks a={a} tile="numeric" route={route} />
      {bars}
      {!!zero.length && <p className="nk-ch__not">IQR is zero for {zero.map((c) => c.name).join(', ')}: the middle half has no spread, so no fences exist.</p>}
      {usability?.contributors && <>
        <EvidenceTable caption={`Feature-usability points: ${n(usability.raw_points)} across ${n(usability.feature_count)} features`} where="the report's scoring section"
          rows={usability.contributors.flatMap((c) => c.rules.map((r) => ({ column: c.column, rule: r.rule, points: r.points })))} />
        {usability.method && <p className="nk-ch__not">{usability.method}</p>}
      </>}
    </>,
  };
}

export function columnsTile(a: Doc, i: number, route: (f: Doc) => string): Tile {
  const cols = columnsOf(a);
  const flags = (c: Column) => [c.constant && 'constant', c.near_constant && 'near-constant', c.high_cardinality && 'high cardinality', zeroIqr(c) && 'IQR 0'].filter(Boolean).join(', ') || '—';
  return {
    id: 'columns', name: 'Columns', n: String(i).padStart(2, '0'), kicker: `${cols.length} columns`, bg: SHADE.card[0], light: SHADE.card[1], wide: true,
    ...faceOf(a, 'columns', route, `${cols.length} columns`),
    detail: 'Every column with its recorded role, type, missingness, distinct values, flags and IQR share.',
    chapter: <>
      <h3>Columns</h3>
      <div className="nk-ch__run"><span>The recorded column profile</span><b>{cols.length} columns</b><p>Sort by any column. Every recorded column is here; the report’s “All columns” table holds the same values.</p></div>
      <FindingBlocks a={a} tile="columns" route={route} />
      <EvidenceTable caption="Column profile" where="the report’s All columns table and analysis.json /profile/columns" page={50}
        rows={cols.map((c) => ({ column: c.name, role: c.role ?? null, type: c.dtype ?? null, missing_pct: c.missing_rate ?? null, distinct: c.unique_count ?? null, flags: flags(c), iqr_pct: c.outlier_rate ?? null }))} />
    </>,
  };
}

export function parsingTile(a: Doc, i: number): Tile | null {
  const warnings = ((a.parsing_warnings as Doc[] | undefined) ?? []);
  const options = ((a.parsing as Doc | undefined)?.options as Doc | undefined) ?? {};
  return {
    id: 'parsing', name: 'Parsing review', n: String(i).padStart(2, '0'), kicker: 'bounded inspection', bg: SHADE.mist[0], light: SHADE.mist[1], tone: warnings.length ? 'finding' : 'info',
    label: warnings.length ? `${warnings.length} review prompt${warnings.length === 1 ? '' : 's'}` : 'No parsing prompts',
    detail: `Missing-value policy ${words(options.missing_policy ?? 'pandas_default')} · encoding ${String(options.encoding ?? 'utf-8')}.`,
    chapter: <>
      <h3>Parsing review</h3>
      <div className="nk-ch__run"><span>Source tokens inspected within recorded bounds</span><b>{warnings.length} prompt{warnings.length === 1 ? '' : 's'}</b><p>Prompts are review items; their absence within the inspected scope does not establish lossless parsing.</p></div>
      {warnings.map((w, k) => <div key={k} className="nk-ch__f"><b>{words(w.code)}{w.column ? ` · ${String(w.column)}` : ''}</b><p>{String(w.interpretation ?? '')}</p>{w.observed_count != null && <p className="nk-ch__lim">{n(w.observed_count)} observed occurrences within bounded inspection; not dataset incidence.</p>}</div>)}
      <Facts rows={[['Missing-value policy', words(options.missing_policy ?? 'pandas_default')], ['Encoding', String(options.encoding ?? 'utf-8')], ['Separator', String(options.delimiter ?? ',')]]} />
    </>,
  };
}

/** Recorded contextual declarations (context_v1) as facts; they never change a score. */
export function contextFacts(a: Doc): [string, string][] {
  const ctx = a.contextual as Doc | undefined;
  if (!ctx) return [];
  if (ctx.status !== 'completed') return [['Contextual evidence', `Not completed${ctx.reason ? `: ${String(ctx.reason)}` : ''}`]];
  const prediction = (ctx.prediction as Doc | undefined) ?? {}, search = (ctx.dependency_search as Doc | undefined) ?? {};
  const checks = (search.checks as Doc[] | undefined) ?? [], flagged = checks.filter((c) => c.flagged).map((c) => String(c.feature));
  return [['Prediction point', String(prediction.point ?? prediction.objective ?? 'Not declared')], ['Availability declared', `${Object.keys((ctx.availability as Doc | undefined) ?? {}).length} columns`],
    ...(checks.length ? [['Dependency search', `${checks.length} features checked; ${flagged.length ? `flagged ${flagged.join(', ')}` : 'none flagged'}`] as [string, string]] : [])];
}

export function identityOf(a: Doc, workflow: string, variant?: string) {
  const ctx = (a.context as Doc | undefined) ?? {}, p = (a.profile as Doc) ?? {};
  return { name: String(ctx.dataset_name ?? ctx.source_filename ?? 'Dataset'), sources: String(ctx.source_filename ?? ((a.dataset as Doc | undefined)?.path ?? '')) || 'Source not recorded',
           workflow, variant, when: (a.generated_at as string) ?? null, methodology: (a.methodology_id as string) ?? null, schema: (a.schema_version as string) ?? null,
           scale: `${n(p.row_count)} rows × ${n(p.column_count)} columns` };
}

/** The composition's route, checked against the tiles it actually drew: a route to a tile this variant does not draw
 *  goes to "Other findings", so the ledger never points at a tile that is not there. */
export function checkedRoute(composition: keyof typeof routes, tiles: Tile[]) {
  const ids = new Set(tiles.map((t) => t.id));
  return (f: Doc) => { const t = routeOf(composition, f); return ids.has(t) ? t : 'other'; };
}

/** An "Other findings" tile when a finding has no explicit route, so nothing is ever unreachable. */
export function otherTile(a: Doc, route: (f: Doc) => string, i: number): Tile | null {
  const fs = canonicalFindings(a).filter(({ f }) => route(f) === 'other');
  if (!fs.length) return null;
  return { id: 'other', name: 'Other findings', n: String(i).padStart(2, '0'), kicker: 'not routed', bg: SHADE.card[0], light: SHADE.card[1], tone: 'finding',
    label: `${fs.length} finding${fs.length === 1 ? '' : 's'}`, detail: 'Findings this dashboard has no tile for; the report shows each in place.',
    chapter: <><h3>Other findings</h3><FindingBlocks a={a} tile="other" route={route} /></> };
}
