// Annotation-aware classification (partial annotations), and the annotation-coverage tile the numerical and multilabel
// compositions share. The risk here is coverage of the labelling process: where expected labels are missing,
// uncertain or contradictory. Expectation, observation and status are recorded separately; unknown stays unknown.
import type { ReactNode } from 'react';
import { BarList, StackedBar } from '../charts/Bars';
import { EvidenceTable } from '../charts/EvidenceTable';
import type { Companion, Dashboard } from '../model';
import { ResultsShell, useCompanion } from '../shell/ResultsShell';
import type { Tile } from '../Tiles';
import { buildDashboard } from './common';
import { checkedRoute, Facts, FindingBlocks, SHADE, columnsTile, identityOf, missingTile, n, numericTile, otherTile, repeatsTile, routeOf, statementOf, toneOf, variationTile, type Doc } from './tabular';

interface AnnTarget { target: string; total_rows: number; observed: number; absent: number; invalid: number; expected: number; optional: number; unknown: number; supplied_expected: number; unavailable_expected: number; uncertain_observed: number }

function coverageParts(rows: Doc) {
  return [{ label: 'complete', count: Number(rows.complete_observed_vector ?? 0) }, { label: 'partial', count: Number(rows.partial_observed_vector ?? 0) }, { label: 'none observed', count: Number(rows.no_observed ?? 0) }];
}

/** Annotation coverage per target and per row; the hero of the annotation composition, a tile elsewhere. */
export function annotationTile(a: Doc, route: (f: Doc) => string, i: number, hero = false): Tile {
  const p = (a.profile as Doc) ?? {}, ann = (p.annotations as Doc | undefined) ?? {}, rows = (ann.rows as Doc | undefined) ?? {};
  const targets = (ann.targets as AnnTarget[] | undefined) ?? [], total = p.row_count as number | undefined;
  const expectedGaps = targets.reduce((s, t) => s + (t.unavailable_expected ?? 0), 0);
  const t = toneOf(a, 'annotations', route);
  const perTarget = <BarList bars={targets.map((x) => ({ label: x.target, value: x.observed, note: x.unavailable_expected ? `${n(x.unavailable_expected)} expected missing` : x.unknown ? `${n(x.unknown)} unknown expectation` : undefined }))}
    denominator={total ?? null} unit="rows" scale="denominator" caption="rows with an observed annotation, per target" max={hero ? 10 : 4} more="the targets table" />;
  const vectors = <StackedBar parts={coverageParts(rows)} denominator={total ?? null} caption="rows by observed annotation vector" />;
  return {
    id: 'annotations', hero, name: 'Annotation coverage', n: String(i).padStart(2, '0'), kicker: `${targets.length} target${targets.length === 1 ? '' : 's'}`, bg: hero ? SHADE.deep[0] : SHADE.pale[0], light: hero ? SHADE.deep[1] : SHADE.pale[1], tone: t.tone,
    label: expectedGaps ? `${n(expectedGaps)} expected annotations missing` : `${n(rows.complete_observed_vector)} of ${n(total)} rows complete`,
    detail: `${n(rows.partial_observed_vector)} partial · ${n(rows.no_observed)} with none observed · ${n(rows.unknown_components)} unknown-expectation components.`,
    viz: hero ? perTarget : vectors, bigViz: <>{vectors}{perTarget}</>,
    chapter: <>
      <h3>Annotation coverage</h3>
      <div className="nk-ch__run"><span>Expectation, observation and status, recorded separately</span><b>{expectedGaps ? `${n(expectedGaps)} expected missing` : `${n(rows.any_observed)} rows with any annotation`}</b>
        <p>{String(ann.meaning ?? 'Observed annotations are supplied evidence, not verified ground truth. Unknown expectations stay unknown.')}</p></div>
      <FindingBlocks a={a} tile="annotations" route={route} />
      <EvidenceTable caption="Annotation coverage per target" where="the report’s annotation tables" rows={targets.map((x) => ({ target: x.target, observed: x.observed, absent: x.absent, invalid: x.invalid,
        expected: x.expected, optional: x.optional, unknown: x.unknown, expected_missing: x.unavailable_expected, uncertain: x.uncertain_observed }))} />
      <Facts rows={[['Rows with any annotation', n(rows.any_observed)], ['Complete vectors', n(rows.complete_observed_vector)], ['Partial vectors', n(rows.partial_observed_vector)], ['None observed', n(rows.no_observed)],
        ['Rows where every expected annotation is supplied', `${n(rows.every_expected_supplied)} of ${n(rows.rows_with_expected)}`]]} />
    </>,
  };
}

