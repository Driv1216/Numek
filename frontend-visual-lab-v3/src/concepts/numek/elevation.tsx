// The DataTrust page hero: adult.csv drawn as an elevation in Markup's line language. Fifteen
// column strips stand on a 48,842-row axis. Every mark is real: empty-cell counts per column, the
// hours_per_week share outside its IQR fences, the target split, the two conflicting rows (drawn
// at their true row positions across every column) and the 52 repeated rows as ticks on the axis.
import { useMemo, useState } from 'react';
import { adult, decodeRows } from '../../fixture';
import { brackets, useDrawn } from './system';

const N = adult.rows;
const X0 = 150, SW = 40, SG = 13, TOP = 196, BOT = 576, H = BOT - TOP;
const sx = (i: number) => X0 + i * (SW + SG);
const ry = (row: number) => TOP + (row / N) * H;
const RIGHT = sx(14) + SW;
const missing: Record<string, number> = { workclass: 2799, occupation: 2809, native_country: 857 };
const iH = adult.header.indexOf('hours_per_week'), iM = adult.header.indexOf('marital_status'), iT = 14;
const g = adult.conflicts[0];

type M = 1 | 2 | 3 | 4;
export const calls: { n: M; t: string; fig: string; effect: string }[] = [
  { n: 1, t: 'Conflicting labels', fig: `rows ${g.rows.map((r) => r.toLocaleString()).join(' & ')} · 5 groups`, effect: 'Evidence only' },
  { n: 2, t: 'Target imbalance', fig: `${adult.majorityBaseline}% ≤50K · balance ${adult.subScores[2].value}`, effect: 'Caps the score at 69' },
  { n: 3, t: 'Outliers · hours_per_week', fig: `${(adult.hours.below + adult.hours.above).toLocaleString()} outside ${adult.hours.lower}–${adult.hours.upper}`, effect: 'Changes a sub-score' },
  { n: 4, t: 'Leakage review · marital_status', fig: 'name prompt only', effect: 'Evidence only' },
];

function Num({ n, x, y, on }: { n: M; x: number; y: number; on: boolean }) {
  return <g className={`nk-sh__num ${on ? 'is-on' : ''}`}><circle cx={x} cy={y} r={11} /><text x={x} y={y + 4} textAnchor="middle">{n}</text></g>;
}

