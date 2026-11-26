// Records and documents (M9). The hero is reconciliation: each declared rule's recorded outcomes over its records,
// named as the report names them (agreements, discrepancies, conflicting supplied evidence, assigned to optional
// investigation). One tile per evidence family, with the report's own section title, population names and per-
// population explanation. Optional model judgments are shown exactly as recorded: when every examined judgment
// abstained, the tile says so with the recorded reasons; "not requested" appears only when no claim was selected.
// The review-target table, inspection, disclosure and review import/export are supplied by the page (`targets`).
import type { ReactNode } from 'react';
import type { Companion, Dashboard } from '../model';
import type { Tile } from '../Tiles';
import { buildDashboard } from './common';
import { SHADE } from './tabular';
import { CountBars, FindingBlock, RecordView, SHADES, arr, firstCount, n, namer, num, plural, toneFrom, words, type Doc, type Ev, type Face, type Fnd } from './evidence';

export interface CrossSlots { targets?: ReactNode }

const OUTCOMES = ['satisfied', 'violated', 'conflicting_evidence', 'inconclusive', 'incomplete', 'unassessed'];
const HOT = new Set(['violated', 'conflicting_evidence']);
// The recorded outcome fields of the optional model investigations (cross_models), including abstention.
const JUDGMENTS = new Set(['abstained', 'support_candidate', 'contradiction_candidate', 'mixed_evidence', 'misassociation_candidate', 'compatibility_candidate']);
const sum = (recs: Ev[], k: string) => recs.reduce((t, e) => t + num(e.data[k]), 0);

const FACE: Record<string, (recs: Ev[]) => Face> = {
  identities: (r) => [`${n(sum(r, 'records'))} records · ${n(sum(r, 'invalid_records'))} invalid`, `${plural(sum(r, 'cardinality_violations'), 'cardinality violation')} · ${plural(r.length, 'source')}`],
  relationships: (r) => [plural(sum(r, 'associations'), 'association'), `${n(sum(r, 'required_gap'))} required gaps · ${n(sum(r, 'inverse_gap'))} inverse gaps · ${n(sum(r, 'duplicate_association_rows'))} duplicate rows`],
  context: (r) => [`${n(sum(r, 'violated'))} violated · ${n(sum(r, 'inconclusive'))} inconclusive`, `of ${plural(sum(r, 'associations'), 'association')} · ${plural(sum(r, 'affected_records'), 'record')} affected`],
  separation: (r) => [`${n(sum(r, 'violated'))} violated · ${n(sum(r, 'inconclusive'))} inconclusive`, `${n(sum(r, 'satisfied'))} satisfied`],
};

