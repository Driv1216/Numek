import { useEffect, useRef, useState } from 'react';
import { Go, href, type Screen } from '../../shared/router';
import { useReducedMotion } from '../../shared/hooks';
import { adult, audits, capabilities, evidenceScore, fmt, majorityShare, pct, principles, type Audit } from '../../shared/data';
import { Frame, StillConflict, StillHours, StillMissing, StillPopulation, stillFor, StillColumn } from './Stills';
import './screening.css';
import '@fontsource-variable/bodoni-moda/opsz';
import '@fontsource-variable/bodoni-moda/opsz-italic';
import '@fontsource/antonio/300';
import '@fontsource/antonio/500';
import '@fontsource/antonio/700';

const C = 'screening';

/* ----------------------------------------------------------------- ticket */

function Ticket({ screen }: { screen: Screen }) {
  const [open, setOpen] = useState(false);
  const title = screen === 'workspace' ? 'Workspace' : screen === 'results' ? 'Adult' : 'DataTrust';
  const sub = screen === 'workspace' ? `${audits.length} audits` : screen === 'results' ? 'Classification' : 'Introduction';
  return (
    <div className={`sc-ticket${open ? ' is-open' : ''}`}>
      <button className="sc-ticket-main" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <span className="sc-ticket-title">{title}</span>
        <span className="sc-ticket-meta">
          <span>{sub}</span>
          <span>Local</span>
          <span>{screen === 'workspace' ? 'Nothing uploaded' : `${adult.findings.length} findings`}</span>
        </span>
        <span className="sc-ticket-caret" aria-hidden="true" />
      </button>
      <span className="sc-ticket-stub" aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
      {open && (
        <nav className="sc-ticket-menu" aria-label="Concept screens">
          <Go to={href(C)}>Introduction</Go>
          <Go to={href(C, 'workspace')}>Workspace</Go>
          <Go to={href(C, 'results')}>The Adult audit</Go>
          <Go to="#/">All concepts</Go>
        </nav>
      )}
    </div>
  );
}

function Top({ screen }: { screen: Screen }) {
  return (
    <header className="sc-top">
      <Go to={href(C)} className="sc-logo" label="DataTrust home">
        <span>NUMEK</span>
        <small>DataTrust</small>
      </Go>
      <Ticket screen={screen} />
    </header>
  );
}

