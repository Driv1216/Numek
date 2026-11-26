// Numerical outcomes: single-target regression (profile.regression), annotation regression and multi-output regression
// (profile.multioutput_regression.outputs[]). The question is whether the recorded target numbers can be trusted:
// their distribution, the declared constraints, relationships that already contain the target, and repeated inputs.
import { useState, type ReactNode } from 'react';
import { BarList, StackedBar } from '../charts/Bars';
import { Histogram, QuantileStrip, type Bin } from '../charts/Distribution';
import { EvidenceTable } from '../charts/EvidenceTable';
import type { Companion, Dashboard } from '../model';
import { ResultsShell, useCompanion } from '../shell/ResultsShell';
import type { Tile } from '../Tiles';
import { annotationTile } from './annotation';
import { buildDashboard } from './common';
import { checkedRoute, Facts, FindingBlocks, SHADE, columnsTile, identityOf, missingTile, n, numericTile, otherTile, pct, repeatsTile, routeOf, statementOf, toneOf, variationTile, type Doc } from './tabular';

interface Rule { rule: string; declaration: unknown; count: number; denominator: number }
interface Relationship { id: string; method: string; columns: string[]; expression: string; target_coverage?: number; total_row_coverage?: number; fully_verified?: boolean; availability?: string; overlap_count?: number }
interface Target {
  target: string; expectations: Doc | null; statistics: Doc | null; constraints: { rules?: Rule[]; violation_union_count?: number; denominator?: number; declaration_source?: string } | null;
  relationships: Relationship[]; search: Doc | null; names: unknown[];
}

/** Every recorded numerical target, under one shape: the single-target regression section, or each output. */
export function targetsOf(a: Doc): Target[] {
  const p = (a.profile as Doc) ?? {};
  const reg = p.regression as Doc | undefined;
  if (reg) return [{ target: String(p.target ?? ''), expectations: (reg.expectations as Doc) ?? null, statistics: (reg.target_statistics as Doc) ?? null,
    constraints: (reg.constraints as Target['constraints']) ?? null, relationships: (reg.relationships as Relationship[]) ?? [], search: (reg.search as Doc) ?? ((a.coverage as Doc)?.relationship_search as Doc) ?? null,
    names: (reg.name_candidates as unknown[]) ?? [] }];
  const mo = p.multioutput_regression as Doc | undefined;
  return (((mo?.outputs as Doc[] | undefined) ?? [])).map((o) => ({ target: String(o.target), expectations: (o.expectations as Doc) ?? null, statistics: (o.statistics as Doc) ?? null,
    constraints: (o.constraints as Target['constraints']) ?? null, relationships: (o.relationships as Relationship[]) ?? [], search: (o.search as Doc) ?? null, names: (o.name_candidates as unknown[]) ?? [] }));
}

const words = (s: unknown) => String(s ?? '').replace(/_/g, ' ');
const declared = (e: Doc | null) => {
  if (!e) return 'not recorded';
  const parts = [e.kind && e.kind !== 'unspecified' ? String(e.kind) : null, e.units ? String(e.units) : null, e.minimum != null ? `min ${e.minimum}` : null, e.maximum != null ? `max ${e.maximum}` : null,
    e.nonnegative ? 'nonnegative' : null, e.integer_required ? 'integer' : null].filter(Boolean);
  return parts.length ? parts.join(' · ') : 'nothing declared';
};

/** One target's recorded distribution: histogram, quantiles with fences, and its counts. */
function TargetEvidence({ t }: { t: Target }) {
  const s = t.statistics ?? {}, ex = (s.extremes as Doc | undefined) ?? null, hist = (s.histogram as { bins?: Bin[]; denominator?: number; method?: string } | undefined) ?? null;
  return <>
    <Histogram bins={hist?.bins} denominator={hist?.denominator} method={hist?.method} caption={`${t.target}: finite values`} unit={(t.expectations?.units as string) ?? null} />
    <QuantileStrip quantiles={s.quantiles as Record<string, number>} min={s.min as number} max={s.max as number} caption={`${t.target}: recorded quantiles`}
      fences={ex ? { lower: ex.lower_fence as number, upper: ex.upper_fence as number, count: ex.count as number, denominator: ex.denominator as number } : null} />
    <Facts rows={[['Finite values', `${n(s.finite_count)} of ${n(s.row_count)}`], ['Missing', n(s.missing_count)], ['Non-finite', n(Number(s.positive_infinity_count ?? 0) + Number(s.negative_infinity_count ?? 0))],
      ['Distinct finite values', n(s.distinct_count)], ['Mean · sample std', `${n(s.mean)} · ${n(s.sample_std)}`], ['Declared', declared(t.expectations)]]} />
  </>;
}

