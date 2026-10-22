// "What you get": the real DataTrust report for Adult, pinned, its eight topics turning page by
// page as you scroll. Every page is built from the audit's real content, and a Markup note beside
// it says, in plain words, why that page matters to the person reading it.
import './report.css';
import { useLayoutEffect, useState, type ReactElement } from 'react';
import { adult } from './content';
import { reducedMotion, useScrollProgress } from '../foundation/motion';

const f = adult.findings, sub = adult.subScores;
const pct = (a: number, b: number) => ((a / b) * 100).toFixed(2);
const n = adult.rows;

const pages: { note: string; body: () => ReactElement }[] = [
  {
    note: 'The answer first. Anyone can read this page and know whether the data is ready, and why not.',
    body: () => (
      <>
        <div className="nk-rp__big"><b>{adult.finalScore.toFixed(1)}</b><span className="nk-rp__band">{adult.band} risk</span></div>
        <p className="nk-rp__lead">{adult.narrative}</p>
        <p className="nk-rp__next">{adult.nextAction}</p>
      </>
    ),
  },
  {
    note: 'What to do next, in order. Each item says what was seen and what to check.',
    body: () => (
      <ol className="nk-rp__acts">
        {[f[1], f[2], f[0], f[3]].map((x) => <li key={x.code}><span className={`nk-rp__sev is-${x.severity.toLowerCase()}`}>{x.severity}</span><b>{x.title}</b><span>{x.review}</span></li>)}
      </ol>
    ),
  },
  {
    note: 'Exactly which file was checked, so a result can always be traced back to its data.',
    body: () => (
      <dl className="nk-rp__kv">
        {[['File', adult.file], ['Rows × columns', `${n.toLocaleString()} × ${adult.header.length}`], ['Task', adult.task], ['Target', adult.target], ['sha256', `${adult.sha256.slice(0, 24)}…`], ['Generated', adult.generatedAt], ['Runtime', `${adult.runtimeSeconds.toFixed(2)} s, on this machine`], ['Missing cells', `${adult.missing.cells.toLocaleString()} (${adult.missing.reportCellRate}%)`]].map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}
      </dl>
    ),
  },
  {
    note: 'Problems with the answers themselves: one class dominates, and some identical rows disagree.',
    body: () => (
      <>
        <div className="nk-rp__split"><i style={{ flex: adult.classes.le50k }}><span>≤50K · {adult.classes.le50k.toLocaleString()}</span></i><i style={{ flex: adult.classes.gt50k }}><span>&gt;50K · {adult.classes.gt50k.toLocaleString()}</span></i></div>
        <p>Majority baseline {adult.majorityBaseline}% · ratio {adult.ratio} · target balance <b className="nk-rp__hot">{sub[2].value}</b> (critical).</p>
        <p>{f[0].finding} {f[0].evidence}</p>
        <div className="nk-rp__rows">{adult.conflicts[0].rows.map((r, i) => <div key={r}><b>row {r.toLocaleString()}</b><span>46 · Private · HS-grad · Craft-repair · 40 h · …</span><em>{adult.conflicts[0].labels[i]}</em></div>)}</div>
      </>
    ),
  },
  {
    note: 'Where values are missing, column by column, and how many rows that touches.',
    body: () => (
      <>
        <ul className="nk-rp__bars">
          {Object.entries(adult.missing.byColumn).map(([c, v]) => <li key={c}><span>{c}</span><i style={{ width: `${(v / 2809) * 100}%` }} /><em>{v.toLocaleString()} · {pct(v, n)}%</em></li>)}
        </ul>
        <p>{(adult.missing.rows.one + adult.missing.rows.two + adult.missing.rows.three_plus).toLocaleString()} rows ({adult.missing.rowRate}%) have a gap: {adult.missing.rows.one.toLocaleString()} with one, {adult.missing.rows.two.toLocaleString()} with two, {adult.missing.rows.three_plus} with three or more. Completeness {sub[0].value}; no finding.</p>
      </>
    ),
  },
  {
    note: 'Repeats and unusual values, with the counts and the thresholds that were used.',
    body: () => (
      <dl className="nk-rp__kv">
        {[['Duplicate groups', String(adult.duplicates.groups)], ['Repeated rows', String(adult.duplicates.repeated_rows)], ['Largest group', String(adult.duplicates.largest)], ['hours_per_week fences', `${adult.hours.lower} – ${adult.hours.upper}`], ['Outside the fences', `${adult.hours.outliers.toLocaleString()} rows`], ['Below / above', `${adult.hours.below.toLocaleString()} / ${adult.hours.above.toLocaleString()}`]].map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}
      </dl>
    ),
  },
  {
    note: 'How the number was made. Every measure and every guardrail is shown: no black box.',
    body: () => (
      <>
        <table className="nk-rp__tbl"><tbody>
          {sub.map((s) => <tr key={s.key} className={s.value <= 50 ? 'is-hot' : ''}><td>{s.label}</td><td>{s.value}</td></tr>)}
          <tr className="is-sum"><td>Evidence score (mean)</td><td>{adult.evidenceScore}</td></tr>
          <tr className="is-hot"><td>Guardrail · critical sub-score</td><td>cap 69</td></tr>
          <tr className="is-sum"><td>Final</td><td>{adult.finalScore.toFixed(1)} · {adult.band}</td></tr>
        </tbody></table>
        <p className="nk-rp__small">{adult.limits}</p>
      </>
    ),
  },
  {
    note: 'For the engineer: every column, its type, gaps, uniqueness and unusual values.',
    body: () => (
      <table className="nk-rp__tbl nk-rp__tbl--cols"><thead><tr><th>column</th><th>type</th><th>missing</th><th>outliers</th></tr></thead><tbody>
        {adult.columnEvidence.slice(0, 15).map((c) => <tr key={c.name} className={c.role === 'target' ? 'is-t' : ''}><td>{c.name}</td><td>{c.type}</td><td>{c.missing}</td><td>{c.outliers}</td></tr>)}
      </tbody></table>
    ),
  },
];

