// The approved M4 Roles layout: a role strip with line-kit connectors, then pair and per-source tiles that
// grow into chapters, then the canonical actions and coverage. Every value is read from the canonical JSON.
import type { ReactNode } from 'react';
import { Status } from '../../foundation/system';
import type { M4Analysis, M4Finding } from '../api';
import { date, type Tone } from './adapter';
import { CheckScope, ScopeNote, Tiles, type Tile } from './Tiles';

type Dict = Record<string, unknown>;
const SHADES: [string, boolean][] = [['#163F52', true], ['#D5E4EB', false], ['#2C6E8E', true], ['#FBFAF7', false], ['#BCD3DE', false]];
const PAIR_ORDER = ['split_integrity', 'schema', 'populations', 'segment_mix'];
const SOURCE_ORDER = ['structure', 'repeated_inputs', 'annotations', 'annotation_cohorts', 'segments', 'missingness_structure', 'dependencies', 'constraints', 'unsupervised_readiness', 'multilabel', 'arithmetic_relationships'];
const NAMES: Record<string, string> = {
  split_integrity: 'Overlap', schema: 'Schema', populations: 'Populations', segment_mix: 'Segment mix', overlap_row_unions: 'Overlap across roles',
  structure: 'Structure', repeated_inputs: 'Repeated inputs', annotations: 'Annotations', annotation_cohorts: 'Annotation cohorts', segments: 'Segments',
  missingness_structure: 'Missingness structure', dependencies: 'Dependencies', constraints: 'Constraints', unsupervised_readiness: 'Unsupervised readiness',
  multilabel: 'Multilabel', arithmetic_relationships: 'Arithmetic relationships',
};
export const M4_MODE_LABEL: Record<string, string> = { splits: 'Split audit', versions: 'Version comparison', advanced: 'Advanced analysis', before_after: 'Before and after preprocessing' };

const n = (v: unknown) => (typeof v === 'number' ? v.toLocaleString('en-US') : v == null ? '—' : String(v));
const pct = (v: unknown) => (typeof v === 'number' ? `${(v * 100).toLocaleString('en-US', { maximumFractionDigits: 1 })}%` : '—');
const arr = (v: unknown) => (Array.isArray(v) ? (v as Dict[]) : []);
const base = (p: string | undefined | null) => (p ? p.split(/[\\/]/).pop() ?? p : '');

export function rolesOf(a: M4Analysis) {
  const sources = (a.profile.sources ?? {}) as Record<string, Dict>;
  if (a.inputs?.length) return a.inputs.map((i) => ({ id: i.id, role: i.role, file: i.dataset.source_filename ?? base(i.dataset.path), rows: sources[i.id]?.row_count, cols: sources[i.id]?.column_count, sha: (sources[i.id]?.source as Dict | undefined)?.sha256 as string | undefined }));
  return [{ id: 'dataset', role: 'dataset', file: a.dataset?.source_filename ?? base(a.dataset?.path), rows: a.profile.row_count, cols: a.profile.column_count, sha: (a.profile.source as Dict | undefined)?.sha256 as string | undefined }];
}

export function runName(a: M4Analysis) {
  return a.context.dataset_name || a.comparison?.dataset_name || M4_MODE_LABEL[a.comparison?.preset ?? a.comparison?.mode ?? 'advanced'];
}

/** Split a measurement key into its scope ('train', 'a:b', 'dataset', 'comparison') and its check. */
function parse(key: string) { const i = key.lastIndexOf('.'); return { scope: key.slice(0, i), check: key.slice(i + 1) }; }

/** Declared identity units lead; otherwise identical records. */
function overlapLabel(m: Dict) {
  const unit = arr(m.units).find((u) => Number(u.shared_distinct_groups) > 0) ?? arr(m.units)[0];
  return unit ? `${n(unit.shared_distinct_groups)} shared ${(unit.columns as string[]).join(' + ')}` : `${n(((m.records ?? {}) as Dict).shared_distinct_groups)} shared records`;
}

