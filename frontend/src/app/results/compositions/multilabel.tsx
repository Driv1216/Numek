// Multilabel indicators: are the label vectors complete and well formed, and how are labels distributed and combined?
// Per-label prevalence is one part of it, not the headline.
import type { ReactNode } from 'react';
import { BarList, StackedBar } from '../charts/Bars';
import { EvidenceTable } from '../charts/EvidenceTable';
import type { Companion, Dashboard } from '../model';
import { ResultsShell, useCompanion } from '../shell/ResultsShell';
import type { Tile } from '../Tiles';
import { annotationTile } from './annotation';
import { buildDashboard } from './common';
import { checkedRoute, FindingBlocks, SHADE, columnsTile, identityOf, missingTile, n, numericTile, otherTile, repeatsTile, routeOf, statementOf, toneOf, type Doc } from './tabular';

interface Label { target: string; positive: number; negative: number; observed: number; absent: number; invalid: number; positive_share_known: number | null }
const words = (s: unknown) => String(s ?? '').replace(/_/g, ' ');

function labelsHero(a: Doc, route: (f: Doc) => string): Tile {
  const p = (a.profile as Doc) ?? {}, ml = (p.multilabel as Doc | undefined) ?? {}, rows = p.row_count as number | undefined;
  const labels = (ml.labels as Label[] | undefined) ?? [];
  const vectors = <StackedBar denominator={rows ?? null} caption="label vectors: complete, partial, empty"
    parts={[{ label: 'complete', count: Number(ml.complete_vector_count ?? 0) }, { label: 'partial', count: Number(ml.partial_vector_count ?? 0) }, { label: 'empty', count: Number(ml.empty_vector_count ?? 0) }]} />;
  const prevalence = (max: number) => <BarList max={max} scale="percent" unit="%" denominator={rows ?? null} caption="positive share of each label’s observed values"
    bars={labels.map((l) => ({ label: l.target, value: l.positive_share_known == null ? null : Number((l.positive_share_known * 100).toFixed(2)), note: `${n(l.positive)} of ${n(l.observed)}` }))} />;
  const t = toneOf(a, 'labels', route);
  return {
    id: 'labels', hero: true, name: 'Label vectors', n: '01', kicker: `${labels.length} labels`, bg: SHADE.deep[0], light: SHADE.deep[1], tone: t.tone,
    label: `${n(ml.complete_vector_count)} of ${n(rows)} complete`, detail: `${n(ml.partial_vector_count)} partial · ${n(ml.empty_vector_count)} empty · positives ${n(ml.observed_positives)} of ${n(ml.observed_cells)} known cells.`,
    viz: prevalence(6), bigViz: <>{vectors}{prevalence(20)}</>,
    chapter: <>
      <h3>Label vectors</h3>
      <div className="nk-ch__run"><span>Binary indicator vectors, one per row</span><b>{n(ml.complete_vector_count)} complete vectors</b><p>{String(ml.interpretation ?? 'Supplied indicators are evidence, not verified labels.')}</p></div>
      <FindingBlocks a={a} tile="labels" route={route} />
      <EvidenceTable caption="Labels" where="the report’s label table" rows={labels.map((l) => ({ label: l.target, positive: l.positive, negative: l.negative, observed: l.observed, absent: l.absent, invalid: l.invalid,
        positive_share: l.positive_share_known == null ? null : Number(l.positive_share_known.toFixed(4)) }))} />
    </>,
  };
}

function cardinalityTile(a: Doc, route: (f: Doc) => string, i: number): Tile {
  const ml = ((a.profile as Doc)?.multilabel as Doc | undefined) ?? {};
  const dist = Object.entries((ml.cardinality_distribution as Record<string, number> | undefined) ?? {}).sort((x, y) => Number(x[0]) - Number(y[0]));
  const reasons = (ml.unavailable_reasons as Record<string, string | null> | undefined) ?? {};
  const t = toneOf(a, 'cardinality', route);
  const bars = dist.length ? <BarList bars={dist.map(([k, v]) => ({ label: `${k} label${k === '1' ? '' : 's'}`, value: v }))} denominator={(ml.cardinality_denominator as number) ?? null} unit="vectors" scale="denominator" caption="complete vectors by number of positive labels" /> : null;
  return {
    id: 'cardinality', name: 'Cardinality', n: String(i).padStart(2, '0'), kicker: 'labels per row', bg: SHADE.pale[0], light: SHADE.pale[1], tone: t.tone,
    label: ml.cardinality == null ? 'Unavailable' : `${n(Number((ml.cardinality as number).toFixed(3)))} labels per row`,
    detail: ml.cardinality == null ? words(reasons.cardinality ?? 'not recorded') : `Density ${n(typeof ml.density === 'number' ? Number((ml.density as number).toFixed(4)) : null)} over complete vectors.`,
    viz: bars ?? undefined,
    chapter: <><h3>Cardinality</h3><div className="nk-ch__run"><span>Positive labels per complete vector</span><b>{ml.cardinality == null ? 'Unavailable' : n(ml.cardinality)}</b><p>{ml.cardinality == null ? `Unavailable: ${words(reasons.cardinality)}` : 'Measured over complete vectors only.'}</p></div>
      <FindingBlocks a={a} tile="cardinality" route={route} />{bars}</>,
  };
}

