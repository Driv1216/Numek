// Temporal reliability (M5). The Timeline hero draws the observed series spans; one tile per report topic present
// (chronology, continuity and history, behavioral investigation, availability and outcome maturity, chronological
// evaluation) reads its own evidence records. Ticks are shown in the unit the chronology evidence records (instants
// and local date-times in nanoseconds, civil dates in days), never as raw integers. Behavioral evidence is worded as
// investigation candidates against configured settings, and unknown availability stays unknown.
import type { ReactNode } from 'react';
import { BarList, ProportionBar } from '../charts/Bars';
import { EvidenceTable } from '../charts/EvidenceTable';
import { RankMark } from '../shell/Ledger';
import { GuidanceFor } from '../shell/Interpretation';
import { recordedRank } from '../normalize';
import type { Tile } from '../Tiles';
import type { Tone } from '../adapter';
import type { Companion, CoverageItem, Dashboard } from '../model';
import { buildDashboard, base } from './common';
import { SHADE, n } from './tabular';
import { fmtSpan, fmtTick, isSpanKey, isTickKey, tickMs, type ClockUnits } from '../ticks';

type Doc = Record<string, unknown>;
type Ev = { id: string; check_id: string; measurement: string | null; source_ids: string[]; population: string; data: Doc };
type TFinding = { id: string; title: string; evidence_type: string; evidence_refs: string[]; source_ids: string[]; measurement: string | null; finding: string; next_action: string; limitations: string; priority?: string };

export const TOPICS: [string, string, string[]][] = [
  ['chronology', 'Chronology', ['chronology', 'elapsed_chronology', 'ordering', 'repetition', 'freshness']],
  ['continuity', 'Continuity and history', ['continuity', 'lookback', 'panel']],
  ['behavior', 'Behavioral investigation', ['behavior', 'behavior_windows', 'behavior_series', 'runs', 'volatility', 'seasonality', 'behavior_panel', 'behavior_scope', 'runs_and_volatility', 'multivariate', 'annotation_windows']],
  ['availability', 'Availability and outcome maturity', ['availability', 'availability_unknown', 'past_observation', 'revision_history', 'selected_revision_timing', 'outcome_maturity', 'annotations']],
  ['evaluation', 'Chronological evaluation', ['evaluation']],
];

const arr = (v: unknown) => (Array.isArray(v) ? (v as Doc[]) : []);
const words = (s: unknown) => String(s ?? '').replace(/_/g, ' ');
const sum = (xs: unknown[]) => xs.reduce<number>((t, x) => t + (typeof x === 'number' ? x : Number(x) || 0), 0);
const fixed = (v: unknown, d = 3) => (typeof v === 'number' && Number.isFinite(v) ? Number(v.toFixed(d)) : null);
const plural = (k: number, one: string, many = `${one}s`) => `${n(k)} ${k === 1 ? one : many}`;
const clip = (s: string, k = 36) => (s.length > k ? `${s.slice(0, k - 1)}…` : s);

/** Ends of an observed span: dates, or to the minute under three days (to the second under an hour), in UTC. */
function ends(lo: number, hi: number): [string, string] {
  const k = hi - lo < 3_600_000 ? 19 : hi - lo < 3 * 86_400_000 ? 16 : 10, t = (ms: number) => `${new Date(ms).toISOString().slice(0, k).replace('T', ' ')}${k > 10 ? ' UTC' : ''}`;
  return [t(lo), t(hi)];
}
const span = (lo: number, hi: number) => ends(lo, hi).join(' → ');

export interface TemporalOptions { live?: boolean; investigate?: (q: string) => void }

/** The clock unit and kind each analytical source records, from its chronology evidence. */
function clocks(ev: Ev[]) {
  const m = new Map<string, { units: ClockUnits; kind: string }>();
  for (const e of ev.filter((x) => x.check_id === 'chronology'))
    for (const s of e.source_ids) m.set(s, { units: String(e.data.clock_units ?? 'nanoseconds'), kind: String((e.data.clock as Doc | undefined)?.kind ?? '') });
  return (source?: string) => m.get(source ?? '') ?? [...m.values()][0] ?? { units: 'nanoseconds', kind: '' };
}