function summary(check: string, m: Dict, role: (id: string) => string, scope: string): { label: string; detail: string; facts: [string, string][] } {
  const [l, r] = scope.split(':').map(role);
  switch (check) {
    case 'split_integrity': {
      const rec = (m.records ?? {}) as Dict, feat = (m.features ?? {}) as Dict, unit = arr(m.units)[0];
      const lead = overlapLabel(m);
      return { label: lead, detail: unit ? `${pct(unit.left_share)} of ${l}, ${pct(unit.right_share)} of ${r}; ${n(rec.shared_distinct_groups)} identical records, ${n(feat.shared_distinct_groups)} identical feature vectors.`
          : `${pct(rec.left_share)} of ${l}, ${pct(rec.right_share)} of ${r}; ${n(feat.shared_distinct_groups)} shared feature vectors.`,
        facts: [...arr(m.units).map((u) => [`Shared ${(u.columns as string[]).join(' + ')} (${u.kind})`, n(u.shared_distinct_groups)] as [string, string]), ['Shared records', n(rec.shared_distinct_groups)], [`${l} rows`, n(rec.left_rows)], [`${r} rows`, n(rec.right_rows)], ['Multiset intersection', n(rec.multiset_intersection)], ['Shared feature vectors', n(feat.shared_distinct_groups)], ['Definition', String(rec.definition ?? '—')]] };
    }
    case 'schema': {
      const add = arr(m.added).length, rem = arr(m.removed).length, ch = arr(m.changes).length;
      return { label: add + rem + ch ? `${add} added · ${rem} removed · ${ch} changed` : 'No change', detail: [...(m.added as string[] ?? []).map((c) => `+${c}`), ...(m.removed as string[] ?? []).map((c) => `−${c}`), ...arr(m.changes).map((c) => `~${c.column}`)].join(' ') || `Same columns in ${l} and ${r}.`,
        facts: [['Added', (m.added as string[] ?? []).join(', ') || 'None'], ['Removed', (m.removed as string[] ?? []).join(', ') || 'None'], ['Storage or role changes', n(ch)]] };
    }
    case 'populations': {
      const cols = arr(m.columns), top = [...cols].sort((x, y) => Number(y.cdf_distance ?? 0) - Number(x.cdf_distance ?? 0))[0];
      return { label: `${n(cols.length)} columns compared`, detail: top && Number(top.cdf_distance) > 0 ? `Largest CDF distance: ${top.column} (${Number(top.cdf_distance).toPrecision(3)}).` : 'No distribution difference measured.',
        facts: [['Columns', n(cols.length)], ['Missingness for review', n(cols.filter((c) => c.missingness_review).length)]] };
    }
    case 'before_after': {
      const o = (m.observed ?? {}) as Dict, rows = (o.rows ?? {}) as Dict, lin = (m.lineage ?? {}) as Dict, ids = (lin.identities ?? {}) as Dict;
      const cov = (o.target_coverage ?? null) as Dict | null, moved = arr(cov?.classes).filter((c) => Math.abs(Number(c.share_change_points)) >= 2);
      return { label: `${n(rows.before)} → ${n(rows.after)} rows`, detail: `${String(rows.explanation ?? '')} ${String(m.statement ?? '')}`,
        facts: [['Reconciliation', String(rows.reconciliation ?? '—')], ['Lineage', lin.available === false ? 'Unavailable without identity keys' : `${n(ids.retained)} retained · ${n(ids.dropped)} dropped · ${n(ids.added)} added`],
          ['Declared transformations', n(arr(m.declared_transformations).length)], ['Declared but not observed', n(arr(o.declared_but_not_observed).length)],
          ['Undeclared changes', n(arr(o.undeclared_changes).length)], ['Class shares moved ≥ 2 points', moved.length ? moved.map((c) => `${c.class} ${Number(c.share_change_points) > 0 ? '+' : ''}${c.share_change_points}`).join(', ') : 'None'],
          ['Pipeline use', 'Not observed']] };
    }
    case 'structure': return { label: `${n(m.row_count)} rows · ${n(m.column_count)} columns`, detail: `${n(arr(m.columns).filter((c) => Number(c.missing_count) > 0).length)} columns with missing values.`, facts: [['Rows', n(m.row_count)], ['Columns', n(m.column_count)]] };
    case 'repeated_inputs': return { label: `${n(m.repeated_group_count)} repeated groups`, detail: `${n(m.participating_rows)} participating rows; ${n(m.varying_row_union)} with varying targets.`, facts: [['Distinct input vectors', n(m.distinct_input_vectors)], ['Largest group', n(m.largest_group)]] };
    case 'annotations': { const t = arr(m.targets); return { label: `${n(t.length)} target${t.length === 1 ? '' : 's'}`, detail: t.map((x) => `${x.target}: ${n(x.observed)} observed`).join(' · ') || 'No targets declared.', facts: t.map((x) => [String(x.target), `${n(x.observed)} observed · ${n(x.contradictions)} contradictions`] as [string, string]) }; }
    case 'missingness_structure': return { label: `${n(m.distinct_patterns)} missingness patterns`, detail: `${n(m.review_affected_row_union)} rows in patterns for review.`, facts: [['Retained patterns', n(m.retained_patterns)], ['Unsearched patterns', n(m.unsearched_patterns)]] };
    case 'dependencies': { const p = arr(m.pairs); return { label: `${n(p.filter((x) => x.review).length)} of ${n(p.length)} pairs for review`, detail: p.filter((x) => x.review).map((x) => (x.columns as string[]).join(' ~ ')).slice(0, 3).join(' · ') || 'No dependence above the review threshold.', facts: [['Pairs', n(p.length)]] }; }
    case 'constraints': { const d = arr(m.declarations); const v = d.reduce((s, x) => s + Number(x.violations ?? 0), 0); return { label: `${n(v)} violating rows`, detail: `${n(d.length)} declared requirement${d.length === 1 ? '' : 's'}.`, facts: [['Declarations', n(d.length)], ['Violations', n(v)]] }; }
    case 'unsupervised_readiness': return { label: `${n(arr(m.quantitative_columns).length)} quantitative columns`, detail: `${n(arr(m.excluded_from_geometry).length)} excluded from geometry.`, facts: [['Complete vectors', n(m.complete_quantitative_vectors)]] };
    default: { const lists = Object.entries(m).filter(([, v]) => Array.isArray(v)); return { label: lists.length ? `${n((lists[0][1] as unknown[]).length)} ${lists[0][0].replace(/_/g, ' ')}` : 'Measured', detail: 'Details in the chapter and the canonical report.', facts: [] }; }
  }
}

