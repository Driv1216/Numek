import '@fontsource-variable/albert-sans';
import '@fontsource/red-hat-mono/400.css';
import '@fontsource/red-hat-mono/500.css';
import './findings.css';
import { useMemo, useState } from 'react';
import { adult, company, formats, local, runs } from '../../fixture';
import { href } from '../../shell/router';
import { effectLabel, rows, type Effect } from './data';

export function Header({ here }: { here: 'landing' | 'app' | 'results' }) {
  return (
    <header className="fd-head">
      <a className="fd-wm" href={href('findings', 'landing')}><i aria-hidden="true" />NUMEK</a>
      <nav aria-label="Primary">
        <a href={href('findings', 'landing')} aria-current={here === 'landing' ? 'page' : undefined}>Findings</a>
        <a href={href('findings', 'app')} aria-current={here === 'app' ? 'page' : undefined}>Workspace</a>
        <a href={href('findings', 'results')} aria-current={here === 'results' ? 'page' : undefined}>Adult</a>
      </nav>
      <span className="fd-head__r"><i className="fd-dot" aria-hidden="true" />local · 127.0.0.1</span>
    </header>
  );
}

/** The jury-style score table: every sub-score, its weight and its contribution, then the guardrail. */
export function ScoreTable() {
  const w = 1 / adult.subScores.length;
  return (
    <div className="fd-score" role="table" aria-label="How Adult's score was made">
      <div role="row" className="fd-score__h"><span>Measure</span><span>Weight</span><span>Score</span><span>Contribution</span></div>
      {adult.subScores.map((s) => (
        <div role="row" key={s.key} className={s.value <= 50 ? 'is-crit' : ''}><span>{s.label}</span><span>{(w * 100).toFixed(0)}%</span><span>{s.value}{s.value <= 50 ? ' · critical' : ''}</span><span>{(s.value * w).toFixed(2)}</span></div>
      ))}
      <div role="row" className="fd-score__sum"><span>Evidence score</span><span>100%</span><span /><span>{adult.evidenceScore}</span></div>
      <div role="row" className="fd-score__cap"><span>Guardrail · critical sub-score</span><span /><span>≤ 50 → cap</span><span>69.0</span></div>
      <div role="row" className="fd-score__final"><span>Final</span><span /><span>{adult.band}</span><span>{adult.finalScore.toFixed(1)}</span></div>
    </div>
  );
}

