import '@fontsource-variable/unbounded';
import '@fontsource-variable/inter';
import '@fontsource/dm-mono/400.css';
import './collection.css';
import { useState } from 'react';
import { adult } from '../../fixture';
import { Spec, flags } from './App';
import { Header } from './Landing';
import { ColumnObject, code, describe, num, runsCols } from './objects';

const A = runsCols.adult;
const at = (n: string) => A.columns.findIndex((c) => c.name === n);
const fcol: Record<string, number> = { conflicting_target_labels: at('annual_income_over_50k'), target_imbalance: at('annual_income_over_50k'), numeric_outlier_concentration: at('hours_per_week'), leakage_review_prompts: at('marital_status') };

export default function Results() {
  const [sel, setSel] = useState(at('hours_per_week'));
  const c = A.columns[sel];
  return (
    <div className="co co--results">
      <Header />
      <section className="co-res__top">
        <div>
          <p className="co-mono">(Result) · {adult.file} · {adult.task} · {adult.generatedAt}</p>
          <h1>Adult</h1>
        </div>
        <dl className="co-score">
          <div className="is-s"><dt className="co-mono">Final</dt><dd>69.0</dd></div>
          <div><dt className="co-mono">Band</dt><dd>Elevated</dd></div>
          <div><dt className="co-mono">Evidence</dt><dd>89.15</dd></div>
          <div><dt className="co-mono">Objects</dt><dd>0_15</dd></div>
        </dl>
      </section>
      <div className="co-res">
        <div>
          <div className="co-frame__stage" style={{ aspectRatio: '4 / 3' }}><ColumnObject c={c} /></div>
          <p className="co-mono" style={{ marginTop: 8 }}>{num(sel)} / {code(sel)} · {c.name} · {describe(c, A.rows)}</p>
        </div>
        <div className="co-res__findings">
          {flags.adult[c.name] && <p className="co-flag"><b>{c.name}, in the report</b>{flags.adult[c.name]}</p>}
          <Spec c={c} rows={A.rows} />
          <p className="co-mono" style={{ margin: '22px 0 6px' }}>(Findings · select to show the object)</p>
          {adult.findings.map((f, i) => (
            <button key={f.code} className={`co-rf ${fcol[f.code] === sel ? 'is-on' : ''}`} onClick={() => setSel(fcol[f.code])}>
              <span className="co-mono">{String(i + 1).padStart(2, '0')} · {f.severity}</span>
              <span><b>{f.title}</b><p>{f.evidence} {f.scoreEffect}</p></span>
            </button>
          ))}
          <p className="co-mono" style={{ marginTop: 18, lineHeight: 1.6 }}>Guardrail: target balance {adult.subScores[2].value} ≤ 50 → final score capped at 69.0. {adult.limits}</p>
        </div>
      </div>
      <nav className="co-strip" aria-label="All objects">
        {A.columns.map((col, i) => (
          <button key={col.name} className={i === sel ? 'is-on' : ''} onClick={() => setSel(i)} aria-label={col.name}>
            <div className="co-cell__stage"><ColumnObject c={col} /></div>
            <span className="co-mono">{code(i)}{flags.adult[col.name] ? ' ●' : ''}</span>
            <span>{col.name}</span>
          </button>
        ))}
      </nav>
    </div>
  );
}