function pairsTile(a: Doc, route: (f: Doc) => string, i: number): Tile {
  const ml = ((a.profile as Doc)?.multilabel as Doc | undefined) ?? {};
  const pairs = (ml.pairs as Doc[] | undefined) ?? [], search = (ml.pair_search as Doc | undefined) ?? {};
  const t = toneOf(a, 'pairs', route);
  return {
    id: 'pairs', name: 'Label pairs', n: String(i).padStart(2, '0'), kicker: words(search.status ?? 'not recorded'), bg: SHADE.blue[0], light: SHADE.blue[1], tone: t.tone,
    label: `${pairs.length} pair${pairs.length === 1 ? '' : 's'}`, detail: `${n(search.comparisons)} comparisons · ${((search.excluded_targets as unknown[]) ?? []).length} labels excluded.`,
    chapter: <><h3>Label pairs</h3><div className="nk-ch__run"><span>Co-occurrence on jointly observed rows</span><b>{pairs.length} pairs</b><p>Co-occurrence describes the supplied labels; it does not establish a dependency.</p></div>
      <FindingBlocks a={a} tile="pairs" route={route} />
      <EvidenceTable caption="Label pairs" where="the report" rows={pairs.map((x) => ({ labels: ((x.targets as string[]) ?? []).join(' · '), jointly_observed: (x.jointly_observed as number) ?? null, both: (x.n11 as number) ?? null,
        jaccard: typeof x.jaccard === 'number' ? Number((x.jaccard as number).toFixed(3)) : null }))} /></>,
  };
}

function constraintsTile(a: Doc, route: (f: Doc) => string, i: number): Tile | null {
  const ml = ((a.profile as Doc)?.multilabel as Doc | undefined) ?? {};
  const rules = (ml.constraints as Doc[] | undefined) ?? [];
  const t = toneOf(a, 'constraints', route);
  return {
    id: 'constraints', name: 'Declared constraints', n: String(i).padStart(2, '0'), kicker: rules.length ? `${rules.length} rules` : 'none declared', bg: SHADE.card[0], light: SHADE.card[1], tone: t.tone,
    label: rules.length ? `${n(ml.constraint_violation_row_union)} violating rows` : 'Nothing declared', detail: rules.length ? `${n(ml.constraint_invalid_vector_count)} invalid vectors.` : 'No label constraint was declared, so none was checked.',
    chapter: <><h3>Declared constraints</h3><div className="nk-ch__run"><span>Your declared label rules</span><b>{rules.length ? `${rules.length} rules` : 'Nothing declared'}</b><p>Violating rows stay in the evidence; nothing is changed.</p></div>
      <FindingBlocks a={a} tile="constraints" route={route} />{rules.length ? <EvidenceTable caption="Declared label rules" rows={rules} /> : null}</>,
  };
}

export function multilabelDashboard(a: Doc, companion: Companion | null, saved: boolean): Dashboard {
  const route = (f: Doc) => routeOf('multilabel', f);
  const ml = ((a.profile as Doc)?.multilabel as Doc | undefined) ?? {};
  const tiles = [labelsHero(a, route), annotationTile(a, route, 2), cardinalityTile(a, route, 3), pairsTile(a, route, 4), constraintsTile(a, route, 5), missingTile(a, route, 6), repeatsTile(a, route, 9, false),
    numericTile(a, route, 7, { legacy: false }), columnsTile(a, 8, route)].filter((t): t is Tile => !!t);
  const final = checkedRoute('multilabel', tiles);
  const other = otherTile(a, final, tiles.length + 1);
  const pairSearch = (ml.pair_search as Doc | undefined) ?? {}, combos = (ml.combinations as Doc | undefined) ?? {};
  const bounded = [
    ...(String(pairSearch.status) === 'bounded' ? [{ text: 'Label pair search is bounded', reason: `${((pairSearch.excluded_targets as unknown[]) ?? []).length} labels excluded from pairing` }] : []),
    ...(String(combos.status) === 'bounded' ? [{ text: `Label combinations: ${n(combos.processed_complete_vectors)} of ${n(combos.eligible_complete_vectors)} complete vectors processed`, reason: words(combos.stop_reason ?? 'planned work limit') }] : []),
  ];
  return buildDashboard(a, companion, { composition: 'multilabel', variant: 'multilabel', saved, identity: identityOf(a, 'Multilabel', `${((ml.labels as unknown[]) ?? []).length} labels`),
    statement: statementOf(a, false), tiles: other ? [...tiles, other] : tiles, tileOf: final, coverage: { bounded } });
}

export function MultilabelPage({ a, out, onOpen, presentation, saved, live }: { a: Doc; out: ReactNode; onOpen: (anchor?: string) => void; presentation: string | null; saved?: boolean; live: boolean }) {
  const companion = useCompanion(presentation);
  if (companion === undefined) return <div className="ap-rs"><div className="nk-mosaic nk-mosaic--big nk-mosaic--run ap-rs__wait" aria-busy="true" /></div>;
  return <ResultsShell d={multilabelDashboard(a, companion, !!saved)} label="Multilabel evidence" out={out} onOpenReport={onOpen} live={live} />;
}
