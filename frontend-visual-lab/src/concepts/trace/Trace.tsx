import { useMemo, useState, type ReactNode } from 'react';
import * as THREE from 'three';
import { Go, href, type Screen } from '../../shared/router';
import { useClock } from '../../shared/hooks';
import { adult, audits, capabilities, evidenceScore, fmt, pct, majorityShare, principles } from '../../shared/data';
import { Cloud, adultRows, toSpace, type Row, type Track } from './Cloud';
import './trace.css';
import '@fontsource/hanken-grotesk/300';
import '@fontsource/hanken-grotesk/400';
import '@fontsource/hanken-grotesk/500';
import '@fontsource/martian-mono/400';

const C = 'trace';

/* --------------------------------------------------------------- tracking */

function useTracks() {
  return useMemo(() => {
    const rows = adultRows();
    const longHours = rows.filter((r) => r.hours >= 80);
    const short = rows.filter((r) => r.hours <= 10);
    const centroid = (rs: Row[]) => {
      const n = rs.length;
      return toSpace(
        rs.reduce((s, r) => s + r.age, 0) / n,
        rs.reduce((s, r) => s + r.hours, 0) / n,
        rs.reduce((s, r) => s + r.edu, 0) / n,
      );
    };
    const conflict: Track = {
      id: 'conflict',
      label: 'Lines 850 and 22,763',
      detail: 'age 39, 40 h, 13 yrs. Labels ≤50K and >50K',
      at: toSpace(39, 40, 13),
    };
    const long: Track = {
      id: 'long',
      label: `hours ≥ 80, ${fmt(longHours.length)} rows`,
      detail: 'Descriptive region, not the engine’s outlier set',
      at: new THREE.Box3(toSpace(17, 80, 1), toSpace(90, 99, 16)),
      tone: 'ink',
    };
    const shortT: Track = {
      id: 'short',
      label: `hours ≤ 10, ${fmt(short.length)} rows`,
      detail: 'Descriptive region',
      at: new THREE.Box3(toSpace(17, 1, 1), toSpace(90, 10, 16)),
      tone: 'ink',
    };
    const low: Track = {
      id: 'low',
      label: `≤50K, ${fmt(adult.classes[0].count)}`,
      detail: `${pct(majorityShare)} of rows. Centroid`,
      at: centroid(rows.filter((r) => r.label === 0)),
      tone: 'ink',
    };
    const high: Track = {
      id: 'high',
      label: `>50K, ${fmt(adult.classes[1].count)}`,
      detail: `${pct(1 - majorityShare)} of rows. Centroid`,
      at: centroid(rows.filter((r) => r.label === 1)),
    };
    return { conflict, long, short: shortT, low, high };
  }, []);
}

function Corners({ tag, children, tone = 'blue' }: { tag?: ReactNode; children: ReactNode; tone?: 'blue' | 'ink' }) {
  return (
    <span className={`tr-corners is-${tone}`}>
      {tag && <span className="tr-corners-tag">{tag}</span>}
      {children}
    </span>
  );
}

/* ------------------------------------------------------------------ frame */

function Frame({ screen, children }: { screen: Screen; children: ReactNode }) {
  const clock = useClock();
  return (
    <div className="c-trace">
      <header className="tr-top">
        <Go to={href(C)} className="tr-mark" label="DataTrust home">
          <svg viewBox="0 0 20 20" aria-hidden="true">
            <circle cx="10" cy="10" r="8.5" fill="none" stroke="currentColor" strokeWidth="1.4" />
            <rect x="6" y="5.5" width="1.6" height="9" fill="currentColor" />
            <rect x="9.2" y="7.5" width="1.6" height="7" fill="currentColor" />
            <circle cx="13.2" cy="13.8" r="1.1" fill="currentColor" />
          </svg>
        </Go>
        <nav className="tr-nav" aria-label="Concept screens">
          <Go to={href(C)} className={screen === 'landing' ? 'is-on' : ''}>
            Index
          </Go>
          <Go to={href(C, 'workspace')} className={screen === 'workspace' ? 'is-on' : ''}>
            Workspace
          </Go>
          <Go to={href(C, 'results')} className={screen === 'results' ? 'is-on' : ''}>
            Adult
          </Go>
        </nav>
        <span className="tr-clock">Local, {clock}</span>
        <Go to="#/" className="tr-out">
          All concepts
        </Go>
      </header>
      <div className="tr-sheet">{children}</div>
      <footer className="tr-bottom">
        <span>Numek DataTrust</span>
        <span>Runs on this machine. Nothing uploaded.</span>
        <span>HTML / PDF / JSON</span>
      </footer>
    </div>
  );
}

/* ----------------------------------------------------------------- glyphs */

