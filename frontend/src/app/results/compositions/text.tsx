// Text reliability (M6). The hero is the report's own review actions (text_presentation.executive_summary, via the
// presentation companion), in the report's order: deterministic violations, contextual observations, heuristic
// candidates, model-assisted candidates. Text findings record an evidence meaning, never a priority, and that is what
// the ledger and tiles show. One tile per evidence family, named as the report names it, with a face read from the
// family's own recorded counts. Counts across representations are never added. Revealing text is a live, local action
// supplied by the page (`reveal`); a saved entry names references only.
import type { ReactNode } from 'react';
import { BarList } from '../charts/Bars';
import type { Companion, Dashboard } from '../model';
import type { Tile } from '../Tiles';
import { buildDashboard } from './common';
import { SHADE } from './tabular';
import { CountBars, FindingBlock, RecordView, References, SHADES, arr, counts, firstCount, n, namer, num, plural, sumOf, toneFrom, words, type Doc, type Ev, type Face, type Fnd } from './evidence';

export interface TextSlots { reveal?: (refs: string[]) => ReactNode; readOnly?: string }

const FACE: Record<string, (d: Doc, recs: Ev[]) => Face> = {
  invalidity: (d) => [plural(d.invalid_items, 'invalid item'), counts(d.reasons).map(([k, v]) => `${words(k)} ${n(v)}`).join(' · ') || 'No invalidity reason recorded.'],
  corpus: (d) => [plural(d.content_units, 'content unit'), `${n(d.characters)} characters · ${n(d.nfc_changed_units)} changed by NFC`],
  identities: (d) => [`${n(d.ambiguous_occurrences)} ambiguous · ${n(d.missing_identities)} missing`, 'logical identities'],
  exact_duplicates: (_, recs) => [recs.map((e) => `${words(e.data.representation)}: ${plural(e.data.groups, 'group')}`).join(' · '),
    recs.length > 1 ? 'Counted per representation; the counts are not added.' : `${n(recs[0]?.data.excess_occurrences)} excess occurrences`],
  annotations: (d) => [plural(d.annotation_items, 'annotation item'), `${n(d.annotation_collections)} collections · correctness not established`],
  annotation_categories: (d) => [plural(d.category_count, 'category', 'categories'), `${n(d.retained_category_omissions)} omitted from retained detail`],
  annotation_disagreement: (d) => [plural(d.repeated_input_groups_with_disagreement, 'disagreeing group'), 'repeated inputs with different annotations'],
  conversations: (d) => [plural(d.conversations, 'conversation'), `${plural(d.messages, 'message')} · ${plural(sumOf(d.violations), 'requirement violation')}`],
  retrieval: (d) => [plural(d.extractive_parent_count, 'extractive parent'), d.extractive_character_coverage == null ? 'Character coverage unavailable for this corpus.' : `character coverage ${n(d.extractive_character_coverage)}`],
  lexical_selection: (d) => [`${n(d.selected_population)} of ${n(d.eligible_population)} units selected`, `${plural(d.framed_records, 'framed record')} · ${n(d.invalid_records)} invalid`],
  repetition: (d) => [`${plural(d.units_with_repeated_nonblank_lines, 'unit')} with repeated lines`, 'Repetition is not claimed as a quality violation.'],
  vocabulary: (d) => [plural(d.observed_distinct_tokens, 'distinct token'), `${n(d.token_occurrences)} occurrences in ${plural(d.unit_count, 'unit')}`],
  near_duplicates: (d) => [plural(d.qualifying_pairs, 'qualifying pair'), `${n(d.subthreshold_candidates)} below the ${n(d.threshold)} threshold · not transitive`],
  passages: (d) => [plural(d.verified_passage_matches, 'verified passage match', 'verified passage matches'), `at least ${n(d.minimum_graphemes)} graphemes`],
  language: (d) => [`${plural(d.window_disagreement_or_unresolved, 'window')} disagree or unresolved`, counts(d.predicted_unit_counts).map(([k, v]) => `${k} ${n(v)}`).join(' · ') || 'model-assisted identification'],
  tokenizer_vocabulary: (d) => [plural(d.observed_distinct_token_ids, 'distinct token id'), `${n(d.token_occurrences)} occurrences in ${plural(d.examined_units, 'unit')}`],
  semantic_similarity: (d) => [plural(arr(d.neighbors).length, 'retained neighbour'), 'Segment similarity; document equivalence is not claimed.'],
};