/** The first list of records in a measurement, as a bounded table, as the report's human view does. */
function Table({ m }: { m: Dict }) {
  const entry = Object.entries(m).find(([, v]) => Array.isArray(v) && v.length && typeof v[0] === 'object');
  if (!entry) return null;
  const rows = entry[1] as Dict[];
  const keys = Object.keys(rows[0]).filter((k) => rows.some((r) => ['string', 'number', 'boolean'].includes(typeof r[k]))).slice(0, 6);
  return (
    <div className="ap-chtab">
      <table><thead><tr>{keys.map((k) => <th key={k}>{k.replace(/_/g, ' ')}</th>)}</tr></thead>
        <tbody>{rows.slice(0, 20).map((r, i) => <tr key={i}>{keys.map((k) => <td key={k}>{typeof r[k] === 'number' ? Number(r[k]).toLocaleString('en-US', { maximumSignificantDigits: 6 }) : String(r[k] ?? '—')}</td>)}</tr>)}</tbody></table>
      {rows.length > 20 && <p>{rows.length - 20} more rows in the canonical JSON.</p>}
    </div>
  );
}

function OverlapViz({ m }: { m: Dict }) {
  const rec = (m.records ?? {}) as Dict, ls = Number(rec.left_share ?? 0), rs = Number(rec.right_share ?? 0);
  return (
    <svg viewBox="0 0 200 60" className="md-viz" preserveAspectRatio="xMidYMax meet">
      <rect x={0} y={8} width={200} height={14} rx={2} className="md-ghost" /><rect x={0} y={8} width={200 * ls} height={14} rx={2} className="md-ink" />
      <rect x={0} y={34} width={200} height={14} rx={2} className="md-ghost" /><rect x={0} y={34} width={200 * rs} height={14} rx={2} className="md-ink" />
    </svg>
  );
}

function QuantileViz({ m }: { m: Dict }) {
  const cols = arr(m.columns).filter((c) => Array.isArray(c.left_quantiles) && Array.isArray(c.right_quantiles)).slice(0, 6);
  if (!cols.length) return null;
  return (
    <svg viewBox={`0 0 200 ${cols.length * 22}`} className="md-viz" preserveAspectRatio="xMidYMax meet">
      {cols.map((c, i) => {
        const all = [...(c.left_quantiles as number[]), ...(c.right_quantiles as number[])], lo = Math.min(...all), hi = Math.max(...all), x = (v: number) => (hi > lo ? ((v - lo) / (hi - lo)) * 190 + 5 : 100);
        return (
          <g key={String(c.column)} transform={`translate(0 ${i * 22})`}>
            <line x1={5} x2={195} y1={11} y2={11} className="md-ghost-l" />
            {(c.left_quantiles as number[]).map((v, k) => <circle key={`l${k}`} cx={x(v)} cy={7} r={2.4} className="md-ghost" />)}
            {(c.right_quantiles as number[]).map((v, k) => <circle key={`r${k}`} cx={x(v)} cy={15} r={2.4} className="md-ink" />)}
          </g>
        );
      })}
    </svg>
  );
}

