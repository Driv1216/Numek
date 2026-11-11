import { columnsProfile, hours, run, nf } from '../../shared/engine';

/*
 * A measured drawing of the real Adult table. Columns run across, all 48,842
 * rows run down (to scale). Flags are drawn where the evidence sits: two CSV
 * lines, three columns and a class proportion. Nothing here is decorative.
 */

const X0 = 70;
const X1 = 1090;
const Y0 = 110;
const Y1 = 560;
const N = columnsProfile.length;
const CW = (X1 - X0) / N;
const rowsY = (line: number) => Y0 + 34 + ((line - 2) / run.rows) * (Y1 - Y0 - 34);
const colX = (name: string) => X0 + columnsProfile.findIndex((c) => c.name === name) * CW;

export type FlagId = 'conflict' | 'outliers' | 'imbalance' | 'leakage';

export function SchemaDrawing({ show = ['conflict', 'outliers', 'imbalance', 'leakage'], className }: { show?: FlagId[]; className?: string }) {
  const hx = colX('hours_per_week');
  const mx = colX('marital_status');
  const tx = colX('annual_income_over_50k');
  const y850 = rowsY(850);
  const y22763 = rowsY(22763);
  const share = run.profile.target_distribution[0].percentage / 100;
  const on = (f: FlagId) => show.includes(f);
  return (
    <svg viewBox="0 0 1200 640" className={className} role="img" aria-label="Drawing of the Adult table with four flagged findings">
      <defs>
        <pattern id="ins-hatch" width="6" height="6" patternUnits="userSpaceOnUse">
          <path d="M0 6 L6 0" stroke="#1d1d1b" strokeWidth="0.5" opacity="0.32" />
        </pattern>
        <pattern id="ins-hatch-hot" width="5" height="5" patternUnits="userSpaceOnUse">
          <path d="M0 5 L5 0" stroke="#ff4f14" strokeWidth="0.8" />
        </pattern>
      </defs>

      {/* table body */}
      <g className="ins-draw" fill="none" stroke="#1d1d1b" strokeWidth="1">
        <rect x={X0} y={Y0} width={X1 - X0} height={Y1 - Y0} />
        <line x1={X0} y1={Y0 + 34} x2={X1} y2={Y0 + 34} />
        {columnsProfile.map((_, i) => i > 0 && <line key={i} x1={X0 + i * CW} y1={Y0} x2={X0 + i * CW} y2={Y1} strokeWidth="0.6" />)}
        {Array.from({ length: 26 }, (_, i) => (
          <line key={`r${i}`} x1={X0} y1={Y0 + 34 + (i + 1) * 16} x2={X1} y2={Y0 + 34 + (i + 1) * 16} strokeWidth="0.35" opacity="0.5" />
        ))}
      </g>

      {/* column headers */}
      {columnsProfile.map((c, i) => (
        <text key={c.name} x={X0 + i * CW + 5} y={Y0 + 21} className="ins-svg-mono" fontSize="7.4">
          {c.name.length > 12 ? `${c.name.slice(0, 11)}…` : c.name}
        </text>
      ))}

      {/* missing values: dimension marks at the column foot, real counts */}
      {columnsProfile
        .filter((c) => c.missing_count > 0)
        .map((c) => {
          const x = colX(c.name);
          return (
            <g key={c.name} className="ins-draw">
              <rect x={x + 4} y={Y1 + 10} width={CW - 8} height={8} fill="url(#ins-hatch)" stroke="#1d1d1b" strokeWidth="0.6" />
              <text x={x + 4} y={Y1 + 32} className="ins-svg-mono" fontSize="7.4">
                {nf(c.missing_count)} missing
              </text>
            </g>
          );
        })}

      {/* rows dimension */}
      <g className="ins-draw" stroke="#1d1d1b" strokeWidth="0.7">
        <line x1={X0 - 24} y1={Y0 + 34} x2={X0 - 24} y2={Y1} />
        <line x1={X0 - 30} y1={Y0 + 34} x2={X0 - 18} y2={Y0 + 34} />
        <line x1={X0 - 30} y1={Y1} x2={X0 - 18} y2={Y1} />
      </g>
      <text x={X0 - 30} y={(Y0 + Y1) / 2 + 40} className="ins-svg-mono" fontSize="8" transform={`rotate(-90 ${X0 - 30} ${(Y0 + Y1) / 2 + 40})`}>
        {nf(run.rows)} rows, to scale
      </text>

      {/* class proportion as a dimension on the right edge */}
      {on('imbalance') && (
        <g className="ins-flag">
          <rect x={tx + 3} y={Y0 + 37} width={CW - 6} height={Y1 - Y0 - 40} fill="url(#ins-hatch-hot)" opacity="0.35" />
          <g stroke="#ff4f14" strokeWidth="1.2">
            <line x1={X1 + 22} y1={Y0 + 34} x2={X1 + 22} y2={Y0 + 34 + share * (Y1 - Y0 - 34)} />
            <line x1={X1 + 16} y1={Y0 + 34} x2={X1 + 28} y2={Y0 + 34} />
            <line x1={X1 + 14} y1={Y0 + 34 + share * (Y1 - Y0 - 34)} x2={X1 + 30} y2={Y0 + 34 + share * (Y1 - Y0 - 34)} />
            <line x1={X1 + 22} y1={Y0 + 34 + share * (Y1 - Y0 - 34)} x2={X1 + 22} y2={Y1} strokeDasharray="3 3" />
            <line x1={X1 + 16} y1={Y1} x2={X1 + 28} y2={Y1} />
          </g>
          <text x={X1 + 36} y={Y0 + 34 + (share * (Y1 - Y0 - 34)) / 2} className="ins-svg-mono hot" fontSize="9">≤50K 76.07%</text>
          <text x={X1 + 36} y={Y0 + 34 + share * (Y1 - Y0 - 34) + 40} className="ins-svg-mono" fontSize="9">&gt;50K 23.93%</text>
        </g>
      )}

      {/* hours_per_week: outlier share as hot hatch, fences in the tag */}
      {on('outliers') && (
        <g className="ins-flag">
          <rect x={hx + 3} y={Y0 + 37} width={CW - 6} height={Y1 - Y0 - 40} fill="url(#ins-hatch-hot)" opacity="0.7" />
          <rect x={hx} y={Y0} width={CW} height={Y1 - Y0} fill="none" stroke="#ff4f14" strokeWidth="2" />
          <line x1={hx + CW / 2} y1={Y0} x2={hx + CW / 2} y2={52} stroke="#ff4f14" strokeWidth="1" />
          <foreignObject x={hx - 90} y={6} width="260" height="58">
            <div className="ins-tag">
              <b>NUMERIC_OUTLIERS · 1.5 × IQR</b>
              <span>
                {hours.outlier_rate}% of hours_per_week outside 32.5–52.5 h
              </span>
            </div>
          </foreignObject>
        </g>
      )}

      {/* marital_status: review-only name prompt */}
      {on('leakage') && (
        <g className="ins-flag">
          <rect x={mx} y={Y0} width={CW} height={34} fill="none" stroke="#ff4f14" strokeWidth="2" strokeDasharray="4 3" />
          <line x1={mx + CW / 2} y1={Y0} x2={mx + CW / 2} y2={70} stroke="#ff4f14" strokeWidth="1" strokeDasharray="3 3" />
          <foreignObject x={mx - 170} y={14} width="230" height="58">
            <div className="ins-tag is-soft">
              <b>TARGET_LEAKAGE · NAME HEURISTIC</b>
              <span>marital_status: confirm when it is known</span>
            </div>
          </foreignObject>
        </g>
      )}

      {/* two CSV lines with identical features and different labels */}
      {on('conflict') && (
        <g className="ins-flag">
          <line x1={X0} y1={y850} x2={X1} y2={y850} stroke="#ff4f14" strokeWidth="1.6" />
          <line x1={X0} y1={y22763} x2={X1} y2={y22763} stroke="#ff4f14" strokeWidth="1.6" />
          <circle cx={tx + CW / 2} cy={y850} r="3.5" fill="#ff4f14" />
          <circle cx={tx + CW / 2} cy={y22763} r="3.5" fill="#ff4f14" />
          <path d={`M${X0 + 40} ${y850} C ${X0 + 10} ${y850 + 40}, ${X0 + 10} ${y22763 - 40}, ${X0 + 40} ${y22763}`} fill="none" stroke="#ff4f14" strokeWidth="1" strokeDasharray="3 3" />
          <foreignObject x={X0 + 180} y={(y850 + y22763) / 2 - 30} width="300" height="62">
            <div className="ins-tag">
              <b>LABEL_CONFLICTS · DETERMINISTIC</b>
              <span>CSV lines 850 and 22,763: same 14 features, different label</span>
            </div>
          </foreignObject>
        </g>
      )}

      <text x={X0} y={622} className="ins-svg-mono" fontSize="8">
        SHEET A-01 · ADULT.CSV · SHA-256 {run.sha256.slice(0, 16)}… · {run.methodology}
      </text>
    </svg>
  );
}
