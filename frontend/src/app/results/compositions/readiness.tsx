// Clustering and anomaly readiness: which features can take part in distance-based geometry, and what would distort it.
// No model is fitted and no readiness verdict is made; the hero says so.
import type { ReactNode } from 'react';
import { BarList, ProportionBar } from '../charts/Bars';
import { EvidenceTable } from '../charts/EvidenceTable';
import type { Companion, Dashboard } from '../model';
import { ResultsShell, useCompanion } from '../shell/ResultsShell';
import type { Tile } from '../Tiles';
import { buildDashboard } from './common';
import { checkedRoute, Facts, FindingBlocks, SHADE, columnsTile, identityOf, missingTile, n, otherTile, routeOf, statementOf, toneOf, type Doc } from './tabular';

const words = (s: unknown) => String(s ?? '').replace(/_/g, ' ');
const rd = (a: Doc) => (((a.profile as Doc)?.readiness as Doc | undefined) ?? {});

function geometryHero(a: Doc, route: (f: Doc) => string, anomaly: boolean): Tile {
  const r = rd(a), rows = (a.profile as Doc)?.row_count as number | undefined;
  const q = (r.quantitative_features as Doc[] | undefined) ?? [], ex = (r.geometry_exclusions as { feature: string; reason: string }[] | undefined) ?? [];
  const complete = <ProportionBar count={(r.complete_finite_quantitative_rows as number) ?? null} denominator={rows ?? null} caption="rows with every quantitative feature finite" />;
  const t = toneOf(a, 'geometry', route);
  const red = r.redundant_quantitative_features as { pairs: { features: string[]; pearson: number }[]; pairs_searched: number; unsearched_pairs: number; status: string } | undefined;
  return {
    id: 'geometry', hero: true, name: 'Feature geometry', n: '01', kicker: anomaly ? 'anomaly readiness' : 'clustering readiness', bg: SHADE.deep[0], light: SHADE.deep[1], tone: t.tone,
    label: `${q.length} quantitative · ${ex.length} excluded`, detail: 'No model fitted; no readiness verdict.',
    viz: complete,
    chapter: <>
      <h3>Feature geometry</h3>
      <div className="nk-ch__run"><span>Features that can take part in distances</span><b>{q.length} quantitative · {ex.length} excluded</b><p>No model is fitted and no readiness verdict is made. {String(r.limitations ?? '')}</p></div>
      <FindingBlocks a={a} tile="geometry" route={route} />
      {complete}
      <EvidenceTable caption="Quantitative features" where="the report" rows={q.map((x) => ({ feature: (x.feature as string) ?? null, finite: (x.finite_count as number) ?? null, missing: (x.missing_count as number) ?? null,
        distinct: (x.distinct_count as number) ?? null, iqr: typeof x.iqr === 'number' ? Number((x.iqr as number).toPrecision(4)) : null, scale_note: (x.scale_ineligible_reason as string) ?? null }))} />
      <Facts rows={[['Excluded from geometry', ex.map((x) => `${x.feature} (${words(x.reason)})`).join(', ') || 'None'], ['Variable dimensions', n(r.variable_dimensions)], ['Distinct feature vectors', n(r.distinct_feature_vectors)],
        ...(red ? [['Near-duplicate feature pairs', red.pairs.length ? red.pairs.map((p) => `${p.features.join(' ≈ ')} (r ${p.pearson.toFixed(3)})`).join('; ') : `None among ${n(red.pairs_searched)} pairs searched`] as [string, string],
          ...(red.status === 'bounded' ? [['Unsearched pairs', `${n(red.unsearched_pairs)} (search bounds)`] as [string, string]] : [])] : [])]} />
    </>,
  };
}

