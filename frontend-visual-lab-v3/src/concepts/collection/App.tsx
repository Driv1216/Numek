import '@fontsource-variable/unbounded';
import '@fontsource-variable/inter';
import '@fontsource/dm-mono/400.css';
import './collection.css';
import { useState } from 'react';
import { runs } from '../../fixture';
import { href } from '../../shell/router';
import { Header } from './Landing';
import { ColumnObject, code, describe, num, runsCols, type Col } from './objects';

/** Flags shown on objects: taken from each run's report. */
export const flags: Record<string, Record<string, string>> = {
  adult: { hours_per_week: 'Numeric outlier concentration · 13,496 rows outside 32.5 – 52.5', marital_status: 'Leakage review prompt · review only', annual_income_over_50k: 'Target imbalance · majority 76.07% · balance 47.86 (critical)', capital_loss: 'Near-constant · feature-usability penalty' },
  german: { duration_months: 'Numeric outlier concentration', credit_amount: 'Numeric outlier concentration · review-only name prompt', checking_account_status: 'Leakage review prompt · review only', credit_history: 'Leakage review prompt · review only', savings_status: 'Leakage review prompt · review only', personal_status_sex: 'Leakage review prompt · review only' },
  bank: { balance: 'Numeric outlier concentration', duration: 'Numeric outlier concentration', campaign: 'Numeric outlier concentration', previous_campaign_outcome: 'Leakage review prompt · prior outcome, review only', subscribed_term_deposit: 'Target imbalance · majority 88.3%' },
  bike: { casual: 'Declared unavailable at prediction · part of cnt = casual + registered', registered: 'Declared unavailable at prediction · part of cnt = casual + registered', cnt: 'Target · supported relationship cnt = casual + registered', holiday: 'Near-constant · 97.12% top share' },
};

export function Spec({ c, rows }: { c: Col; rows: number }) {
  const items: [string, string][] = c.kind === 'numeric'
    ? [['Kind', 'numeric'], ['Range', `${c.min} – ${c.max}`], ['Median', String(c.median)], ['Quartiles', `${c.q1} · ${c.q3}`], ['Unique', c.unique.toLocaleString()], ['Missing', c.missing ? `${c.missing.toLocaleString()} · ${((c.missing / rows) * 100).toFixed(2)}%` : '0']]
    : [['Kind', c.target ? 'categorical · target' : 'categorical'], ['Values', String(c.unique)], ['Most common', c.values![0][0]], ['Top share', `${((c.values![0][1] / rows) * 100).toFixed(2)}%`], ['Missing', c.missing ? `${c.missing.toLocaleString()} · ${((c.missing / rows) * 100).toFixed(2)}%` : '0'], ['Rows', rows.toLocaleString()]];
  return <dl className="co-spec">{items.map(([k, v]) => <div key={k}><dt className="co-mono">{k}</dt><dd>{v}</dd></div>)}</dl>;
}

export default function App() {
  const [run, setRun] = useState('adult');
  const [sel, setSel] = useState(12);
  const R = runsCols[run];
  const r = runs.find((x) => x.id === run)!;
  const c = R?.columns[Math.min(sel, (R?.columns.length ?? 1) - 1)];
  return (
    <div className="co co--app">
      <Header />
      <div className="co-ws">
        <nav className="co-colls" aria-label="Collections">
          <p className="co-mono" style={{ padding: '4px 8px 10px' }}>Collections · 0_{runs.length}</p>
          {runs.map((x) => (
            <button key={x.id} className={run === x.id ? 'is-on' : ''} onClick={() => { setRun(x.id); setSel(0); }}>
              <b>{x.name}</b><span className="co-mono">{runsCols[x.id] ? `0_${runsCols[x.id].columns.length}` : '—'}</span>
              <span className="co-mono">{x.score == null ? 'no score defined' : `${x.score.toFixed(1)} · ${x.band}`}</span>
            </button>
          ))}
        </nav>
        <main className="co-idx">
          <div className="co-idx__h"><h1>{r.name}</h1><span className="co-mono">{r.size} · {r.when}</span></div>
          {R ? (
            <div className="co-grid">
              {R.columns.map((col, i) => (
                <button key={col.name} className={`co-cell ${i === sel ? 'is-on' : ''} ${col.target ? 'is-target' : ''}`} onClick={() => setSel(i)}>
                  <div className="co-cell__stage"><ColumnObject c={col} /></div>
                  <span className="co-mono">{num(i)} / {code(i)}{flags[run]?.[col.name] ? ' · ●' : ''}</span>
                  <b>{col.name}</b>
                </button>
              ))}
            </div>
          ) : <p className="co-empty">{r.name} is not a table. DataTrust reports it by its own units — {r.lead.toLowerCase()}.</p>}
        </main>
        <aside className="co-detail" aria-label="Selected object">
          {R && c ? (
            <>
              <div className="co-frame__stage"><ColumnObject c={c} /></div>
              <span className="co-mono">{num(sel)} / {code(sel)} · {r.name}</span>
              <h2>{c.name}</h2>
              <p className="co-mono">{describe(c, R.rows)}</p>
              {flags[run]?.[c.name] && <p className="co-flag"><b>In the report</b>{flags[run][c.name]}</p>}
              <Spec c={c} rows={R.rows} />
              {run === 'adult' && <a className="co-btn" href={href('collection', 'results')}>Open the Adult result ↗</a>}
            </>
          ) : <p className="co-empty">Select a table collection.</p>}
        </aside>
      </div>
    </div>
  );
}
