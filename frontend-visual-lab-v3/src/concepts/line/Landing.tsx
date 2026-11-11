// No webfonts are imported anywhere in this concept: the page practises what it says.
import './line.css';
import { useEffect, useRef, type ReactNode } from 'react';
import { adult, company, local, runs } from '../../fixture';
import { href } from '../../shell/router';
import { Branches, Columns, Loopback, ReportStack, RowsStack, ScoreJoin } from './draw';

export function Header({ here }: { here: 'landing' | 'app' | 'results' }) {
  return (
    <header className="ln-head">
      <a className="ln-wm" href={href('line', 'landing')}>NUMEK</a>
      <nav aria-label="Primary">
        <a href={href('line', 'landing')} aria-current={here === 'landing' ? 'page' : undefined}>The line</a>
        <a href={href('line', 'app')} aria-current={here === 'app' ? 'page' : undefined}>Runs</a>
        <a href={href('line', 'results')} aria-current={here === 'results' ? 'page' : undefined}>Adult</a>
      </nav>
      <span className="ln-head__r">system fonts · no trackers · no images</span>
    </header>
  );
}

const stages: { n: string; k: string; title: string; body: ReactNode; figs: [string, string][]; draw: ReactNode }[] = [
  { n: '01', k: 'Read', title: 'It starts with one file, on this disk.', body: 'adult.csv is read where it sits. Its fingerprint is taken so the report can say exactly which bytes it describes.', figs: [['File', adult.file], ['sha256', `${adult.sha256.slice(0, 16)}…`], ['Rows × columns', `${adult.rows.toLocaleString()} × ${adult.columns}`]], draw: <RowsStack /> },
  { n: '02', k: 'Profile', title: 'Every column, measured.', body: 'Type, range, distinct values, gaps and distribution — for all fifteen columns, before any judgement is made.', figs: [['Feature cells', adult.missing.featureCells.toLocaleString()], ['Numeric features', String(adult.numericFeatures)], ['Other features', String(adult.nonNumericFeatures)]], draw: <Columns /> },
  { n: '03', k: 'Check', title: 'Six checks, each with an exact count.', body: 'Gaps, repeats, the balance of the target, rows that disagree on the label, values beyond the fences, and names that might know the answer. A name alone is only a prompt — drawn dotted.', figs: [['Findings', '4'], ['Change a sub-score', '2'], ['Evidence only', '2']], draw: <Branches /> },
  { n: '04', k: 'Score', title: 'Five measures, one mean, one cap.', body: 'The evidence score is the mean of five sub-scores: 89.15. Target balance is 47.86 — at or below 50 is critical — so the result is held at 69.0, Elevated.', figs: [['Evidence', String(adult.evidenceScore)], ['Guardrail', 'critical sub-score'], ['Final', `${adult.finalScore.toFixed(1)} · ${adult.band}`]], draw: <ScoreJoin /> },
  { n: '05', k: 'Report', title: 'Three files out. Nothing else.', body: 'The same evidence, written three ways: a canonical HTML report, a PDF for decisions, and strict JSON for anything downstream.', figs: [['HTML', 'adult.html'], ['PDF', 'adult.pdf'], ['JSON', 'adult.json']], draw: <ReportStack /> },
];

export default function Landing() {
  const track = useRef<HTMLDivElement>(null);
  // The line fills to the middle of the viewport as you read.
  useEffect(() => {
    let raf = 0;
    const on = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const el = track.current; if (!el) return;
        const r = el.getBoundingClientRect();
        el.style.setProperty('--fill', `${Math.max(0, Math.min(r.height, innerHeight / 2 - r.top))}px`);
      });
    };
    on(); addEventListener('scroll', on, { passive: true }); addEventListener('resize', on);
    return () => { removeEventListener('scroll', on); removeEventListener('resize', on); cancelAnimationFrame(raf); };
  }, []);
  const tabular = runs.filter((r) => r.rep === 'tables' || r.rep === 'outcomes');

  return (
    <div className="ln ln--landing">
      <Header here="landing" />
      <section className="ln-hero">
        <p className="ln-mono ln-amber">DataTrust by {company.name}</p>
        <h1>From a file to a finding, on this machine.</h1>
        <div className="ln-wire" aria-hidden="true"><i /></div>
        <p className="ln-hero__s">DataTrust reads a dataset where it sits, checks it, scores it where a score is defined, and writes a report. This page follows one real file — the public Adult dataset — along that line.</p>
        <p className="ln-mono ln-dim">this page practises what it says: no webfonts · no trackers · no images · nothing fetched after load</p>
      </section>

      <div className="ln-track" ref={track}>
        <div className="ln-track__line" aria-hidden="true"><i /></div>
        {stages.map((s) => (
          <section key={s.n} className="ln-stage" aria-labelledby={`ln-${s.n}`}>
            <div className="ln-stage__t">
              <span className="ln-mono ln-amber">{s.n} · {s.k}</span>
              <h2 id={`ln-${s.n}`}>{s.title}</h2>
              <p>{s.body}</p>
              <dl>{s.figs.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
            </div>
            <div className="ln-stage__d">{s.draw}</div>
          </section>
        ))}
        <section className="ln-stage ln-stage--end" aria-labelledby="ln-06">
          <div className="ln-stage__t">
            <span className="ln-mono ln-amber">06 · Multiply</span>
            <h2 id="ln-06">Seven runs. Zero bytes sent.</h2>
            <p>Every run in this lab followed the same line, on the same machine. Regression, text, image and record-to-document runs report evidence without a universal score, because none is defined for them.</p>
          </div>
          <div className="ln-stage__d">
            <ul className="ln-runs">
              {runs.map((r) => <li key={r.id}><span>{r.name}</span><span className="ln-dim">{r.size}</span><b>{r.score == null ? 'no score defined' : `${r.score.toFixed(1)} · ${r.band}`}</b></li>)}
            </ul>
            <p className="ln-mono ln-dim">{tabular.reduce((a, r) => a + Number(r.size.split(' ')[0].replace(/,/g, '')), 0).toLocaleString()} table rows across {tabular.length} runs · 0 network calls during analysis</p>
            <Loopback />
          </div>
        </section>
      </div>

      <section className="ln-cmd">
        <h2>Run the line yourself.</h2>
        <pre><span>$</span> {local.commands[0]}{'\n'}<em>{local.cliOutput.join('\n')}</em>{'\n\n'}<span>$</span> {local.commands[1]}{'\n'}<em>→ http://127.0.0.1:8000/</em></pre>
      </section>
      <footer className="ln-foot">
        <span className="ln-wm">NUMEK</span>
        <p>{company.line}. DataTrust is the product. {company.direction}</p>
        <p className="ln-dim">{adult.source} · Findings support human review; they are not certification.</p>
      </footer>
    </div>
  );
}