export function crossDashboard(a: Doc, companion: Companion | null, saved: boolean, slots: CrossSlots = {}): Dashboard {
  const ev = (a.evidence as Ev[] | undefined) ?? [], fs = (a.findings as Fnd[] | undefined) ?? [], profile = (a.profile as Doc | undefined) ?? {}, cov = (a.coverage as Doc | undefined) ?? {};
  const name = namer(companion), method = (cov.families ?? {}) as Record<string, Doc>;

  // Hero: every declared rule's outcomes over its records.
  const rules = ev.filter((e) => e.family === 'reconciliation').map((e) => ({ e, records: num(e.data.records), parts: OUTCOMES.filter((k) => num(e.data[k]) > 0).map((k) => ({ k, count: num(e.data[k]) })) }));
  const assessed = rules.filter((r) => r.records > num(r.e.data.unassessed));
  const satisfied = assessed.reduce((t, r) => t + num(r.e.data.satisfied), 0), checked = assessed.reduce((t, r) => t + r.records, 0);
  // Each rule as a named row: its outcomes in the report's words, and a bar of those outcomes over its records.
  const ruleBars = (big?: boolean) => (
    <ul className="ap-rules" aria-label="Outcomes per declared rule">
      {(big ? rules : rules.slice(0, 3)).map((r) => (
        <li key={r.e.id}>
          <b>{name.population(r.e.population)} · {String(method[String(r.e.population)]?.method ?? r.e.data.method ?? '')}</b>
          <span className="ap-rules__t" aria-hidden="true">{r.parts.map((p) => <i key={p.k} className={`is-${p.k} ${HOT.has(p.k) ? 'is-hot' : ''}`} style={{ width: `${r.records ? (p.count / r.records) * 100 : 0}%` }} />)}</span>
          <span>{r.parts.map((p) => `${name.status(p.k)} ${n(p.count)}`).join(' · ')} · of {plural(r.records, 'record')}</span>
        </li>
      ))}
    </ul>
  );
  const recFindings = fs.filter((f) => f.family === 'reconciliation');
  const hero: Tile = {
    id: 'reconciliation', hero: true, name: name.family('reconciliation'), n: '01', kicker: plural(rules.length, 'rule'), bg: SHADE.deep[0], light: true,
    tone: toneFrom(recFindings), label: assessed.length ? `${n(satisfied)} of ${n(checked)} ${assessed.length === 1 ? 'records' : 'record checks'} agree` : 'No rule could be assessed',
    detail: `${plural(profile.records, 'record')} · ${plural(profile.documents, 'document')} · ${plural(profile.pages, 'page')}`,
    viz: ruleBars(), bigViz: ruleBars(true),
    chapter: (
      <>
        <h3>{name.family('reconciliation')}</h3>
        <div className="nk-ch__run"><span>Records against supplied evidence, per declared rule</span><b>{assessed.length ? `${n(satisfied)} of ${n(checked)} agree` : 'No rule could be assessed'}</b>
          <p>Agreement is judged on examined evidence only. A satisfied rule does not certify a document, and an unassessed rule makes no claim.</p></div>
        {recFindings.map((f) => <FindingBlock key={f.id} f={f} title={String(f.title ?? name.family(f.family))}><p>{name.population(f.population)}</p></FindingBlock>)}
        {rules.map((r) => name.explanation(r.e.id) && <p key={r.e.id} className="nk-ch__not">{name.population(r.e.population)}: {name.explanation(r.e.id)}</p>)}
        {slots.targets}
      </>
    ),
  };

  const families = [...new Set(ev.map((e) => e.family))].filter((f) => f !== 'reconciliation');
  const tiles: Tile[] = families.map((fam, i) => {
    const recs = ev.filter((e) => e.family === fam), ffs = fs.filter((f) => f.family === fam), shade = SHADES[i % SHADES.length];
    let [label, detail] = (FACE[fam] ?? ((r: Ev[]) => firstCount(r[0]?.data ?? {})))(recs);
    let viz: ReactNode;
    if (fam === 'models') {
      // Judgment outcomes are the recorded counts; reasons come from the retained details.
      const outcomes: Doc = {};
      for (const e of recs) for (const [k, v] of Object.entries(e.data)) if (typeof v === 'number' && JUDGMENTS.has(k)) outcomes[k] = num(outcomes[k]) + v;
      const total = Object.values(outcomes).reduce<number>((t, v) => t + num(v), 0), abstained = num(outcomes.abstained);
      const reasons = new Map<string, number>();
      for (const e of recs) for (const d of arr(e.data.details)) if (d.status === 'abstained' && d.reason) reasons.set(String(d.reason), (reasons.get(String(d.reason)) ?? 0) + 1);
      const models = cov.models as Doc | undefined;
      if (total && abstained === total) { label = `All ${n(total)} judgments abstained`; detail = [...reasons].map(([k, v]) => `${words(k)} ${n(v)}`).join(' · ') || 'No model judgment was made.'; }
      else if (total) { label = plural(total, 'optional judgment'); detail = Object.entries(outcomes).filter(([, v]) => num(v) > 0).map(([k, v]) => `${name.status(k)} ${n(v)}`).join(' · ') + (models ? ` · ${n(models.examined)} of ${n(models.selected)} selected claims examined` : ''); }
      viz = <CountBars o={outcomes} caption="Optional judgments by recorded outcome (candidates, not verdicts)" label={name.status} />;
    }
    return {
      id: fam, name: name.family(fam), n: '', kicker: recs.length > 1 ? plural(recs.length, 'population') : name.population(recs[0]?.population), bg: shade[0], light: shade[1], tone: toneFrom(ffs), label,
      detail: ffs.length ? String(ffs[0].title ?? detail) : detail, bigViz: viz,
      chapter: (
        <>
          <h3>{name.family(fam)}</h3>
          <div className="nk-ch__run"><span>{recs.map((e) => name.population(e.population)).join(' · ')} · {words(recs[0]?.scope)}</span><b>{ffs.length ? plural(ffs.length, 'finding') : label}</b><p>{detail}</p></div>
          {ffs.map((f) => <FindingBlock key={f.id} f={f} title={String(f.title ?? name.family(f.family))}><p>{name.population(f.population)}</p></FindingBlock>)}
          {recs.map((e) => <RecordView key={e.id} e={e} title={recs.length > 1 ? name.population(e.population) : undefined} note={name.explanation(e.id)} />)}
        </>
      ),
    };
  });

  const models = cov.models as Doc | null | undefined, selected = (cov.model_selected as Record<string, number> | undefined) ?? {};
  const anyModel = Object.values(selected).some((v) => num(v) > 0);
  const countsOf = (f: Doc) => Object.entries((f.counts as Doc) ?? {}).filter(([k, v]) => typeof v === 'number' && k !== 'records' && v > 0).map(([k, v]) => `${name.status(k)} ${n(v)}`).join(' · ');
  return buildDashboard(a, companion, {
    composition: 'cross', variant: 'records_documents', saved,
    identity: { name: String(profile.dataset_name ?? 'Records ↔ documents'), sources: plural(profile.source_count, 'source'), workflow: 'Records ↔ documents',
                when: String(a.generated_at ?? ''), methodology: String(a.methodology_id ?? ''), schema: String(a.schema_version ?? ''),
                scale: `${plural(profile.records, 'record')} · ${plural(profile.documents, 'document')} · ${plural(profile.pages, 'page')}` },
    statement: String(profile.summary ?? '') || undefined, tiles: [hero, ...tiles],
    tileOf: (f) => String(f.family),
    extract: (f) => ({ scope: name.population(String(f.population ?? '')), statement: countsOf(f) || undefined }),
    coverage: {
      // The optional investigations examine only the claims selected for them: a planned bound on the search.
      bounded: models && num(models.selected) ? [{ text: `Optional model judgments examined ${n(models.examined)} of ${n(models.selected)} selected claims`, reason: models.stop_reason ? String(models.stop_reason) : 'within the configured work limits' }] : [],
      notRequested: anyModel ? [] : [{ text: 'Optional model judgments (NLI, paired image–text)', reason: 'no claim was selected for a model judgment in this configuration' }],
      methodology: [{ text: 'Portable downloads', reason: 'analytical downloads omit source content and use opaque references; the private manifest and review JSON are separate files, and review JSON includes your notes' }],
    },
  });
}