/** A recorded value for a table cell or fact, with ticks and tick durations in readable units. */
function cell(key: string, v: unknown, units: ClockUnits): string | number | boolean | null {
  if (v == null) return null;
  if ((typeof v === 'string' || typeof v === 'number') && /^-?\d+$/.test(String(v))) {
    if (isTickKey(key)) return fmtTick(v, units);
    if (isSpanKey(key)) return fmtSpan(v, units);
  }
  if (typeof v === 'number') return Number.isInteger(v) ? v : Number(v.toPrecision(4));
  if (typeof v === 'string' || typeof v === 'boolean') return v;
  if (Array.isArray(v)) return v.every((x) => typeof x !== 'object') ? v.join(', ') || '—' : `${v.length} entries`;
  return null;
}

function Facts({ rows }: { rows: [string, ReactNode][] }) {
  return <dl>{rows.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>;
}

/** Any evidence record this composition draws no designed view for: its scalar facts and its first table, with ticks
 *  formatted. */
function EvidenceRecord({ e, units }: { e: Ev; units: ClockUnits }) {
  const scalars = Object.entries(e.data).map(([k, v]) => [k, cell(k, v, units)] as const).filter(([, v]) => v != null && typeof v !== 'object').slice(0, 10);
  const table = Object.entries(e.data).find(([, v]) => Array.isArray(v) && v.length && typeof v[0] === 'object');
  return (
    <div className="nk-ch__rec">
      <h4>{words(e.check_id)}{e.measurement ? ` · ${e.measurement}` : ''}</h4>
      {!!scalars.length && <Facts rows={scalars.map(([k, v]) => [words(k), typeof v === 'number' ? n(v) : String(v)])} />}
      {table && <EvidenceTable caption={words(table[0])} where="the canonical JSON" rows={(table[1] as Doc[]).map((r) => Object.fromEntries(Object.entries(r).map(([k, v]) => [k, cell(k, v, units)])))} />}
    </div>
  );
}

function FindingBlocks({ fs }: { fs: TFinding[] }) {
  return <>{fs.map((f) => (
    <div key={f.id} className="nk-ch__f" data-ref={f.id}>
      <b>{f.title} <RankMark rank={recordedRank(f as unknown as Doc)} /></b>
      <p>{f.finding}</p><p>{f.next_action}</p><p className="nk-ch__lim">{f.limitations}</p>
      <GuidanceFor refKey={f.id} />
    </div>
  ))}</>;
}

/** Observed series spans per source on one shared axis (in milliseconds, so sources with different clock units
 *  compare); coral where a finding cites the series. A span the evidence does not record is not drawn. The face is a
 *  compact drawing; the chapter lists each series as an HTML row so names stay readable at every width. */
function Timeline({ ev, findings, unitOf, big }: { ev: Ev[]; findings: TFinding[]; unitOf: ReturnType<typeof clocks>; big?: boolean }) {
  const bands = ev.filter((e) => e.check_id === 'panel').map((e) => {
    const { units } = unitOf(e.source_ids[0]);
    return { source: e.source_ids[0], series: arr(e.data.retained_histories).map((h) => ({ m: String(h.measurement ?? ''), who: arr(h.entity).map(String).join(' · '), a: tickMs(h.first_tick, units), b: tickMs(h.last_tick, units) }))
      .filter((h): h is { m: string; who: string; a: number; b: number } => h.a != null && h.b != null)
      .map((h) => ({ ...h, hot: findings.some((f) => f.source_ids.includes(e.source_ids[0]) && f.measurement === h.m) })) };
  }).filter((b) => b.series.length);
  if (!bands.length) return null;
  const lo = Math.min(...bands.flatMap((b) => b.series.map((s) => s.a))), hi = Math.max(...bands.flatMap((b) => b.series.map((s) => s.b)));
  const [from, to] = ends(lo, hi), total = bands.reduce((t, b) => t + b.series.length, 0);
  const pos = (t: number) => (hi > lo ? ((t - lo) / (hi - lo)) * 100 : 50);
  if (big) {
    const max = 24; let left = max;
    return (
      <figure className="ap-chart ap-tl">
        {bands.map((b) => { const shown = b.series.slice(0, Math.max(left, 0)); left -= shown.length; return shown.length ? (
          <ul key={b.source} aria-label={`Series observed in ${b.source}`}>
            {bands.length > 1 && <li className="ap-tl__src">{b.source}</li>}
            {shown.map((s) => <li key={`${s.who}|${s.m}`} className={s.hot ? 'is-hot' : ''}><span className="ap-tl__l">{s.who ? `${s.who} · ${s.m}` : s.m}</span>
              <span className="ap-tl__t" aria-hidden="true"><i style={{ left: `${pos(s.a)}%`, width: `${Math.max(pos(s.b) - pos(s.a), 0.6)}%` }} /></span></li>)}
          </ul>) : null; })}
        <div className="ap-tl__axis"><span>{from}</span><span>{to}</span></div>
        <figcaption>First to last observation per retained series{total > max ? ` · ${max} of ${total} series drawn; all in the chapter table` : ''} · coral: a finding cites the series</figcaption>
      </figure>
    );
  }
  const max = 8, W = 400, x = (t: number) => 10 + (pos(t) / 100) * (W - 20);
  let y = 10, drawn = 0; const rows: ReactNode[] = [];
  for (const b of bands) {
    y += 2;
    for (const s of b.series.slice(0, Math.max(max - drawn, 0))) {
      rows.push(<g key={`${b.source}-${s.who}-${s.m}`} className="md-grow"><line x1={x(s.a)} x2={Math.max(x(s.b), x(s.a) + 2)} y1={y} y2={y} className={`md-tl ${s.hot ? 'is-hot' : ''}`} strokeWidth={4} />{s.hot && <circle cx={x(s.b)} cy={y} r={3.4} className="md-hot" />}</g>);
      y += 12; drawn += 1;
    }
    y += 6;
  }
  return <svg viewBox={`0 0 ${W} ${y + 4}`} className="md-viz" preserveAspectRatio="xMidYMid meet" role="img" aria-label={`Observed series spans, ${from} to ${to}`}>{rows}</svg>;
}

export function temporalDashboard(a: Doc, companion: Companion | null, saved: boolean, opt: TemporalOptions = {}): Dashboard {
  const ev = (a.evidence as Ev[] | undefined) ?? [], findings = (a.findings as TFinding[] | undefined) ?? [];
  const inputs = (((a.spec as Doc | undefined)?.inputs as Doc[] | undefined) ?? []);
  const unitOf = clocks(ev);
  const of = (...checks: string[]) => ev.filter((e) => checks.includes(e.check_id));
  const citing = (recs: Ev[]) => { const ids = new Set(recs.map((e) => e.id)); return findings.filter((f) => f.evidence_refs.some((r) => ids.has(r))); };
  const toneOf = (fs: TFinding[]): Tone => (fs.some((f) => f.priority === 'High' || f.evidence_type === 'declared_violation') ? 'critical' : fs.length ? 'finding' : 'info');
  const sourcesOf = (recs: Ev[]) => [...new Set(recs.flatMap((e) => e.source_ids))].join(' · ');
  const investigate = opt.live ? opt.investigate : undefined;
  const designed = new Set(['chronology', 'ordering', 'repetition', 'continuity', 'panel', 'behavior_windows', 'behavior_scope', 'behavior_series', 'runs', 'volatility', 'availability_unknown', 'revision_history']);
  const rest = (recs: Ev[]) => recs.filter((e) => !designed.has(e.check_id)).map((e) => <EvidenceRecord key={e.id} e={e} units={unitOf(e.source_ids[0]).units} />);
  const notRequested: CoverageItem[] = [];

  // Hero: the observed spans.
  const panels = of('panel');
  const spans = panels.flatMap((e) => arr(e.data.retained_histories).flatMap((h) => [tickMs(h.first_tick, unitOf(e.source_ids[0]).units), tickMs(h.last_tick, unitOf(e.source_ids[0]).units)])).filter((v): v is number => v != null);
  const series = sum(panels.map((e) => e.data.distinct_series)), entities = sum(panels.map((e) => e.data.distinct_entities));
  const hero: Tile = {
    id: 'timeline', hero: true, name: 'Timeline', n: '01', kicker: plural(inputs.length, 'source'), bg: SHADE.deep[0], light: true,
    tone: toneOf(citing(panels)),
    label: spans.length ? span(Math.min(...spans), Math.max(...spans)) : 'No span in the evidence',
    detail: panels.length ? `${plural(series, 'series', 'series')} · ${plural(entities, 'entity', 'entities')} with complete keys and valid clocks` : 'No panel evidence was recorded.',
    viz: <Timeline ev={ev} findings={findings} unitOf={unitOf} />, bigViz: <Timeline ev={ev} findings={findings} unitOf={unitOf} big />,
    chapter: (
      <>
        <h3>Timeline</h3>
        <div className="nk-ch__run"><span>Observed spans from the panel evidence</span><b>{plural(series, 'series', 'series')}</b><p>Each line runs from a series’ first to its last observation. Observed entry and exit are not a declared lifecycle.</p></div>
        <Facts rows={inputs.map((i) => { const t = i.temporal as Doc | null, c = (t?.clock ?? {}) as Doc, s = (t?.schedule ?? {}) as Doc;
          return [`${String(i.id)} · ${String(i.role)}`, t ? `${String(c.column)} · ${words(c.kind)}${c.timezone ? ` · ${String(c.timezone)}` : ''} · schedule ${String(s.kind ?? 'none')}${s.cadence_ns ? ` every ${fmtSpan(s.cadence_ns)}` : ''}` : 'auxiliary source'] as [string, string]; })} />
        {panels.map((e) => { const { units } = unitOf(e.source_ids[0]);
          return <EvidenceTable key={e.id} caption={`Retained series · ${e.source_ids.join(', ')}`} where="the canonical JSON"
            rows={arr(e.data.retained_histories).map((h) => ({ measurement: String(h.measurement ?? ''), entity: arr(h.entity).length ? (h.entity as unknown[]).join(' · ') : '—',
              observations: (h.observations as number) ?? null, first: fmtTick(h.first_tick, units), last: fmtTick(h.last_tick, units), span: fmtSpan(h.span_ticks, units) }))} />; })}
      </>
    ),
  };

  const tiles: Tile[] = [hero];
  const shades = [SHADE.pale, SHADE.blue, SHADE.card, SHADE.mist, SHADE.deep];
  for (const [i, [id, name, checks]] of TOPICS.entries()) {
    const recs = of(...checks);
    if (!recs.length) continue;
    const fs = citing(recs), shade = shades[i % shades.length];
    let label = fs.length ? plural(fs.length, 'finding') : 'No finding', detail = fs[0]?.title ?? [...new Set(recs.map((e) => words(e.check_id)))].join(' · ');
    let viz: ReactNode, big: ReactNode, body: ReactNode = null;

    if (id === 'chronology') {
      const chron = of('chronology'), ordering = of('ordering'), repetition = of('repetition');
      const cells = sum(chron.map((e) => e.data.cells)), states = new Map<string, number>();
      for (const e of chron) for (const [k, v] of Object.entries((e.data.parse_states ?? {}) as Doc)) states.set(k, (states.get(k) ?? 0) + Number(v));
      const unresolved = cells - (states.get('valid') ?? 0), cited = citing(chron).length > 0;
      label = unresolved ? `${n(unresolved)} of ${n(cells)} clock cells not valid` : `All ${n(cells)} clock cells valid`;
      detail = `${plural(sum(ordering.map((e) => e.data.adjacent_backward_cells)), 'backward step')} · ${plural(sum(repetition.map((e) => e.data.conflicting_simultaneous_identities)), 'conflicting identity', 'conflicting identities')}`;
      viz = <BarList scale="denominator" unit="cells" denominator={cells || null} caption="Clock cells by recorded parse state"
        bars={[...states].sort((x, y) => y[1] - x[1]).map(([k, v]) => ({ label: words(k), value: v, hot: cited && k !== 'valid' }))} />;
      body = <>
        {chron.map((e) => { const c = (e.data.clock ?? {}) as Doc; return <div key={e.id} className="nk-ch__rec"><h4>Clock · {e.source_ids.join(', ')}</h4>
          <Facts rows={[['Rows · cells', `${n(e.data.rows)} · ${n(e.data.cells)}`], ['Clock', `${String(c.column)} · ${words(c.kind)} · ${String(c.encoding)}${c.timezone ? ` · ${String(c.timezone)}` : ''}${c.epoch_unit ? ` · epoch ${String(c.epoch_unit)}` : ''}`],
            ['Ticks recorded in', String(e.data.clock_units ?? 'nanoseconds')], ['Precision', Object.entries((e.data.precision_counts ?? {}) as Doc).map(([k, v]) => `${k} ${n(v)}`).join(' · ') || '—'],
            ['Observation meaning', words(e.data.observation_meaning)], ['Missing entity cells · incomplete keys', `${n(e.data.missing_entity_cells)} · ${n(e.data.incomplete_observation_keys)}`]]} />
          <EvidenceTable caption="Value states per measurement" rows={arr(e.data.value_states).map((s) => ({ measurement: String(s.measurement), state: words(s.state), cells: (s.cells as number) ?? null }))} /></div>; })}
        {ordering.map((e) => <div key={e.id} className="nk-ch__rec"><h4>Ordering · {e.source_ids.join(', ')}</h4><Facts rows={[['Backward steps between adjacent cells', n(e.data.adjacent_backward_cells)],
          ['Rows · entities affected', `${n(e.data.affected_row_union)} · ${n(e.data.affected_entities)}`], ['Largest backward step', e.data.largest_backward_step_ticks == null ? 'None' : fmtSpan(e.data.largest_backward_step_ticks, unitOf(e.source_ids[0]).units)],
          ['Source order declared as arrival order', e.data.arrival_order_declared ? 'Yes' : 'No']]} /></div>)}
        {repetition.map((e) => <div key={e.id} className="nk-ch__rec"><h4>Repetition · {e.source_ids.join(', ')}</h4><Facts rows={[['Additional observations of an identity', n(e.data.additional_observations)],
          ['Identical repeats', n(e.data.identical_repeated_identities)], ['Conflicting simultaneous identities · cells', `${n(e.data.conflicting_simultaneous_identities)} · ${n(e.data.conflicting_cells)}`],
          ['Uniqueness required', e.data.uniqueness_required ? 'Yes' : 'No']]} /></div>)}
      </>;
    }

    if (id === 'continuity') {
      const cont = of('continuity'), declared = cont.filter((e) => String(e.data.schedule ?? 'none') !== 'none'), cited = citing(cont).length > 0;
      // A continuity check that was itself excluded is listed once, as excluded, from the recorded checks.
      const ran = (e: Ev) => String((((a.coverage as Doc | undefined)?.checks as Doc | undefined)?.[e.id] as Doc | undefined)?.status ?? 'completed') === 'completed';
      for (const e of cont.filter((x) => !declared.includes(x) && ran(x)))
        notRequested.push({ text: `Continuity against a schedule · ${e.source_ids.join(', ')}`, reason: 'no schedule or expected population was declared, so absent records are not counted' });
      if (declared.length) {
        const expected = sum(declared.map((e) => e.data.expected_records_or_opportunities)), occupied = sum(declared.map((e) => e.data.occupied_distinct_slots));
        const longest = declared.map((e) => Number(e.data.longest_gap_slots ?? 0)).reduce((x, y) => Math.max(x, y), 0);
        label = `${n(occupied)} of ${n(expected)} expected slots occupied`;
        detail = `${plural(sum(declared.map((e) => e.data.absent_expected_records_or_opportunities)), 'absent slot')}${longest ? ` · longest gap ${plural(longest, 'slot')}` : ''}`;
        viz = <ProportionBar count={occupied} denominator={expected || null} caption="expected slots occupied" hot={cited} />;
      } else {
        label = `${plural(series, 'series', 'series')} · ${plural(entities, 'entity', 'entities')}`;
        detail = 'No schedule declared: continuity not assessed.';
      }
      body = <>
        {cont.map((e) => { const d = e.data, { units } = unitOf(e.source_ids[0]), gaps = d.inter_observation_distances as Doc | undefined;
          const sched = ((inputs.find((i) => i.id === e.source_ids[0])?.temporal as Doc | undefined)?.schedule ?? {}) as Doc;
          return <div key={e.id} className="nk-ch__rec"><h4>Continuity · {e.source_ids.join(', ')}</h4>
            {String(d.schedule ?? 'none') === 'none'
              ? <><p className="nk-ch__not">No schedule declared: continuity against expectations was not assessed. Absent records cannot be counted without one.</p>
                  {gaps && <Facts rows={[['Spacing between observations', `${fmtSpan(gaps.minimum_ticks, units)} to ${fmtSpan(gaps.maximum_ticks, units)}`], ['Distances measured', n(gaps.count)], ['Leading and trailing completeness', words(d.leading_trailing_completeness)]]} />}</>
              : <><ProportionBar count={Number(d.occupied_distinct_slots ?? 0)} denominator={Number(d.expected_records_or_opportunities ?? 0) || null} caption="expected slots occupied" hot={citing([e]).length > 0} />
                  <Facts rows={[['Schedule', `${String(d.schedule)}${sched.cadence_ns ? ` · every ${fmtSpan(sched.cadence_ns)}` : sched.civil_unit ? ` · ${String(sched.civil_unit)}` : ''}${sched.anchor ? ` · from ${String(sched.anchor)}` : ''}`], ['Expectation', words(d.expectation)],
                    ['Absent expected slots', n(d.absent_expected_records_or_opportunities)], ['Gap intervals · longest', `${n(d.compressed_gap_intervals)} · ${d.longest_gap_slots == null ? 'none' : plural(Number(d.longest_gap_slots), 'slot')}`],
                    ['Absent expected entities', n(d.absent_expected_entities)], ['Off the grid or outside lifecycle', n(d.off_grid_or_outside_lifecycle_observations)],
                    ['Leading and trailing scope', String(d.leading_trailing_scope ?? '—')], ['An absent event establishes an outage', d.event_absence_establishes_outage ? 'Yes' : 'No']]} />
                  {!!arr(d.gap_witnesses).length && <EvidenceTable caption="Gap witnesses (slot positions on the declared schedule)" rows={arr(d.gap_witnesses).map((g) => ({ measurement: String(g.measurement ?? ''), entity: String(g.entity ?? ''), first_absent_slot: Number(g.first_absent_slot), absent_slots: Number(g.absent_slots) }))} />}</>}
          </div>; })}
        {panels.map((e) => { const h = (e.data.history_counts ?? {}) as Doc; return <div key={e.id} className="nk-ch__rec"><h4>History · {e.source_ids.join(', ')}</h4>
          <Facts rows={[['Entities · series', `${n(e.data.distinct_entities)} · ${n(e.data.distinct_series)}`], ['Observations per series', `${n(h.min)} to ${n(h.max)}`],
            ['Observed span', `${fmtTick(e.data.observed_first_tick, unitOf(e.source_ids[0]).units)} → ${fmtTick(e.data.observed_last_tick, unitOf(e.source_ids[0]).units)}`]]} /></div>; })}
      </>;
    }

    if (id === 'behavior') {
      const windows = of('behavior_windows'), comps = windows.flatMap((e) => arr(e.data.comparisons).map((c): Doc => ({ ...c, measurement: e.measurement ?? String(e.data.measurement ?? '') })));
      const flagged = (c: Doc) => !!(c.distribution_review || c.missingness_review);
      const per = windows.map((e) => ({ e, total: arr(e.data.comparisons).length, hits: arr(e.data.comparisons).filter(flagged).length }));
      const same = per.every((p) => p.total === per[0]?.total), settings = (windows[0]?.data.investigation_defaults ?? {}) as Doc;
      if (windows.length) {
        label = `${n(comps.filter(flagged).length)} of ${n(comps.length)} window comparisons`;
        detail = `meet the configured investigation settings · ${plural(windows.length, 'measurement')}`;
        const bars = (k: number) => <BarList max={k} scale={same ? 'denominator' : 'max'} unit="comparisons" denominator={same ? per[0]?.total || null : comps.length || null}
          caption={`Window comparisons meeting the configured investigation settings, per measurement${same ? '' : ' (counts; measurements differ in comparisons)'}`}
          bars={[...per].sort((x, y) => y.hits - x.hits).map((p) => ({ label: clip(String(p.e.measurement ?? p.e.data.measurement ?? '')), value: p.hits, hot: citing([p.e]).length > 0 }))} more="the comparisons table" />;
        // The face has no room for a chart under this label; the chapter draws every measurement.
        big = bars(24);
      }
      const first = windows[0], units = unitOf(first?.source_ids[0]).units;
      body = <>
        {first && <>
          <p className="nk-ch__not">{String(first.data.interpretation ?? '')}</p>
          <Facts rows={[['Windows', `${n(settings.windows ?? arr(first.data.windows).length)} · reference window ${String(first.data.reference_window ?? '—')}${first.data.reference_was_replaced ? ' (replaced)' : ''}`],
            ['Distribution effect setting', `CDF ${String(settings.distribution_effect ?? '—')} · normalised W1 ${String(settings.normalized_w1 ?? '—')}`], ['Missingness increase setting', String(settings.missingness_increase ?? '—')],
            ['Minimum support', n(settings.min_support)], ['Settings', `${String(settings.version ?? 'recorded defaults')} · investigation settings, not validated defect criteria`]]} />
          <EvidenceTable caption="Window comparisons" where="the canonical JSON" rows={comps.map((c) => ({ measurement: String(c.measurement), windows: `${String(c.reference_window)} → ${String(c.comparison_window)}`,
            support: `${n(c.reference_support)} · ${n(c.comparison_support)}`, cdf_distance: fixed(c.cdf_distance), normalized_w1: fixed(c.normalized_w1), missingness_change: fixed(c.missingness_change),
            meets_settings: [c.distribution_review && 'distribution', c.missingness_review && 'missingness'].filter(Boolean).join(', ') || '—', below_support: !!c.below_support_descriptive_only }))} />
          <EvidenceTable caption={`Windows (spans shared by the measurements; cells for ${String(first.measurement ?? first.data.measurement ?? '')})`}
            rows={arr(first.data.windows).map((w) => ({ window: (w.window_id as number) ?? null, start: fmtTick(w.start_tick, units), end: fmtTick(w.end_tick, units), cells: (w.cells as number) ?? null, missing_rate: fixed(w.missing_rate) }))} />
        </>}
        {!!of('runs').length && <EvidenceTable caption="Runs of repeated or missing values (investigation candidates at the configured run length)" rows={of('runs').map((e) => ({ measurement: String(e.data.measurement ?? e.measurement ?? ''),
          valid_observations: (e.data.valid_observations as number) ?? null, repetition_runs: (e.data.exact_repetition_runs as number) ?? null, longest_repetition: (e.data.longest_repetition as number) ?? null,
          missing_runs: (e.data.missing_state_runs as number) ?? null, longest_missing_run: (e.data.longest_missing_state_run as number) ?? null, run_setting: (e.data.candidate_threshold as number) ?? null }))} />}
        {!!of('volatility').length && <EvidenceTable caption="Volatility windows against the reference window" rows={of('volatility').map((e) => ({ measurement: String(e.data.measurement ?? e.measurement ?? ''),
          windows: arr(e.data.windows).length, meet_settings: arr(e.data.windows).filter((w) => w.review).length, not_comparable: arr(e.data.windows).filter((w) => w.block).length, definition: String(e.data.definition ?? '') }))} />}
        {of('behavior_series').map((e) => <div key={e.id} className="nk-ch__rec"><h4>Within-series windows</h4>
          <Facts rows={[['Series selected', n(e.data.selected_series)], ['Series windows compared', n(e.data.compared_series_windows)], ['Investigation candidates', n(e.data.investigation_candidates)], ['Window pairs not searched', n(e.data.unsearched_window_pairs)]]} />
          <EvidenceTable caption="Series window comparisons" where="the canonical JSON" rows={arr(e.data.details).map((d) => ({ measurement: String(d.measurement ?? ''), entity: arr(d.entity).length ? (d.entity as unknown[]).join(' · ') : '—',
            windows: `${String(d.reference_window)} → ${String(d.comparison_window)}`, cdf: fixed(d.cdf), normalized_w1: fixed(d.normalized_w1), tv: fixed(d.tv), candidate: !!d.investigation_candidate }))} /></div>)}
        {of('behavior_scope').map((e) => <div key={e.id} className="nk-ch__rec"><h4>Search scope</h4>
          <Facts rows={[['Measurements searched', n(arr(e.data.selected_measurements).length)], ['Not searched', n(arr(e.data.unsearched_scope).length)], ['Comparisons', n(e.data.comparisons)], ['Selection', String(e.data.selection ?? '')]]} /></div>)}
        {investigate && <div className="ap-acts">{[...new Set(windows.map((e) => e.measurement).filter(Boolean))].map((m) => <button key={m} type="button" className="ap-sheet__dl" onClick={() => investigate(`measurement=${encodeURIComponent(String(m))}`)}>Investigate {clip(String(m), 28)}</button>)}</div>}
      </>;
    }

    if (id === 'availability') {
      const unknown = of('availability_unknown'), revisions = of('revision_history'), features = [...new Set(unknown.flatMap((e) => (e.data.features as string[] | undefined) ?? []))];
      const states = new Map<string, number>();
      for (const e of revisions) for (const [k, v] of Object.entries((e.data.comparison_states ?? {}) as Doc)) states.set(k, (states.get(k) ?? 0) + Number(v));
      if (!fs.length) {
        label = features.length ? `${plural(features.length, 'feature')}: availability unknown` : revisions.length ? `${plural(sum([...states.values()]), 'revision comparison')}` : 'Availability declared';
        detail = features.length ? 'Unknown unless declared; no timestamp is inherited.' : revisions.length ? [...states].map(([k, v]) => `${n(v)} ${words(k)}`).join(' · ') : detail;
      }
      if (revisions.length) viz = <BarList scale="denominator" unit="comparisons" denominator={sum([...states.values()]) || null} caption="Revision history comparisons by recorded state" bars={[...states].map(([k, v]) => ({ label: words(k), value: v }))} />;
      body = <>
        {!!unknown.length && <div className="nk-ch__rec"><h4>Availability at prediction time</h4>
          {features.length ? <><p>{String(unknown[0].data.meaning ?? '')}</p><ul className="ap-names">{features.map((f) => <li key={f}>{f}</li>)}</ul></> : <p>Every analytical feature has declared availability evidence.</p>}</div>}
        {revisions.map((e) => <div key={e.id} className="nk-ch__rec"><h4>Revision history · {String(e.data.feature ?? '')}</h4>
          <Facts rows={[['Comparison states', Object.entries((e.data.comparison_states ?? {}) as Doc).map(([k, v]) => `${words(k)} ${n(v)}`).join(' · ') || '—'], ['Inconsistencies · complete histories', n(e.data.complete_history_inconsistencies)],
            ['Inconsistencies · qualified', n(e.data.qualified_history_inconsistencies)], ['Unassignable history rows', n(e.data.unassignable_history_rows)], ['Later value match candidates', n(e.data.later_value_match_candidates)],
            ['Units', `${String(e.data.feature_unit ?? 'undeclared')} · history ${String(e.data.history_unit ?? 'undeclared')}`]]} />
          <p className="nk-ch__not">{String(e.data.agreement_meaning ?? '')} {String(e.data.unit_assumption ?? '')}</p></div>)}
      </>;
    }

    tiles.push({
      id, name, n: '', kicker: sourcesOf(recs), bg: shade[0], light: shade[1], tone: toneOf(fs), label, detail, viz, bigViz: big,
      chapter: (
        <>
          <h3>{name}</h3>
          <div className="nk-ch__run"><span>{plural(recs.length, 'evidence record')}</span><b>{fs.length ? plural(fs.length, 'finding') : 'No finding'}</b><p>{[...new Set(recs.map((e) => e.population))].join(' · ')}</p></div>
          <FindingBlocks fs={fs} />
          {body}
          {rest(recs)}
          {investigate && <div className="ap-acts">{[...new Set(recs.map((e) => e.check_id))].map((c) => <button key={c} type="button" className="ap-link" onClick={() => investigate(`family=${c}`)}>Investigate {words(c)}</button>)}</div>}
        </>
      ),
    });
  }

  const topicOf = new Map(ev.map((e) => [e.id, TOPICS.find(([, , checks]) => checks.includes(e.check_id))?.[0] ?? null]));
  const tileOf = (f: Doc) => ((f.evidence_refs as string[] | undefined) ?? []).map((r) => topicOf.get(r)).find(Boolean) ?? 'timeline';
  const ctx = (a.context as Doc | undefined) ?? {};
  const unsearched = arr((a.coverage as Doc | undefined)?.unsearched_analytical_scope).filter((u) => arr(u.unsearched_scope).length);
  return buildDashboard(a, companion, {
    composition: 'temporal', variant: 'temporal', saved,
    identity: { name: String(ctx.dataset_name ?? 'Temporal audit'), sources: inputs.map((i) => base((i.source as Doc | undefined)?.source_filename ?? (i.source as Doc | undefined)?.path ?? i.id)).join(' · '),
                workflow: 'Temporal reliability', when: String(a.generated_at ?? ''), methodology: String(a.methodology_id ?? ''), schema: String(a.schema_version ?? ''), scale: plural(inputs.length, 'source') },
    statement: String((a.narrative as Doc | undefined)?.summary ?? '') || undefined,
    tiles, tileOf,
    extract: (f) => ({ statement: String(f.finding ?? '') || undefined, nextAction: String(f.next_action ?? '') || undefined, limitations: String(f.limitations ?? '') || undefined,
                       scope: [...((f.source_ids as string[] | undefined) ?? []), f.measurement].filter(Boolean).map(String).join(' · ') || undefined }),
    coverage: {
      bounded: unsearched.map((u) => ({ text: `Behavioral investigation searched ${n(arr(u.selected_measurements).length)} measurements; ${n(arr(u.unsearched_scope).length)} were not searched`, reason: String(u.selection ?? '') })),
      notRequested,
    },
  });
}
