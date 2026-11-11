// The DataTrust interface at full fidelity. The landing page films this same DOM;
// the app and results screens use it at 1:1. All values come from the fixture.
import type { ReactNode } from 'react';
import columnsAll from '../../fixture/columns.generated.json';
import { adult, local, runs, type Severity } from '../../fixture';
import { href } from '../../shell/router';

interface Col { name: string; target: boolean; missing: number; unique: number; kind: 'numeric' | 'categorical'; min?: number; max?: number; median?: number; q1?: number; q3?: number; bins?: number[]; values?: [string, number][] }
const cols = (columnsAll as unknown as Record<string, { rows: number; columns: Col[] }>).adult.columns;
const ev = Object.fromEntries(adult.columnEvidence.map((c) => [c.name, c]));

export type Tab = 'overview' | 'findings' | 'columns' | 'evidence' | 'report';
export const tabs: [Tab, string][] = [['overview', 'Overview'], ['findings', 'Findings'], ['columns', 'Columns'], ['evidence', 'Evidence'], ['report', 'Report']];

const sevClass: Record<Severity, string> = { High: 'is-high', Moderate: 'is-mod', Low: 'is-low' };
const effectOf = (s: string) => (s.startsWith('Evidence only') ? ['Evidence only', 'is-ev'] : s.startsWith('Reduces the target') ? ['Score + guardrail', 'is-cap'] : ['Sub-score', 'is-sub']);

export const Icon = {
  table: <svg viewBox="0 0 16 16" aria-hidden="true"><rect x="2" y="3" width="12" height="10" rx="1.5" /><path d="M2 6.5h12M6 6.5V13" /></svg>,
  outcomes: <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2.5 12.5 6 8l3 2.5 4.5-6" /><path d="M2.5 13.5h11" /></svg>,
  text: <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 4h10M3 7h10M3 10h7M3 13h5" /></svg>,
  images: <svg viewBox="0 0 16 16" aria-hidden="true"><rect x="2" y="3" width="12" height="10" rx="1.5" /><path d="m3.5 11 3-3 2.5 2.5L11 8.5l1.5 2" /><circle cx="10.5" cy="5.8" r="1" /></svg>,
  connected: <svg viewBox="0 0 16 16" aria-hidden="true"><rect x="1.5" y="4" width="5" height="8" rx="1" /><rect x="9.5" y="2.5" width="5" height="11" rx="1" /><path d="M6.5 8h3" /></svg>,
  time: <svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="5.5" /><path d="M8 5v3l2 1.5" /></svg>,
  down: <svg viewBox="0 0 16 16" aria-hidden="true"><path d="m4.5 6.5 3.5 3.5 3.5-3.5" /></svg>,
  file: <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 1.5h5.5L12.5 4.5v10H4z" /><path d="M9.5 1.5v3h3" /></svg>,
  lock: <svg viewBox="0 0 16 16" aria-hidden="true"><rect x="3.5" y="7" width="9" height="7" rx="1.5" /><path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2" /></svg>,
};
const repIcon: Record<string, ReactNode> = { tables: Icon.table, outcomes: Icon.outcomes, text: Icon.text, images: Icon.images, connected: Icon.connected, time: Icon.time };

export function Sidebar({ active = 'adult', link = false }: { active?: string; link?: boolean }) {
  return (
    <aside className="cm-side">
      <div className="cm-brand"><span className="cm-brand__mark" aria-hidden="true" /><b>DataTrust</b><span>by NUMEK</span></div>
      <p className="cm-side__h">Local runs</p>
      <nav className="cm-runs" aria-label="Local runs" data-cam="side">
        {runs.map((r) => {
          const inner = (<>
            <span className="cm-runs__i">{repIcon[r.rep]}</span>
            <span className="cm-runs__n">{r.name}</span>
            <span className={`cm-badge ${r.score == null ? 'is-none' : r.band === 'Low' ? 'is-ok' : 'is-mod'}`}>{r.score == null ? '—' : r.score.toFixed(1)}</span>
          </>);
          return link
            ? <a key={r.id} className={r.id === active ? 'is-on' : ''} href={r.id === 'adult' ? href('camera', 'results') : href('camera', 'app')}>{inner}</a>
            : <span key={r.id} className={`cm-runs__row ${r.id === active ? 'is-on' : ''}`}>{inner}</span>;
        })}
      </nav>
      <div className="cm-side__foot">
        <span className="cm-dot" aria-hidden="true" /> {local.host}:8000
        <small>Local only · no network at analysis time</small>
      </div>
    </aside>
  );
}