function Glyph({ kind }: { kind: number }) {
  const s = { fill: 'currentColor' };
  return (
    <svg viewBox="0 0 64 64" className="tr-glyph" aria-hidden="true">
      {kind === 0 && (
        <>
          <circle cx="32" cy="32" r="26" fill="none" stroke="currentColor" strokeWidth="2.4" />
          <circle cx="24" cy="36" r="3" {...s} />
          <circle cx="33" cy="28" r="3" {...s} />
          <circle cx="41" cy="37" r="3" {...s} />
        </>
      )}
      {kind === 1 && (
        <>
          {[10, 20, 30, 40, 50].map((x, i) => (
            <rect key={x} x={x - 1.5} y={i === 2 ? 14 : 24} width="3" height={i === 2 ? 36 : 26} {...s} />
          ))}
          <path d="M22 10h-6v6M42 10h6v6M22 54h-6v-6M42 54h6v-6" fill="none" stroke="#2433ff" strokeWidth="2.4" />
        </>
      )}
      {kind === 2 && (
        <>
          {[44, 40, 46, 22, 42].map((h, i) => (
            <rect key={i} x={9 + i * 11} y={56 - h} width="3" height={h} {...s} />
          ))}
          <rect x="4" y="28" width="56" height="2.4" fill="#2433ff" />
        </>
      )}
      {kind === 3 && (
        <>
          <path d="M32 6a26 26 0 1 1-18.4 7.6" fill="none" stroke="currentColor" strokeWidth="2.4" />
          <rect x="30.8" y="20" width="2.4" height="18" {...s} />
          <circle cx="32" cy="45" r="2.4" {...s} />
        </>
      )}
    </svg>
  );
}

/* ---------------------------------------------------------------- landing */

function Landing() {
  const t = useTracks();
  return (
    <Frame screen="landing">
      <section className="tr-hero">
        <p className="tr-hero-note">
          <span className="tr-mono">[Adult, {fmt(adult.rows)} rows]</span>
          Every point is one row, placed by age, hours per week and years of education. Blue rows earn &gt;50K.
          Drag to turn it.
        </p>
        <Cloud tracks={[t.conflict, t.long]} height="min(78vh, 760px)" />
        <div className="tr-hero-foot">
          <h1>
            See which rows
            <br />
            a finding is about.
          </h1>
          <div className="tr-hero-cta">
            <p>DataTrust audits training data on your machine and points at the evidence behind every risk.</p>
            <Go to={href(C, 'workspace')} className="tr-pill">
              Open the workspace
            </Go>
          </div>
        </div>
      </section>

      <section className="tr-rules">
        {principles.map((p, i) => (
          <article key={p.title}>
            <Glyph kind={i} />
            <h2>{p.title}</h2>
            <p>{p.body}</p>
          </article>
        ))}
      </section>

      <section className="tr-caps">
        <h2>It reads tables, time, text, images and the documents behind records.</h2>
        <ul>
          {capabilities.map((c) => (
            <li key={c.name}>
              <span className="tr-mono">[{c.name}]</span>
              <span>{c.detail}</span>
            </li>
          ))}
          <li className="is-muted">
            <span className="tr-mono">[Audio]</span>
            <span>Deferred</span>
          </li>
        </ul>
      </section>
    </Frame>
  );
}

/* -------------------------------------------------------------- workspace */

function Workspace() {
  const [sel, setSel] = useState(0);
  const a = audits[sel];
  return (
    <Frame screen="workspace">
      <section className="tr-ws">
        <div className="tr-ws-list">
          <div className="tr-ws-head">
            <h1>Workspace</h1>
            <span className="tr-mono">[~/numek/audits, {audits.length} audits]</span>
          </div>
          <ol>
            {audits.map((x, i) => (
              <li key={x.id}>
                <button className={`tr-ws-row${sel === i ? ' is-on' : ''}`} onClick={() => setSel(i)} aria-pressed={sel === i}>
                  <span className="tr-mono tr-ws-kind">{x.kind}</span>
                  <span className="tr-ws-name">{x.name}</span>
                  <span className="tr-ws-score">{x.score === null ? '—' : x.score}</span>
                  <span className="tr-mono tr-ws-shape">
                    {fmt(x.rows)}
                    {x.columns ? ` × ${x.columns}` : ' records'}
                  </span>
                </button>
              </li>
            ))}
          </ol>
          <div className="tr-drop">
            <span className="tr-mono">[New audit]</span>
            <p>Drop a table, corpus or image folder. It is read here and stays here.</p>
            <code className="tr-mono">datatrust audit data.csv</code>
          </div>
        </div>

        <div className="tr-ws-preview" aria-live="polite">
          <p className="tr-mono tr-ws-crumb">
            [{a.kind}] {a.name}
          </p>
          <div className="tr-ws-figure">
            <Corners tag={a.score === null ? 'no score by design' : `score, ${a.band.toLowerCase()}`}>
              <span className="tr-ws-big">{a.score === null ? '∅' : a.score}</span>
            </Corners>
          </div>
          <div className="tr-ws-facts">
            <Corners tone="ink" tag="rows">
              <b>{fmt(a.rows)}</b>
            </Corners>
            <Corners tone="ink" tag="findings">
              <b>{a.findings}</b>
            </Corners>
            <Corners tone="ink" tag="read in">
              <b>{a.runtime === null ? 'n/a' : `${a.runtime.toFixed(2)} s`}</b>
            </Corners>
          </div>
          <p className="tr-ws-note">{a.note}.</p>
          {a.sub && (
            <div className="tr-scores tr-scores--preview">
              {a.sub.map((v, i) => (
                <div key={i} className={`tr-score${v < 50 ? ' is-alert' : ''}`}>
                  <span className="tr-mono">{adult.subScores[i].label}</span>
                  <span className="tr-score-line">
                    <i style={{ left: `${v}%` }} />
                  </span>
                  <span className="tr-score-v">{v.toFixed(2)}</span>
                </div>
              ))}
            </div>
          )}
          {a.id === 'adult' ? (
            <Go to={href(C, 'results')} className="tr-pill">
              Open the Adult audit
            </Go>
          ) : (
            <span className="tr-pill is-off">Only Adult is prototyped</span>
          )}
        </div>
      </section>
    </Frame>
  );
}