function SchemaViz({ m }: { m: Dict }) {
  const order = (m.right_order as string[] | undefined) ?? [], added = new Set(m.added as string[] ?? []), changed = new Set(arr(m.changes).map((c) => String(c.column)));
  return (
    <svg viewBox={`0 0 200 ${Math.ceil(Math.max(order.length, 1) / 5) * 16}`} className="md-viz" preserveAspectRatio="xMidYMax meet">
      {order.map((c, i) => <rect key={c} x={(i % 5) * 40 + 1} y={Math.floor(i / 5) * 16 + 2} width={36} height={10} rx={2} className={added.has(c) ? 'md-hot' : changed.has(c) ? 'md-ring' : 'md-ghost'} />)}
    </svg>
  );
}

function StructureViz({ m }: { m: Dict }) {
  const cols = arr(m.columns).slice(0, 24), W = 196, bw = W / Math.max(cols.length, 1);
  return (
    <svg viewBox="0 0 196 60" className="md-viz" preserveAspectRatio="xMidYMax meet">
      {cols.map((c, i) => { const h = 6 + 50 * Number(c.missing_rate ?? 0) / 100; return <rect key={i} x={i * bw + 1} y={58 - h} width={bw - 2} height={h} className={Number(c.missing_count) > 0 ? 'md-ink' : 'md-ghost'} />; })}
    </svg>
  );
}

/** Role frames joined by line-kit connectors; coral where a finding for that pair is High or a declared violation. */
function RolesViz({ roles, links, big }: { roles: { role: string; file: string }[]; links: { hot: boolean; text: string }[]; big?: boolean }) {
  const W = 300, H = big ? 170 : 130, k = roles.length, gap = k > 1 ? (W - 20 - k * 96) / (k - 1) : 0, x = (i: number) => 10 + i * (96 + gap), y = H / 2 - 34;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="md-viz" preserveAspectRatio="xMidYMid meet">
      {links.map((l, i) => (
        <g key={i}>
          <line x1={x(i) + 96} x2={x(i + 1)} y1={y + 34} y2={y + 34} className={l.hot ? 'md-cap' : 'md-ghost-l'} />
          <circle cx={x(i) + 96} cy={y + 34} r={3} className={l.hot ? 'md-hot' : 'md-ink'} /><circle cx={x(i + 1)} cy={y + 34} r={3} className={l.hot ? 'md-hot' : 'md-ink'} />
          {big && <text x={(x(i) + 96 + x(i + 1)) / 2} y={y + 26} className="md-t md-t--c md-t--s">{l.text}</text>}
        </g>
      ))}
      {roles.map((r, i) => (
        <g key={i} transform={`translate(${x(i)} ${y})`} className="md-grow" style={{ ['--i' as string]: i }}>
          <rect width={96} height={68} rx={4} className="md-page" />
          <rect width={96} height={6} rx={2} className="md-ink" />
          <text x={8} y={26} className="md-t">{r.role}</text>
          {big && <text x={8} y={44} className="md-t md-t--s">{r.file.length > 14 ? `${r.file.slice(0, 13)}…` : r.file}</text>}
        </g>
      ))}
    </svg>
  );
}

const VIZ: Record<string, (p: { m: Dict }) => ReactNode> = { split_integrity: OverlapViz, populations: QuantileViz, schema: SchemaViz, structure: StructureViz };