export function Elevation() {
  const [ref, drawn] = useDrawn<HTMLDivElement>('0px 0px -5% 0px');
  const [act, setAct] = useState<M | null>(null);
  const on = (n: M) => act === null || act === n;
  const dups = useMemo(() => { const r = decodeRows(); const out: number[] = []; for (let i = 0; i < r.n; i++) if (r.dup[i]) out.push(i); return out; }, []);
  const below = adult.hours.below / N, above = adult.hours.above / N, maj = adult.majorityBaseline / 100;
  const LY = BOT + 58; // label rail under the strips
  return (
    <div ref={ref} className={`nk-elev nk-sheet ${drawn ? 'is-drawn' : ''} ${act ? 'has-act' : ''}`}>
      <div className="nk-sheet__pan">
        <svg viewBox="0 0 1200 680" className="nk-sh" role="img" aria-label={`adult.csv drawn as an elevation: 15 columns over ${N.toLocaleString()} rows, with four numbered findings.`}>
          <defs>
            <pattern id="nk-grid2" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" className="nk-sh__grid" /></pattern>
            <pattern id="nk-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="6" className="nk-el__hatchl" /></pattern>
          </defs>
          <rect x={16} y={16} width={1168} height={648} fill="url(#nk-grid2)" />
          <rect x={16} y={16} width={1168} height={648} className="nk-sh__ln nk-sh__frame" pathLength={1} />

          {/* dimensions */}
          <g className="nk-dimg">
            <path d={`M${X0} ${36}V${48}M${RIGHT} ${36}V${48}M${X0} 42H${RIGHT}`} className="nk-sh__ln" pathLength={1} />
            <text x={(X0 + RIGHT) / 2} y={34} textAnchor="middle" className="nk-sh__t">15 COLUMNS · adult.csv · sha256 {adult.sha256.slice(0, 8)}…</text>
            <path d={`M${58} ${TOP}H${70}M${58} ${BOT}H${70}M${64} ${TOP}V${BOT}`} className="nk-sh__ln" pathLength={1} />
            <text transform={`translate(52 ${(TOP + BOT) / 2}) rotate(-90)`} textAnchor="middle" className="nk-sh__t">48,842 ROWS</text>
            {[0, 10000, 20000, 30000, 40000, N].map((v) => <g key={v}><line x1={112} x2={120} y1={ry(v)} y2={ry(v)} className="nk-sh__tick" /><text x={108} y={ry(v) + 3} textAnchor="end" className="nk-sh__c nk-sh__c--g">{v === N ? '48,842' : `${v / 1000}k`}</text></g>)}
            <line x1={124} x2={124} y1={TOP} y2={BOT} className="nk-sh__ln" pathLength={1} />
            {dups.map((r) => <line key={r} x1={124} x2={132} y1={ry(r)} y2={ry(r)} className="nk-el__dup" />)}
            <text x={64} y={BOT + 40} className="nk-sh__c nk-sh__c--g">52 repeated rows</text>
          </g>

          {/* strips */}
          {adult.header.map((c, i) => {
            const x = sx(i), miss = missing[c];
            return (
              <g key={c} className={`nk-el__col ${i === iT ? (on(2) ? '' : 'is-dim') : i === iH ? (on(3) ? '' : 'is-dim') : i === iM ? (on(4) ? '' : 'is-dim') : act ? 'is-dim' : ''}`}>
                <text transform={`translate(${x + SW / 2 + 4} ${TOP - 12}) rotate(-90)`} className={`nk-sh__h ${i === iT ? 'nk-el__tl' : ''}`}>{c}</text>
                {i === iT ? (
                  <><rect x={x} y={TOP} width={SW} height={maj * H} className="nk-el__maj" /><rect x={x} y={TOP + maj * H} width={SW} height={(1 - maj) * H} className="nk-el__min" /></>
                ) : (
                  <rect x={x} y={TOP} width={SW} height={H} className={`nk-sh__ln ${i === iM ? 'nk-el__dotted' : ''}`} pathLength={i === iM ? undefined : 1} />
                )}
                {i === iH && <><rect x={x} y={BOT - below * H} width={SW} height={below * H} fill="url(#nk-hatch)" className="nk-el__out" /><rect x={x} y={TOP} width={SW} height={above * H} fill="url(#nk-hatch)" className="nk-el__out" /></>}
                {miss && <><rect x={x + 4} y={BOT - Math.max(4, (miss / N) * H)} width={SW - 8} height={Math.max(4, (miss / N) * H)} className="nk-el__miss" /><text x={x + SW / 2} y={BOT + 18} textAnchor="middle" className="nk-sh__c">{miss.toLocaleString()}</text></>}
              </g>
            );
          })}
          <text x={sx(iH) + SW + 6} y={BOT - below * H - 4} className="nk-sh__c nk-sh__c--hot">{adult.hours.lower}</text>
          <text x={sx(iH) + SW + 6} y={TOP + above * H + 12} className="nk-sh__c nk-sh__c--hot">{adult.hours.upper}</text>

          {/* 1 · the conflicting rows, at their true positions, across every column */}
          <g className={`nk-sh__m ${on(1) ? '' : 'is-dim'}`}>
            {g.rows.map((r, k) => <g key={r}>
              <line x1={X0 - 6} x2={RIGHT + 6} y1={ry(r)} y2={ry(r)} className="nk-el__row" pathLength={1} />
              <text x={108} y={ry(r) + 3} textAnchor="end" className="nk-sh__c nk-sh__c--hot">{r.toLocaleString()}</text>
              <text x={RIGHT + 10} y={ry(r) + 4} className="nk-sh__c nk-sh__c--hot">{g.labels[k]}</text>
            </g>)}
          </g>
          <g className={`nk-sh__m ${on(2) ? '' : 'is-dim'}`}><path d={brackets(sx(iT) - 7, TOP - 7, SW + 14, H + 14, 12)} className="nk-sh__ln nk-sh__br" pathLength={1} /></g>
          <g className={`nk-sh__m ${on(3) ? '' : 'is-dim'}`}><path d={brackets(sx(iH) - 7, TOP - 7, SW + 14, H + 14, 12)} className="nk-sh__ln nk-sh__br" pathLength={1} /></g>

          {/* numbered marks, each with a short local leader */}
          <g className={`nk-sh__m ${on(1) ? '' : 'is-dim'}`}>
            <path d={`M${RIGHT + 50} ${ry(g.rows[0])}V${ry(g.rows[0]) - 40}H${RIGHT + 70}`} className="nk-el__lead" pathLength={1} />
            <text x={RIGHT + 76} y={ry(g.rows[0]) - 36} className="nk-sh__t nk-sh__t--hot">same 14 features</text>
            <Num n={1} x={RIGHT + 50} y={ry(g.rows[0])} on={act === 1} />
          </g>
          <g className={`nk-sh__m ${on(2) ? '' : 'is-dim'}`}>
            <path d={`M${RIGHT + 18} ${TOP + maj * H}H${RIGHT + 70}`} className="nk-el__lead" pathLength={1} />
            <text x={RIGHT + 76} y={TOP + maj * H + 4} className="nk-sh__t nk-sh__t--hot">{adult.majorityBaseline}% ≤50K</text>
            <Num n={2} x={RIGHT + 18} y={TOP - 4} on={act === 2} />
          </g>
          <g className={`nk-sh__m ${on(3) ? '' : 'is-dim'}`}>
            <path d={`M${sx(iH) + SW / 2} ${BOT + 8}V${LY}H${sx(iH) + SW / 2 + 16}`} className="nk-el__lead" pathLength={1} />
            <text x={sx(iH) + SW / 2 + 22} y={LY + 4} className="nk-sh__t nk-sh__t--hot">{(adult.hours.below + adult.hours.above).toLocaleString()} outside {adult.hours.lower}–{adult.hours.upper}</text>
            <Num n={3} x={sx(iH) - 9} y={TOP - 4} on={act === 3} />
          </g>
          <g className={`nk-sh__m ${on(4) ? '' : 'is-dim'}`}>
            <path d={`M${sx(iM) + SW / 2} ${BOT + 26}V${LY}H${sx(iM) + SW / 2 + 16}`} className="nk-el__lead" pathLength={1} />
            <text x={sx(iM) + SW / 2 + 22} y={LY + 4} className="nk-sh__t">review only · name prompt</text>
            <Num n={4} x={sx(iM) - 9} y={TOP - 4} on={act === 4} />
          </g>

          {/* legend */}
          <g className="nk-el__legend">
            <text x={1040} y={60} className="nk-sh__t nk-sh__t--b">LEGEND</text>
            <rect x={1040} y={74} width={12} height={20} className="nk-sh__ln" /><text x={1060} y={88} className="nk-sh__c">column</text>
            <rect x={1040} y={104} width={12} height={10} className="nk-el__miss" /><text x={1060} y={113} className="nk-sh__c">empty cells</text>
            <rect x={1040} y={126} width={12} height={12} fill="url(#nk-hatch)" className="nk-el__out" /><text x={1060} y={137} className="nk-sh__c">outside fences</text>
            <line x1={1040} x2={1054} y1={156} y2={156} className="nk-el__row" /><text x={1060} y={160} className="nk-sh__c">conflicting row</text>
            <line x1={1040} x2={1048} y1={178} y2={178} className="nk-el__dup" /><text x={1060} y={182} className="nk-sh__c">repeated row</text>
            <rect x={1040} y={194} width={12} height={20} className="nk-sh__ln nk-el__dotted" /><text x={1060} y={208} className="nk-sh__c">review only</text>
            <circle cx={1046} cy={234} r={7} className="nk-sh__legnum" /><text x={1060} y={238} className="nk-sh__c">finding · below</text>
          </g>

          {/* title block */}
          <g>
            <rect x={1000} y={590} width={172} height={62} className="nk-sh__ln" pathLength={1} />
            <line x1={1000} x2={1172} y1={612} y2={612} className="nk-sh__ln" pathLength={1} />
            <text x={1010} y={606} className="nk-sh__t nk-sh__t--b">DATATRUST · ELEVATION</text>
            <text x={1010} y={628} className="nk-sh__c">Adult · 13 Aug 2026</text>
            <text x={1010} y={644} className="nk-sh__c nk-sh__c--g">{adult.runtimeSeconds.toFixed(2)} s · on this machine</text>
          </g>
        </svg>
      </div>
      <ol className="nk-sched nk-sched--dt" onMouseLeave={() => setAct(null)}>
        {calls.map((c, i) => (
          <li key={c.n} className={act === c.n ? 'is-act' : ''} onMouseEnter={() => setAct(c.n)} onFocus={() => setAct(c.n)} onBlur={() => setAct(null)} tabIndex={0}>
            <span className="nk-sched__n" aria-hidden="true">{c.n}</span>
            <h3>{adult.findings[i].title}</h3>
            <p>{adult.findings[i].finding}</p>
            <em>{c.effect} · {adult.findings[i].severity}</em>
          </li>
        ))}
      </ol>
    </div>
  );
}
