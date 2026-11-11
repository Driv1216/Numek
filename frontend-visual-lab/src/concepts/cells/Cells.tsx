import { useState, type ReactNode } from 'react';
import { Go, href, type Screen } from '../../shared/router';
import {
  adult,
  audits,
  capabilities,
  evidenceScore,
  fmt,
  imbalanceRatio,
  majorityShare,
  pct,
  principles,
  type Audit,
} from '../../shared/data';
import { Dither } from './Dither';
import './cells.css';
import '@fontsource/big-shoulders-display/700';
import '@fontsource/big-shoulders-display/900';
import '@fontsource/gloock/400';
import '@fontsource/public-sans/400';
import '@fontsource/public-sans/500';

const C = 'cells';
const LINE = '#f4bcc4';

/*
 * Shape grammar. Every cell's outline encodes what it holds:
 *   circle   a measured number
 *   stadium  an action or a filter
 *   slab     prose
 *   bay      a chart (large radius on one corner)
 */
type Shape = 'circle' | 'stadium' | 'slab' | 'bay';

function Cell({
  shape = 'slab',
  className = '',
  children,
  style,
  label,
}: {
  shape?: Shape;
  className?: string;
  children?: ReactNode;
  style?: React.CSSProperties;
  label?: string;
}) {
  return (
    <div className={`ce-cell is-${shape} ${className}`} style={style} aria-label={label}>
      {children}
    </div>
  );
}

function Header({ screen }: { screen: Screen }) {
  return (
    <header className="ce-head">
      <Go to={href(C)} className="ce-logo" label="DataTrust home">
        <span>NU</span>
        <span>ME</span>
        <span>K</span>
      </Go>
      <nav className="ce-nav" aria-label="Concept screens">
        <Go to={href(C)} className={`ce-word${screen === 'landing' ? ' is-on' : ''}`}>
          INTRO
        </Go>
        <Go to={href(C, 'workspace')} className={`ce-serif${screen === 'workspace' ? ' is-on' : ''}`}>
          workspace
        </Go>
        <Go to={href(C, 'results')} className={`ce-word${screen === 'results' ? ' is-on' : ''}`}>
          ADULT
        </Go>
      </nav>
      <div className="ce-head-right">
        <Go to="#/" className="ce-btn is-ghost">
          All concepts
        </Go>
        <Go to={href(C, 'workspace')} className="ce-btn">
          Open workspace
        </Go>
      </div>
    </header>
  );
}

function ClassSplit({ tall = 180 }: { tall?: number }) {
  return (
    <div className="ce-split" style={{ height: tall }}>
      {adult.classes.map((c, i) => (
        <div key={c.label} className="ce-split-part" style={{ flexGrow: c.count }}>
          <Dither level={i === 0 ? 0.32 : 1} color={LINE} className="ce-dither" />
          <span className="ce-split-tag">
            <b>{c.label}</b> {fmt(c.count)}
          </span>
        </div>
      ))}
    </div>
  );
}

function HoursStrip() {
  const max = Math.max(...adult.hourBins.map((b) => b.low + b.high));
  return (
    <div className="ce-strip">
      {adult.hourBins.map((b) => (
        <div key={b.label} title={`${b.label} h: ${fmt(b.low + b.high)} rows`}>
          <Dither level={Math.max(0.04, (b.low + b.high) / max)} color={LINE} className="ce-dither" />
        </div>
      ))}
    </div>
  );
}

