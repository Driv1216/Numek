// Image reliability (M7). The hero is the report's own decisions (image_presentation executive actions, via the
// presentation companion), grouped by consequence in the report's order: source and identity problems and declared
// separation first, then comparison limits and review candidates. Image findings record an evidence meaning, never a
// priority. One tile per evidence family, named as the report names it, with a face read from its recorded counts.
// A retained pair is drawn in coral only when one finding's recorded references include both of its images: direct
// support, not membership of the same family. Viewing images is a live, local action supplied by the page (`pairs`).
import type { ReactNode } from 'react';
import type { Companion, Dashboard } from '../model';
import type { Tile } from '../Tiles';
import { buildDashboard } from './common';
import { SHADE } from './tabular';
import { CountBars, FindingBlock, RecordView, References, SHADES, arr, counts, firstCount, n, namer, num, plural, sumOf, toneFrom, words, type Doc, type Ev, type Face, type Fnd } from './evidence';

export type Pair = { left: string; right: string; family: string; hamming_distance?: number; cosine?: number };
export interface ImageSlots { pairs?: (pairs: Pair[]) => ReactNode; readOnly?: string }

const measure = (p: Pair) => (p.hamming_distance != null ? `distance ${p.hamming_distance}` : p.cosine != null ? `cosine ${p.cosine.toFixed(3)}` : '');
const short = (r: string) => `…${r.slice(-6)}`;
const pairsIn = (e: Ev): Pair[] => arr(e.data.examples ?? e.data.candidates).filter((v) => v.left && v.right).map((v) => ({ ...(v as unknown as Pair), family: e.family }));

const duplicates = (d: Doc): Face => [`${plural(d.groups, 'group')} · ${plural(d.participating_occurrences, 'occurrence')}`, `${n(d.cross_split_occurrences)} across splits`];
const FACE: Record<string, (d: Doc, recs: Ev[]) => Face> = {
  inventory: (d) => [plural(d.occurrences, 'occurrence'), `${plural(d.image_locations, 'image location')} · ${plural(d.physical_media_files, 'file')}`],
  decode: (d) => { const s = (d.asset_states ?? {}) as Doc; return [`${n(num(s.decoded))} of ${n(sumOf(s))} assets decoded`, counts(d.encoded_formats).map(([k, v]) => `${k} ${n(v)}`).join(' · ')]; },
  visual_quality: (d) => [plural(d.eligible_assets, 'eligible asset'), String(d.representation ?? '')],
  visual_extremes: (d) => [plural(arr(d.examples).length, 'retained extreme'), String(d.interpretation ?? '')],
  annotations: (d) => { const v = (d.validity ?? {}) as Doc, states = counts(v).map(([k, x]) => `${words(k)} ${n(x)}`).join(' · ');
    return ['valid' in v ? `${n(num(v.valid))} of ${n(sumOf(v))} annotations valid` : states || 'No annotation recorded', `${plural(d.normalized_occurrences, 'occurrence')} · ${plural(sumOf(d.blocked_geometric_checks), 'blocked check')}`]; },
  quality_expectations: (d) => [plural(sumOf(d.declared_violations), 'declared violation'), counts(d.declared_violations).map(([k, v]) => `${words(k)} ${n(v)}`).join(' · ') || 'No declared rule was violated.'],
  composition: (d) => [plural(d.distinct_source_categories, 'category', 'categories'), `${plural(d.crowd_objects, 'crowd object')} · ${n(d.category_detail_omissions)} omitted from detail`],
  multilabel_composition: (d) => firstCount(d),
  exact_duplicates_bytes: duplicates, exact_duplicates_native: duplicates, exact_duplicates_oriented: duplicates,
  annotation_disagreement: (d) => [plural(d.compatible_exact_raster_groups_with_differences, 'differing group'), `${n(d.payload_difference_groups_blocked)} blocked by compatibility · no correct label identified`],
  split_requirements: (d) => [`${n(d.exact_asset_overlap_occurrences)} exact · ${n(d.declared_group_overlap_occurrences)} group overlaps`, `${n(d.left_occurrences)} left, ${n(d.right_occurrences)} right occurrences · ${words(d.group_separation_applicability)} applicability`],
  versions: (_, recs) => [`${plural(recs.length, 'version comparison')}${recs.some((e) => e.data.alignment === 'blocked') ? ` · ${n(recs.filter((e) => e.data.alignment === 'blocked').length)} alignment blocked` : ''}`,
    recs.map((e) => `${words(e.data.reference)} → ${words(e.data.current)}: ${num(e.data.population_delta) > 0 ? '+' : ''}${n(e.data.population_delta)} occurrences`).join(' · ')],
  logical_identity: (d) => [`${plural(d.occurrences_with_duplicate_source_keys, 'occurrence')} with repeated keys`, 'logical identities'],
  near_duplicates: (d) => [plural(d.qualifying_raster_pairs ?? d.qualifying_pairs, 'qualifying pair'), `radius ${n(d.radius)} · groups are not equivalence classes`],
  embeddings: (d) => firstCount(d),
};

