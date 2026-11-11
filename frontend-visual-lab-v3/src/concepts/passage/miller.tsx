import { useEffect, useRef, type ReactNode } from 'react';
import { adult, runFindings, runs, subScoresByRun, type Representation } from '../../fixture';
import { fmt } from '../../shell/motion';
import { repColour } from './artefacts';

export interface Node { id: string; label: string; meta?: string; tone?: string; kids?: () => Node[]; detail?: () => ReactNode; rep?: Representation }

const g = (id: number) => adult.conflicts.find((c) => c.id === id)!;

function groupRows(id: number) {
  const grp = g(id);
  return (
    <div className="ps-rows">
      <p className="ps-mono">Conflict group {id} · rows {grp.rows.join(' & ')} · all 14 features identical</p>
      <table>
        <thead><tr><th>column</th>{grp.rows.map((r) => <th key={r}>row {r}</th>)}</tr></thead>
        <tbody>
          {adult.header.map((c, i) => {
            const vals = i === 14 ? grp.labels : grp.rows.map(() => String(grp.features[c] ?? '?'));
            const diff = new Set(vals).size > 1;
            return <tr key={c} className={diff ? 'is-diff' : ''}><td>{c}</td>{vals.map((v, k) => <td key={k}>{v}</td>)}</tr>;
          })}
        </tbody>
      </table>
      <p className="ps-rows__note">Only <b>annual_income_over_50k</b> differs. Review whether this is a label error, the same person over time, a target update, or a feature that was not recorded. This finding changes no score.</p>
    </div>
  );
}

const finding = (code: string) => adult.findings.find((f) => f.code === code)!;
function findingDetail(code: string) {
  const f = finding(code);
  return (
    <dl className="ps-finding">
      <div><dt>Finding · {f.severity}</dt><dd>{f.finding}</dd></div>
      <div><dt>Evidence</dt><dd>{f.evidence}</dd></div>
      <div><dt>Modelling impact</dt><dd>{f.impact}</dd></div>
      <div><dt>Review</dt><dd>{f.review}</dd></div>
      <div><dt>Score effect</dt><dd>{f.scoreEffect}</dd></div>
    </dl>
  );
}

const conflictNode: Node = {
  id: 'conflicting_target_labels', label: 'Potentially conflicting target labels', meta: '5 groups · 10 rows · Moderate', tone: 'hit',
  kids: () => adult.conflicts.map((c) => ({ id: `g${c.id}`, label: `Group ${c.id}`, meta: `rows ${c.rows.join(' & ')} · ${c.labels.join(' / ')}`, detail: () => groupRows(c.id) })),
};

function adultTopics(): Node[] {
  return [
    { id: 'decision', label: 'Decision summary', meta: '69.0 · Elevated', detail: () => (
      <div className="ps-dec"><b>69.0</b><span>Elevated</span><p>{adult.narrative}</p><p>{adult.nextAction}</p></div>
    ) },
    { id: 'actions', label: 'Priority actions', meta: '4 findings', kids: () => adult.findings.map((f) => f.code === 'conflicting_target_labels' ? conflictNode : ({ id: f.code, label: f.title, meta: f.severity, detail: () => findingDetail(f.code) })) },
    { id: 'target', label: 'Target and label evidence', meta: 'baseline 76.07%', kids: () => [{ id: 'target_imbalance', label: 'Target imbalance', meta: 'Moderate', detail: () => (
      <div className="ps-bars"><p className="ps-mono">annual_income_over_50k</p>
        <div><span>≤50K</span><i style={{ width: '76.07%' }} /><em>{fmt(adult.classes.le50k)} · 76.07%</em></div>
        <div><span>&gt;50K</span><i style={{ width: '23.93%' }} /><em>{fmt(adult.classes.gt50k)} · 23.93%</em></div>
        {findingDetail('target_imbalance')}
      </div>) }] },
    { id: 'missing', label: 'Missingness evidence', meta: '7.41% of rows', detail: () => (
      <div className="ps-bars"><p className="ps-mono">6,465 of 683,788 feature cells · 0.95%</p>
        {Object.entries(adult.missing.byColumn).sort((a, b) => b[1] - a[1]).map(([c, n]) => <div key={c}><span>{c}</span><i style={{ width: `${(n / 2809) * 100}%` }} /><em>{fmt(n)}</em></div>)}
      </div>) },
    { id: 'duplicates', label: 'Duplicate and feature evidence', meta: '49 groups · 5 conflicting', tone: 'hit', kids: () => [
      conflictNode,
      { id: 'dups', label: 'Exact duplicate rows', meta: '52 repeated · 49 groups', detail: () => <p className="ps-plain">52 repeated rows were detected across 49 exact duplicate groups; the largest group has 3 rows. Uniqueness sub-score 99.89.</p> },
      { id: 'leakage_review_prompts', label: 'Leakage review prompts', meta: 'marital_status · review only', detail: () => findingDetail('leakage_review_prompts') },
    ] },
    { id: 'method', label: 'Scoring and limitations', meta: '5 sub-scores · 1 guardrail', detail: () => (
      <div className="ps-bars"><p className="ps-mono">Evidence 89.15 → final 69.0 · guardrail: critical sub-score</p>
        {adult.subScores.map((s) => <div key={s.key} className={s.critical ? 'is-hit' : ''}><span>{s.label}</span><i style={{ width: `${s.value}%` }} /><em>{s.value.toFixed(2)}</em></div>)}
        <p className="ps-plain">{adult.limits}</p>
      </div>) },
    { id: 'appendix', label: 'Technical appendix', meta: '15 columns', detail: () => (
      <div className="ps-rows"><table><thead><tr><th>column</th><th>missing</th><th>unique</th><th>outliers</th></tr></thead>
        <tbody>{adult.columnEvidence.map((c) => <tr key={c.name} className={c.name === 'hours_per_week' ? 'is-diff' : ''}><td>{c.name}</td><td>{c.missing}</td><td>{c.unique}</td><td>{c.outliers}</td></tr>)}</tbody></table></div>) },
  ];
}