function outputsHero(a: Doc, ts: Target[], route: (f: Doc) => string, multi: boolean): Tile {
  const p = (a.profile as Doc) ?? {}, mo = (p.multioutput_regression as Doc | undefined) ?? {}, rows = p.row_count as number | undefined;
  const t0 = ts[0], s0 = t0?.statistics ?? {};
  const vectors = <StackedBar denominator={rows ?? null} caption="output vectors: complete, partial, empty"
    parts={[{ label: 'complete', count: Number(mo.complete_vector_count ?? 0) }, { label: 'partial', count: Number(mo.partial_vector_count ?? 0) }, { label: 'empty', count: Number(mo.empty_vector_count ?? 0) }]} />;
  const hist = (t: Target) => { const h = (t.statistics?.histogram as { bins?: Bin[]; denominator?: number; method?: string } | undefined); return <Histogram bins={h?.bins} denominator={h?.denominator} method={h?.method} caption={`${t.target}: finite values`} />; };
  return {
    id: 'target', hero: true, name: multi ? 'Outputs' : 'Target evidence', n: '01', kicker: multi ? `${ts.length} outputs` : t0?.target ?? 'target', bg: SHADE.deep[0], light: SHADE.deep[1],
    tone: toneOf(a, 'target', route).tone,
    label: multi ? `${n(mo.complete_vector_count)} of ${n(rows)} complete vectors` : `${n(s0.finite_count)} of ${n(s0.row_count)} finite`,
    detail: multi ? ts.map((t) => t.target).join(' · ') : `Observed ${n(s0.min)} to ${n(s0.max)} · median ${n((s0.quantiles as Doc | undefined)?.median)} · declared: ${declared(t0?.expectations ?? null)}.`,
    viz: multi ? vectors : (t0 ? hist(t0) : undefined),
    bigViz: multi ? <OutputPicker ts={ts} /> : t0 ? <TargetEvidence t={t0} /> : undefined,
    chapter: <>
      <h3>{multi ? 'Outputs' : 'Target evidence'}</h3>
      <div className="nk-ch__run"><span>{multi ? 'Joint numerical outputs' : `${t0?.target} · finite target values`}</span><b>{multi ? `${ts.length} outputs` : `${n(s0.finite_count)} finite values`}</b>
        <p>Recorded distribution evidence. Ordinary precision is descriptive; an extreme or concentrated value is a review candidate, not an error.</p></div>
      <FindingBlocks a={a} tile="target" route={route} />
      {multi && vectors}
      {multi && <EvidenceTable caption="Outputs" where="the report’s output tables" rows={ts.map((t) => ({ output: t.target, finite: (t.statistics?.finite_count as number) ?? null, missing: (t.statistics?.missing_count as number) ?? null,
        min: (t.statistics?.min as number) ?? null, median: ((t.statistics?.quantiles as Doc | undefined)?.median as number) ?? null, max: (t.statistics?.max as number) ?? null, outside_fences: ((t.statistics?.extremes as Doc | undefined)?.count as number) ?? null }))} />}
    </>,
  };
}

/** One output at a time on the hero's big drawing, chosen by tab. */
function OutputPicker({ ts }: { ts: Target[] }) {
  const [i, setI] = useState(0);
  const t = ts[Math.min(i, ts.length - 1)];
  return (
    <div className="ap-picker">
      <div className="ap-chips" role="tablist" aria-label="Output">{ts.map((x, k) => <button key={x.target} type="button" role="tab" aria-selected={k === i} className={k === i ? 'is-on' : ''} onClick={() => setI(k)}>{x.target}</button>)}</div>
      <TargetEvidence t={t} />
    </div>
  );
}