function faceViz(fam: string, d: Doc, hot: boolean): ReactNode {
  if (fam === 'decode') return <CountBars o={d.asset_states} caption="Assets by decode state" unit="assets" hot={(k) => hot && k !== 'decoded'} />;
  if (fam === 'annotations') return <CountBars o={d.validity} caption="Annotations by validity" hot={(k) => hot && k !== 'valid'} />;
  if (fam === 'quality_expectations') return <CountBars o={d.declared_violations} caption="Declared quality-rule violations by rule" unit="occurrences" hot={() => hot} />;
  return null;
}

/** Retained pairs, each with its recorded measure; coral only for a pair one finding cites directly. */
function PairDiagram({ pairs, cited, big }: { pairs: Pair[]; cited: (p: Pair) => boolean; big?: boolean }) {
  const shown = pairs.slice(0, big ? 10 : 4);
  if (!shown.length) return null;
  return (
    <figure className="ap-chart">
      <svg viewBox={`0 0 300 ${shown.length * 34 + 4}`} className="md-viz" preserveAspectRatio="xMidYMid meet" role="img" aria-label={`${pairs.length} retained pairs`}>
        {shown.map((p, i) => (
          <g key={i} transform={`translate(0 ${i * 34 + 4})`} className="md-grow" style={{ ['--i' as string]: i }}>
            <rect x={4} y={2} width={40} height={26} rx={2} className="md-page" /><rect x={256} y={2} width={40} height={26} rx={2} className="md-page" />
            <line x1={44} x2={256} y1={15} y2={15} className={cited(p) ? 'md-tl is-hot' : 'md-tl'} strokeWidth={2} />
            {big && <text x={150} y={11} className="md-t md-t--c md-t--s">{measure(p) || 'pair'}</text>}
          </g>
        ))}
      </svg>
      {big && <figcaption>{pairs.length > shown.length ? `${shown.length} of ${pairs.length} retained pairs · ` : ''}coral: both images are among one finding’s recorded references</figcaption>}
    </figure>
  );
}

