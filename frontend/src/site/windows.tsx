// The three product windows the landing camera films. DataTrust is the real Modules dashboard
// (its tiles, states and live drawings, recoloured in Deep water). ConfidenceGuard is a CG1
// workbench screen built from CG1's recorded German Credit evaluation. HallucinationGuard is a
// labelled placeholder.
import { adult, runs } from './content';
import cg from './content/cg1.generated.json';
import { mods, runStates, type ModId } from './modules/data';
import { Viz } from './modules/viz';
import { Status, brackets } from '../foundation/system';

/* ——— DataTrust: the Modules dashboard ——— */

// Which run each drawing comes from (as in Modules): a drawing appears only when it shows the selected run.
const drawnFrom: Record<ModId, string | null> = {
  score: 'adult', gaps: 'adult', dups: 'adult', conflicts: 'adult', imbalance: 'adult', leakage: 'adult', outliers: 'adult',
  relations: 'bike', time: null, text: 'sms', images: 'coco', docs: 'finance', local: '*', reports: '*',
};
// Deep water shades for DataTrust (tide): dark, mid, light, pale, card. Light-ink tiles marked `true`.
export const shade: Record<ModId, [string, boolean]> = {
  score: ['#163F52', true], gaps: ['#D5E4EB', false], dups: ['#FBFAF7', false], conflicts: ['#2C6E8E', true], imbalance: ['#D5E4EB', false],
  leakage: ['#163F52', true], outliers: ['#BCD3DE', false], relations: ['#FBFAF7', false], time: ['#D5E4EB', false], text: ['#2C6E8E', true],
  images: ['#FBFAF7', false], docs: ['#BCD3DE', false], local: ['#163F52', true], reports: ['#D5E4EB', false],
};
const cam: Partial<Record<ModId, string>> = { score: 'dt-score', conflicts: 'dt-conflicts' };

