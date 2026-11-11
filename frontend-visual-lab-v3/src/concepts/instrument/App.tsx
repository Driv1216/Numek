import '@fontsource-variable/instrument-sans';
import '@fontsource/instrument-serif/400.css';
import '@fontsource/instrument-serif/400-italic.css';
import '@fontsource-variable/jetbrains-mono';
import './instrument.css';
import { useState } from 'react';
import { finance, runs } from '../../fixture';
import { Header } from './Landing';
import { Instrument } from './Instrument';
import { runCols } from './dial';

/** Runs that are not tables get a simple instrument of their own units. */
function UnitsInstrument({ id }: { id: string }) {
  const r = runs.find((x) => x.id === id)!;
  const units = id === 'coco' ? { n: 128, mark: 61, label: '128 images · 61 ICC-bearing images excluded from default visual methods' }
    : id === 'finance' ? { n: finance.records, mark: finance.discrepancies + finance.conflicts, label: `${finance.records} records · ${finance.agreements} agree · ${finance.discrepancies} discrepancy · ${finance.conflicts} conflict` }
    : { n: 120, mark: 0, label: '5,574 records, one ray per ~46 · near-duplicate candidates from calibrated MinHash search' };
  return (
    <div className="in-units">
      <svg viewBox="0 0 520 520" className="in-dial" role="img" aria-label={units.label}>
        <circle cx={260} cy={260} r={244} className="in-bezel" />
        {Array.from({ length: units.n }, (_, i) => {
          const a = (i / units.n) * Math.PI * 2 - Math.PI / 2;
          return <line key={i} x1={260 + 90 * Math.cos(a)} y1={260 + 90 * Math.sin(a)} x2={260 + 220 * Math.cos(a)} y2={260 + 220 * Math.sin(a)} className={i < units.mark ? 'in-ray in-ray--red' : 'in-ray'} />;
        })}
        <circle cx={260} cy={260} r={48} className="in-core" />
        <text x={260} y={256} textAnchor="middle" className="in-core__v">—</text>
        <text x={260} y={274} textAnchor="middle" className="in-core__l">no score defined</text>
      </svg>
      <div className="in-legend"><span className="in-legend__k">{r.task}</span><h3>{r.name}</h3><p>{units.label}.</p><p>{r.lead}.</p></div>
    </div>
  );
}

export default function App() {
  const [run, setRun] = useState('adult');
  const r = runs.find((x) => x.id === run)!;
  return (
    <div className="in in--app">
      <Header here="app" />
      <div className="in-apphead">
        <div><span className="in-kicker">{r.file} · {r.task} · {r.when}</span><h1><em>{r.name}</em></h1></div>
        <div className="in-runs" role="tablist" aria-label="Runs">
          {runs.map((x) => <button key={x.id} type="button" role="tab" aria-selected={x.id === run} onClick={() => setRun(x.id)}>{x.name}<span>{x.score == null ? 'no score' : x.score.toFixed(1)}</span></button>)}
        </div>
      </div>
      {runCols[run] ? <Instrument key={run} run={run} /> : <UnitsInstrument id={run} />}
    </div>
  );
}