export function Topbar({ tab, onTab, exportOpen = false, onExport, crumbs = ['Runs', 'Adult'] }: { tab?: Tab; onTab?: (t: Tab) => void; exportOpen?: boolean; onExport?: () => void; crumbs?: string[] }) {
  return (
    <header className="cm-top">
      <div className="cm-crumbs">{crumbs.map((c, i) => <span key={c}>{i > 0 && <i>/</i>}{c}</span>)}</div>
      {tab && (
        <div className="cm-tabs" role="tablist" aria-label="Result views" data-cam="tabs">
          {tabs.map(([t, l]) => <button key={t} type="button" role="tab" aria-selected={tab === t} className={tab === t ? 'is-on' : ''} onClick={() => onTab?.(t)} tabIndex={onTab ? 0 : -1}>{l}</button>)}
        </div>
      )}
      <div className="cm-top__r" data-cam="export">
        <span className="cm-kbd">{adult.file}</span>
        <button type="button" className="cm-btn" onClick={onExport} aria-expanded={exportOpen} tabIndex={onExport ? 0 : -1}>Export {Icon.down}</button>
        {exportOpen && (
          <div className="cm-pop" role="menu">
            <p>Same evidence, three formats</p>
            {[['adult.html', 'Canonical · eight topics'], ['adult.pdf', 'Decision pages + appendix'], ['adult.json', 'Strict, complete']].map(([f, n]) => (
              <div key={f} className="cm-pop__i" role="menuitem">{Icon.file}<b>{f}</b><span>{n}</span></div>
            ))}
            <code>$ {local.commands[0]}</code>
          </div>
        )}
      </div>
    </header>
  );
}

/* ---------- Overview pieces ---------- */

export function ScoreCard() {
  return (
    <section className="cm-card cm-score" data-cam="score">
      <div className="cm-card__h"><span>Reliability score</span><span className="cm-chip is-cap">Guardrail applied</span></div>
      <div className="cm-score__row">
        <div className="cm-score__big"><b>{adult.finalScore.toFixed(1)}</b><span className="cm-band is-mod">{adult.band}</span></div>
        <div className="cm-score__flow">
          <div><span>Evidence</span><b>{adult.evidenceScore}</b></div>
          <i aria-hidden="true">→</i>
          <div><span>Critical sub-score</span><b>cap 69</b></div>
          <i aria-hidden="true">→</i>
          <div><span>Final</span><b className="is-mod">{adult.finalScore.toFixed(1)}</b></div>
        </div>
      </div>
      <p className="cm-note">{adult.guardrail.explanation} Bands: ≥85 Low · 70–84 Moderate · 50–69 Elevated · &lt;50 High.</p>
    </section>
  );
}

export function SubScores() {
  return (
    <section className="cm-card cm-subs" data-cam="subs">
      <div className="cm-card__h"><span>Sub-scores</span><span className="cm-muted">mean = {adult.evidenceScore}</span></div>
      {adult.subScores.map((s) => {
        const crit = 'critical' in s && s.critical;
        return (
          <div key={s.key} className={`cm-sub ${crit ? 'is-crit' : ''}`}>
            <span>{s.label}</span>
            <span className="cm-sub__bar"><i style={{ width: `${s.value}%` }} /><em style={{ left: '50%' }} /></span>
            <b>{s.value}</b>
          </div>
        );
      })}
      <p className="cm-note">Any sub-score ≤ 50 caps the final score at 69.</p>
    </section>
  );
}