function scaleTile(a: Doc, route: (f: Doc) => string, i: number): Tile {
  const ratios = (rd(a).scale_ratios as Doc[] | undefined) ?? [];
  const t = toneOf(a, 'scale', route), first = ratios[0];
  return {
    id: 'scale', name: 'Scale', n: String(i).padStart(2, '0'), kicker: `${ratios.length} populations`, bg: SHADE.blue[0], light: SHADE.blue[1], tone: t.tone,
    label: first && typeof first.ratio === 'number' ? `Ratio ${n(Number((first.ratio as number).toFixed(1)))}` : 'Unavailable',
    detail: first ? String(first.interpretation ?? '') : 'No scale ratio recorded.',
    chapter: <><h3>Scale</h3><div className="nk-ch__run"><span>Largest to smallest spread among eligible features</span><b>{ratios.length} populations</b><p>Scale differences matter to some distance formulations; the encoding choice is yours.</p></div>
      <FindingBlocks a={a} tile="scale" route={route} />
      <EvidenceTable caption="Scale ratios" rows={ratios.map((x) => ({ population: words(x.population), features: ((x.eligible_features as string[]) ?? []).length, ratio: typeof x.ratio === 'number' ? Number((x.ratio as number).toFixed(2)) : (x.unavailable_reason as string) ?? null, review: !!x.conditional_review }))} /></>,
  };
}

function sparsityTile(a: Doc, route: (f: Doc) => string, i: number): Tile {
  const r = rd(a), hist = Object.entries((r.nonzero_quantitative_count_histogram as Record<string, number> | undefined) ?? {}).sort((x, y) => Number(x[0]) - Number(y[0]));
  const t = toneOf(a, 'sparsity', route);
  const bars = hist.length ? <BarList bars={hist.map(([k, v]) => ({ label: `${k} nonzero`, value: v }))} denominator={(r.complete_finite_quantitative_rows as number) ?? null} unit="rows" scale="denominator" caption="complete rows by number of nonzero quantitative values" /> : null;
  return {
    id: 'sparsity', name: 'Sparsity', n: String(i).padStart(2, '0'), kicker: 'zeros · binary', bg: SHADE.pale[0], light: SHADE.pale[1], tone: t.tone,
    label: `Zero density ${typeof r.zero_density_known_quantitative_cells === 'number' ? `${Number(((r.zero_density_known_quantitative_cells as number) * 100).toFixed(2))}%` : 'unavailable'}`,
    detail: `${n(r.complete_all_zero_quantitative_vectors)} all-zero complete vectors · ${((r.binary_sparsity as unknown[]) ?? []).length} binary features.`, viz: bars ?? undefined,
    chapter: <><h3>Sparsity</h3><div className="nk-ch__run"><span>Zeros among known quantitative cells</span><b>{n(r.finite_quantitative_cells)} known cells</b><p>Sparsity affects some similarity formulations; it is not a defect.</p></div>
      <FindingBlocks a={a} tile="sparsity" route={route} />{bars}
      {!!((r.binary_sparsity as Doc[]) ?? []).length && <EvidenceTable caption="Binary features" rows={(r.binary_sparsity as Doc[])} />}</>,
  };
}

function categoriesTile(a: Doc, route: (f: Doc) => string, i: number): Tile | null {
  const cats = (rd(a).categorical_frequency as Doc[] | undefined) ?? [];
  if (!cats.length) return null;
  const t = toneOf(a, 'categories', route);
  return {
    id: 'categories', name: 'Categories', n: String(i).padStart(2, '0'), kicker: `${cats.length} features`, bg: SHADE.mist[0], light: SHADE.mist[1], tone: t.tone,
    label: `${cats.reduce((s, c) => s + Number(c.singleton_category_count ?? 0), 0)} singleton categories`, detail: 'Observed category frequencies, not anomaly correctness.',
    chapter: <><h3>Categories</h3><div className="nk-ch__run"><span>Observed category frequency</span><b>{cats.length} features</b><p>Low frequency describes observed categories, not anomaly correctness.</p></div>
      <FindingBlocks a={a} tile="categories" route={route} />
      <EvidenceTable caption="Categorical features" rows={cats.map((c) => ({ feature: (c.feature as string) ?? null, observed: (c.observed_count as number) ?? null, categories: (c.category_count as number) ?? null, singletons: (c.singleton_category_count as number) ?? null,
        rows_in_rare: (c.rows_in_categories_with_fewer_than_five as number) ?? null }))} /></>,
  };
}