export function Report() {
  const [ref, p] = useScrollProgress<HTMLElement>('pinned');
  const [act, setAct] = useState(0);
  useLayoutEffect(() => { setAct(Math.min(pages.length - 1, Math.floor(p * pages.length * 0.999))); }, [p]);
  const rm = reducedMotion();
  const Body = pages[act].body;
  const go = (i: number) => { const el = ref.current; if (!el) return; scrollTo({ top: el.getBoundingClientRect().top + scrollY + ((i + 0.5) / pages.length) * (el.offsetHeight - innerHeight), behavior: rm ? 'auto' : 'smooth' }); };
  return (
    <section id="dt-report" ref={ref} className="nk-rp" aria-labelledby="dt-rp-h" style={{ height: `${pages.length * 42 + 60}vh` }}>
      <div className="nk-rp__stage">
        <div className="nk-rp__side">
          <span className="nk-label">What you get</span>
          <h2 id="dt-rp-h" className="nk-rp__h">A report you can hand to anyone.</h2>
          <ol className="nk-rp__toc">
            {adult.topics.map((t, i) => <li key={t}><button type="button" className={i === act ? 'is-on' : i < act ? 'is-past' : ''} aria-current={i === act ? 'true' : undefined} onClick={() => go(i)}><span>{String(i + 1).padStart(2, '0')}</span>{t}</button></li>)}
          </ol>
          <div className="nk-rp__fmt">{[['HTML', 'canonical'], ['PDF', 'decision pages + appendix'], ['JSON', 'strict, complete']].map(([k, v]) => <span key={k}><b>{k}</b>{v}</span>)}</div>
        </div>
        <div className="nk-rp__desk">
          <div className="nk-rp__stack" aria-hidden="true"><i /><i /></div>
          <article className="nk-rp__page" key={act} aria-live="polite">
            <header><span>adult.html · DataTrust report</span><span>{String(act + 1).padStart(2, '0')} / 08</span></header>
            <h3>{adult.topics[act]}</h3>
            <div className="nk-rp__body"><Body /></div>
            <footer><span>Findings support human review. Not a certificate.</span><span>{adult.generatedAt}</span></footer>
          </article>
          <aside className="nk-rp__note" key={`n${act}`}><i aria-hidden="true" /><p>{pages[act].note}</p></aside>
        </div>
      </div>
    </section>
  );
}
