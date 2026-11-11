// How DataTrust works, scroll-driven. One Markup drawing of five stations inside the 127.0.0.1
// boundary; a camera moves from station to station as you scroll, the path fills behind it, and
// the copy says what the user gets at each step. The last step pulls back to the whole drawing.
import { useLayoutEffect, useRef, useState } from 'react';
import { adult } from '../../fixture';
import { reducedMotion, useScrollProgress } from '../../shell/motion';
import { brackets } from './system';

const steps = [
  { t: 'Point it at a file.', b: 'Your dataset stays on your machine. DataTrust reads it where it sits: no upload, no account, no network.', m: 'adult.csv · 48,842 rows' },
  { t: 'It understands the shape.', b: 'Tables, outcomes, time series, text, images, or records checked against their documents, each read by its own rules.', m: 'six kinds of data' },
  { t: 'It finds what would hurt a model.', b: 'Missing values, repeats, labels that contradict each other, unusual values, leaked answers and lopsided targets.', m: 'in Adult: 4 findings' },
  { t: 'It shows you exactly where.', b: 'Every finding points to the rows or columns behind it, so you can check it yourself instead of trusting a number.', m: 'rows 16,684 and 34,343' },
  { t: 'You get a report you can share.', b: 'A score only where one makes sense, every guardrail explained, written as HTML, PDF and JSON.', m: `${adult.finalScore.toFixed(1)} · ${adult.band} · ${adult.runtimeSeconds.toFixed(2)} s` },
];
const CX = [150, 375, 600, 825, 1050], CY = 230;
const checks: [string, boolean][] = [['missing values', false], ['repeated rows', false], ['contradicting labels', true], ['unusual values', true], ['leaked answers', true], ['lopsided target', true]];
// Camera per state: five close-ups, then the whole drawing.
const cams = [...CX.map((cx) => ({ cx, cy: CY - 10, s: 2.15 })), { cx: 600, cy: 210, s: 1 }];
const smooth = (t: number) => t * t * (3 - 2 * t);

function Arrow({ x0, x1, k, at }: { x0: number; x1: number; k: number; at: number }) {
  const fill = Math.max(0, Math.min(1, at - k));
  return (
    <g>
      <line x1={x0} x2={x1 - 2} y1={CY} y2={CY} className="nk-sh__ln nk-hw__track" />
      <line x1={x0} x2={x0 + (x1 - 2 - x0) * fill} y1={CY} y2={CY} className="nk-hw__flow" />
      <path d={`M${x1 - 8} ${CY - 5}L${x1} ${CY}L${x1 - 8} ${CY + 5}`} className={fill >= 1 ? 'nk-hw__ah is-on' : 'nk-hw__ah'} />
    </g>
  );
}

