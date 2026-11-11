import '@fontsource-variable/recursive/full.css';
import './two-readings.css';
import { useState } from 'react';
import { adult } from '../../fixture';
import { fmt } from '../../shell/motion';
import { CommandBar, Palette, usePalette } from './App';
import { Json, axes, findingJson } from './shared';

export default function Results() {
  const [open, setOpen] = usePalette();
  const [global, setGlobal] = useState<'machine' | 'human'>('human');
  const [per, setPer] = useState<Record<string, 'machine' | 'human'>>({ conflicting_target_labels: 'machine' });
  const mode = (code: string) => per[code] ?? global;
  return (
    <div className="tr tr--app tr--results">
      <CommandBar onOpen={() => setOpen(true)} />
      <main className="tr-res">
        <header className="tr-res__head">
          <div>
            <p className="tr-pane__h" style={axes(1)}>$ datatrust audit {adult.file} --target {adult.target} · {adult.runtimeSeconds.toFixed(2)} s · {adult.generatedAt}</p>
            <h1 style={axes(0, 0.2)}>Adult</h1>
          </div>
          <div className="tr-toggle" role="group" aria-label="Reading for all findings">
            {(['machine', 'human'] as const).map((m) => (
              <button key={m} aria-pressed={global === m} style={axes(m === 'machine' ? 1 : 0)} onClick={() => { setGlobal(m); setPer({}); }}>{m}</button>
            ))}
          </div>
        </header>

        <section className="tr-calc" aria-label="Score path">
          <div className="tr-calc__row" style={axes(1)}>
            <span>evidence_score</span><b>89.15</b>
            <span className="op">→ min(</span><b>89.15</b><span className="op">,</span><span>cap</span><b className="tr-amber">69.0</b><span className="op">)</span>
            <span className="op">=</span><b className="tr-final">69.0</b>
          </div>
          <p style={axes(0, 0.2)}>Final score <b>69.0, Elevated</b>. The critical-sub-score guardrail applies because target balance is <b className="tr-amber">47.86</b>; the other four sub-scores sit between 98.86 and 100.</p>
          <div className="tr-subs">
            {adult.subScores.map((s) => (
              <div key={s.key} className={s.critical ? 'is-crit' : ''}>
                <span style={axes(1)}>{s.key}</span>
                <i><em style={{ width: `${s.value}%` }} /></i>
                <b style={axes(1)}>{s.value.toFixed(2)}</b>
              </div>
            ))}
          </div>
        </section>

        <section className="tr-findings" aria-label="Findings">
          {adult.findings.map((f, i) => {
            const m = mode(f.code);
            return (
              <article key={f.code} className={`tr-f tr-f--${m}`}>
                <header>
                  <span className="tr-f__n" style={axes(1)}>{String(i + 1).padStart(2, '0')}</span>
                  <span className={`tr-sev tr-sev--${f.severity.toLowerCase()}`}>{f.severity}</span>
                  <button className="tr-f__flip" onClick={() => setPer({ ...per, [f.code]: m === 'machine' ? 'human' : 'machine' })} style={axes(1)} aria-label={`Show the ${m === 'machine' ? 'human' : 'machine'} reading of ${f.title}`}>
                    {m === 'machine' ? 'read as prose →' : '← read as json'}
                  </button>
                </header>
                {m === 'machine' ? <Json value={findingJson(f.code)} /> : (
                  <div className="tr-f__h" style={axes(0, 0.15)}>
                    <h3>{f.title}</h3>
                    <p className="tr-lead">{f.finding}</p>
                    <p>{f.evidence} {f.impact}</p>
                    <p><b>Review next.</b> {f.review}</p>
                    <p className="tr-f__eff">{f.scoreEffect}</p>
                  </div>
                )}
              </article>
            );
          })}
        </section>

        <section className="tr-evidence" aria-label="Evidence tables">
          <div>
            <p className="tr-pane__h" style={axes(1)}>evidence · conflicting groups</p>
            <table style={axes(1)}>
              <thead><tr><th>group</th><th>rows</th><th>age</th><th>education</th><th>hours</th><th>labels</th></tr></thead>
              <tbody>{adult.conflicts.map((g) => <tr key={g.id}><td>{g.id}</td><td>{g.rows.join(', ')}</td><td>{String(g.features.age)}</td><td>{String(g.features.education)}</td><td>{String(g.features.hours_per_week)}</td><td className="tr-amber">{g.labels.join(' / ')}</td></tr>)}</tbody>
            </table>
          </div>
          <div>
            <p className="tr-pane__h" style={axes(1)}>evidence · missing by column</p>
            <table style={axes(1)}>
              <thead><tr><th>column</th><th>missing</th><th>share</th></tr></thead>
              <tbody>{Object.entries(adult.missing.byColumn).sort((a, b) => b[1] - a[1]).map(([c, n]) => <tr key={c}><td>{c}</td><td>{fmt(n)}</td><td>{((n / adult.rows) * 100).toFixed(2)}%</td></tr>)}</tbody>
            </table>
            <p className="tr-note" style={axes(0)}>{adult.limits}</p>
          </div>
        </section>
      </main>
      <Palette open={open} onClose={() => setOpen(false)} />
    </div>
  );
}