export function DataTrustWindow() {
  const st = runStates.adult;
  const applies = mods.filter((m) => st[m.id]).length;
  return (
    <div className="nk-win nk-win--dt" data-cam="dt">
      <div className="nk-win__bar"><b>DataTrust</b><span>adult.csv · 127.0.0.1:8000</span><Status tone="on">Available</Status></div>
      <div className="nk-dt">
        <nav className="nk-dt__runs" aria-hidden="true">
          <span className="nk-k">Local runs</span>
          {runs.map((r) => (
            <div key={r.id} className={r.id === 'adult' ? 'is-on' : ''}>
              <b>{r.name}</b><span>{r.rep} · {r.size}</span><span>{r.score == null ? 'No score defined' : `${r.score.toFixed(1)} · ${r.band}`}</span>
            </div>
          ))}
        </nav>
        <div className="nk-dt__main">
          <header className="nk-dt__h">
            <h3>Adult</h3>
            <p>{adult.file} · {adult.task}<br />13 Aug 2026 · {adult.runtimeSeconds.toFixed(2)} s · {applies} of 14 modules apply</p>
          </header>
          <div className="nk-mosaic">
            {mods.map((m) => {
              const s = st[m.id];
              const src = drawnFrom[m.id];
              const [bg, light] = shade[m.id];
              return (
                <div key={m.id} data-mod={m.id} data-cam={cam[m.id]} className={`nk-tile ${light ? 'is-light' : ''} ${s ? '' : 'is-dim'}`} style={{ gridArea: m.area, ['--bg' as string]: bg }}>
                  <span className="nk-tile__top"><span className="nk-tile__name">{m.name}</span><span className="nk-tile__n">{m.n}</span></span>
                  <span className="nk-tile__fig">
                    <b className={s && (s.tone === 'critical' || s.tone === 'finding') ? `is-${s.tone}` : ''}>{s ? s.label : 'Not for this data'}</b>
                    <span>{s ? s.detail : m.line}</span>
                  </span>
                  {s && (src === 'adult' || src === '*') && <span className="nk-tile__viz"><Viz id={m.id} /></span>}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ——— ConfidenceGuard: a CG1 workbench screen ——— */

const M = cg.measurements;
export const cgFig = {
  caught: Math.round(M.recall.value * M.recall.denominator),
  flagged: M.precision.denominator,
  goodKept: Math.round(M.specificity.value * M.specificity.denominator),
  correct: Math.round(M.accuracy.value * M.accuracy.denominator),
};
const missed = cg.bad - cgFig.caught, falseAlarm = cgFig.flagged - cgFig.caught;
const pc = (v: number) => `${(v * 100).toFixed(1)}%`;

function Measure({ k, v, pop, hot, cam }: { k: string; v: string; pop: string; hot?: boolean; cam?: string }) {
  return <div className={`nk-meas ${hot ? 'is-hot' : ''}`} data-cam={cam}><span>{k}</span><b>{v}</b><em>{pop}</em></div>;
}

function Reliability() {
  const W = 300, H = 230, x0 = 34, y0 = 12, w = W - x0 - 10, h = H - y0 - 30;
  const X = (v: number) => x0 + v * w, Y = (v: number) => y0 + (1 - v) * h;
  const pts = cg.calibration.filter((b) => b.n > 0 && b.mean_p != null && b.observed != null) as { n: number; mean_p: number; observed: number }[];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="nk-rel" role="img" aria-label="Reliability diagram: predicted probability of bad credit against the observed rate, ten bins">
      <rect x={x0} y={y0} width={w} height={h} className="nk-rel__bg" />
      {[0.25, 0.5, 0.75].map((v) => <g key={v}><line x1={X(v)} x2={X(v)} y1={y0} y2={y0 + h} className="nk-rel__g" /><line x1={x0} x2={x0 + w} y1={Y(v)} y2={Y(v)} className="nk-rel__g" /></g>)}
      <line x1={X(0)} y1={Y(0)} x2={X(1)} y2={Y(1)} className="nk-rel__d" />
      <polyline points={pts.map((b) => `${X(b.mean_p)},${Y(b.observed)}`).join(' ')} className="nk-rel__l" />
      {pts.map((b, i) => <circle key={i} cx={X(b.mean_p)} cy={Y(b.observed)} r={2 + Math.sqrt(b.n) * 0.7} className="nk-rel__p" />)}
      <text x={x0} y={H - 8} className="nk-rel__t">predicted p(bad) →</text>
      <text x={x0 + w} y={H - 8} textAnchor="end" className="nk-rel__t">1.0</text>
      <text x={x0 - 6} y={y0 + 8} textAnchor="end" className="nk-rel__t">1.0</text>
    </svg>
  );
}

export function ConfidenceWindow() {
  return (
    <div className="nk-win nk-win--cg" data-cam="cg">
      <div className="nk-win__bar"><b>ConfidenceGuard</b><span>CG1 workbench · german_credit predictions · {cg.n} held-out</span><Status tone="dev">In development</Status></div>
      <div className="nk-cg">
        <header className="nk-cg__h">
          <h3>Binary evaluation · model0</h3>
          <p>Outcome: German Credit supplied credit_risk · positive class “{cg.positive}” · {cg.bad} bad / {cg.n - cg.bad} good</p>
        </header>
        <div className="nk-cg__meas">
          <Measure k="Accuracy" v={pc(M.accuracy.value)} pop={`${cgFig.correct} of ${cg.n}`} />
          <Measure k="Recall · bad credit" v={pc(M.recall.value)} pop={`${cgFig.caught} of ${cg.bad} caught`} hot cam="cg-recall" />
          <Measure k="Specificity" v={pc(M.specificity.value)} pop={`${cgFig.goodKept} of ${M.specificity.denominator} good`} />
          <Measure k="Precision" v={pc(M.precision.value)} pop={`${cgFig.caught} of ${cgFig.flagged} flagged`} />
          <Measure k="Balanced accuracy" v={pc(M.balanced_accuracy.value)} pop={`${cg.n} rows`} />
          <Measure k="ROC AUC" v={M.roc_auc.value.toFixed(3)} pop={`${cg.n} rows`} />
          <Measure k="Brier" v={M.brier.value.toFixed(3)} pop={`${cg.n} rows`} />
          <Measure k="Issued errors" v={String(M.issued_errors.value)} pop={`of ${cg.n}`} />
        </div>
        <div className="nk-cg__side">
          <div className="nk-conf" data-cam="cg-conf">
            <span className="nk-k">Confusion · actual × predicted</span>
            <div className="nk-conf__g">
              <span /><span>pred. bad</span><span>pred. good</span>
              <span>bad</span><b>{cgFig.caught}</b><b className="is-hot">{missed}</b>
              <span>good</span><b>{falseAlarm}</b><b>{cgFig.goodKept}</b>
            </div>
          </div>
          <div className="nk-relbox"><span className="nk-k">Calibration · 10 bins</span><Reliability /></div>
        </div>
        <footer className="nk-cg__f">No universal reliability score · exact local report and conservative shareable projection · the model is never run</footer>
      </div>
    </div>
  );
}

/* ——— HallucinationGuard: a labelled placeholder ——— */

export function HallucinationWindow() {
  return (
    <div className="nk-win nk-win--hg" data-cam="hg">
      <div className="nk-win__bar"><b>HallucinationGuard</b><span>research direction</span><Status tone="res">Prototype placeholder</Status></div>
      <div className="nk-hg">
        <div className="nk-hg__ans">
          <span className="nk-k">Generated answer</span>
          <p className="nk-hg__q">What does the refund policy allow?</p>
          <p className="nk-hg__a">
            Refunds are available <span className="nk-claim is-ok">within 30 days of delivery<sup>S1</sup></span> and <span className="nk-claim is-x">include the original shipping cost<sup>S2</sup></span>.
          </p>
          <svg viewBox="0 0 420 70" className="nk-hg__legend" aria-hidden="true">
            <path d={brackets(4, 8, 120, 26, 7)} className="nk-hg__b" /><text x={134} y={26} className="nk-ld__t">contradicted by S2</text>
            <line x1={4} x2={124} y1={56} y2={56} className="nk-hg__ok" /><text x={134} y={60} className="nk-ld__t">supported by S1</text>
          </svg>
        </div>
        <div className="nk-hg__src">
          <span className="nk-k">Sources</span>
          <p><b>S1 · Policy §2</b> Customers may request a refund within 30 days of delivery.</p>
          <p><b>S2 · Policy §4</b> <mark>Shipping costs are not refundable.</mark></p>
        </div>
        <span className="nk-hg__wm" aria-hidden="true">PLACEHOLDER</span>
        <footer className="nk-cg__f">Illustrative content for this prototype. HallucinationGuard is a research direction, not a product.</footer>
      </div>
    </div>
  );
}