export function How() {
  const [ref, p] = useScrollProgress<HTMLElement>('pinned');
  const g = useRef<SVGGElement>(null);
  const [act, setAct] = useState(0);
  const rm = reducedMotion();
  // States: 0..4 stations, 5 overview. Each holds, then glides to the next.
  const f = Math.min(5, p * 5.6);
  const i = Math.min(4, Math.floor(f)), raw = f - i;
  const t = rm ? (raw < 0.5 ? 0 : 1) : smooth(Math.min(1, Math.max(0, (raw - 0.45) / 0.55)));
  const at = i + t; // progress along the path, 0..5

  useLayoutEffect(() => {
    const a = cams[i], b = cams[i + 1];
    // Narrow screens zoom less; the camera never looks past the drawing's edges.
    const z = innerWidth < 900 ? 0.7 : 1, sa = a.s === 1 ? 1 : a.s * z, sb = b.s === 1 ? 1 : b.s * z;
    const s = Math.exp(Math.log(sa) + (Math.log(sb) - Math.log(sa)) * t);
    const half = 600 / s, cx = Math.min(1200 - half, Math.max(half, a.cx + (b.cx - a.cx) * t)), cy = a.cy + (b.cy - a.cy) * t;
    g.current?.setAttribute('transform', `translate(${600 - cx * s} ${210 - cy * s}) scale(${s})`);
    setAct(Math.min(5, Math.round(at)));
  }, [i, t, at]);

  const on = (k: number) => (act === 5 || act === k ? 'is-on' : act > k ? 'is-past' : '');
  const step = steps[Math.min(4, act)];
  return (
    <section id="dt-how" ref={ref} className="nk-hw" aria-labelledby="dt-how-h" style={{ height: '430vh' }}>
      <div className="nk-hw__stage">
        <div className="nk-hw__copy">
          <span className="nk-label">How it works</span>
          <h2 id="dt-how-h" className="nk-hw__h">{act === 5 ? 'Five steps, all on your machine.' : step.t}</h2>
          <p className="nk-hw__b" key={act}>{act === 5 ? 'From file to shareable report without the data ever leaving 127.0.0.1.' : step.b}</p>
          <span className="nk-hw__m">{act === 5 ? `${adult.rows.toLocaleString()} rows · ${adult.runtimeSeconds.toFixed(2)} s · nothing uploaded` : step.m}</span>
          <ol className="nk-hw__dots" aria-hidden="true">{steps.map((_, k) => <li key={k} className={on(k)}><b>{k + 1}</b></li>)}</ol>
        </div>
        <div className="nk-hw__view">
          <svg viewBox="0 0 1200 420" className="nk-sh nk-hw__svg" role="img" aria-label="Five steps inside your machine: your file, its shape, the checks, the marked rows, and the report.">
            <defs><pattern id="nk-grid4" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" className="nk-sh__grid" /></pattern></defs>
            <rect x={0} y={0} width={1200} height={420} fill="url(#nk-grid4)" />
            <g ref={g}>
              <rect x={40} y={44} width={1120} height={344} rx={6} className="nk-sh__boundary nk-hw__bd" />
              <text x={56} y={66} className="nk-sh__t nk-sh__t--b">127.0.0.1 · YOUR MACHINE · NOTHING UPLOADED</text>

              <g className={`nk-hw__st ${on(0)}`}>
                <path d={`M${CX[0] - 44} ${CY - 62}H${CX[0] + 22}L${CX[0] + 44} ${CY - 40}V${CY + 62}H${CX[0] - 44}Z`} className="nk-sh__ln nk-sh__page" />
                <path d={`M${CX[0] + 22} ${CY - 62}V${CY - 40}H${CX[0] + 44}`} className="nk-sh__ln" />
                {[0, 1, 2, 3, 4, 5, 6].map((k) => <line key={k} x1={CX[0] - 32} x2={CX[0] + (k % 3 === 2 ? 4 : 32)} y1={CY - 30 + k * 12} y2={CY - 30 + k * 12} className="nk-how__l" />)}
                <text x={CX[0]} y={CY + 86} textAnchor="middle" className="nk-sh__t">adult.csv</text>
              </g>
              <Arrow x0={CX[0] + 58} x1={CX[1] - 72} k={0} at={at} />

              <g className={`nk-hw__st ${on(1)}`}>
                {[0, 1, 2, 3, 4, 5].map((k) => {
                  const x = CX[1] - 58 + (k % 2) * 64, y = CY - 64 + Math.floor(k / 2) * 46;
                  return (
                    <g key={k} transform={`translate(${x} ${y})`}>
                      <rect width={52} height={36} rx={3} className="nk-sh__ln nk-sh__page" />
                      {k === 0 && <path d="M0 12H52M0 24H52M17 0V36M34 0V36" className="nk-how__g" />}
                      {k === 1 && <path d="M6 28L16 20L26 24L36 12L46 8" className="nk-how__g2" />}
                      {k === 2 && <><circle cx={26} cy={18} r={11} className="nk-how__g" /><path d="M26 18V11M26 18L31 21" className="nk-how__g2" /></>}
                      {k === 3 && <path d="M7 10H45M7 18H40M7 26H30" className="nk-how__g2" />}
                      {k === 4 && <path d="M6 30L18 16L28 26L34 20L46 30Z" className="nk-how__g" />}
                      {k === 5 && <><rect x={6} y={8} width={14} height={20} className="nk-how__g" /><rect x={32} y={8} width={14} height={20} className="nk-how__g" /><path d="M20 18H32" className="nk-how__g2" /></>}
                    </g>
                  );
                })}
                <text x={CX[1]} y={CY + 86} textAnchor="middle" className="nk-sh__t">your data, any shape</text>
              </g>
              <Arrow x0={CX[1] + 78} x1={CX[2] - 86} k={1} at={at} />

              <g className={`nk-hw__st ${on(2)}`}>
                {checks.map(([c, hit], k) => (
                  <g key={c} transform={`translate(${CX[2] - 78} ${CY - 66 + k * 24})`}>
                    <rect width={14} height={14} className="nk-sh__ln" />
                    <path d="M3 7L6 10L11 4" className="nk-how__tick" />
                    <text x={22} y={11} className="nk-sh__c">{c}</text>
                    {hit && <circle cx={164} cy={7} r={4} className="nk-how__hit" />}
                  </g>
                ))}
                <text x={CX[2]} y={CY + 86} textAnchor="middle" className="nk-sh__t">checked</text>
              </g>
              <Arrow x0={CX[2] + 100} x1={CX[3] - 64} k={2} at={at} />

              <g className={`nk-hw__st ${on(3)}`}>
                {Array.from({ length: 8 }, (_, k) => <rect key={k} x={CX[3] - 50} y={CY - 60 + k * 15} width={100} height={9} className={k === 3 || k === 4 ? 'nk-how__rowhot' : 'nk-how__row'} />)}
                <path d={brackets(CX[3] - 58, CY - 60 + 3 * 15 - 6, 116, 2 * 15 + 3, 8)} className="nk-sh__br nk-hw__br" />
                <text x={CX[3]} y={CY + 86} textAnchor="middle" className="nk-sh__t nk-sh__t--hot">marked</text>
              </g>
              <Arrow x0={CX[3] + 66} x1={CX[4] - 80} k={3} at={at} />

              <g className={`nk-hw__st ${on(4)}`}>
                <text x={CX[4] - 72} y={CY - 34} className="nk-how__big">{adult.finalScore.toFixed(1)}</text>
                <text x={CX[4] + 10} y={CY - 34} className="nk-sh__c">{adult.band}</text>
                <line x1={CX[4] - 72} x2={CX[4] + 72} y1={CY - 14} y2={CY - 14} className="nk-sh__ln" />
                <line x1={CX[4] - 72 + 144 * 0.69} x2={CX[4] - 72 + 144 * 0.69} y1={CY - 24} y2={CY - 4} className="nk-sh__cap" />
                <path d={`M${CX[4] - 72 + (144 * adult.evidenceScore) / 100} ${CY - 18}l-4 -7h8z`} className="nk-sh__tri" />
                {['HTML', 'PDF', 'JSON'].map((x, k) => (
                  <g key={x} transform={`translate(${CX[4] - 72 + k * 52} ${CY + 6})`}><path d="M0 0H30L40 10V44H0Z" className="nk-sh__ln nk-sh__page" /><text x={20} y={30} textAnchor="middle" className="nk-sh__c">{x}</text></g>
                ))}
                <text x={CX[4]} y={CY + 86} textAnchor="middle" className="nk-sh__t">reported</text>
              </g>
              {CX.map((x, k) => <g key={k} className={`nk-sh__num nk-hw__num ${on(k)}`}><circle cx={x} cy={96} r={12} /><text x={x} y={100} textAnchor="middle">{k + 1}</text></g>)}
            </g>
          </svg>
        </div>
      </div>
    </section>
  );
}