export const root: Node[] = runs.map((r) => ({
  id: r.id, label: r.name, rep: r.rep, meta: r.score != null ? `${r.score.toFixed(1)} · ${r.band}` : 'no score defined',
  kids: r.id === 'adult' ? adultTopics : () => {
    const fs = runFindings[r.id] ?? [];
    const subs = subScoresByRun[r.id];
    return fs.length
      ? fs.map((f, i) => ({ id: `${r.id}${i}`, label: f.title, meta: f.severity, detail: () => (
        <dl className="ps-finding"><div><dt>Evidence</dt><dd>{f.evidence}</dd></div><div><dt>Score effect</dt><dd>{f.effect === 'none-defined' ? 'No score is defined for this task family.' : f.effect === 'evidence' ? 'Evidence only.' : 'Affects a sub-score.'}</dd></div>
          {subs && <div><dt>Sub-scores</dt><dd>{subs.map((s) => `${s.label} ${s.value}`).join(' · ')}</dd></div>}</dl>) }))
      : [{ id: `${r.id}-lead`, label: 'Summary', meta: r.task, detail: () => <p className="ps-plain">{r.lead}. The full report is available in HTML, PDF and JSON.</p> }];
  },
}));

export function Miller({ path, setPath }: { path: string[]; setPath: (p: string[]) => void }) {
  const box = useRef<HTMLDivElement>(null);
  const cols: { nodes: Node[]; sel?: string }[] = [{ nodes: root, sel: path[0] }];
  let leaf: Node | undefined;
  let nodes = root;
  for (let d = 0; d < path.length; d++) {
    const n = nodes.find((x) => x.id === path[d]);
    if (!n) break;
    if (n.kids) { nodes = n.kids(); cols.push({ nodes, sel: path[d + 1] }); }
    else { leaf = n; break; }
  }
  const run = runs.find((r) => r.id === path[0]);
  const colour = run ? repColour[run.rep] : '#22262A';

  useEffect(() => { box.current?.scrollTo({ left: box.current.scrollWidth, behavior: 'smooth' }); }, [path.join('/')]);

  return (
    <div className="ps-miller" ref={box} style={{ ['--run' as string]: colour }}>
      {cols.map((c, d) => (
        <div key={d} className="ps-col" role="listbox" aria-label={d === 0 ? 'Runs' : 'Items'}>
          <p className="ps-col__h">{d === 0 ? 'Runs' : d === 1 ? 'Topics' : d === 2 ? 'Findings' : d === 3 ? 'Evidence' : 'Detail'}</p>
          {c.nodes.map((n) => (
            <button key={n.id} role="option" aria-selected={c.sel === n.id} className={`ps-item ${c.sel === n.id ? 'is-on' : ''} ${n.tone === 'hit' ? 'is-hit' : ''}`}
              onClick={() => setPath([...path.slice(0, d), n.id])}>
              {n.rep && <i style={{ background: repColour[n.rep] }} />}
              <span>{n.label}<small>{n.meta}</small></span>
              {n.kids && <em aria-hidden="true">›</em>}
            </button>
          ))}
        </div>
      ))}
      <div className="ps-col ps-col--detail">
        {leaf?.detail ? leaf.detail() : <p className="ps-empty">Select an item to follow the evidence.</p>}
      </div>
    </div>
  );
}