export function imageDashboard(a: Doc, companion: Companion | null, saved: boolean, slots: ImageSlots = {}): Dashboard {
  const ev = (a.evidence as Ev[] | undefined) ?? [], fs = (a.findings as Fnd[] | undefined) ?? [], profile = (a.profile as Doc | undefined) ?? {};
  const name = namer(companion), families = [...new Set(ev.map((e) => e.family))];
  const cited = (p: Pair) => fs.some((f) => (f.references ?? []).includes(p.left) && (f.references ?? []).includes(p.right));
  type Decision = { title?: string; meaning?: string | null; facts?: string[]; action?: string | null };
  const decisions: Decision[] = companion?.actions ?? fs.map((f) => ({ title: name.family(f.family), meaning: name.meaning(f.meaning), facts: [], action: f.action }));
  const Decisions = ({ full }: { full?: boolean }) => (
    <ol className="ap-actions">
      {decisions.map((x, i) => (
        <li key={i}>
          <b>{x.title}</b><span>{x.meaning}{!full && x.facts?.length ? ` · ${x.facts[0]}` : ''}</span>
          {full && !!x.facts?.length && <ul>{x.facts.map((f) => <li key={f}>{f}</li>)}</ul>}
          {full && x.action && <p>{x.action}</p>}
        </li>
      ))}
    </ol>
  );
  const hero: Tile = {
    id: 'decisions', hero: true, name: 'Decisions', n: '01', kicker: plural(profile.occurrences, 'occurrence'), bg: SHADE.deep[0], light: true,
    tone: toneFrom(fs), label: decisions.length ? plural(decisions.length, 'decision') : 'No decision to make',
    detail: decisions.length ? `${decisions[0].title} first · ordered as in the report` : String(profile.summary ?? ''),
    viz: decisions.length ? <Decisions /> : undefined, bigViz: decisions.length ? <Decisions full /> : undefined,
    chapter: (
      <>
        <h3>Decisions</h3>
        <div className="nk-ch__run"><span>As the report groups them, by consequence</span><b>{decisions.length ? plural(decisions.length, 'decision') : 'No decision to make'}</b>
          <p>Blockers first: images that cannot be read or identified, and declared separation. Then comparison limits and review candidates. Similarity alone proves neither leakage nor an incorrect label.</p></div>
        {!companion?.actions && fs.length > 0 && <p className="nk-ch__not">The report’s grouping could not be read for this result; the recorded findings are listed in recorded order.</p>}
        <ul className="ap-scope"><li>{plural(profile.occurrences, 'occurrence')} across {plural(profile.source_count, 'source')} and {plural(profile.image_locations, 'image location')}.</li></ul>
      </>
    ),
  };

  const tiles: Tile[] = families.map((fam, i) => {
    const recs = ev.filter((e) => e.family === fam), ffs = fs.filter((f) => f.family === fam), d = recs[0]?.data ?? {}, shade = SHADES[i % SHADES.length];
    const [label, detail] = (FACE[fam] ?? (() => firstCount(d)))(d, recs);
    const pairs = recs.flatMap(pairsIn), pairFamily = fam === 'near_duplicates' || fam === 'embeddings';
    return {
      id: fam, name: name.family(fam), n: '', kicker: words(recs[0]?.scope), bg: shade[0], light: shade[1], tone: toneFrom(ffs), label,
      detail: ffs.length ? `${name.meaning(ffs[0].meaning)} · ${detail}` : detail,
      // A face has room for its label and detail only; the chart is drawn in the chapter.
      bigViz: pairFamily && pairs.length ? <PairDiagram pairs={pairs} cited={cited} big /> : faceViz(fam, d, ffs.length > 0) ?? undefined,
      chapter: (
        <>
          <h3>{name.family(fam)}</h3>
          <div className="nk-ch__run"><span>{name.meaning(recs[0]?.meaning)} · {words(recs[0]?.scope)}</span><b>{ffs.length ? plural(ffs.length, 'finding') : label}</b><p>{ffs.length ? label : detail}</p></div>
          {ffs.map((f) => (
            <FindingBlock key={f.id} f={f} title={`${name.family(fam)} · ${n(f.count)}`}>
              {!pairFamily && <References refs={f.references ?? []} note={slots.readOnly ?? ''} />}
            </FindingBlock>
          ))}
          {pairFamily && (pairs.length
            ? <>
                <p className="nk-ch__not">Similarity is a review candidate: it does not prove leakage or identify a correct annotation.{pairs.some(cited) ? '' : ' No retained pair is cited directly by a finding in this result.'}</p>
                {slots.pairs ? slots.pairs(pairs) : <><ul className="ap-more__list">{pairs.slice(0, 12).map((p, k) => <li key={k}>{measure(p)} · {short(p.left)} ↔ {short(p.right)}{cited(p) ? ' · cited' : ''}</li>)}</ul><p className="nk-ch__lim">{slots.readOnly}</p></>}
              </>
            : <p className="nk-ch__not">No pair was retained.</p>)}
          {recs.map((e) => <RecordView key={e.id} e={e} title={recs.length > 1 ? `${name.family(fam)} · ${words(e.data.reference ?? e.id)} → ${words(e.data.current ?? '')}` : undefined} />)}
        </>
      ),
    };
  });

  // A similarity search that stopped at a planned bound: what it did not examine is not a negative result.
  const near = (((a.coverage as Doc | undefined)?.families ?? {}) as Record<string, Doc>).near_duplicates;
  const bounded = near?.stop_reason && near.stop_reason !== 'examined_scope_completed'
    ? [{ text: `Perceptual near-duplicate search stopped at a planned bound (${words(near.stop_reason)})`, reason: String(near.absence_claim ?? 'unexamined search is not a negative result') }] : [];
  return buildDashboard(a, companion, {
    composition: 'image', variant: 'image', saved,
    identity: { name: String(profile.dataset_name ?? 'Image audit'), sources: plural(profile.source_count, 'source'), workflow: 'Image reliability',
                when: String(a.generated_at ?? ''), methodology: String(a.methodology_id ?? ''), schema: String(a.schema_version ?? ''), scale: plural(profile.occurrences, 'occurrence') },
    statement: String(profile.summary ?? '') || undefined, tiles: [hero, ...tiles], tileOf: (f) => String(f.family),
    extract: (f) => ({ scope: `${words(f.family)} · ${n(f.count)}`, statement: String(f.action ?? '') || undefined }),
    coverage: { bounded, methodology: [{ text: 'Portable downloads', reason: 'aggregate evidence and opaque references only; no images or labels unless explicitly disclosed' }] },
  });
}
