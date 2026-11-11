import '@fontsource-variable/anybody';
import '@fontsource-variable/jetbrains-mono';
import './slab.css';
import { useEffect, useRef, useState } from 'react';
import { adult, company, local, runFindings, runs, subScoresByRun } from '../../fixture';
import { reducedMotion } from '../../shell/motion';
import { href } from '../../shell/router';
import { Credits, Shutter, SlabMark, useInViewOnce } from './slabs';

export function Header({ here, run = 'Adult' }: { here: 'landing' | 'app' | 'results'; run?: string }) {
  return (
    <header className="sl-head">
      <a href={href('slab', 'landing')} className="sl-head__wm">NUMEK</a>
      <span>DATATRUST</span>
      <span>{run.toUpperCase()}</span>
      <span>127.0.0.1</span>
      <nav aria-label="Primary">
        <a href={href('slab', 'landing')} aria-current={here === 'landing' ? 'page' : undefined}>Index</a>
        <a href={href('slab', 'app')} aria-current={here === 'app' ? 'page' : undefined}>Runs</a>
        <a href={href('slab', 'results')} aria-current={here === 'results' ? 'page' : undefined}>Adult</a>
      </nav>
    </header>
  );
}

export const adultCredits: [string, string][] = [['Source', 'UCI Adult'], ['Rows', adult.rows.toLocaleString()], ['Columns', String(adult.columns)], ['Target', adult.target], ['Task', adult.task], ['Generated', adult.generatedAt], ['Runtime', `${adult.runtimeSeconds.toFixed(2)} s · local`]];
const subs = adult.subScores.map((s) => ({ label: s.label, value: s.value }));

function FindingShutter({ i }: { i: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const open = useInViewOnce(ref);
  const f = adult.findings[i];
  return (
    <div ref={ref}>
      <Shutter open={open} label={f.title}>
        <span className="sl-k">{String(i + 1).padStart(2, '0')} · {f.severity.toUpperCase()} · {f.scoreEffect.startsWith('Evidence only') ? 'EVIDENCE ONLY' : 'CHANGES THE SCORE'}</span>
        <h3>{f.title}</h3>
        <p>{f.finding} {f.evidence}</p>
        <p className="sl-dim">{f.review}</p>
      </Shutter>
    </div>
  );
}

export default function Landing() {
  const sec = useRef<HTMLElement>(null);
  const [p, setP] = useState(reducedMotion() ? 1 : 0);
  const [run, setRun] = useState('adult');
  const [menu, setMenu] = useState(false);
  useEffect(() => {
    if (reducedMotion()) return;
    let raf = 0;
    const on = () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(() => {
      const el = sec.current; if (!el) return;
      const r = el.getBoundingClientRect();
      setP(Math.min(1, Math.max(0, -r.top / Math.max(1, r.height - innerHeight)) * 1.15));
    }); };
    on(); addEventListener('scroll', on, { passive: true });
    return () => { removeEventListener('scroll', on); cancelAnimationFrame(raf); };
  }, []);
  const r = runs.find((x) => x.id === run)!;
  const rs = subScoresByRun[run];
  return (
    <div className="sl sl--landing">
      <Header here="landing" />
      <section ref={sec} className="sl-hero" style={{ height: reducedMotion() ? 'auto' : '240vh' }}>
        <div className="sl-hero__stage">
          <SlabMark values={subs} p={p} />
          <div className="sl-hero__cap">
            {p < 0.5 ? <p><b>DataTrust</b> by {company.name}. Five measures of a dataset, made on your machine. Scroll, and the name becomes the measurement.</p>
              : <p><b>Adult.</b> Four slabs stand near the top. One — target balance, 47.86 — falls below the critical line at 50, so the final score is held at the cap: <b className="sl-red">69.0</b>.</p>}
          </div>
        </div>
      </section>

      <section className="sl-sec">
        <div className="sl-sec__h"><span className="sl-k">THE CAP</span><h2>Evidence 89.15.<br />Final 69.0.</h2></div>
        <div className="sl-cap-row">
          <SlabMark values={subs} p={1} />
          <Credits items={adultCredits} />
        </div>
      </section>

      <section className="sl-sec">
        <div className="sl-sec__h"><span className="sl-k">FINDINGS · {adult.findings.length}</span><h2>Behind each slab, the evidence.</h2></div>
        <div className="sl-shutters">{adult.findings.map((_, i) => <FindingShutter key={i} i={i} />)}</div>
      </section>

      <section className="sl-sec">
        <div className="sl-sec__h">
          <span className="sl-k">NOW SHOWING</span>
          <div className="sl-now">
            <button type="button" aria-expanded={menu} onClick={() => setMenu(!menu)}><b>{r.name}</b><span>{String(runs.indexOf(r) + 1).padStart(2, '0')} / {String(runs.length).padStart(2, '0')}</span><i>▾</i></button>
            {menu && <ol>{runs.map((x, k) => <li key={x.id}><button type="button" className={x.id === run ? 'is-on' : ''} onClick={() => { setRun(x.id); setMenu(false); }}><span>{String(k + 1).padStart(2, '0')}</span>{x.name}</button></li>)}</ol>}
          </div>
        </div>
        {rs ? <SlabMark key={run} values={rs} p={1} /> : (
          <div className="sl-none"><p><b>No slabs.</b> {r.task} has no universal score, so there is nothing to stand against the cap. DataTrust reports the evidence:</p>
            <ul>{(runFindings[run] ?? [{ title: r.lead, severity: '—', evidence: '', effect: 'none-defined' }]).map((f) => <li key={f.title}><b>{f.title}</b>{f.evidence && <span> · {f.evidence}</span>}</li>)}</ul>
          </div>
        )}
      </section>

      <footer className="sl-foot">
        <SlabMark values={subs} p={0} labels={false} showLines={false} />
        <pre>$ {local.commands[0]}{'\n'}{local.cliOutput.join('\n')}</pre>
        <p className="sl-dim">{company.line}. DataTrust is the product. {company.direction} Findings support human review; they are not certification.</p>
      </footer>
    </div>
  );
}
