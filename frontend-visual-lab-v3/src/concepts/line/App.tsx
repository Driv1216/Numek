import './line.css';
import { useState, type ReactNode } from 'react';
import { runs, runFindings, subScoresByRun } from '../../fixture';
import { href } from '../../shell/router';
import { Branches, Columns, ReportStack, RowsStack, ScoreJoin, checks, runCols } from './draw';
import { Header } from './Landing';

const STAGES = ['Read', 'Profile', 'Check', 'Score', 'Report'] as const;
type Stage = (typeof STAGES)[number];

export default function App() {
  const [run, setRun] = useState('adult');
  const [stage, setStage] = useState<Stage>('Check');
  const r = runs.find((x) => x.id === run)!;
  const cols = runCols[run];
  const f = runFindings[run] ?? [];
  const subs = subScoresByRun[run];

  const figs: Record<Stage, string> = {
    Read: r.size,
    Profile: cols ? `${cols.columns.filter((c) => c.kind === 'numeric').length} numeric · ${cols.columns.filter((c) => c.kind !== 'numeric').length} other` : 'by its own units',
    Check: f.length ? `${f.length} findings` : 'by its own units',
    Score: r.score == null ? 'none defined' : `${r.score.toFixed(1)} · ${r.band}`,
    Report: 'HTML · PDF · JSON',
  };

  let draw: ReactNode;
  if (stage === 'Read') draw = cols ? <RowsStack rows={cols.rows} /> : <p className="ln-note">{r.file} · {r.size}. Not a table: DataTrust reads it by its own units.</p>;
  else if (stage === 'Profile') draw = cols ? <Columns run={run} /> : <p className="ln-note">{r.task}. Profiled by its own units — {r.lead.toLowerCase()}.</p>;
  else if (stage === 'Check') draw = run === 'adult' ? <Branches /> : f.length ? <Branches items={f.map((x) => ({ k: x.title, v: x.severity, sub: x.evidence.length > 64 ? x.evidence.slice(0, 63) + '…' : x.evidence, dotted: x.effect === 'evidence' }))} /> : <p className="ln-note">{r.lead}.</p>;
  else if (stage === 'Score') draw = subs ? <ScoreJoin subs={subs} final={r.score} evidence={Math.round((subs.reduce((a, s) => a + s.value, 0) / subs.length) * 100) / 100} /> : <p className="ln-note">No universal score is defined for {r.task.toLowerCase()}. The line goes straight from Check to Report.</p>;
  else draw = <ReportStack />;

  return (
    <div className="ln ln--app">
      <Header here="app" />
      <div className="ln-ws">
        <nav className="ln-side" aria-label="Local runs">
          <p className="ln-mono ln-dim">RUNS · {runs.length}</p>
          {runs.map((x) => (
            <button key={x.id} type="button" className={x.id === run ? 'is-on' : ''} aria-pressed={x.id === run} onClick={() => setRun(x.id)}>
              <span>{x.name}</span><em>{x.score == null ? 'no score' : x.score.toFixed(1)}</em>
            </button>
          ))}
        </nav>
        <ol className="ln-rail" aria-label="Pipeline">
          {STAGES.map((s, i) => (
            <li key={s}>
              <button type="button" className={s === stage ? 'is-on' : ''} aria-pressed={s === stage} onClick={() => setStage(s)}>
                <span className="ln-mono ln-amber">0{i + 1}</span><b>{s}</b><em>{figs[s]}</em>
              </button>
            </li>
          ))}
        </ol>
        <main className="ln-main">
          <div className="ln-main__h"><h1>{r.name}</h1><span className="ln-mono ln-dim">{r.file} · {r.task} · {r.when} · {r.runtime}</span></div>
          <div className="ln-main__d">{draw}</div>
          {stage === 'Check' && run === 'adult' && (
            <ul className="ln-legend">{checks.map((c) => <li key={c.k}><b>{c.k}</b><span>{c.v}</span><span className="ln-dim">{c.sub}</span></li>)}</ul>
          )}
          {run === 'adult' && <a className="ln-btn" href={href('line', 'results')}>Follow the whole Adult line →</a>}
        </main>
      </div>
    </div>
  );
}