export function FindingsCard({ open, onOpen }: { open?: string | null; onOpen?: (c: string) => void }) {
  return (
    <section className="cm-card cm-finds" data-cam="findings">
      <div className="cm-card__h"><span>Findings</span><span className="cm-muted">{adult.findings.length} · 2 change the score</span></div>
      {adult.findings.map((f) => {
        const [el, ec] = effectOf(f.scoreEffect);
        const isOpen = open === f.code;
        return (
          <div key={f.code} className={`cm-find ${isOpen ? 'is-open' : ''}`}>
            <button type="button" className="cm-find__row" onClick={() => onOpen?.(isOpen ? '' : f.code)} aria-expanded={isOpen} tabIndex={onOpen ? 0 : -1}>
              <span className={`cm-sev ${sevClass[f.severity]}`}>{f.severity}</span>
              <span className="cm-find__t">{f.title}<small>{f.evidence}</small></span>
              <span className={`cm-chip ${ec}`}>{el}</span>
            </button>
            {isOpen && (
              <div className="cm-find__d">
                <p><b>Finding</b>{f.finding}</p><p><b>Impact</b>{f.impact}</p><p><b>Review</b>{f.review}</p><p><b>Score effect</b>{f.scoreEffect}</p>
              </div>
            )}
          </div>
        );
      })}
    </section>
  );
}

export function DatasetCard() {
  return (
    <section className="cm-card cm-ds" data-cam="dataset">
      <div className="cm-card__h"><span>Dataset</span><span className="cm-muted">{adult.generatedAt}</span></div>
      <dl>
        <div><dt>Rows</dt><dd>{adult.rows.toLocaleString()}</dd></div>
        <div><dt>Columns</dt><dd>{adult.columns}</dd></div>
        <div><dt>Target</dt><dd className="cm-mono">{adult.target}</dd></div>
        <div><dt>Features</dt><dd>{adult.numericFeatures} numeric · {adult.nonNumericFeatures} other</dd></div>
        <div><dt>Runtime</dt><dd>{adult.runtimeSeconds.toFixed(2)} s · local</dd></div>
        <div><dt>sha256</dt><dd className="cm-mono">{adult.sha256.slice(0, 12)}…</dd></div>
      </dl>
    </section>
  );
}

function Spark({ c }: { c: Col }) {
  if (c.kind === 'numeric' && c.bins) {
    const m = Math.max(...c.bins);
    return <svg className="cm-spark" viewBox="0 0 64 18" preserveAspectRatio="none" aria-hidden="true">{c.bins.map((v, i) => <rect key={i} x={i * 2} y={18 - Math.max(.6, Math.sqrt(v / m) * 18)} width={1.5} height={Math.max(.6, Math.sqrt(v / m) * 18)} />)}</svg>;
  }
  const total = (c.values ?? []).reduce((s, [, n]) => s + n, 0) + c.missing;
  let x = 0;
  return (
    <svg className="cm-spark" viewBox="0 0 64 18" preserveAspectRatio="none" aria-hidden="true">
      {(c.values ?? []).slice(0, 6).map(([k, n], i) => { const w = (n / total) * 64; const r = <rect key={k} x={x} y={4} width={Math.max(.5, w - .6)} height={10} opacity={1 - i * .14} />; x += w; return r; })}
      {c.missing > 0 && <rect x={64 - (c.missing / total) * 64} y={4} width={(c.missing / total) * 64} height={10} className="cm-spark__miss" />}
    </svg>
  );
}

const flagged: Record<string, string> = { hours_per_week: 'Outliers', marital_status: 'Review', annual_income_over_50k: 'Target', capital_loss: 'Near-const.' };

