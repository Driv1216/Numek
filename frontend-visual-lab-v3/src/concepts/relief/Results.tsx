import '@fontsource-variable/cormorant';
import '@fontsource-variable/cormorant/wght-italic.css';
import '@fontsource-variable/figtree';
import './relief.css';
import { useState } from 'react';
import { adult } from '../../fixture';
import { Header, fences, windows } from './Landing';
import { Relief, adultGrid } from './surface';

/** Where each window sits on the relief (fractions of width/height). */
const at: Record<string, [number, number]> = { target: [0.06, 0.12], conflict: [0.52, 0.08], fences: [0.3, 0.56], score: [0.68, 0.52] };

export default function Results() {
  const [big, setBig] = useState<string | null>(null);
  const w = windows.find((x) => x.id === big);
  return (
    <div className="rl rl--results">
      <Header here="results" />
      <section className="rl-res-h"><span className="rl-kicker">{adult.file} · {adult.generatedAt} · sha256 {adult.sha256.slice(0, 12)}…</span><h1>Adult, <em>in relief.</em></h1><p className="rl-cap">Age 17–90 down, hours 1–99 across; height is row count. Fences cut at 32.5 and 52.5 hours. Select a window to open it.</p></section>
      <div className="rl-res">
        <Relief grid={adultGrid} label="Adult relief: rows by age and hours per week" lines={fences} className="rl-canvas--res" />
        {windows.map((x) => (
          <button key={x.id} type="button" className={`rl-win rl-win--${x.tone} rl-win--abs`} style={{ left: `${at[x.id][0] * 100}%`, top: `${at[x.id][1] * 100}%` }} onClick={() => setBig(x.id)}>
            <span className="rl-win__k">{x.k}</span>{x.body}
          </button>
        ))}
      </div>
      {w && (
        <div className="rl-modal" role="dialog" aria-label={w.k} onClick={(e) => e.target === e.currentTarget && setBig(null)}>
          <div className={`rl-win rl-win--${w.tone} rl-win--big`}><button type="button" className="rl-x" onClick={() => setBig(null)} autoFocus>Close</button><span className="rl-win__k">{w.k}</span>{w.body}<p className="rl-cap rl-cap--in">{w.caption}</p></div>
        </div>
      )}
      <p className="rl-dim rl-limits">{adult.limits}</p>
    </div>
  );
}
