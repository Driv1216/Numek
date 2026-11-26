// Classification (binary, multiclass, single-class; with or without context declarations): the one composition with a
// defined scoring policy. The score earns the hero; target balance and the guardrails explain it.
import type { ReactNode } from 'react';
import { BarList } from '../charts/Bars';
import { EvidenceTable } from '../charts/EvidenceTable';
import type { Companion, Dashboard } from '../model';
import { ResultsShell, useCompanion } from '../shell/ResultsShell';
import { buildDashboard } from './common';
import { checkedRoute, Facts, FindingBlocks, SHADE, columnsTile, contextFacts, identityOf, missingTile, n, numericTile, otherTile, pct, repeatsTile, routeOf, statementOf, toneOf, type Doc } from './tabular';

interface Guardrail { code: string; cap: number; explanation: string }
interface Values { sub_scores: Record<string, number>; evidence_score: number; overall: number; risk_level: string; guardrails: Guardrail[]; recommended_action?: string }
const SUB: Record<string, string> = { completeness: 'Completeness', uniqueness: 'Uniqueness', target_balance: 'Target balance', feature_usability: 'Feature usability', leakage_risk: 'Leakage risk' };
const CRITICAL = 50;

/** Sub-scores on their 0–100 scale with the critical line at 50, then the evidence score and the governing cap. */
export function SubScores({ v, compact }: { v: Values; compact?: boolean }) {
  const cap = v.guardrails.length ? Math.min(...v.guardrails.map((g) => g.cap)) : null;
  const row = (label: string, value: number, extra?: ReactNode, critical = true) => (
    <li key={label} className={critical && value <= CRITICAL ? 'is-hot' : ''}>
      <span className="ap-subs__l">{label}</span>
      <span className="ap-subs__t" aria-hidden="true"><i style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />{critical && <em style={{ left: `${CRITICAL}%` }} />}{extra}</span>
      <span className="ap-subs__v">{value.toLocaleString('en-US')}</span>
    </li>
  );
  return (
    <figure className="ap-chart ap-subs">
      <ul aria-label="Sub-scores, evidence score and final score on a 0 to 100 scale">
        {Object.entries(v.sub_scores).map(([k, value]) => row(SUB[k] ?? k, value))}
        {!compact && row('Evidence score (mean)', v.evidence_score, cap != null ? <b style={{ left: `${cap}%` }} title={`cap ${cap}`} /> : null, false)}
      </ul>
      <figcaption>0–100 · line at {CRITICAL}: a sub-score at or below it triggers the critical-sub-score guardrail{cap != null ? ` · coral mark: governing cap ${cap}` : ''}.</figcaption>
    </figure>
  );
}

function scoreTile(a: Doc, v: Values, route: (f: Doc) => string): Dashboard['tiles'][number] {
  const cap = v.guardrails.length ? Math.min(...v.guardrails.map((g) => g.cap)) : null;
  const governing = v.guardrails.filter((g) => g.cap === cap), others = v.guardrails.filter((g) => g.cap !== cap);
  const method = (((a.guidance as Doc | undefined)?.scoring as Doc | undefined)?.overall_method as string | undefined);
  return {
    id: 'score', hero: true, name: 'Reliability score', n: '01', kicker: 'review policy', bg: SHADE.deep[0], light: SHADE.deep[1],
    tone: v.guardrails.length ? 'critical' : v.risk_level === 'Low' ? 'clear' : 'finding',
    label: `${v.overall.toFixed(1)} · ${v.risk_level}`,
    detail: cap != null ? `Capped at ${cap}: ${governing.map((g) => g.explanation).join(' ')}` : `Evidence score ${v.evidence_score}; no guardrail applied.`,
    viz: <SubScores v={v} compact />, bigViz: <SubScores v={v} />,
    chapter: <>
      <h3>Reliability score</h3>
      <div className="nk-ch__run"><span>DataTrust’s classification review policy</span><b>{v.overall.toFixed(1)} · {v.risk_level} risk</b>
        <p>A heuristic review policy, not a validated probability. The evidence score is the mean of five sub-scores; the final score is that mean, capped by the lowest triggered guardrail.</p></div>
      <FindingBlocks a={a} tile="score" route={route} />
      <Facts rows={[['Evidence score', `${v.evidence_score} (mean of ${Object.keys(v.sub_scores).length} sub-scores)`], ['Governing cap', cap != null ? `${cap} · ${governing.map((g) => g.code.replace(/_/g, ' ')).join(', ')}` : 'None triggered'],
        ['Final score', `${v.overall} · ${v.risk_level}`], ...(others.length ? [['Also triggered', others.map((g) => `${g.code.replace(/_/g, ' ')} (cap ${g.cap})`).join('; ')] as [string, string]] : []),
        ...(v.recommended_action ? [['Recommended action', v.recommended_action] as [string, string]] : [])]} />
      {!!v.guardrails.length && <EvidenceTable caption="Triggered guardrails" where="the report’s scoring section" rows={v.guardrails.map((g) => ({ guardrail: g.code.replace(/_/g, ' '), cap: g.cap, governing: g.cap === cap, explanation: g.explanation }))} />}
      {method && <p className="nk-ch__not">{method}</p>}
    </>,
  };
}