export function RolesReport({ a, header, out }: { a: M4Analysis; header: ReactNode; out: ReactNode }) {
  const roles = rolesOf(a);
  const role = (id: string) => roles.find((r) => r.id === id)?.role ?? id;
  const scopeLabel = (scope: string) => (scope.includes(':') ? scope.split(':').slice(0, 2).map(role).join(' ↔ ') : scope === 'comparison' ? 'all roles' : role(scope));
  const checkOf = new Map(a.evidence.map((e) => [e.id, e.check_id]));
  const byCheck = new Map<string, M4Finding[]>();
  for (const f of a.findings) for (const ref of f.evidence_refs ?? []) { const k = checkOf.get(ref); if (k) byCheck.set(k, [...(byCheck.get(k) ?? []), f]); }
  const rank = { High: 0, Moderate: 1, Low: 2 } as const;
  const keys = Object.keys(a.coverage.measurements).filter((k) => parse(k).scope.split(':').length <= 2);
  const order = (k: string) => { const { scope, check } = parse(k); const pair = scope.includes(':'); const roleIdx = roles.findIndex((r) => r.id === scope.split(':')[0]);
    return [pair ? 0 : scope === 'comparison' ? 1 : 2, pair ? PAIR_ORDER.indexOf(check) : roleIdx, pair ? 0 : SOURCE_ORDER.indexOf(check)]; };
  keys.sort((x, y) => { const a1 = order(x), b1 = order(y); return a1[0] - b1[0] || a1[1] - b1[1] || a1[2] - b1[2]; });

  const tiles: Tile[] = keys.map((key, i) => {
    const { scope, check } = parse(key), m = a.coverage.measurements[key], diag = a.coverage.diagnostics[key];
    const fs = [...(byCheck.get(key) ?? [])].sort((x, y) => rank[x.priority] - rank[y.priority]);
    const s = summary(check, m, role, scope);
    const tone: Tone = fs.some((f) => f.priority === 'High' || f.evidence_type === 'declared_violation') ? 'critical' : fs.length ? 'finding' : diag && diag.status !== 'completed' ? 'finding' : 'info';
    const label = fs.length ? `${fs[0].priority}${fs[0].evidence_type === 'declared_violation' ? ' · violated' : ''}` : diag && diag.status !== 'completed' ? diag.status.replace(/_/g, ' ') : s.label;
    const detail = fs.length ? fs[0].title : s.detail;
    const [bg, light] = scope.includes(':') ? SHADES[i % 3] : SHADES[3 + (i % 2)];
    const V = VIZ[check];
    return {
      id: key, name: NAMES[check] ?? check.replace(/_/g, ' '), n: String(i + 2).padStart(2, '0'), kicker: scopeLabel(scope), bg, light, wide: scope.includes(':'), tone, label, detail,
      viz: V ? <V m={m} /> : undefined,
      chapter: (
        <>
          <h3>{NAMES[check] ?? check}</h3>
          <div className="nk-ch__run"><span>{scopeLabel(scope)}</span><b>{fs.length ? `${fs.length} finding${fs.length > 1 ? 's' : ''}` : s.label}</b><p>{s.detail}</p></div>
          {fs.map((f) => (
            <div key={f.id} className="nk-ch__f">
              <b>{f.title} <em>{f.priority}</em></b>
              <p>{f.next_action}{f.affected_count != null ? ` ${n(f.affected_count)} affected${f.denominator ? ` of ${n(f.denominator)} rows` : ''}.` : ''}</p>
              <p className="nk-ch__lim">{f.limitations}</p>
            </div>
          ))}
          {!!s.facts.length && <dl>{s.facts.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>}
          <Table m={m} />
          {diag && <p className="nk-ch__not">{diag.status.replace(/_/g, ' ')} · {diag.population}{diag.unsearched_scope ? ` · ${n(diag.unsearched_scope)} unsearched` : ''}</p>}
        </>
      ),
    };
  });

  const pairFinding = (x: string, y: string) => a.findings.filter((f) => f.scope === `${x}:${y}` || f.scope === `${y}:${x}`);
  const integrity = (x: string, y: string) => (a.coverage.measurements[`${x}:${y}.split_integrity`] ?? a.coverage.measurements[`${y}:${x}.split_integrity`]) as Dict | undefined;
  const schema = (x: string, y: string) => (a.coverage.measurements[`${x}:${y}.schema`] ?? a.coverage.measurements[`${y}:${x}.schema`]) as Dict | undefined;
  const links = roles.slice(0, -1).map((r, i) => {
    const next = roles[i + 1], si = integrity(r.id, next.id), sc = schema(r.id, next.id);
    const hot = pairFinding(r.id, next.id).some((f) => f.priority === 'High' || f.evidence_type === 'declared_violation');
    return { hot, text: `${si ? overlapLabel(si) : sc ? `${arr(sc.added).length + arr(sc.removed).length + arr(sc.changes).length} schema changes` : 'compared'}${hot ? ' · review' : ''}` };
  });
  const intent = a.comparison?.evaluation_intent && a.comparison.evaluation_intent !== 'unknown'
    ? `Declared intent: ${a.comparison.evaluation_intent.replace(/_/g, ' ')}${a.comparison.identity_keys?.length ? ` · identity keys ${a.comparison.identity_keys.map((k) => k.join(' + ')).join('; ')}` : ''}` : null;
  const pairFindings = a.findings.filter((f) => f.scope.includes(':')).sort((x, y) => rank[x.priority] - rank[y.priority]);
  const mode = M4_MODE_LABEL[a.comparison?.preset ?? a.comparison?.mode ?? 'advanced'];
  const hero: Tile = {
    id: 'roles', hero: true, name: 'Roles', n: '01', kicker: mode, bg: '#163F52', light: true,
    tone: links.some((l) => l.hot) ? 'critical' : pairFindings.length ? 'finding' : 'info',
    label: `${roles.length} role${roles.length === 1 ? '' : 's'}`,
    detail: intent ?? (roles.length > 1 ? 'No evaluation intent declared.' : 'One dataset, analysed on its own.'),
    viz: <RolesViz roles={roles} links={links} />, bigViz: <RolesViz roles={roles} links={links} big />,
    chapter: (
      <>
        <h3>Roles</h3>
        <div className="nk-ch__run"><span>{mode}</span><b>{roles.map((r) => r.role).join(' · ')}</b><p>{intent ?? 'No evaluation intent declared.'}</p></div>
        <ul className="ap-rolecards">
          {roles.map((r, i) => (
            <li key={r.id}>
              <span className="ap-strip__role">{r.role}</span><b>{r.file}</b><span>{n(r.rows)} rows · {n(r.cols)} columns{r.sha ? ` · ${r.sha.slice(0, 16)}…` : ''}</span>
              {links[i] && <em className={links[i].hot ? 'is-hot' : ''}>↓ {links[i].text}</em>}
            </li>
          ))}
        </ul>
        {pairFindings.map((f) => (
          <div key={f.id} className="nk-ch__f"><b>{f.title} <em>{f.priority}</em></b><p>{scopeLabel(f.scope)} · {f.next_action}</p><p className="nk-ch__lim">{f.limitations}</p></div>
        ))}
      </>
    ),
  };
  return (
    <div className="ap-rs">
      {header}
      <p className="ap-rs__saved"><Status tone="dev">{a.scoring.status === 'available' && a.scoring.values ? `Standalone classification score ${a.scoring.values.overall} · ${a.scoring.values.risk_level}` : (a.scoring.reason ?? 'No composite score for this analysis.')}</Status></p>
      {a.execution.status === 'partial' && <p className="ap-note ap-note--warn"><b>Analysis incomplete</b> Review unavailable checks; completed evidence remains available.</p>}
      <CheckScope checks={(a as Record<string, unknown>).checks} />
      <ScopeNote guidance={(a as Record<string, unknown>).guidance} />
      <Tiles tiles={[hero, ...tiles]} label="Comparison checks" />
      <section className="ap-sec ap-actions" aria-labelledby="ap-act-h">
        <h2 id="ap-act-h" className="ap-q">Actions</h2>
        {a.findings.length ? (
          <ul className="ap-sheet__fs">
            {[...a.findings].sort((x, y) => rank[x.priority] - rank[y.priority]).map((f) => (
              <li key={f.id}><span className={`ap-sev is-${f.priority.toLowerCase()}`}>{f.priority}</span><b>{f.title} · <span className="ap-actions__scope">{scopeLabel(f.scope)}</span></b><span>{f.next_action} {f.limitations}</span></li>
            ))}
          </ul>
        ) : <p className="ap-muted">No qualifying findings were produced within completed scope. Review declarations and unsearched scope before relying on this result.</p>}
        <p className="ap-muted">{a.narrative.summary}</p>
      </section>
      {out}
      <details className="ap-more ap-rs__cov">
        <summary>Coverage and limitations</summary>
        <p className="ap-muted">Execution: {a.execution.status} · backend {String(a.execution.backend ?? '—')} · generated {date(a.generated_at)}.</p>
        {Object.entries(a.coverage.diagnostics).map(([k, d]) => <p key={k} className="ap-muted">{k} · {d.status.replace(/_/g, ' ')} · {d.population}{d.reason ? ` — ${d.reason}` : ''}</p>)}
        {a.narrative.limitations.map((l, i) => <p key={i} className="ap-muted">{l}</p>)}
      </details>
    </div>
  );
}
