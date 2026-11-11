import '@fontsource-variable/space-grotesk';
import '@fontsource/space-mono/400.css';
import '@fontsource/space-mono/700.css';
import './cells.css';
import { adult } from '../../fixture';
import { Header } from './Landing';

const T = adult.topics;
export default function Results() {
  const ce = adult.columnEvidence;
  return (
    <div className="ce ce--results">
      <Header here="results" />
      <div className="ce-grid ce-grid--res">
        <div className="ce-c ce-c--w12 ce-c--title"><span className="ce-k">{adult.file.toUpperCase()} · {adult.generatedAt} · SHA256 {adult.sha256.slice(0, 12).toUpperCase()}…</span><b>Adult — the report, in cells</b></div>
        <div className="ce-c ce-c--w5 ce-c--acc"><span className="ce-k">01 · {T[0].toUpperCase()}</span><b className="ce-xl">{adult.finalScore.toFixed(1)}</b><em>{adult.band} · evidence {adult.evidenceScore} · capped at 69</em><p>{adult.nextAction}</p></div>
        <div className="ce-c ce-c--w7"><span className="ce-k">02 · {T[1].toUpperCase()}</span><ol className="ce-list">{adult.findings.map((f) => <li key={f.code}><b>{f.title}</b><span>{f.severity}</span><em>{f.review}</em></li>)}</ol></div>
        <div className="ce-c ce-c--w4 ce-c--dark"><span className="ce-k">03 · {T[2].toUpperCase()}</span><b>48,842 × 15</b><em>{adult.numericFeatures} numeric · {adult.nonNumericFeatures} other · target {adult.target} · {adult.runtimeSeconds.toFixed(2)} s</em></div>
        <div className="ce-c ce-c--w4"><span className="ce-k">04 · {T[3].toUpperCase()}</span><b>{adult.majorityBaseline}%</b><em>{adult.classes.le50k.toLocaleString()} ≤50K · {adult.classes.gt50k.toLocaleString()} &gt;50K · {adult.ratio} · 5 conflicting groups</em></div>
        <div className="ce-c ce-c--w4"><span className="ce-k">05 · {T[4].toUpperCase()}</span><b>{adult.missing.cells.toLocaleString()}</b><em>{Object.entries(adult.missing.byColumn).map(([k, v]) => `${k} ${v.toLocaleString()}`).join(' · ')}</em></div>
        <div className="ce-c ce-c--w6"><span className="ce-k">06 · {T[5].toUpperCase()}</span><b>{adult.duplicates.repeated_rows} · {adult.hours.outliers.toLocaleString()}</b><em>repeated rows ({adult.duplicates.groups} groups) · hours_per_week outside {adult.hours.lower} – {adult.hours.upper}</em></div>
        <div className="ce-c ce-c--w6"><span className="ce-k">07 · {T[6].toUpperCase()}</span><ol className="ce-list ce-list--sub">{adult.subScores.map((s) => <li key={s.key}><b>{s.label}</b><span className={s.value <= 50 ? 'ce-red' : ''}>{s.value}</span></li>)}</ol><em>{adult.limits}</em></div>
        <div className="ce-c ce-c--w12"><span className="ce-k">08 · {T[7].toUpperCase()}</span>
          <div className="ce-apx" role="table" aria-label="Column evidence">
            <div role="row" className="ce-apx__h"><span>COLUMN</span><span>TYPE</span><span>MISSING</span><span>UNIQUE</span><span>TOP SHARE</span><span>IQR OUTLIERS</span></div>
            {ce.map((c) => <div role="row" key={c.name}><span>{c.name}</span><span>{c.type}</span><span>{c.missing}</span><span>{c.unique}</span><span>{c.top_share}</span><span>{c.outliers}</span></div>)}
          </div>
        </div>
      </div>
    </div>
  );
}
