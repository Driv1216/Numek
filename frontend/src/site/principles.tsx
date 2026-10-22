// The principles as a Markup sheet: one technical drawing of what NUMEK does on your machine
// (rows in, report out, a score against its cap), with four numbered marks on the evidence and
// a schedule beneath that explains each mark. Every value drawn is real (Adult audit).
import { useState } from 'react';
import { adult } from './content';
import { brackets, useDrawn } from '../foundation/system';

type P = 1 | 2 | 3 | 4;
export const schedule: { n: P; t: string; b: string; marked: string }[] = [
  { n: 1, t: 'Evidence before verdicts.', b: 'Every finding names the rows, columns, predictions or pages it came from, so it can be checked, not just believed.', marked: `Rows ${adult.conflicts[0].rows.map((r) => r.toLocaleString()).join(' and ')}: same fourteen features, different label.` },
  { n: 2, t: 'A report, not a certificate.', b: 'NUMEK shows what was found and what to review. It does not certify data, models or compliance.', marked: 'The report page: findings and review prompts, never a certification stamp.' },
  { n: 3, t: 'Your data stays where it is.', b: 'Analysis runs on your machine. The interface binds to 127.0.0.1 and nothing is uploaded.', marked: 'The boundary: everything on this sheet happens inside 127.0.0.1.' },
  { n: 4, t: 'A score only where it means something.', b: 'DataTrust scores classification datasets with every guardrail explained. Elsewhere there is evidence and no universal score.', marked: `Evidence ${adult.evidenceScore}, held at the cap of 69 because target balance is ${adult.subScores[2].value}.` },
];

const cols: [string, number, number][] = [['age', 0, 34], ['workclass', 1, 92], ['education', 3, 82], ['occupation', 6, 112], ['hours', 12, 44], ['income', 14, 50]];
const colX = cols.reduce<number[]>((a, _c, i) => [...a, i === 0 ? 0 : a[i - 1] + cols[i - 1][2]], []);
const TW = cols.reduce((s, c) => s + c[2], 0);
const g = adult.conflicts[0];
const feat = adult.header.map((h) => String((g.features as Record<string, string | number>)[h] ?? ''));

function Num({ n, x, y, on }: { n: P; x: number; y: number; on: boolean }) {
  return <g className={`nk-sh__num ${on ? 'is-on' : ''}`}><circle cx={x} cy={y} r={11} /><text x={x} y={y + 4} textAnchor="middle">{n}</text></g>;
}