function constraintsTile(a: Doc, ts: Target[], route: (f: Doc) => string, i: number): Tile {
  const rows = ts.flatMap((t) => (t.constraints?.rules ?? []).map((r) => ({ target: t.target, rule: words(r.rule), declaration: typeof r.declaration === 'object' ? JSON.stringify(r.declaration) : (r.declaration as string | number | boolean), violating: r.count, of: r.denominator })));
  const union = ts.reduce((s, t) => s + Number(t.constraints?.violation_union_count ?? 0), 0);
  const t = toneOf(a, 'constraints', route);
  return {
    id: 'constraints', name: 'Declared constraints', n: String(i).padStart(2, '0'), kicker: rows.length ? `${rows.length} rule${rows.length === 1 ? '' : 's'}` : 'none declared', bg: SHADE.card[0], light: SHADE.card[1], tone: t.tone,
    label: rows.length ? `${n(union)} violating value${union === 1 ? '' : 's'}` : 'Nothing declared',
    detail: rows.length ? rows.map((r) => `${r.target}: ${r.rule} ${n(r.violating)} of ${n(r.of)}`).slice(0, 3).join(' · ') : 'No range, sign or integer requirement was declared, so none was checked.',
    chapter: <>
      <h3>Declared constraints</h3>
      <div className="nk-ch__run"><span>Your declared requirements on the target values</span><b>{rows.length ? `${n(union)} violating` : 'Nothing declared'}</b><p>Violating values stay in the distribution evidence; nothing is removed.</p></div>
      <FindingBlocks a={a} tile="constraints" route={route} />
      {rows.length ? <EvidenceTable caption="Declared rules" where="the report" rows={rows} /> : <p className="nk-ch__not">Declare a range, sign or integer requirement to have it checked.</p>}
    </>,
  };
}

function relationshipsTile(a: Doc, ts: Target[], route: (f: Doc) => string, i: number): Tile {
  const rels = ts.flatMap((t) => t.relationships.map((r) => ({ ...r, target: t.target })));
  const searches = ts.map((t) => ({ target: t.target, status: String(t.search?.status ?? 'not recorded') }));
  const bounded = searches.some((s) => s.status === 'bounded');
  const t = toneOf(a, 'relationships', route);
  return {
    id: 'relationships', name: 'Relationships', n: String(i).padStart(2, '0'), kicker: bounded ? 'bounded' : 'search', bg: SHADE.blue[0], light: SHADE.blue[1], tone: t.tone,
    label: rels.length ? `${rels.length} supported relationship${rels.length === 1 ? '' : 's'}` : 'None found',
    detail: rels.length ? rels.slice(0, 2).map((r) => r.expression).join(' · ') : `Search ${searches.map((s) => words(s.status)).join(', ')}.`,
    chapter: <>
      <h3>Relationships</h3>
      <div className="nk-ch__run"><span>Bounded copy, affine and two-feature-sum search</span><b>{rels.length ? `${rels.length} supported` : 'None found'}</b>
        <p>A supported relationship means a target is already inside the features. Whether those features are available at prediction time is a separate question; arbitrary formulas are not searched.</p></div>
      <FindingBlocks a={a} tile="relationships" route={route} />
      {rels.map((r) => (
        <div key={`${r.target}:${r.id}`} className="nk-ch__f ap-rel">
          <code className="ap-rel__x">{r.expression}</code>
          <p>{words(r.method)} · target coverage {pct(r.target_coverage)} · all rows {pct(r.total_row_coverage)} · {r.fully_verified ? 'fully verified on every overlapping row' : 'not fully verified'} · availability {words(r.availability ?? 'unknown')}</p>
        </div>
      ))}
      <Facts rows={searches.map((s) => [`Search · ${s.target}`, words(s.status)] as [string, string])} />
    </>,
  };
}