export function ColumnsCard({ limit }: { limit?: number }) {
  const list = limit ? cols.slice(0, limit) : cols;
  return (
    <section className="cm-card cm-cols" data-cam="columns">
      <div className="cm-card__h"><span>Columns</span><span className="cm-muted">{cols.length} · distributions from the file</span></div>
      <div className="cm-tbl" role="table" aria-label="Columns">
        <div role="row" className="cm-tbl__h"><span>Name</span><span>Type</span><span>Distribution</span><span>Missing</span><span>Unique</span><span>IQR outliers</span><span /></div>
        {list.map((c) => (
          <div role="row" key={c.name} className={flagged[c.name] ? 'is-flag' : ''}>
            <span className="cm-mono">{c.name}</span>
            <span className="cm-muted">{ev[c.name]?.type}</span>
            <span><Spark c={c} /></span>
            <span>{ev[c.name]?.missing}</span>
            <span>{ev[c.name]?.unique}</span>
            <span>{ev[c.name]?.outliers}</span>
            <span>{flagged[c.name] && <span className={`cm-chip ${c.name === 'annual_income_over_50k' ? 'is-cap' : c.name === 'hours_per_week' ? 'is-sub' : 'is-ev'}`}>{flagged[c.name]}</span>}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

export function ConflictCard({ group = 0 }: { group?: number }) {
  const g = adult.conflicts[group];
  const keys = Object.keys(g.features);
  return (
    <section className="cm-card cm-conf" data-cam="conflict">
      <div className="cm-card__h"><span>Evidence · conflicting labels</span><span className="cm-muted">group {g.id} of {adult.conflicts.length}</span></div>
      <div className="cm-conf__grid">
        <span className="cm-muted">Feature</span>
        {g.rows.map((r) => <span key={r} className="cm-muted cm-mono">row {r.toLocaleString()}</span>)}
        {keys.map((k) => (
          <div key={k} className="cm-conf__r">
            <span className="cm-mono">{k}</span>
            {g.rows.map((r) => <span key={r} className="cm-mono">{String(g.features[k])}</span>)}
          </div>
        ))}
        <div className="cm-conf__r is-diff">
          <span className="cm-mono">{adult.target}</span>
          {g.labels.map((l, i) => <span key={i} className="cm-mono">{l}</span>)}
        </div>
      </div>
      <p className="cm-note">14 of 14 features equal; labels differ. Evidence only — no score changes.</p>
    </section>
  );
}

export function HoursCard() {
  const h = adult.hours; const c = h.hist.counts; const m = Math.max(...c);
  const W = 392, H = 96, bw = W / c.length;
  const x = (v: number) => (v - h.hist.start) * bw;
  return (
    <section className="cm-card cm-hours" data-cam="hours">
      <div className="cm-card__h"><span>hours_per_week · 1.5 × IQR</span><span className="cm-muted">{h.outliers.toLocaleString()} outside · 27.63%</span></div>
      <svg viewBox={`0 0 ${W} ${H + 16}`} className="cm-hist" aria-label={`Histogram of hours per week with fences at ${h.lower} and ${h.upper}`}>
        <rect x={x(h.lower)} y={0} width={x(h.upper) - x(h.lower)} height={H} className="cm-hist__band" />
        {c.map((v, i) => { const val = h.hist.start + i; const hh = Math.max(.8, Math.sqrt(v / m) * H); return <rect key={i} x={i * bw + .4} y={H - hh} width={bw - .8} height={hh} className={val < h.lower || val > h.upper ? 'is-out' : ''} />; })}
        <text x={x(h.lower)} y={H + 12} textAnchor="middle">{h.lower}</text>
        <text x={x(h.upper)} y={H + 12} textAnchor="middle">{h.upper}</text>
      </svg>
    </section>
  );
}

/** The Overview layout, used by the landing camera and the results screen. */
export function Overview({ open, onOpen }: { open?: string | null; onOpen?: (c: string) => void }) {
  return (
    <div className="cm-ov">
      <div className="cm-ov__a"><ScoreCard /><SubScores /></div>
      <div className="cm-ov__b"><FindingsCard open={open} onOpen={onOpen} /><DatasetCard /></div>
      <div className="cm-ov__c"><ConflictCard /><HoursCard /></div>
      <div className="cm-ov__d"><ColumnsCard limit={7} /></div>
    </div>
  );
}

/** A browser window around the app, the way `datatrust ui` opens. */
export function Window({ children, url = 'http://127.0.0.1:8000/runs/adult' }: { children: ReactNode; url?: string }) {
  return (
    <div className="cm-win">
      <div className="cm-win__bar"><span className="cm-win__dots" aria-hidden="true"><i /><i /><i /></span><span className="cm-win__url"><span className="cm-dot" aria-hidden="true" />{url}</span><span /></div>
      <div className="cm-win__body">{children}</div>
    </div>
  );
}