export function FindingsTable({ q, effect, open, setOpen }: { q: string; effect: Effect | 'all'; open: string | null; setOpen: (id: string | null) => void }) {
  const list = useMemo(() => rows.filter((r) => (effect === 'all' || r.effect === effect) && (q.trim() === '' || `${r.title} ${r.runName} ${r.evidence}`.toLowerCase().includes(q.toLowerCase()))), [q, effect]);
  return (
    <div className="fd-table" role="table" aria-label="Findings">
      <div role="row" className="fd-table__h"><span>Finding</span><span>Run</span><span>Severity</span><span>Effect</span><span /></div>
      {list.length === 0 && <p className="fd-empty">No finding matches “{q}”.</p>}
      {list.map((r) => (
        <div role="row" key={r.id} className={`fd-row ${open === r.id ? 'is-open' : ''}`}>
          <button type="button" className="fd-row__main" aria-expanded={open === r.id} onClick={() => setOpen(open === r.id ? null : r.id)}>
            <span className="fd-row__t"><b>{r.title}</b><small>{r.evidence}</small></span>
            <span>{r.runName}</span>
            <span className={`fd-sev fd-sev--${r.severity.toLowerCase()}`}>{r.severity}</span>
            <span className={`fd-eff fd-eff--${r.effect}`}>{effectLabel[r.effect]}</span>
            <span className="fd-row__chev" aria-hidden="true">{open === r.id ? '−' : '+'}</span>
          </button>
          {open === r.id && (
            <div className="fd-hood">
              {r.raw ? (
                <dl>
                  <div><dt>code</dt><dd>{r.raw.code}</dd></div><div><dt>finding</dt><dd>{r.raw.finding}</dd></div><div><dt>evidence</dt><dd>{r.raw.evidence}</dd></div>
                  <div><dt>impact</dt><dd>{r.raw.impact}</dd></div><div><dt>review</dt><dd>{r.raw.review}</dd></div><div><dt>score effect</dt><dd>{r.raw.scoreEffect}</dd></div>
                </dl>
              ) : <dl><div><dt>run</dt><dd>{r.runName}</dd></div><div><dt>evidence</dt><dd>{r.evidence}</dd></div><div><dt>effect</dt><dd>{effectLabel[r.effect]}</dd></div></dl>}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export default function Landing() {
  const [q, setQ] = useState('');
  const [effect, setEffect] = useState<Effect | 'all'>('all');
  const [open, setOpen] = useState<string | null>(null);
  return (
    <div className="fd fd--landing">
      <Header here="landing" />
      <section className="fd-hero">
        <div className="fd-hero__l">
          <span className="fd-tag">DataTrust · {rows.length} findings · {runs.length} runs</span>
          <h1>Every finding, from every run on this machine.</h1>
          <p>DataTrust audits the data behind ML and AI systems, locally, and reports each finding with its evidence and its effect on the score.</p>
          <form className="fd-search" role="search" onSubmit={(e) => e.preventDefault()}>
            <input type="search" placeholder="Search findings, runs or evidence" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search findings" />
            <button type="submit">Search</button>
          </form>
        </div>
        <aside className="fd-latest">
          <div className="fd-latest__h"><span>Latest scored run</span><span className="fd-chip">{adult.band}</span></div>
          <b>Adult</b><span className="fd-mono">{adult.file} · {adult.generatedAt} · {adult.runtimeSeconds.toFixed(2)} s</span>
          <div className="fd-latest__s"><div><span>Final</span><b>{adult.finalScore.toFixed(1)}</b></div><div><span>Evidence</span><b>{adult.evidenceScore}</b></div><div><span>Findings</span><b>{adult.findings.length}</b></div></div>
          <a href={href('findings', 'results')}>Full result →</a>
        </aside>
      </section>

      <section className="fd-sec">
        <div className="fd-seg" role="tablist" aria-label="Filter by effect">
          {(['all', 'score', 'evidence', 'none-defined'] as const).map((e) => <button key={e} type="button" role="tab" aria-selected={effect === e} onClick={() => setEffect(e)}>{e === 'all' ? 'All' : effectLabel[e]} <span className="fd-mono">{e === 'all' ? rows.length : rows.filter((r) => r.effect === e).length}</span></button>)}
        </div>
        <FindingsTable q={q} effect={effect} open={open} setOpen={setOpen} />
      </section>

      <section className="fd-sec fd-method">
        {[['01', 'Built from the file', 'Every finding traces back to rows, columns or pages of the file you gave it. Open any row to see the fields it was computed from.', 'black'],
          ['02', 'Evidence first', 'Each finding says what was seen, what it may mean and what to review. Two of Adult’s four change the score; two are evidence only.', 'blue'],
          ['03', 'Scores only where defined', 'Classification tables get transparent sub-scores and guardrails. Regression, time, text, image and document runs get evidence and no universal score.', 'plain']].map(([n, t, b, c]) => (
          <article key={n} className={`fd-card fd-card--${c}`}><span className="fd-mono">{n}</span><h3>{t}</h3><p>{b}</p></article>
        ))}
      </section>

      <section className="fd-sec fd-split">
        <div><span className="fd-tag">Adult · how the number was made</span><h2>Every weight, every row, visible.</h2><p>The evidence score is the plain mean of five measures. A guardrail then applies: any measure at or below 50 holds the final score at 69.</p></div>
        <ScoreTable />
      </section>

      <section className="fd-sec">
        <span className="fd-tag">Local runs</span>
        <div className="fd-runs">
          {runs.map((r) => (
            <article key={r.id} className="fd-runcard">
              <div className="fd-runcard__h"><b>{r.name}</b><span className="fd-mono">{r.score == null ? 'no score defined' : `${r.score.toFixed(1)} · ${r.band}`}</span></div>
              <span className="fd-mono">{r.file} · {r.size}</span>
              <p>{r.lead}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="fd-sec fd-split">
        <div><span className="fd-tag">Run it</span><h2>Two commands. Three formats.</h2><ul className="fd-formats">{formats.map((f) => <li key={f.name}><b>{f.name}</b> {f.note}</li>)}</ul></div>
        <pre className="fd-term"><span>$</span> {local.commands[0]}{'\n'}<em>{local.cliOutput.join('\n')}</em>{'\n\n'}<span>$</span> {local.commands[1]}</pre>
      </section>
      <footer className="fd-foot"><span>NUMEK · {company.line}</span><span>{company.direction}</span><span>Findings support human review; they are not certification.</span></footer>
    </div>
  );
}