function shapeTile(a: Doc, ts: Target[], route: (f: Doc) => string, i: number): Tile {
  const t0 = ts[0], s = t0?.statistics ?? {};
  const grids = ((s.rounding as Doc | undefined)?.grids as { step: number; aligned_count: number; share: number }[] | undefined) ?? [];
  const bounds = (s.boundary_concentration as { boundary: string; value: number; count: number; share: number; review_candidate: boolean }[] | undefined) ?? [];
  const t = toneOf(a, 'shape', route);
  return {
    id: 'shape', name: 'Distribution shape', n: String(i).padStart(2, '0'), kicker: t0?.target ?? '', bg: SHADE.pale[0], light: SHADE.pale[1], tone: t.tone,
    label: `Modal ${n(s.modal_value)} · ${pct(typeof s.modal_share === 'number' ? Number((s.modal_share as number).toFixed(2)) : null)}`,
    detail: `Bowley skewness ${n(typeof s.bowley_skewness === 'number' ? Number((s.bowley_skewness as number).toFixed(3)) : null)} · central 90% span ${n(s.central_90_span)}.`,
    chapter: <>
      <h3>Distribution shape</h3>
      <div className="nk-ch__run"><span>{t0?.target} · grid, boundaries and concentration</span><b>Modal value {n(s.modal_value)}</b><p>Boundary concentration describes where values gather; it does not establish clipping.</p></div>
      <FindingBlocks a={a} tile="shape" route={route} />
      {!!grids.length && <BarList bars={grids.map((g) => ({ label: `step ${g.step}`, value: Number(g.share.toFixed(2)), note: n(g.aligned_count) }))} denominator={(s.finite_count as number) ?? null} unit="%" scale="percent" caption="finite values aligned to each recorded grid step" />}
      {!!bounds.length && <EvidenceTable caption="Boundary concentration" rows={bounds.map((b) => ({ boundary: words(b.boundary), value: b.value, rows: b.count, share_pct: Number(b.share.toFixed(3)), review: b.review_candidate }))} />}
      <Facts rows={[['Modal value · count', `${n(s.modal_value)} · ${n(s.modal_count)}`], ['IQR', n(s.iqr)], ['Integer values', `${n(s.integer_count)} of ${n(s.finite_count)}`], ['Zero · negative', `${n(s.zero_count)} · ${n(s.negative_count)}`]]} />
    </>,
  };
}

function repeatedTile(a: Doc, route: (f: Doc) => string, i: number): Tile | null {
  const p = (a.profile as Doc) ?? {};
  const r = ((p.regression as Doc | undefined)?.repeated_inputs ?? (p.multioutput_regression as Doc | undefined)?.repeated_inputs ?? p.repeated_inputs) as Doc | undefined;
  if (!r) return null;
  const groups = (r.repeated_group_count as number) ?? 0, varying = (r.varying_group_count ?? r.varying_row_union) as number | undefined;
  const t = toneOf(a, 'repeated', route);
  return {
    id: 'repeated', name: 'Repeated inputs', n: String(i).padStart(2, '0'), kicker: 'identical features', bg: SHADE.mist[0], light: SHADE.mist[1], tone: t.tone,
    label: `${n(groups)} repeated group${groups === 1 ? '' : 's'}`, detail: `${n(r.participating_rows)} participating rows; ${n(varying)} with varying targets.`,
    chapter: <>
      <h3>Repeated inputs</h3>
      <div className="nk-ch__run"><span>Rows with identical feature values</span><b>{n(groups)} groups</b><p>{String(r.interpretation ?? 'Variation may reflect repeated measurements, stochastic outcomes or omitted context; contradictory targets are not established.')}</p></div>
      <FindingBlocks a={a} tile="repeated" route={route} />
      <Facts rows={[['Repeated groups', n(groups)], ['Participating rows', n(r.participating_rows)], ['Varying', n(varying)], ['Largest group', n(r.largest_group)], ...(r.distinct_input_vectors != null ? [['Distinct input vectors', n(r.distinct_input_vectors)] as [string, string]] : [])]} />
    </>,
  };
}

function availabilityTile(a: Doc, ts: Target[], route: (f: Doc) => string, i: number): Tile {
  const p = (a.profile as Doc) ?? {};
  const avail = (((p.regression as Doc | undefined)?.feature_availability ?? (p.multioutput_regression as Doc | undefined)?.feature_availability) as Record<string, string> | undefined) ?? {};
  const names = ts.flatMap((t) => t.names.map((x) => (typeof x === 'string' ? x : String((x as Doc).column ?? (x as Doc).name ?? ''))));
  const unavailable = Object.entries(avail).filter(([, v]) => v === 'unavailable_at_prediction').map(([k]) => k);
  const t = toneOf(a, 'availability', route);
  return {
    id: 'availability', name: 'Availability and names', n: String(i).padStart(2, '0'), kicker: 'declared · names', bg: SHADE.deep[0], light: SHADE.deep[1], tone: t.tone,
    label: unavailable.length ? `${unavailable.length} declared unavailable` : `${Object.keys(avail).length} declared`,
    detail: `${names.length} target-related name${names.length === 1 ? '' : 's'}. Undeclared features are not verified.`,
    chapter: <>
      <h3>Availability and names</h3>
      <div className="nk-ch__run"><span>Your availability declarations and name cues</span><b>{Object.keys(avail).length} declared</b><p>Unknown is the default; a name is never treated as proof.</p></div>
      <FindingBlocks a={a} tile="availability" route={route} />
      <Facts rows={[['Declared unavailable at prediction', unavailable.join(', ') || 'None'], ['Declared available', Object.entries(avail).filter(([, v]) => v === 'available_at_prediction').map(([k]) => k).join(', ') || 'None'],
        ['Target-related names', names.join(', ') || 'None']]} />
    </>,
  };
}