function classTile(a: Doc, route: (f: Doc) => string, i: number): Tile | null {
  const c = ((a.profile as Doc)?.classification as Doc | undefined);
  if (!c) return null;
  const dist = (c.distribution as { label: string; count: number; share: number }[] | undefined) ?? [];
  const t = toneOf(a, 'class', route);
  const bars = <BarList bars={dist.map((d) => ({ label: d.label, value: Number((d.share * 100).toFixed(2)), note: n(d.count) }))} denominator={(c.observed_count as number) ?? null} unit="%" scale="percent" caption="class share of observed annotations" />;
  return {
    id: 'class', name: 'Observed classes', n: String(i).padStart(2, '0'), kicker: String(c.target ?? ''), bg: SHADE.card[0], light: SHADE.card[1], tone: t.tone,
    label: `${n(c.class_count)} class${c.class_count === 1 ? '' : 'es'}`, detail: `${n(c.observed_count)} observed annotations.`, viz: bars,
    chapter: <><h3>Observed classes</h3><div className="nk-ch__run"><span>{String(c.target ?? '')}</span><b>{n(c.class_count)} classes</b><p>{String(c.interpretation ?? '')}</p></div><FindingBlocks a={a} tile="class" route={route} />{bars}</>,
  };
}

function cohortsTile(a: Doc, route: (f: Doc) => string, i: number): Tile | null {
  const records = ((((a.profile as Doc)?.annotation_cohorts as Doc | undefined)?.records) as Doc[] | undefined) ?? [];
  if (!records.length) return null;
  const t = toneOf(a, 'cohorts', route);
  const fmt = (v: unknown) => (Array.isArray(v) ? v.map((x) => (typeof x === 'number' ? x.toLocaleString('en-US', { maximumSignificantDigits: 4 }) : String(x))).join(' vs ') : String(v ?? '—'));
  return {
    id: 'cohorts', name: 'Cohort contrasts', n: String(i).padStart(2, '0'), kicker: `${records.length} comparisons`, bg: SHADE.mist[0], light: SHADE.mist[1], tone: t.tone,
    label: `${records.length} feature comparisons`, detail: 'Annotated versus unannotated rows, compared on each feature.',
    chapter: <>
      <h3>Cohort contrasts</h3>
      <div className="nk-ch__run"><span>Rows by annotation state, compared feature by feature</span><b>{records.length} comparisons</b><p>A difference describes who was annotated; it does not establish bias or label quality.</p></div>
      <FindingBlocks a={a} tile="cohorts" route={route} />
      <EvidenceTable caption="Cohort comparisons" where="the report" rows={records.map((r) => ({ cohort: String(r.cohort ?? '').replace(/_/g, ' '), feature: (r.feature as string) ?? null, sizes: fmt(r.sizes), missing_shares: fmt(r.missing_shares),
        medians: fmt(((r.numerical as Doc[] | null) ?? []).map((x) => x?.median)), note: (r.reason as string) ?? null }))} />
    </>,
  };
}

function repeatedTile(a: Doc, route: (f: Doc) => string, i: number): Tile | null {
  const r = ((a.profile as Doc)?.repeated_inputs as Doc | undefined);
  if (!r) return null;
  const t = toneOf(a, 'repeated', route);
  return {
    id: 'repeated', name: 'Repeated inputs', n: String(i).padStart(2, '0'), kicker: 'identical features', bg: SHADE.mist[0], light: SHADE.mist[1], tone: t.tone,
    label: `${n(r.repeated_group_count)} repeated groups`, detail: `${n(r.participating_rows)} participating rows; ${n(r.varying_row_union)} with differing annotations.`,
    chapter: <><h3>Repeated inputs</h3><div className="nk-ch__run"><span>Rows with identical feature values</span><b>{n(r.repeated_group_count)} groups</b><p>{String(r.interpretation ?? 'Differing annotations on identical inputs are review candidates; which is right is not assessed.')}</p></div>
      <FindingBlocks a={a} tile="repeated" route={route} />
      <Facts rows={[['Participating rows', n(r.participating_rows)], ['Differing', n(r.varying_row_union)], ['Largest group', n(r.largest_group)], ['Distinct input vectors', n(r.distinct_input_vectors)]]} /></>,
  };
}

export function annotationDashboard(a: Doc, companion: Companion | null, saved: boolean): Dashboard {
  const route = (f: Doc) => routeOf('annotation', f);
  const tiles = [annotationTile(a, route, 1, true), classTile(a, route, 2), cohortsTile(a, route, 3), repeatedTile(a, route, 4), missingTile(a, route, 5),
    repeatsTile(a, route, 6, false), variationTile(a, route, 7), numericTile(a, route, 8, { legacy: false }), columnsTile(a, 9, route)].filter((t): t is Tile => !!t);
  const final = checkedRoute('annotation', tiles);
  const other = otherTile(a, final, tiles.length + 1);
  return buildDashboard(a, companion, { composition: 'annotation', variant: 'classification', saved, identity: identityOf(a, 'Classification with partial annotations'),
    statement: statementOf(a, false), tiles: other ? [...tiles, other] : tiles, tileOf: final });
}

export function AnnotationPage({ a, out, onOpen, presentation, saved, live }: { a: Doc; out: ReactNode; onOpen: (anchor?: string) => void; presentation: string | null; saved?: boolean; live: boolean }) {
  const companion = useCompanion(presentation);
  if (companion === undefined) return <div className="ap-rs"><div className="nk-mosaic nk-mosaic--big nk-mosaic--run ap-rs__wait" aria-busy="true" /></div>;
  return <ResultsShell d={annotationDashboard(a, companion, !!saved)} label="Annotation evidence" out={out} onOpenReport={onOpen} live={live} />;
}
