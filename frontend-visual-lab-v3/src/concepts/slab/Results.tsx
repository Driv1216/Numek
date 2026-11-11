import '@fontsource-variable/anybody';
import '@fontsource-variable/jetbrains-mono';
import './slab.css';
import { useEffect, useState } from 'react';
import { adult } from '../../fixture';
import { Header, adultCredits } from './Landing';
import { Credits, Shutter, SlabMark } from './slabs';

export default function Results() {
  const [all, setAll] = useState(false);
  // The shutters part once, shortly after the page settles.
  useEffect(() => { const t = setTimeout(() => setAll(true), 600); return () => clearTimeout(t); }, []);
  const subs = adult.subScores.map((s) => ({ label: s.label, value: s.value }));
  return (
    <div className="sl sl--results">
      <Header here="results" />
      <div className="sl-res">
        <div className="sl-res__top">
          <div>
            <span className="sl-k">{adult.file.toUpperCase()} · SHA256 {adult.sha256.slice(0, 12).toUpperCase()}…</span>
            <h1>Adult <b className="sl-red">69.0</b></h1>
            <p>{adult.band}. Evidence {adult.evidenceScore}. {adult.guardrail.explanation}</p>
          </div>
          <Credits items={adultCredits} />
        </div>
        <SlabMark values={subs} p={1} />
        <div className="sl-res__bar"><span className="sl-k">FINDINGS · 4</span><button type="button" onClick={() => setAll(!all)} aria-pressed={all}>{all ? 'Close all shutters' : 'Open all shutters'}</button></div>
        <div className="sl-shutters sl-shutters--4">
          {adult.findings.map((f, i) => (
            <Shutter key={f.code} open={all} label={f.title}>
              <span className="sl-k">{String(i + 1).padStart(2, '0')} · {f.severity.toUpperCase()}</span>
              <h3>{f.title}</h3>
              <p>{f.finding} {f.evidence}</p>
              <p className="sl-dim">{f.scoreEffect}</p>
            </Shutter>
          ))}
        </div>
        <p className="sl-dim sl-limits">{adult.limits}</p>
      </div>
    </div>
  );
}