function dependenciesTile(a: Doc, route: (f: Doc) => string, i: number): Tile | null {
  const mo = ((a.profile as Doc)?.multioutput_regression as Doc | undefined);
  const deps = (mo?.output_dependencies as Doc[] | undefined) ?? [];
  if (deps.length === 0) return null;
  const t = toneOf(a, 'dependencies', route);
  return {
    id: 'dependencies', name: 'Output dependencies', n: String(i).padStart(2, '0'), kicker: `${deps.length} pairs`, bg: SHADE.pale[0], light: SHADE.pale[1], tone: t.tone,
    label: `${deps.length} output pair${deps.length === 1 ? '' : 's'}`, detail: `Search ${words(((mo?.dependency_search as Doc | undefined)?.status) ?? 'not recorded')}.`,
    chapter: <>
      <h3>Output dependencies</h3>
      <div className="nk-ch__run"><span>Pairs of outputs on their finite overlap</span><b>{deps.length} pairs</b><p>Correlation between outputs does not establish redundancy or causality.</p></div>
      <FindingBlocks a={a} tile="dependencies" route={route} />
      <EvidenceTable caption="Output pairs" rows={deps.map((d) => ({ outputs: ((d.targets as string[]) ?? []).join(' · '), overlap: (d.finite_overlap as number) ?? null, coverage: (d.coverage as number) ?? null,
        pearson: typeof d.pearson === 'number' ? Number((d.pearson as number).toFixed(3)) : (d.pearson_unavailable_reason as string) ?? null, identities: ((d.identities as unknown[]) ?? []).length }))} />
    </>,
  };
}

export function numericDashboard(a: Doc, companion: Companion | null, saved: boolean, variant: string): Dashboard {
  const route = (f: Doc) => routeOf('numeric', f);
  const ts = targetsOf(a), multi = ts.length > 1;
  const p = (a.profile as Doc) ?? {};
  const annotated = !!p.annotations;
  const tiles: (Tile | null)[] = [
    outputsHero(a, ts, route, multi), relationshipsTile(a, ts, route, 2), constraintsTile(a, ts, route, 3),
    multi ? dependenciesTile(a, route, 4) : shapeTile(a, ts, route, 4), annotated ? annotationTile(a, route, 5) : null, repeatedTile(a, route, 6),
    availabilityTile(a, ts, route, 7), missingTile(a, route, 8), repeatsTile(a, route, 9, false), variationTile(a, route, 10), numericTile(a, route, 11, { legacy: false }), columnsTile(a, 12, route),
  ];
  const list = tiles.filter((t): t is Tile => !!t);
  const final = checkedRoute('numeric', list);
  const other = otherTile(a, final, list.length + 1);
  const bounded = ts.filter((t) => String(t.search?.status) === 'bounded').map((t) => ({ text: `Relationship search for ${t.target} is bounded`, reason: String((t.search as Doc)?.meaning ?? 'planned pool and work limits; a coverage limit, not a failure') }));
  const label = variant === 'multioutput' ? 'Multi-output regression' : variant === 'annotation' ? 'Regression with annotations' : 'Regression';
  return buildDashboard(a, companion, {
    composition: 'numeric', variant, saved, identity: identityOf(a, label, multi ? `${ts.length} outputs` : `target ${ts[0]?.target ?? ''}`),
    statement: statementOf(a, false), tiles: other ? [...list, other] : list, tileOf: final, coverage: { bounded },
  });
}

export function NumericPage({ a, out, onOpen, presentation, saved, live, variant }: { a: Doc; out: ReactNode; onOpen: (anchor?: string) => void; presentation: string | null; saved?: boolean; live: boolean; variant: string }) {
  const companion = useCompanion(presentation);
  if (companion === undefined) return <div className="ap-rs"><div className="nk-mosaic nk-mosaic--big nk-mosaic--run ap-rs__wait" aria-busy="true" /></div>;
  return <ResultsShell d={numericDashboard(a, companion, !!saved, variant)} label="Numerical outcome evidence" out={out} onOpenReport={onOpen} live={live} />;
}