function targetTile(a: Doc, route: (f: Doc) => string): Dashboard['tiles'][number] {
  const p = (a.profile as Doc) ?? {};
  const dist = (p.target_distribution as { label: string; count: number; percentage: number }[] | undefined) ?? [];
  const t = toneOf(a, 'target', route);
  const bars = <BarList bars={dist.map((c) => ({ label: c.label, value: c.percentage, note: n(c.count) }))} denominator={(p.labeled_row_count as number) ?? null} unit="%" scale="percent"
    caption="class share of labelled rows" max={12} more="the class table below and the report" />;
  return {
    id: 'target', name: 'Target balance', n: '02', kicker: String(p.target ?? 'target'), bg: SHADE.pale[0], light: SHADE.pale[1], tone: t.tone,
    label: t.count ? `${t.count} finding${t.count === 1 ? '' : 's'} · ${String(t.top?.severity)}` : `${dist.length} class${dist.length === 1 ? '' : 'es'}`,
    detail: `Majority ${pct(p.majority_class_baseline)} · majority : minority ${p.majority_to_minority_ratio == null ? 'unavailable' : `${p.majority_to_minority_ratio} : 1`}.`,
    viz: bars,
    chapter: <>
      <h3>Target balance</h3>
      <div className="nk-ch__run"><span>{String(p.target ?? 'Target')} · {String(p.classification_subtype ?? '')} classification</span><b>{dist.length} class{dist.length === 1 ? '' : 'es'}</b>
        <p>Balance is reported, not corrected: DataTrust does not resample or reweight. Missing labels are excluded from the shares.</p></div>
      <FindingBlocks a={a} tile="target" route={route} />
      {bars}
      <Facts rows={[['Labelled rows', n(p.labeled_row_count)], ['Missing labels', `${n(p.target_missing_count)} (${pct(p.target_missing_rate)})`], ['Majority class baseline', pct(p.majority_class_baseline)],
        ['Majority : minority', p.majority_to_minority_ratio == null ? 'Unavailable' : `${p.majority_to_minority_ratio} : 1`]]} />
      {dist.length > 12 && <EvidenceTable caption="Every class" rows={dist.map((c) => ({ class: c.label, rows: c.count, share_pct: c.percentage }))} where="the report" />}
    </>,
  };
}

function leakageTile(a: Doc, route: (f: Doc) => string): Dashboard['tiles'][number] {
  const p = (a.profile as Doc) ?? {};
  const strong = (p.strong_leakage_candidates as string[] | undefined) ?? [], review = (p.review_only_leakage_candidates as string[] | undefined) ?? [];
  const details = (p.leakage_details as { column: string; classification: string; reason: string }[] | undefined) ?? [];
  const t = toneOf(a, 'leakage', route);
  return {
    id: 'leakage', name: 'Leakage name review', n: '03', kicker: 'names · declarations', bg: SHADE.deep[0], light: SHADE.deep[1], tone: t.tone,
    label: t.count ? `${t.count} finding${t.count === 1 ? '' : 's'} · ${String(t.top?.severity)}` : 'No outcome-like names',
    detail: `${strong.length} strong · ${review.length} review-only. When each feature becomes available is not verified.`,
    chapter: <>
      <h3>Leakage name review</h3>
      <div className="nk-ch__run"><span>Column names{a.contextual ? ' and your declarations' : ''}</span><b>{strong.length} strong · {review.length} review-only</b><p>A column name is never treated as proof; strong candidates would cap the score, review-only prompts do not.</p></div>
      <FindingBlocks a={a} tile="leakage" route={route} />
      <Facts rows={[['Strong candidates', strong.join(', ') || 'None'], ['Review-only prompts', review.join(', ') || 'None'], ['Not verified', 'When each feature becomes available'], ...contextFacts(a)]} />
      {!!details.length && <EvidenceTable caption="Name review" rows={details.map((d) => ({ column: d.column, classification: d.classification.replace(/_/g, ' '), reason: d.reason }))} />}
    </>,
  };
}

export function classificationDashboard(a: Doc, companion: Companion | null, saved: boolean): Dashboard {
  const route = (f: Doc) => routeOf('classification', f);
  const scoring = a.scoring as { status?: string; values?: Values | null } | undefined;
  const v = scoring?.status === 'computed' && scoring.values ? scoring.values : null;
  const usability = (((a.guidance as Doc | undefined)?.scoring as Doc | undefined)?.feature_usability as Doc | undefined) ?? null;
  const tiles = [
    ...(v ? [scoreTile(a, v, route)] : []), targetTile(a, route), leakageTile(a, route), missingTile(a, route, 4), repeatsTile(a, route, 5, true),
    numericTile(a, route, 6, { legacy: a.methodology_id === 'classification_legacy_2026_08_13', usability }), columnsTile(a, 7, route),
  ];
  const final = checkedRoute('classification', tiles);
  const other = otherTile(a, final, tiles.length + 1);
  const subtype = String((a.profile as Doc)?.classification_subtype ?? '');
  return buildDashboard(a, companion, {
    composition: 'classification', variant: subtype || 'classification', saved, identity: identityOf(a, 'Classification', subtype ? `${subtype} · target ${String((a.profile as Doc)?.target ?? '')}` : undefined),
    statement: statementOf(a, !!v), tiles: other ? [...tiles, other] : tiles, tileOf: final,
    coverage: { methodology: [{ text: 'Scoring', reason: v ? 'a heuristic review policy (five sub-scores, mean, capped by guardrails), not a validated probability' : scoring?.status ? `scoring ${String(scoring.status).replace(/_/g, ' ')}` : 'not recorded' }] },
  });
}

export function ClassificationPage({ a, out, onOpen, presentation, saved, live }: { a: Doc; out: ReactNode; onOpen: (anchor?: string) => void; presentation: string | null; saved?: boolean; live: boolean }) {
  const companion = useCompanion(presentation);
  if (companion === undefined) return <div className="ap-rs"><div className="nk-mosaic nk-mosaic--big nk-mosaic--run ap-rs__wait" aria-busy="true" /></div>;
  return <ResultsShell d={classificationDashboard(a, companion, !!saved)} label="Classification evidence" out={out} onOpenReport={onOpen} live={live} />;
}
