import { adult, finance } from '../../fixture';
import bikeHours from '../../fixture/bike-hours.generated.json';
import type { Representation } from '../../fixture';

export const repColour: Record<Representation, string> = {
  tables: '#B4633B', outcomes: '#5D6A72', time: '#6D7A55', text: '#D7C5A3', images: '#8DA2B6', connected: '#22262A',
};
export const repInk: Record<Representation, string> = {
  tables: '#F6EEE7', outcomes: '#EEF1F2', time: '#F1F2EA', text: '#2A251C', images: '#17202A', connected: '#ECEAE5',
};

/** Each representation is shown through an artefact of its own kind. */
export function Artefact({ rep }: { rep: Representation }) {
  if (rep === 'tables') {
    const g = adult.conflicts[0];
    const cols = ['age', 'workclass', 'education', 'occupation', 'hours_per_week', 'annual_income_over_50k'];
    return (
      <div className="ps-art ps-art--csv" aria-label="Excerpt of adult.csv including one conflicting-label group">
        <div className="ps-csv__h">{cols.join(',')}</div>
        {adult.sampleRows.slice(0, 7).map((r, i) => <div key={i} className="ps-csv__r"><span>{i + 1}</span>{[r[0], r[1], r[3], r[6], r[12], r[14]].join(',')}</div>)}
        <div className="ps-csv__gap">⋮</div>
        {g.rows.map((row, i) => (
          <div key={row} className="ps-csv__r is-hit"><span>{row}</span>{[g.features.age, g.features.workclass, g.features.education, g.features.occupation, g.features.hours_per_week].join(',')},<b>{g.labels[i]}</b></div>
        ))}
      </div>
    );
  }
  if (rep === 'outcomes') {
    const hs = bikeHours.hours.slice(0, 36);
    const max = Math.max(...hs.map((h) => h.cnt));
    return (
      <div className="ps-art ps-art--bike">
        <svg viewBox="0 0 360 170" role="img" aria-label="36 real hours of bike rentals: casual plus registered equals cnt in every row.">
          {hs.map((h, i) => {
            const x = 4 + i * 9.9, hr = (h.registered / max) * 140, hc = (h.casual / max) * 140;
            return <g key={i}><rect x={x} y={150 - hr} width={7} height={hr} className="reg" /><rect x={x} y={150 - hr - hc} width={7} height={hc} className="cas" /></g>;
          })}
          <line x1="0" x2="360" y1="150.5" y2="150.5" className="base" />
          <text x="4" y="166" className="t">{hs[0].t}</text><text x="356" y="166" className="t" textAnchor="end">{hs[hs.length - 1].t}</text>
        </svg>
        <p className="ps-eq"><span className="cas">casual</span> + <span className="reg">registered</span> = cnt</p>
      </div>
    );
  }
  if (rep === 'time') {
    const ev = [8, 20, 33, 47, 60, 74, 86];
    return (
      <div className="ps-art ps-art--time">
        <svg viewBox="0 0 360 170" role="img" aria-label="Illustration: event times and the later times their values become available; one revision arrives after the cutoff.">
          <text x="0" y="34" className="t">event clock</text><text x="0" y="114" className="t">available</text>
          <line x1="70" x2="356" y1="40" y2="40" className="ax" /><line x1="70" x2="356" y1="120" y2="120" className="ax" />
          <line x1="268" x2="268" y1="18" y2="146" className="cut" /><text x="272" y="18" className="t">cutoff</text>
          {ev.map((v, i) => {
            const x = 70 + v * 3, a = x + (i === 4 ? 64 : 14);
            return <g key={i} className={i === 4 ? 'late' : ''}><circle cx={x} cy={40} r={4} /><path d={`M${x} 44 L${a} 116`} /><rect x={a - 4} y={116} width={8} height={8} /></g>;
          })}
        </svg>
        <p className="ps-cap">Illustration · availability after the evaluation cutoff</p>
      </div>
    );
  }
  if (rep === 'text') {
    return (
      <div className="ps-art ps-art--text" aria-label="Illustration of two near-duplicate text records">
        <p className="ps-rec"><span>r0412</span>Your parcel is waiting. Confirm delivery details at the link below.</p>
        <p className="ps-rec is-hit"><span>r2219</span>Your parcel is waiting! Confirm your delivery details at the link below</p>
        <p className="ps-rec"><span>r2220</span>See you at seven, bring the charger please.</p>
        <p className="ps-rec is-hit"><span>r5101</span>your parcel is waiting. confirm delivery details at the link below.</p>
        <p className="ps-cap">Illustration · near-duplicate candidates from bounded MinHash search, for review</p>
      </div>
    );
  }
  if (rep === 'images') {
    return (
      <div className="ps-art ps-art--img">
        <svg viewBox="0 0 360 200" role="img" aria-label="Illustration: an image with three annotated boxes; one box extends beyond the image bounds.">
          <rect x="20" y="10" width="320" height="180" className="frame" />
          <path d="M20 150 Q90 110 150 140 T340 120 V190 H20 Z" className="ground" />
          <circle cx="270" cy="52" r="20" className="sun" />
          <rect x="60" y="88" width="70" height="62" className="box" /><text x="62" y="84" className="t">person</text>
          <rect x="160" y="104" width="56" height="44" className="box" /><text x="162" y="100" className="t">bicycle</text>
          <rect x="290" y="96" width="70" height="60" className="box is-hit" /><text x="292" y="92" className="t">dog · outside bounds</text>
        </svg>
        <p className="ps-cap">Illustration · coordinate compatibility</p>
      </div>
    );
  }
  return (
    <div className="ps-art ps-art--conn">
      <div className="ps-rec2"><span>records.csv</span><b>{finance.example.entity} · {finance.example.period}</b><em>{finance.example.record}</em></div>
      <svg viewBox="0 0 60 40" className="ps-link" aria-hidden="true"><path d="M0 20 C30 20 30 20 60 20" /></svg>
      <div className="ps-pdf">
        <span className="ps-pdf__h">statement_07_q2.pdf · page 2</span>
        <table><thead><tr><th>Metric</th><th>Period</th><th>Value</th></tr></thead>
          <tbody><tr><td>Cost of sales</td><td>FY2025 Q2</td><td>27,940,000</td></tr><tr className="is-hit"><td>Revenue</td><td>FY2025 Q2</td><td>41,520,000</td></tr><tr><td>Operating income</td><td>FY2025 Q2</td><td>6,105,000</td></tr></tbody>
        </table>
      </div>
      <p className="ps-cap">Illustrative record · exact page, table and row locator</p>
    </div>
  );
}
