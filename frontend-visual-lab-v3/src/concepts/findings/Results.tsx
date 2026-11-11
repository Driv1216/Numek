import '@fontsource-variable/albert-sans';
import '@fontsource/red-hat-mono/400.css';
import '@fontsource/red-hat-mono/500.css';
import './findings.css';
import { useState } from 'react';
import { adult } from '../../fixture';
import { FindingsTable, Header, ScoreTable } from './Landing';
import { rows } from './data';

export default function Results() {
  const [open, setOpen] = useState<string | null>(rows.find((r) => r.run === 'adult')?.id ?? null);
  return (
    <div className="fd fd--results">
      <Header here="results" />
      <div className="fd-res">
        <main>
          <span className="fd-tag">{adult.file} · {adult.task} · {adult.generatedAt}</span>
          <h1>Adult</h1>
          <div className="fd-latest__s fd-latest__s--big"><div><span>Final</span><b>{adult.finalScore.toFixed(1)}</b></div><div><span>Band</span><b>{adult.band}</b></div><div><span>Evidence</span><b>{adult.evidenceScore}</b></div><div><span>Rows</span><b>{adult.rows.toLocaleString()}</b></div></div>
          <h2 className="fd-h2">Findings</h2>
          <FindingsTableAdult open={open} setOpen={setOpen} />
          <h2 className="fd-h2">How the number was made</h2>
          <ScoreTable />
          <p className="fd-dimp fd-limits">{adult.limits}</p>
        </main>
        <aside className="fd-topics" aria-label="Report topics">
          <span className="fd-tag">Report · eight topics</span>
          <ol>{adult.topics.map((t, i) => <li key={t}><span className="fd-mono">{String(i + 1).padStart(2, '0')}</span>{t}</li>)}</ol>
          <p className="fd-dimp">Same evidence in HTML, PDF and strict JSON.</p>
        </aside>
      </div>
    </div>
  );
}

/** The landing table, limited to Adult. */
function FindingsTableAdult({ open, setOpen }: { open: string | null; setOpen: (id: string | null) => void }) {
  return <FindingsTable q="Adult" effect="all" open={open} setOpen={setOpen} />;
}
