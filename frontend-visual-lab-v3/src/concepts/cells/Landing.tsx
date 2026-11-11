import '@fontsource-variable/space-grotesk';
import '@fontsource/space-mono/400.css';
import '@fontsource/space-mono/700.css';
import './cells.css';
import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react';
import { adult, bike, company, finance, local, representations } from '../../fixture';
import { reducedMotion } from '../../shell/motion';
import { href } from '../../shell/router';

/** The machine's own clock: proof of presence, not decoration. */
export function useClock() {
  const [t, setT] = useState(() => new Date());
  useEffect(() => { const i = setInterval(() => setT(new Date()), 1000); return () => clearInterval(i); }, []);
  return t.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function Header({ here }: { here: 'landing' | 'app' | 'results' }) {
  const clock = useClock();
  return (
    <header className="ce-head">
      <a className="ce-head__wm" href={href('cells', 'landing')}>NUMEK</a>
      <span className="ce-head__c">THIS MACHINE {clock}</span>
      <span className="ce-head__c">127.0.0.1</span>
      <nav aria-label="Primary">
        <a href={href('cells', 'landing')} aria-current={here === 'landing' ? 'page' : undefined}>DataTrust</a>
        <a href={href('cells', 'app')} aria-current={here === 'app' ? 'page' : undefined}>Runs</a>
        <a href={href('cells', 'results')} aria-current={here === 'results' ? 'page' : undefined}>Adult</a>
      </nav>
    </header>
  );
}

/** A line glyph per representation, drawn in one stroke weight. */
export function Glyph({ id }: { id: string }) {
  const p: Record<string, ReactNode> = {
    tables: <><rect x="8" y="12" width="48" height="40" /><path d="M8 24h48M8 36h48M24 12v40M40 12v40" /></>,
    outcomes: <><path d="M8 50 L22 34 L34 42 L56 16" /><path d="M8 54h48" /></>,
    time: <><circle cx="32" cy="32" r="22" /><path d="M32 18v14l10 8" /></>,
    text: <path d="M10 18h44M10 28h44M10 38h30M10 48h20" />,
    images: <><rect x="8" y="12" width="48" height="40" /><path d="M12 46l14-14 10 10 8-8 8 12" /><circle cx="44" cy="22" r="4" /></>,
    connected: <><rect x="6" y="16" width="20" height="32" /><rect x="38" y="10" width="20" height="44" /><path d="M26 32h12" /></>,
  };
  return <svg viewBox="0 0 64 64" className="ce-glyph" aria-hidden="true">{p[id]}</svg>;
}

const STEPS = [['12-COLUMN', 'GRID'], ['1 PX', 'RULE'], ['8 PX', 'GUTTER'], ['ONE', 'ACCENT'], ['', '']] as const;

export default function Landing() {
  const sec = useRef<HTMLElement>(null);
  const [step, setStep] = useState(reducedMotion() ? 4 : 0);
  const [lit, setLit] = useState<number | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const clock = useClock();

  // The grid builds itself as you scroll through the first section, then content drops in.
  useEffect(() => {
    if (reducedMotion()) return;
    let raf = 0;
    const on = () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(() => {
      const el = sec.current; if (!el) return;
      const r = el.getBoundingClientRect();
      const p = Math.min(1, Math.max(0, -r.top / Math.max(1, r.height - innerHeight)));
      setStep(Math.min(4, Math.floor(p * 5.2)));
    }); };
    on(); addEventListener('scroll', on, { passive: true });
    return () => { removeEventListener('scroll', on); cancelAnimationFrame(raf); };
  }, []);

  const findings = [
    ...adult.findings.map((f) => ({ run: 'Adult', title: f.title, sev: f.severity, ev: f.evidence, eff: f.scoreEffect.startsWith('Evidence only') ? 'Evidence only' : 'Changes the score', detail: f.review })),
    { run: 'Bike hourly', title: 'Supported target relationship', sev: 'High', ev: bike.relationship + ' on 17,379 / 17,379 rows', eff: 'No score defined', detail: 'casual and registered are declared unavailable at prediction time.' },
    { run: 'Finance ↔ PDFs', title: 'Record and document disagree', sev: 'High', ev: `${finance.discrepancies} discrepancy · ${finance.conflicts} conflict, with page locators`, eff: 'No score defined', detail: finance.note },
  ];

  return (
    <div className="ce ce--landing">
      <Header here="landing" />
      <section ref={sec} className="ce-build" style={{ height: reducedMotion() ? 'auto' : '300vh' }} aria-label="NUMEK DataTrust">
        <div className={`ce-build__stage s-${step}`}>
          <div className="ce-cols" aria-hidden="true">{Array.from({ length: 12 }, (_, i) => <i key={i} style={{ ['--i' as string]: i } as CSSProperties} />)}</div>
          {step < 4 && <div className="ce-label" aria-hidden="true"><b>{STEPS[step][0]}</b><b>{STEPS[step][1]}</b></div>}
          <div className="ce-fill">
            <div className="ce-c ce-c--w12 ce-c--wm"><span className="ce-k">DATATRUST BY {company.name}</span><b>NUMEK</b></div>
            <div className="ce-c ce-c--w7 ce-c--lede"><p>Every fact about a dataset, in its own cell — measured on this machine.</p></div>
            <div className="ce-c ce-c--w5 ce-c--acc"><span className="ce-k">ADULT · FINAL</span><b>{adult.finalScore.toFixed(1)}</b><em>{adult.band} · held at the cap</em></div>
            <div className="ce-c ce-c--w3"><span className="ce-k">EVIDENCE</span><b>{adult.evidenceScore}</b></div>
            <div className="ce-c ce-c--w3"><span className="ce-k">TARGET BALANCE</span><b>{adult.subScores[2].value}</b><em>≤ 50 is critical</em></div>
            <div className="ce-c ce-c--w3 ce-c--dark"><span className="ce-k">ROWS × COLUMNS</span><b>48,842 × 15</b></div>
            <div className="ce-c ce-c--w3 ce-c--dither" aria-hidden="true" />
          </div>
        </div>
      </section>

      <section className="ce-sec">
        <div className="ce-sec__h"><span className="ce-k">01 — THE RUN</span><h2>Adult, cell by cell.</h2></div>
        <div className="ce-grid">
          <div className="ce-c ce-c--w4 ce-c--acc"><span className="ce-k">FINAL</span><b className="ce-xl">{adult.finalScore.toFixed(1)}</b><em>{adult.band}</em></div>
          <div className="ce-c ce-c--w4"><span className="ce-k">WHY</span><p>{adult.guardrail.explanation} Any sub-score at or below 50 caps the result at 69.</p></div>
          <div className="ce-c ce-c--w4 ce-c--dark"><span className="ce-k">RUN</span><b>{adult.generatedAt.split(' ')[1]}</b><em>{adult.generatedAt.split(' ')[0]} · {adult.runtimeSeconds.toFixed(2)} s · local</em></div>
          {adult.subScores.map((s) => <div key={s.key} className={`ce-c ce-c--w2 ${s.value <= 50 ? 'ce-c--acc2' : ''}`}><span className="ce-k">{s.label.toUpperCase()}</span><b>{s.value}</b></div>)}
          <div className="ce-c ce-c--w2 ce-c--dither" aria-hidden="true" />
          <div className="ce-c ce-c--w3"><span className="ce-k">EMPTY CELLS</span><b>{adult.missing.cells.toLocaleString()}</b><em>3 columns · {adult.missing.rowRate}% of rows</em></div>
          <div className="ce-c ce-c--w3"><span className="ce-k">REPEATED ROWS</span><b>{adult.duplicates.repeated_rows}</b><em>{adult.duplicates.groups} groups</em></div>
          <div className="ce-c ce-c--w3"><span className="ce-k">OUTSIDE FENCES</span><b>{adult.hours.outliers.toLocaleString()}</b><em>hours_per_week · 27.63%</em></div>
          <div className="ce-c ce-c--w3"><span className="ce-k">DISAGREEING ROWS</span><b>10</b><em>5 groups · evidence only</em></div>
        </div>
      </section>

      <section className="ce-sec ce-sec--dark">
        <div className="ce-sec__h"><span className="ce-k">02 — SIX KINDS OF DATA</span><h2>Each read by its own unit.</h2></div>
        <ol className="ce-practice">
          {representations.map((r, i) => (
            <li key={r.id}>
              <span className="ce-k">{String(i + 1).padStart(2, '0')}</span>
              <b>{r.name}</b>
              <Glyph id={r.id} />
              <ul>{r.checks.map((c) => <li key={c}>{c.toUpperCase()}</li>)}</ul>
              <em>per {r.unit} · {r.example}</em>
            </li>
          ))}
        </ol>
      </section>

      <section className="ce-sec">
        <div className="ce-sec__h"><span className="ce-k">03 — FINDINGS</span><h2>Six findings, three runs.</h2></div>
        <div className="ce-fgrid">
          {findings.map((f, i) => (
            <button key={f.title} type="button" className={`ce-f ${lit === i ? 'is-lit' : ''} ${open === i ? 'is-open' : ''}`} onMouseEnter={() => setLit(i)} onMouseLeave={() => setLit(null)} onFocus={() => setLit(i)} onBlur={() => setLit(null)} aria-expanded={open === i} onClick={() => setOpen(open === i ? null : i)}>
              <span className="ce-k">{String(i + 1).padStart(2, '0')} · {f.run.toUpperCase()}</span>
              <b>{f.title}</b>
              <em>{f.sev} · {f.eff}</em>
              <span className="ce-f__ev">{f.ev}</span>
              {open === i && <span className="ce-f__d">{f.detail}</span>}
            </button>
          ))}
        </div>
      </section>

      <section className="ce-sec">
        <div className="ce-grid">
          <div className="ce-c ce-c--w6 ce-c--dark"><span className="ce-k">LOCAL</span><b>{clock}</b><em>this machine · nothing leaves it</em></div>
          <div className="ce-c ce-c--w2"><span className="ce-k">NETWORK CALLS</span><b>0</b></div>
          <div className="ce-c ce-c--w2"><span className="ce-k">REPORTS</span><b>3</b><em>HTML · PDF · JSON</em></div>
          <div className="ce-c ce-c--w2 ce-c--dither" aria-hidden="true" />
          <div className="ce-c ce-c--w12 ce-c--cmd"><span className="ce-k">COMMAND</span><code>$ {local.commands[0]}</code><code className="ce-dim">{local.cliOutput.join(' · ')}</code></div>
        </div>
      </section>

      <footer className="ce-foot">
        <div className="ce-c ce-c--w6"><b>NUMEK</b><em>{company.line}</em></div>
        <div className="ce-c ce-c--w6"><p>DataTrust is the product. {company.direction} Findings support human review; they are not certification.</p></div>
      </footer>
    </div>
  );
}