/* ---------------------------------------------------------------- results */

function Results() {
  const t = useTracks();
  const [sel, setSel] = useState(0);
  const f = adult.findings[sel];
  const view = useMemo(() => {
    switch (f.code) {
      case 'conflicting_target_labels':
        return { tracks: [t.conflict], focus: undefined };
      case 'target_imbalance':
        return { tracks: [t.low, t.high], focus: undefined };
      case 'numeric_outlier_concentration':
        return { tracks: [t.long, t.short], focus: (r: Row) => r.hours >= 80 || r.hours <= 10 };
      default:
        return { tracks: [], focus: undefined };
    }
  }, [f.code, t]);

  return (
    <Frame screen="results">
      <section className="tr-res-head">
        <div>
          <span className="tr-mono">[Binary classification, target annual_income_over_50k]</span>
          <h1>Adult</h1>
        </div>
        <div className="tr-res-score">
          <Corners tag={`capped, evidence ${evidenceScore}`}>
            <span className="tr-res-big">{adult.score}</span>
          </Corners>
          <span className="tr-res-band">{adult.band}</span>
        </div>
      </section>

      <section className="tr-res">
        <div className="tr-res-stage">
          <Cloud tracks={view.tracks} focus={view.focus} height={600} />
          {f.code === 'leakage_review_prompts' && (
            <div className="tr-res-overlay">
              <Corners tag="name-based prompt only">
                <span className="tr-res-col">marital_status</span>
              </Corners>
              <p>This finding is about a column name, not a set of rows. No points are highlighted.</p>
            </div>
          )}
          <div className="tr-scores">
            {adult.subScores.map((s) => (
              <div key={s.key} className={`tr-score${s.value < 50 ? ' is-alert' : ''}`}>
                <span className="tr-mono">{s.label}</span>
                <span className="tr-score-line">
                  <i style={{ left: `${s.value}%` }} />
                </span>
                <span className="tr-score-v">{s.value.toFixed(2)}</span>
              </div>
            ))}
            <p className="tr-guard">{adult.guardrail.text} The final score is capped at {adult.guardrail.cap}.</p>
          </div>
        </div>

        <aside className="tr-res-side">
          <ol className="tr-findings" role="tablist" aria-label="Findings">
            {adult.findings.map((x, i) => (
              <li key={x.code}>
                <button role="tab" aria-selected={sel === i} className={sel === i ? 'is-on' : ''} onClick={() => setSel(i)}>
                  <span className="tr-mono">{x.severity}</span>
                  <span>{x.title}</span>
                </button>
              </li>
            ))}
          </ol>
          <div className="tr-detail" role="tabpanel">
            <p className="tr-detail-lede">{f.finding}</p>
            <dl>
              <dt className="tr-mono">Evidence</dt>
              <dd>{f.evidence}</dd>
              <dt className="tr-mono">Why it matters</dt>
              <dd>{f.impact}</dd>
              <dt className="tr-mono">Check next</dt>
              <dd>{f.next}</dd>
              <dt className="tr-mono">Score effect</dt>
              <dd>{f.scoreEffect}</dd>
            </dl>
          </div>
          <div className="tr-exports">
            <button className="tr-pill">Export HTML</button>
            <button className="tr-pill is-ghost">PDF</button>
            <button className="tr-pill is-ghost">JSON</button>
          </div>
        </aside>
      </section>
    </Frame>
  );
}

export default function Trace({ screen }: { screen: Screen }) {
  if (screen === 'workspace') return <Workspace />;
  if (screen === 'results') return <Results />;
  return <Landing />;
}