function HoursBars() {
  const max = Math.max(...adult.hourBins.map((b) => b.low + b.high));
  return (
    <div className="ce-hours">
      {adult.hourBins.map((b) => {
        const t = b.low + b.high;
        return (
          <div key={b.label} className="ce-hours-col">
            <div className="ce-hours-bar" style={{ height: `${Math.max(1.5, (t / max) * 100)}%` }}>
              <Dither level={0.32} color={LINE} className="ce-dither" />
              <div className="ce-hours-hi" style={{ height: `${(b.high / t) * 100}%` }} />
            </div>
            <span>{b.label.split('–')[0]}</span>
          </div>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ Landing */

function Landing() {
  return (
    <main className="ce-main">
      <section className="ce-grid ce-hero">
        <Cell className="ce-g-a">
          <span className="ce-small">Numek</span>
          <span className="ce-cell-big">DataTrust</span>
        </Cell>
        <Cell shape="bay" className="ce-g-b">
          <HoursStrip />
          <span className="ce-small ce-strip-cap">Adult, hours_per_week. Density is the share of rows in each 10-hour bin.</span>
        </Cell>
        <Cell shape="stadium" className="ce-g-c">
          <span className="ce-small">Python API, command line, browser</span>
        </Cell>
        <Cell className="ce-g-side">
          <span className="ce-vert">DataTrust reliability report</span>
        </Cell>
        <div className="ce-title">
          <h1>
            <span className="ce-pill">EVIDENCE</span>
            <span className="ce-pill is-serif">before</span>
            <span className="ce-pill">TRAINING</span>
          </h1>
          <p className="ce-dek">Dataset reliability, read on your own machine.</p>
        </div>
        <Cell shape="circle" className="ce-g-d" label="Rows read">
          <span className="ce-num">{fmt(adult.rows)}</span>
          <span className="ce-small">rows read in {adult.runtime.toFixed(2)} s</span>
        </Cell>
        <Cell className="ce-g-e">
          <span className="ce-small">Out</span>
          <span className="ce-cell-big">HTML, PDF, JSON</span>
        </Cell>
        <Cell shape="bay" className="ce-g-f">
          <div className="ce-f-split">
            {adult.classes.map((c, i) => (
              <div key={c.label} style={{ flexGrow: c.count }}>
                <Dither level={i === 0 ? 0.32 : 1} color={LINE} className="ce-dither" />
              </div>
            ))}
          </div>
          <span className="ce-small ce-strip-cap">≤50K and &gt;50K, to scale</span>
        </Cell>
        <Cell shape="stadium" className="ce-g-g">
          <span className="ce-small">Local only. Nothing uploaded.</span>
        </Cell>
      </section>

      <section className="ce-grid ce-intro">
        <Cell className="ce-g-label">
          <span className="ce-small">Introduction</span>
        </Cell>
        <Cell className="ce-g-text">
          <p className="ce-lede">
            DataTrust reads a dataset before you train on it and writes a report your CTO, risk lead or customer can
            follow. Every risk names its evidence, what it may do to a model, and what to check next.
          </p>
        </Cell>
        <Cell shape="bay" className="ce-g-chart">
          <p className="ce-small">Adult, census income. Who earns more than 50K?</p>
          <ClassSplit />
          <p className="ce-chart-note">
            A model that always answers ≤50K is right {pct(majorityShare)} of the time. DataTrust says so before the
            accuracy number does.
          </p>
        </Cell>
        <Cell shape="circle" className="ce-g-ratio">
          <span className="ce-num">{imbalanceRatio.toFixed(2)}</span>
          <span className="ce-small">majority to minority</span>
        </Cell>
      </section>

      <section className="ce-grid ce-rules">
        <Cell className="ce-g-label">
          <span className="ce-small">Method</span>
        </Cell>
        {principles.map((p) => (
          <Cell key={p.title} className="ce-rule">
            <h3>{p.title}</h3>
            <p>{p.body}</p>
          </Cell>
        ))}
      </section>

      <section className="ce-grid ce-caps">
        <Cell className="ce-g-label">
          <span className="ce-small">What it reads</span>
        </Cell>
        <div className="ce-caps-list">
          {capabilities.map((c) => (
            <Cell key={c.name} shape="stadium" className="ce-cap">
              <b>{c.name}</b>
              <span>{c.detail}</span>
            </Cell>
          ))}
          <Cell shape="stadium" className="ce-cap is-off">
            <b>Audio</b>
            <span>Deferred</span>
          </Cell>
        </div>
      </section>

      <section className="ce-grid ce-end">
        <Cell shape="bay" className="ce-g-end">
          <h2>
            <span className="ce-pill">READ</span>
            <span className="ce-pill is-serif">the</span>
            <span className="ce-pill">ADULT AUDIT</span>
          </h2>
          <Go to={href(C, 'results')} className="ce-btn is-light">
            Open the report
          </Go>
        </Cell>
        <Cell shape="circle" className="ce-g-out">
          <span className="ce-small">HTML</span>
          <span className="ce-small">PDF</span>
          <span className="ce-small">JSON</span>
        </Cell>
      </section>
    </main>
  );
}

/* ---------------------------------------------------------------- Workspace */

function shapeFor(a: Audit): Shape {
  if (a.kind === 'Regression') return 'stadium';
  if (a.kind === 'Connected evidence') return 'bay';
  return 'circle';
}

function Workspace() {
  const [kind, setKind] = useState<'All' | Audit['kind']>('All');
  const kinds: ('All' | Audit['kind'])[] = ['All', 'Classification', 'Regression', 'Connected evidence', 'Controlled mutation'];
  return (
    <main className="ce-main">
      <section className="ce-grid ce-ws-top">
        <div className="ce-title ce-title--left">
          <h1>
            <span className="ce-pill">SEVEN</span>
            <span className="ce-pill is-serif">audits</span>
            <span className="ce-pill">ON THIS MACHINE</span>
          </h1>
        </div>
        <Cell className="ce-ws-path">
          <span className="ce-small">~/numek/audits</span>
          <p>Shape tells the task. Circles carry a score, stadiums are regression with no score defined, the bay is connected evidence. A dashed circle is a controlled test.</p>
        </Cell>
      </section>

      <div className="ce-filters" role="tablist" aria-label="Filter audits">
        {kinds.map((k) => (
          <button key={k} role="tab" aria-selected={kind === k} className={`ce-btn${kind === k ? '' : ' is-ghost'}`} onClick={() => setKind(k)}>
            {k}
          </button>
        ))}
      </div>

      <section className="ce-tiles">
        {audits.map((a) => {
          const dim = kind !== 'All' && a.kind !== kind;
          const size = 150 + Math.log10(a.rows) * 32;
          const body = (
            <>
              <span className="ce-small">{a.kind}</span>
              <span className="ce-tile-score">{a.score === null ? 'no score' : a.score}</span>
              <span className="ce-tile-name">{a.name}</span>
              <span className="ce-small">
                {fmt(a.rows)} {a.kind === 'Connected evidence' ? 'records' : 'rows'}, {a.findings} findings
              </span>
            </>
          );
          const cls = `ce-tile${a.kind === 'Controlled mutation' ? ' is-dashed' : ''}${dim ? ' is-dim' : ''}${a.band === 'Elevated' || a.band === 'High' ? ' is-raised' : ''}`;
          const style = shapeFor(a) === 'circle' ? { width: size, height: size } : { minHeight: size * 0.62 };
          return a.id === 'adult' ? (
            <Go key={a.id} to={href(C, 'results')} className={`ce-cell is-${shapeFor(a)} ${cls} is-link`}>
              <span style={style} className="ce-tile-inner">
                {body}
              </span>
            </Go>
          ) : (
            <Cell key={a.id} shape={shapeFor(a)} className={cls}>
              <span style={style} className="ce-tile-inner">
                {body}
              </span>
            </Cell>
          );
        })}
        <Cell shape="bay" className="ce-tile ce-tile-new">
          <span className="ce-tile-inner">
            <span className="ce-tile-name">New audit</span>
            <span className="ce-small">Drop a table, corpus or image folder</span>
            <code>datatrust audit data.csv</code>
          </span>
        </Cell>
      </section>
    </main>
  );
}

/* ------------------------------------------------------------------ Results */

function FindingVisual({ code }: { code: string }) {
  if (code === 'target_imbalance') return <ClassSplit tall={150} />;
  if (code === 'numeric_outlier_concentration') return <HoursBars />;
  if (code === 'conflicting_target_labels')
    return (
      <div className="ce-pair">
        {adult.conflictPair.map((r) => (
          <div key={r.row} className="ce-cell is-stadium ce-pair-row">
            <span className="ce-pair-id">
              <span className="ce-small">CSV line {fmt(r.row)}</span>
              <span>
                age {r.age}, {r.education}, {r.hours} h
              </span>
            </span>
            <b className={r.label.startsWith('>') ? 'is-hot' : ''}>{r.label}</b>
          </div>
        ))}
      </div>
    );
  return (
    <div className="ce-pair">
      <div className="ce-cell is-stadium ce-pair-row">
        <span className="ce-pair-id">
          <span className="ce-small">column</span>
          <span>marital_status</span>
        </span>
        <b>name only</b>
      </div>
    </div>
  );
}

function Results() {
  const [open, setOpen] = useState(0);
  return (
    <main className="ce-main">
      <section className="ce-grid ce-res-top">
        <div className="ce-title ce-title--left">
          <h1>
            <span className="ce-pill">ADULT</span>
            <span className="ce-pill is-serif">is</span>
            <span className="ce-pill">ELEVATED</span>
          </h1>
          <p className="ce-dek">
            Binary classification of <code>annual_income_over_50k</code>. {fmt(adult.rows)} rows, {adult.columns}{' '}
            columns.
          </p>
        </div>
        <Cell shape="circle" className="ce-res-score" label={`Score ${adult.score}`}>
          <span className="ce-big">{adult.score}</span>
          <span className="ce-small">capped from {evidenceScore}</span>
        </Cell>
      </section>

      <section className="ce-subs">
        {adult.subScores.map((s) => (
          <Cell key={s.key} shape="circle" className={`ce-sub${s.value < 50 ? ' is-alert' : ''}`}>
            <Dither level={0.42} color={LINE} className="ce-dither" fillFrom="bottom" fill={s.value / 100} />
            <span className="ce-sub-v">{s.value.toFixed(1)}</span>
            <span className="ce-small">{s.label}</span>
          </Cell>
        ))}
        <Cell className="ce-guard">
          <span className="ce-small">Guardrail</span>
          <p>{adult.guardrail.text} The final score is capped at {adult.guardrail.cap}, so the average cannot hide it.</p>
        </Cell>
      </section>

      <section className="ce-findings">
        {adult.findings.map((f, i) => (
          <article key={f.code} className={`ce-cell is-slab ce-finding${open === i ? ' is-open' : ''}`}>
            <button className="ce-finding-head" onClick={() => setOpen(i)} aria-expanded={open === i}>
              <span className={`ce-sev is-${f.severity.toLowerCase()}`}>{f.severity}</span>
              <h2>{f.title}</h2>
            </button>
            {open === i ? (
              <div className="ce-finding-body">
                <div className="ce-finding-text">
                  <p className="ce-lede">{f.finding}</p>
                  <p>
                    <span className="ce-small">Evidence</span> {f.evidence}
                  </p>
                  <p>
                    <span className="ce-small">Why it matters</span> {f.impact}
                  </p>
                  <p>
                    <span className="ce-small">Check next</span> {f.next}
                  </p>
                  <p className="ce-effect">{f.scoreEffect}</p>
                </div>
                <div className="ce-cell is-bay ce-finding-vis">
                  <FindingVisual code={f.code} />
                </div>
              </div>
            ) : (
              <p className="ce-finding-peek">{f.evidence}</p>
            )}
          </article>
        ))}
      </section>

      <section className="ce-exports">
        <Cell className="ce-g-label">
          <span className="ce-small">Missing values</span>
        </Cell>
        {adult.missingness.map((m) => (
          <Cell key={m.field} shape="stadium" className="ce-miss">
            <code>{m.field}</code>
            <b>{fmt(m.count)}</b>
          </Cell>
        ))}
        <button className="ce-btn">Export HTML</button>
        <button className="ce-btn is-ghost">PDF</button>
        <button className="ce-btn is-ghost">JSON</button>
      </section>
    </main>
  );
}

export default function Cells({ screen }: { screen: Screen }) {
  return (
    <div className="c-cells">
      <Header screen={screen} />
      {screen === 'landing' && <Landing />}
      {screen === 'workspace' && <Workspace />}
      {screen === 'results' && <Results />}
    </div>
  );
}