export function Sheet() {
  const [ref, drawn] = useDrawn<HTMLDivElement>('0px 0px -20% 0px');
  const [act, setAct] = useState<P | null>(null);
  const on = (n: P) => act === null || act === n;
  const T = { x: 84, y: 134 }, RH = 17;
  const rows = adult.sampleRows.slice(0, 8);
  const confY = T.y + 22 + rows.length * RH + 26;
  // Score scale: 0–100 across x 84…800.
  const sx = (v: number) => 84 + (v / 100) * 716, SY = 452;
  return (
    <div ref={ref} className={`nk-sheet ${drawn ? 'is-drawn' : ''} ${act ? 'has-act' : ''}`}>
      <div className="nk-sheet__pan">
        <svg viewBox="0 0 1200 620" className="nk-sh" role="img" aria-label="Technical sheet: Adult rows on your machine pass through a DataTrust audit into a report, with the score drawn against its cap. Four numbered marks match the principles below.">
          <defs>
            <pattern id="nk-grid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" className="nk-sh__grid" /></pattern>
            <marker id="nk-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0L10 5L0 10z" className="nk-sh__arrowhead" /></marker>
          </defs>
          <rect x={16} y={16} width={1168} height={588} fill="url(#nk-grid)" />
          <rect x={16} y={16} width={1168} height={588} className="nk-sh__ln nk-sh__frame" pathLength={1} />
          {Array.from({ length: 49 }, (_, i) => <line key={i} x1={16 + i * 24} x2={16 + i * 24} y1={16} y2={i % 5 ? 22 : 28} className="nk-sh__tick" />)}

          {/* 3 · the machine boundary */}
          <g className={`nk-sh__m ${on(3) ? '' : 'is-dim'}`}>
            <rect x={52} y={70} width={800} height={430} className="nk-sh__ln nk-sh__boundary" pathLength={1} />
            <text x={64} y={92} className="nk-sh__t nk-sh__t--b">127.0.0.1 · YOUR MACHINE</text>
            <path d={brackets(40, 58, 824, 454, 22)} className="nk-sh__ln nk-sh__br" pathLength={1} />
            <Num n={3} x={864} y={58} on={act === 3} />
          </g>

          {/* 1 · the rows */}
          <g className={`nk-sh__m ${on(1) ? '' : 'is-dim'}`}>
            <text x={T.x} y={T.y - 14} className="nk-sh__t nk-sh__t--b">adult.csv · 48,842 × 15</text>
            <rect x={T.x} y={T.y} width={TW} height={confY + 2 * RH - T.y + 4} className="nk-sh__ln" pathLength={1} />
            {cols.map(([c], i) => <text key={c} x={T.x + colX[i] + 5} y={T.y + 15} className="nk-sh__h">{c}</text>)}
            <line x1={T.x} x2={T.x + TW} y1={T.y + 22} y2={T.y + 22} className="nk-sh__ln" pathLength={1} />
            {rows.map((r, ri) => cols.map(([c, k, w], i) => <text key={`${ri}${c}`} x={T.x + colX[i] + 5} y={T.y + 22 + ri * RH + 13} className="nk-sh__c">{r[k].length * 6.4 > w - 8 ? r[k].slice(0, Math.floor((w - 8) / 6.4) - 1) + '…' : r[k]}</text>))}
            <text x={T.x + TW / 2} y={confY - 9} textAnchor="middle" className="nk-sh__c nk-sh__c--g">⋮ 48,831 rows</text>
            {g.rows.map((n, ri) => cols.map(([c, k, w], i) => {
              const v = k === 14 ? g.labels[ri] : feat[k];
              return <text key={`c${n}${c}`} x={T.x + colX[i] + 5} y={confY + ri * RH + 13} className={`nk-sh__c ${k === 14 ? 'nk-sh__c--hot' : ''}`}>{v.length * 6.4 > w - 8 ? v.slice(0, Math.floor((w - 8) / 6.4) - 1) + '…' : v}</text>;
            }))}
            <path d={brackets(T.x - 8, confY - 4, TW + 16, 2 * RH + 8, 10)} className="nk-sh__ln nk-sh__br" pathLength={1} />
            <Num n={1} x={T.x - 8} y={confY - 4} on={act === 1} />
            <text x={T.x + TW} y={confY + 2 * RH + 22} textAnchor="end" className="nk-sh__t nk-sh__t--hot">rows {g.rows.map((r) => r.toLocaleString()).join(' / ')}</text>
          </g>

          {/* the audit */}
          <line x1={T.x + TW + 14} x2={598} y1={210} y2={210} className="nk-sh__ln" markerEnd="url(#nk-arrow)" pathLength={1} />
          <rect x={T.x + TW + 34} y={192} width={118} height={36} rx={18} className="nk-sh__pill" />
          <text x={T.x + TW + 93} y={214} textAnchor="middle" className="nk-sh__t">datatrust audit</text>

          {/* 2 · the report */}
          <g className={`nk-sh__m ${on(2) ? '' : 'is-dim'}`}>
            <path d="M610 112H782L812 142V396H610Z" className="nk-sh__ln nk-sh__page" pathLength={1} />
            <path d="M782 112V142H812" className="nk-sh__ln" pathLength={1} />
            <text x={624} y={138} className="nk-sh__t nk-sh__t--b">adult.html · report</text>
            <text x={624} y={190} className="nk-sh__big">{adult.finalScore.toFixed(1)}</text>
            <text x={718} y={190} className="nk-sh__t">{adult.band}</text>
            {[214, 230, 246, 262, 284, 300].map((y, i) => <line key={y} x1={624} x2={i % 3 === 2 ? 720 : 796} y1={y} y2={y} className="nk-sh__ghost" />)}
            <g transform="rotate(-8 712 350)"><rect x={650} y={330} width={124} height={34} rx={4} className="nk-sh__stamp" /><text x={712} y={352} textAnchor="middle" className="nk-sh__stampt">CERTIFIED</text><line x1={644} x2={780} y1={347} y2={347} className="nk-sh__strike" pathLength={1} /></g>
            <path d={brackets(600, 102, 222, 304, 12)} className="nk-sh__ln nk-sh__br" pathLength={1} />
            <Num n={2} x={600} y={102} on={act === 2} />
          </g>

          {/* 4 · the score against its cap */}
          <g className={`nk-sh__m ${on(4) ? '' : 'is-dim'}`}>
            <line x1={sx(0)} x2={sx(100)} y1={SY} y2={SY} className="nk-sh__ln" pathLength={1} />
            {Array.from({ length: 11 }, (_, i) => <g key={i}><line x1={sx(i * 10)} x2={sx(i * 10)} y1={SY - 5} y2={SY + 5} className="nk-sh__tick" /><text x={sx(i * 10)} y={SY + 20} textAnchor="middle" className="nk-sh__c nk-sh__c--g">{i * 10}</text></g>)}
            <line x1={sx(50)} x2={sx(50)} y1={SY - 30} y2={SY} className="nk-sh__dash" />
            <text x={sx(50) - 6} y={SY - 10} textAnchor="end" className="nk-sh__c nk-sh__c--g">critical ≤ 50</text>
            <path d={`M${sx(adult.evidenceScore)} ${SY - 4}l-6 -10h12z`} className="nk-sh__tri" />
            <text x={sx(adult.evidenceScore)} y={SY - 20} textAnchor="middle" className="nk-sh__c">evidence {adult.evidenceScore}</text>
            <line x1={sx(69)} x2={sx(69)} y1={SY - 36} y2={SY + 6} className="nk-sh__cap" pathLength={1} />
            <line x1={sx(adult.evidenceScore)} x2={sx(69) + 4} y1={SY - 10} y2={SY - 10} className="nk-sh__hold" markerEnd="url(#nk-arrow)" pathLength={1} />
            <text x={sx(69) - 8} y={SY - 26} textAnchor="end" className="nk-sh__t nk-sh__t--hot">cap 69 · final {adult.finalScore.toFixed(1)}</text>
            <path d={brackets(sx(66), SY - 60, sx(93) - sx(66), 72, 10)} className="nk-sh__ln nk-sh__br" pathLength={1} />
            <Num n={4} x={sx(66)} y={SY - 60} on={act === 4} />
          </g>

          {/* title block */}
          <g className="nk-sh__tb">
            <rect x={880} y={500} width={292} height={92} className="nk-sh__ln" pathLength={1} />
            <line x1={880} x2={1172} y1={530} y2={530} className="nk-sh__ln" pathLength={1} /><line x1={880} x2={1172} y1={560} y2={560} className="nk-sh__ln" pathLength={1} />
            <text x={892} y={520} className="nk-sh__t nk-sh__t--b">NUMEK · PRINCIPLES</text>
            <text x={892} y={550} className="nk-sh__c">Sheet P · 4 marks · scale none</text>
            <text x={892} y={580} className="nk-sh__c nk-sh__c--g">Drawn from the Adult audit</text>
          </g>
          <g className="nk-sh__legend">
            <text x={880} y={100} className="nk-sh__t nk-sh__t--b">LEGEND</text>
            <circle cx={892} cy={124} r={8} className="nk-sh__legnum" /><text x={908} y={128} className="nk-sh__c">numbered mark · see schedule</text>
            <path d={brackets(884, 144, 16, 16, 5)} className="nk-sh__br nk-sh__br--s" /><text x={908} y={157} className="nk-sh__c">evidence, bracketed</text>
            <line x1={884} x2={900} y1={182} y2={182} className="nk-sh__boundary nk-sh__ln" /><text x={908} y={186} className="nk-sh__c">machine boundary</text>
          </g>
        </svg>
      </div>
      <ol className="nk-sched" onMouseLeave={() => setAct(null)}>
        {schedule.map((s) => (
          <li key={s.n} className={act === s.n ? 'is-act' : ''} onMouseEnter={() => setAct(s.n)} onFocus={() => setAct(s.n)} onBlur={() => setAct(null)} tabIndex={0}>
            <span className="nk-sched__n" aria-hidden="true">{s.n}</span>
            <h3>{s.t}</h3>
            <p>{s.b}</p>
            <em>Marked: {s.marked}</em>
          </li>
        ))}
      </ol>
    </div>
  );
}