function Credits({ rows }: { rows: [string, string][] }) {
  return (
    <dl className="sc-credits">
      {rows.map(([k, v]) => (
        <div key={k}>
          <dt>{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  );
}

/* ---------------------------------------------------------------- landing */

function useParallax() {
  const ref = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();
  useEffect(() => {
    if (reduced) return;
    const el = ref.current!;
    let raf = 0;
    let mx = 0;
    let my = 0;
    const onMove = (e: PointerEvent) => {
      mx = e.clientX / window.innerWidth - 0.5;
      my = e.clientY / window.innerHeight - 0.5;
    };
    const tick = () => {
      const sy = window.scrollY;
      el.querySelectorAll<HTMLElement>('[data-depth]').forEach((n) => {
        const d = Number(n.dataset.depth);
        n.style.transform = `translate3d(${mx * d * 40}px, ${my * d * 30 - sy * d * 0.35}px, 0)`;
      });
      raf = requestAnimationFrame(tick);
    };
    window.addEventListener('pointermove', onMove);
    tick();
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('pointermove', onMove);
    };
  }, [reduced]);
  return ref;
}

function Landing() {
  const hero = useParallax();
  return (
    <main>
      <section className="sc-hero" ref={hero}>
        <Frame className="sc-float sc-float--a" caption="Still 01. The population, one dot per 20 rows" style={{}}>
          <StillPopulation />
        </Frame>
        <div className="sc-float-wrap" data-depth="0.6">
          <Frame className="sc-float sc-float--b" caption="Still 02. hours_per_week">
            <StillHours />
          </Frame>
        </div>
        <div className="sc-float-wrap" data-depth="1.2">
          <Frame className="sc-float sc-float--c" caption="Still 03. CSV lines 850 and 22,763">
            <StillConflict />
          </Frame>
        </div>
        <div className="sc-float-wrap" data-depth="0.35">
          <Frame className="sc-float sc-float--d" caption="Still 04. Missing values">
            <StillMissing />
          </Frame>
        </div>
        <div className="sc-hero-title">
          <h1>
            Evidence
            <sup>({String(adult.findings.length).padStart(2, '0')})</sup>
          </h1>
          <p>
            before you train. A reliability report on the data itself, made on your own machine, with every finding
            shown in its rows.
          </p>
        </div>
        <div className="sc-scroll" aria-hidden="true">
          Scroll
        </div>
      </section>

      <section className="sc-billing">
        <div className="sc-billing-copy">
          <p className="sc-label">Now showing</p>
          <h2>Adult, a census table of {fmt(adult.rows)} people.</h2>
          <p>
            Three in four earn ≤50K. A model that always answers ≤50K is right {pct(majorityShare)} of the time, and
            that is the first thing the report says.
          </p>
          <Go to={href(C, 'results')} className="sc-btn">
            Watch the audit
          </Go>
        </div>
        <Credits
          rows={[
            ['Task', 'Binary classification'],
            ['Target', 'annual_income_over_50k'],
            ['Score', `${adult.score}, ${adult.band.toLowerCase()}`],
            ['Evidence', String(evidenceScore)],
            ['Read in', `${adult.runtime.toFixed(2)} seconds`],
          ]}
        />
      </section>

      <section className="sc-reel" aria-label="Findings">
        <p className="sc-label">Four scenes, in priority order</p>
        <div className="sc-reel-track">
          {adult.findings.map((f, i) => (
            <Go key={f.code} to={href(C, 'results')} className="sc-reel-item">
              <Frame caption={`Scene ${i + 1}. ${f.severity}`}>{stillFor(f.code)}</Frame>
              <h3>{f.title}</h3>
            </Go>
          ))}
        </div>
      </section>

      <section className="sc-method">
        <div>
          <p className="sc-label">How it is made</p>
          <h2>Four rules the report keeps.</h2>
        </div>
        <Credits rows={principles.map((p) => [p.title, p.body])} />
      </section>

      <section className="sc-program">
        <p className="sc-label">Also reads</p>
        <ul>
          {capabilities.map((c) => (
            <li key={c.name}>
              <span className="sc-program-name">{c.name}</span>
              <span className="sc-program-detail">{c.detail}</span>
            </li>
          ))}
        </ul>
      </section>

      <footer className="sc-foot">
        <p className="sc-foot-word">NUMEK</p>
        <Go to={href(C, 'workspace')} className="sc-btn">
          Open the workspace
        </Go>
      </footer>
    </main>
  );
}

/* -------------------------------------------------------------- workspace */

function stillForAudit(a: Audit) {
  if (a.id === 'adult') return <StillPopulation />;
  if (a.id === 'adult-leak') return <StillColumn />;
  return null;
}

function Workspace() {
  const [hover, setHover] = useState<string | null>(null);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const [kind, setKind] = useState<'All' | Audit['kind']>('All');
  const kinds: ('All' | Audit['kind'])[] = ['All', 'Classification', 'Regression', 'Connected evidence', 'Controlled mutation'];
  const list = audits.filter((a) => kind === 'All' || a.kind === kind);
  const hovered = audits.find((a) => a.id === hover);
  return (
    <main className="sc-ws" onPointerMove={(e) => setPos({ x: e.clientX, y: e.clientY })}>
      <section className="sc-ws-head">
        <h1>
          Programme
          <sup>({String(audits.length).padStart(2, '0')})</sup>
        </h1>
        <p>Every audit in ~/numek/audits, read on this machine. Hover a title for its still.</p>
      </section>
      <ol className="sc-ws-list">
        {list.map((a) => {
          const inner = (
            <>
              <span className="sc-ws-kind">{a.kind}</span>
              <span className="sc-ws-title">{a.name}</span>
              <span className="sc-ws-credits">
                <span>{fmt(a.rows)} {a.kind === 'Connected evidence' ? 'records' : 'rows'}</span>
                <span>{a.findings} findings</span>
                <span>{a.score === null ? a.band : `${a.score}, ${a.band.toLowerCase()}`}</span>
              </span>
            </>
          );
          return (
            <li key={a.id} onPointerEnter={() => setHover(a.id)} onPointerLeave={() => setHover(null)}>
              {a.id === 'adult' ? (
                <Go to={href(C, 'results')} className="sc-ws-row is-link">
                  {inner}
                </Go>
              ) : (
                <div className="sc-ws-row">{inner}</div>
              )}
            </li>
          );
        })}
      </ol>
      {hovered && (
        <div className="sc-cursor-still" style={{ transform: `translate(${pos.x + 24}px, ${pos.y - 120}px)` }} aria-hidden="true">
          <Frame caption={hovered.note}>
            {stillForAudit(hovered) ?? (
              <div className="sc-placeholder">
                <span>{hovered.score === null ? 'No score' : hovered.score}</span>
              </div>
            )}
          </Frame>
        </div>
      )}
      <section className="sc-ws-new">
        <div className="sc-ticket sc-ticket--static">
          <div className="sc-ticket-main">
            <span className="sc-ticket-title">New audit</span>
            <span className="sc-ticket-meta">
              <span>Drop a table, corpus or image folder</span>
            </span>
            <code>datatrust audit data.csv</code>
          </div>
          <span className="sc-ticket-stub" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
        </div>
      </section>
      <nav className="sc-switch" aria-label="Filter by task">
        <span className="sc-switch-thumb" aria-hidden="true">
          <StillHours />
        </span>
        <span className="sc-switch-label">Showing</span>
        <select value={kind} onChange={(e) => setKind(e.target.value as typeof kind)} aria-label="Task filter">
          {kinds.map((k) => (
            <option key={k}>{k}</option>
          ))}
        </select>
      </nav>
    </main>
  );
}

/* ---------------------------------------------------------------- results */

function Results() {
  return (
    <main className="sc-res">
      <section className="sc-res-hero">
        <Frame className="sc-res-still">
          <StillPopulation />
        </Frame>
        <div className="sc-res-title">
          <p className="sc-label">Binary classification</p>
          <h1>Adult</h1>
        </div>
        <Credits
          rows={[
            ['Score', String(adult.score)],
            ['Band', adult.band],
            ['Evidence', String(evidenceScore)],
            ['Capped at', String(adult.guardrail.cap)],
            ['Rows', fmt(adult.rows)],
            ['Columns', String(adult.columns)],
          ]}
        />
      </section>

      <section className="sc-res-guard">
        <p>
          {adult.guardrail.text} The average of the evidence is {evidenceScore}, but the guardrail holds the final
          score at {adult.guardrail.cap} so the weakness stays in view.
        </p>
        <div className="sc-subs">
          {adult.subScores.map((s) => (
            <div key={s.key} className={`sc-sub${s.value < 50 ? ' is-alert' : ''}`}>
              <span className="sc-sub-v">{s.value.toFixed(2)}</span>
              <span className="sc-sub-bar">
                <i style={{ width: `${s.value}%` }} />
              </span>
              <span className="sc-sub-k">{s.label}</span>
            </div>
          ))}
        </div>
      </section>

      {adult.findings.map((f, i) => (
        <section key={f.code} className={`sc-scene${i % 2 ? ' is-flip' : ''}`}>
          <Frame className="sc-scene-still" caption={f.evidence}>
            {f.code === 'target_imbalance' ? <StillPopulation /> : f.code === 'numeric_outlier_concentration' ? <StillHours /> : f.code === 'conflicting_target_labels' ? <StillConflict /> : <StillColumn />}
          </Frame>
          <div className="sc-scene-text">
            <p className="sc-label">
              Scene {i + 1}, {f.severity.toLowerCase()}
            </p>
            <h2>{f.title}</h2>
            <p className="sc-scene-lede">{f.finding}</p>
            <Credits
              rows={[
                ['Why it matters', f.impact],
                ['Check next', f.next],
                ['Score effect', f.scoreEffect],
              ]}
            />
          </div>
        </section>
      ))}

      <section className="sc-res-end">
        <p className="sc-label">Take it with you</p>
        <div className="sc-res-exports">
          <button className="sc-btn">HTML report</button>
          <button className="sc-btn is-ghost">PDF</button>
          <button className="sc-btn is-ghost">JSON evidence</button>
        </div>
      </section>
    </main>
  );
}

export default function Screening({ screen }: { screen: Screen }) {
  return (
    <div className="c-screening">
      <Top screen={screen} />
      {screen === 'landing' && <Landing />}
      {screen === 'workspace' && <Workspace />}
      {screen === 'results' && <Results />}
      <span className="sc-grain sc-grain--page" aria-hidden="true" />
    </div>
  );
}