function repetitionTile(a: Doc, route: (f: Doc) => string, i: number): Tile {
  const rep = (rd(a).feature_vector_repetition as Doc | undefined) ?? {};
  const t = toneOf(a, 'repetition', route);
  return {
    id: 'repetition', name: 'Repeated vectors', n: String(i).padStart(2, '0'), kicker: 'feature vectors', bg: SHADE.card[0], light: SHADE.card[1], tone: t.tone,
    label: `${n(rep.duplicate_rows)} repeated rows`, detail: `${n(rep.duplicate_group_count)} groups · largest ${n(rep.largest_duplicate_group_size)}.`,
    chapter: <><h3>Repeated vectors</h3><div className="nk-ch__run"><span>Identical selected feature vectors</span><b>{n(rep.duplicate_rows)} repeated</b><p>{String(rd(a).interpretation ?? 'Repetition affects observation weighting.')}</p></div>
      <FindingBlocks a={a} tile="repetition" route={route} />
      <Facts rows={[['Groups', n(rep.duplicate_group_count)], ['Rows in groups', n(rep.rows_in_duplicate_groups)], ['Largest group', n(rep.largest_duplicate_group_size)], ['Rate', `${n(rep.duplicate_rate)}%`]]} /></>,
  };
}

function extremesTile(a: Doc, route: (f: Doc) => string, i: number): Tile {
  const r = rd(a), rows = (a.profile as Doc)?.row_count as number | undefined;
  const hist = Object.entries((r.extreme_candidate_feature_count_histogram as Record<string, number> | undefined) ?? {}).sort((x, y) => Number(x[0]) - Number(y[0]));
  const t = toneOf(a, 'extremes', route);
  return {
    id: 'extremes', name: 'Extreme candidates', n: String(i).padStart(2, '0'), kicker: 'marginal', bg: SHADE.blue[0], light: SHADE.blue[1], tone: t.tone,
    label: r.marginal_extreme_candidate_rows == null ? 'Unavailable' : `${n(r.marginal_extreme_candidate_rows)} candidate rows`,
    detail: r.marginal_extreme_candidate_rows == null ? 'Not recorded for this result.' : `of ${n(rows)} rows, outside at least one feature’s 1.5 × IQR fences.`,
    chapter: <><h3>Extreme candidates</h3><div className="nk-ch__run"><span>Rows outside at least one feature’s 1.5 × IQR fences</span><b>{n(r.marginal_extreme_candidate_rows)} rows</b><p>Marginal candidates are context for review, not anomaly labels or contamination estimates.</p></div>
      <FindingBlocks a={a} tile="extremes" route={route} />
      {hist.length ? <BarList bars={hist.map(([k, v]) => ({ label: `${k} feature${k === '1' ? '' : 's'}`, value: v }))} denominator={rows ?? null} unit="rows" scale="denominator" caption="candidate rows by number of features outside their fences" /> : null}</>,
  };
}

export function readinessDashboard(a: Doc, companion: Companion | null, saved: boolean, variant: string): Dashboard {
  const route = (f: Doc) => routeOf('readiness', f);
  const anomaly = variant === 'anomaly';
  const tiles = [geometryHero(a, route, anomaly), scaleTile(a, route, 2), ...(anomaly ? [extremesTile(a, route, 3)] : []), sparsityTile(a, route, 4), categoriesTile(a, route, 5), repetitionTile(a, route, 6),
    missingTile(a, route, 7), columnsTile(a, 8, route)].filter((t): t is Tile => !!t);
  const final = checkedRoute('readiness', tiles);
  const other = otherTile(a, final, tiles.length + 1);
  return buildDashboard(a, companion, { composition: 'readiness', variant, saved, identity: identityOf(a, anomaly ? 'Anomaly-detection readiness' : 'Clustering readiness'),
    statement: statementOf(a, false), tiles: other ? [...tiles, other] : tiles, tileOf: final,
    coverage: { methodology: [{ text: 'No model fitted', reason: String(rd(a).limitations ?? 'no clustering quality, anomaly correctness or readiness verdict is inferred') }] } });
}

export function ReadinessPage({ a, out, onOpen, presentation, saved, live, variant }: { a: Doc; out: ReactNode; onOpen: (anchor?: string) => void; presentation: string | null; saved?: boolean; live: boolean; variant: string }) {
  const companion = useCompanion(presentation);
  if (companion === undefined) return <div className="ap-rs"><div className="nk-mosaic nk-mosaic--big nk-mosaic--run ap-rs__wait" aria-busy="true" /></div>;
  return <ResultsShell d={readinessDashboard(a, companion, !!saved, variant)} label="Readiness evidence" out={out} onOpenReport={onOpen} live={live} />;
}