function faceViz(fam: string, d: Doc, hot: boolean): ReactNode {
  if (fam === 'invalidity') return <CountBars o={d.reasons} caption="Invalid items by recorded reason" unit="items" hot={() => hot} />;
  if (fam === 'corpus') return <CountBars o={d.states} caption="Content units by recorded state" unit="units" />;
  if (fam === 'conversations') return <CountBars o={d.role_counts} caption="Messages by recorded role" unit="messages" />;
  if (fam === 'near_duplicates') {
    const q = num(d.qualifying_pairs), s = num(d.subthreshold_candidates);
    return q + s ? <BarList scale="max" unit="pairs" denominator={q + s} caption={`Candidate pairs at and below the ${n(d.threshold)} threshold`}
      bars={[{ label: 'qualifying', value: q, hot }, { label: 'below threshold', value: s }]} /> : null;
  }
  return null;
}

export function textDashboard(a: Doc, companion: Companion | null, saved: boolean, slots: TextSlots = {}): Dashboard {
  const ev = (a.evidence as Ev[] | undefined) ?? [], fs = (a.findings as Fnd[] | undefined) ?? [], profile = (a.profile as Doc | undefined) ?? {};
  const name = namer(companion), families = [...new Set(ev.map((e) => e.family))];
  const coverage = ((a.coverage as Doc | undefined)?.families ?? {}) as Record<string, Doc>;
  const lexical = coverage.lexical_selection, semantic = coverage.semantic_similarity;
  const populations = Object.values((profile.source_populations ?? {}) as Record<string, Doc>);
  const framed = populations.reduce((t, p) => t + num(p.records), 0), invalid = populations.reduce((t, p) => t + num(p.invalid_records), 0);

  // The report's review actions, in its order. Without the companion, the recorded findings in recorded order.
  type Action = { family?: string; meaning?: string | null; action?: string | null; observations?: string[] };
  const actions: Action[] = companion?.actions ?? fs.map((f) => ({ family: f.family, meaning: f.meaning, action: f.action, observations: [] }));
  const scope = [
    `Required checks accounted for ${plural(framed, 'framed record')}; ${n(invalid)} invalid records remain in the population.`,
    ...(lexical ? [`Lexical selection examined ${n(lexical.selected_population)} of ${n(lexical.eligible_population)} eligible units.`] : []),
    ...(semantic ? [`Semantic investigation embedded ${n(semantic.embedded_parents)} of ${n(semantic.eligible_parents)} eligible parents; segment similarity does not establish document equivalence.`] : []),
  ];
  const ActionList = ({ full }: { full?: boolean }) => (
    <ol className="ap-actions">
      {actions.map((x, i) => (
        <li key={i} className={x.meaning === 'deterministic_violation' ? 'is-hot' : ''}>
          <b>{name.family(String(x.family ?? ''))}</b><span>{name.meaning(x.meaning ?? undefined)}{x.observations?.length ? ` · ${x.observations.join(' · ')}` : ''}</span>
          {full && x.action && <p>{x.action}</p>}
        </li>
      ))}
    </ol>
  );
  const hero: Tile = {
    id: 'actions', hero: true, name: 'Review actions', n: '01', kicker: plural(fs.length, 'technical finding'), bg: SHADE.deep[0], light: true,
    tone: toneFrom(fs), label: actions.length ? plural(actions.length, 'review action') : 'No review action',
    detail: actions.length ? `${name.family(String(actions[0].family ?? ''))} first · ordered as in the report` : scope[0],
    viz: actions.length ? <ActionList /> : undefined, bigViz: actions.length ? <ActionList full /> : undefined,
    chapter: (
      <>
        <h3>Review actions</h3>
        <div className="nk-ch__run"><span>As the report groups them</span><b>{actions.length ? plural(actions.length, 'review action') : 'No review action'}</b>
          <p>Grouped by family, evidence meaning and action, in the report’s order. Counts across representations are not added. Candidates are review items, not verdicts.</p></div>
        {!companion?.actions && fs.length > 0 && <p className="nk-ch__not">The report’s grouping could not be read for this result; the recorded findings are listed in recorded order.</p>}
        <ul className="ap-scope">{scope.map((s) => <li key={s}>{s}</li>)}</ul>
      </>
    ),
  };

  const tiles: Tile[] = families.map((fam, i) => {
    const recs = ev.filter((e) => e.family === fam), ffs = fs.filter((f) => f.family === fam), d = recs[0]?.data ?? {}, shade = SHADES[i % SHADES.length];
    const [label, detail] = (FACE[fam] ?? (() => firstCount(d)))(d, recs);
    const observations = (companion?.actions ?? []).filter((x) => x.family === fam).flatMap((x) => x.observations ?? []);
    return {
      id: fam, name: name.family(fam), n: '', kicker: words(recs[0]?.scope), bg: shade[0], light: shade[1], tone: toneFrom(ffs), label,
      detail: ffs.length ? `${name.meaning(ffs[0].meaning)}${observations.length ? ` · ${observations.join(' · ')}` : ''}` : detail,
      // A face has room for its label and detail only; the chart is drawn in the chapter.
      bigViz: faceViz(fam, d, ffs.length > 0) ?? undefined,
      chapter: (
        <>
          <h3>{name.family(fam)}</h3>
          <div className="nk-ch__run"><span>{name.meaning(recs[0]?.meaning)} · {words(recs[0]?.scope)}</span><b>{ffs.length ? plural(ffs.length, 'finding') : label}</b><p>{ffs.length ? label : detail}</p></div>
          {ffs.map((f) => (
            <FindingBlock key={f.id} f={f} title={`${name.family(fam)} · ${n(f.count)}`}>
              {f.references?.length ? (slots.reveal ? slots.reveal(f.references) : <References refs={f.references} note={slots.readOnly ?? ''} />) : null}
            </FindingBlock>
          ))}
          {recs.map((e) => <RecordView key={e.id} e={e} title={recs.length > 1 ? `${name.family(fam)} · ${words(e.data.representation ?? e.scope)}` : undefined} />)}
        </>
      ),
    };
  });

  const bounded = [
    ...(lexical && num(lexical.selected_population) < num(lexical.eligible_population) ? [{ text: `Lexical selection examined ${n(lexical.selected_population)} of ${n(lexical.eligible_population)} eligible units`, reason: 'each investigation has its own additional work limits' }] : []),
    ...(semantic && num(semantic.embedded_parents) < num(semantic.eligible_parents) ? [{ text: `Semantic investigation embedded ${n(semantic.embedded_parents)} of ${n(semantic.eligible_parents)} eligible parents`, reason: 'segment similarity does not establish document equivalence' }] : []),
  ];
  return buildDashboard(a, companion, {
    composition: 'text', variant: 'text', saved,
    identity: { name: String(profile.dataset_name ?? 'Text audit'), sources: plural(profile.source_count, 'source'), workflow: 'Text reliability',
                when: String(a.generated_at ?? ''), methodology: String(a.methodology_id ?? ''), schema: String(a.schema_version ?? ''), scale: plural(framed, 'framed record') },
    statement: String(profile.summary ?? '') || undefined, tiles: [hero, ...tiles], tileOf: (f) => String(f.family),
    extract: (f) => ({ scope: [words(f.family), ...(companion?.actions ?? []).filter((x) => x.family === f.family && x.meaning === f.meaning).flatMap((x) => x.observations ?? []).slice(0, 2)].join(' · '),
                       statement: String(f.action ?? '') || undefined }),
    coverage: { bounded },
  });
}
