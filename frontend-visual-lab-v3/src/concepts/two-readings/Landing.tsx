import '@fontsource-variable/recursive/full.css';
import './two-readings.css';
import { useEffect, useState } from 'react';
import { adult, formats, local } from '../../fixture';
import { clamp, reducedMotion, seg, useInView, useScrollProgress } from '../../shell/motion';
import { href } from '../../shell/router';
import { Json, Wordmark, axes, findingJson, pairs } from './shared';

const terminal = [
  { p: true, t: `datatrust audit adult.csv --target annual_income_over_50k --out adult.pdf --format pdf --json-out adult.json` },
  ...local.cliOutput.map((t) => ({ p: false, t })),
  { p: true, t: 'datatrust ui' },
  { p: false, t: 'Starting DataTrust at http://127.0.0.1:8000/' },
];

export default function Landing() {
  const [heroRef, hp] = useScrollProgress<HTMLDivElement>('pinned');
  const [transRef, tp] = useScrollProgress<HTMLDivElement>('pinned');
  const open = seg(hp, 0.05, 0.75);
  return (
    <div className="tr tr--landing">
      <header className="tr-head">
        <Wordmark mono={1 - clamp(hp * 2)} />
        <nav aria-label="Primary">
          <a href="#two">Two readings</a><a href="#local">Local</a><a href="#formats">Formats</a>
          <a className="tr-btn tr-btn--s" href={href('two-readings', 'app')}>Open DataTrust <kbd>⌘O</kbd></a>
        </nav>
      </header>

      <section className="tr-hero" ref={heroRef}>
        <div className="tr-hero__stage">
          <p className="tr-kicker" style={axes(1)}>DataTrust by NUMEK · AI reliability verification</p>
          <h1 className="tr-hero__line" aria-label="Machine output, human evidence.">
            <span style={{ ...axes(1), transform: `translateX(${-open * 22}vw)`, opacity: 1 - seg(open, 0.55, 1) }}>Machine output,</span>
            <span className="tr-window" style={{ width: `${3.4 + open * 76}vw`, height: `${5.2 + open * 52}vh` }}>
              <Terminal run={hp > 0.02} />
            </span>
            <span style={{ ...axes(0, 0.4), transform: `translateX(${open * 22}vw)`, opacity: 1 - seg(open, 0.55, 1) }}>human evidence.</span>
          </h1>
          <p className="tr-hero__sub" style={{ opacity: 1 - open * 1.6 }}>DataTrust audits the datasets behind ML and AI systems on your own machine and returns every result twice: exact output an engineer can diff, and evidence a reviewer can read.</p>
          <div className="tr-hero__cta" style={{ opacity: open > 0.92 ? 1 : 0 }}>
            <a className="tr-btn" href={href('two-readings', 'results')}>Read the Adult result</a>
          </div>
        </div>
      </section>

      <section className="tr-trans" ref={transRef} aria-label="One result, translated">
        <div className="tr-trans__stage">
          <div className="tr-trans__head">
            <span style={axes(1)}>adult.json</span><i style={{ transform: `scaleX(${tp})` }} /><span style={axes(0)}>Decision summary</span>
          </div>
          <div className="tr-trans__lines">
            {pairs.map((x, i) => {
              const t = reducedMotion() ? 1 : seg(tp, 0.08 + i * 0.1, 0.22 + i * 0.1);
              return (
                <p key={i} className="tr-pair" style={axes(1 - t, t * 0.5)}>
                  <span className="tr-pair__m" style={{ opacity: 1 - t, transform: `translateY(${-t * 10}px)` }}>{x.m}</span>
                  <span className="tr-pair__h" style={{ opacity: t, transform: `translateY(${(1 - t) * 10}px)` }}>{x.h}</span>
                </p>
              );
            })}
          </div>
          <p className="tr-trans__note" style={axes(seg(tp, 0.8, 1) > 0.5 ? 0 : 1)}>Same evidence, same file. Nothing is re-computed for the reader.</p>
        </div>
      </section>

      <TwoReadings />
      <Facts />

      <section className="tr-formats" id="formats">
        <h2 style={axes(0, 0.2)}>Three readings of one result.</h2>
        <div className="tr-formats__grid">
          <article>
            <span className="tr-tag" style={axes(1)}>adult.html · canonical</span>
            <div className="tr-mini tr-mini--html" style={axes(0)}><b>69.0</b><span>Elevated Risk</span><p>{adult.findings[0].finding}</p></div>
            <p>{formats[0].note}.</p>
          </article>
          <article>
            <span className="tr-tag" style={axes(1)}>adult.pdf</span>
            <div className="tr-mini tr-mini--pdf" style={axes(0)}><i /><i /><i className="l" /></div>
            <p>{formats[1].note}.</p>
          </article>
          <article>
            <span className="tr-tag" style={axes(1)}>adult.json · strict</span>
            <div className="tr-mini tr-mini--json"><Json value={{ overall: 69.0, risk_level: 'Elevated', sub_scores: { target_balance: 47.86 } }} /></div>
            <p>{formats[2].note}.</p>
          </article>
        </div>
      </section>

      <footer className="tr-foot">
        <h2 style={axes(0, 0.3)}>Run it where the data is.</h2>
        <div className="tr-cmds" style={axes(1)}>
          {local.commands.map((c) => <code key={c}><span>$</span>{c}</code>)}
        </div>
        <a className="tr-btn" href={href('two-readings', 'app')}>Open DataTrust</a>
        <p className="tr-foot__fine">NUMEK · AI reliability verification. DataTrust is the product. Model-confidence and LLM-grounding work are research directions, not products.</p>
      </footer>
    </div>
  );
}

function Terminal({ run }: { run: boolean }) {
  const [n, setN] = useState(reducedMotion() ? terminal.length : 0);
  useEffect(() => {
    if (!run || n >= terminal.length) return;
    const t = setTimeout(() => setN(n + 1), n === 0 ? 300 : 420);
    return () => clearTimeout(t);
  }, [run, n]);
  const done = n >= terminal.length;
  return (
    <span className="tr-term" aria-label="Terminal session: datatrust audit on adult.csv writes HTML, PDF and JSON reports; the decision summary appears beside it.">
      <span className="tr-term__bar"><i /><i /><i /><em>~/datasets — local</em><em className="tr-term__r">adult.html — decision summary</em></span>
      <span className="tr-term__split">
        <span className="tr-term__m" style={axes(1)}>
          {terminal.slice(0, Math.max(1, n)).map((l, i) => (
            <span key={i} className={`tr-term__l ${l.p ? 'is-p' : ''}`}>{l.p && <b>$ </b>}{l.t}</span>
          ))}
          <span className="tr-caret" />
        </span>
        <span className={`tr-term__h ${done ? 'is-in' : ''}`} style={axes(0, 0.15)}>
          <span className="tr-term__k">Decision summary · Adult</span>
          <span className="tr-term__score"><b>69.0</b><em>Elevated</em></span>
          <span className="tr-term__p">Evidence score 89.15 → 69.0 after the critical-sub-score guardrail: target balance is 47.86.</span>
          {adult.findings.slice(0, 3).map((f) => <span key={f.code} className="tr-term__f"><i>{f.severity}</i>{f.title}</span>)}
        </span>
      </span>
    </span>
  );
}

function TwoReadings() {
  const [v, setV] = useState(0.5);
  const f = findingJson('conflicting_target_labels');
  return (
    <section className="tr-two" id="two">
      <div className="tr-two__head">
        <h2 style={axes(1 - v, v * 0.3)}>Same finding,<br />two readings.</h2>
        <label className="tr-slider">
          <span style={axes(1)}>machine</span>
          <input type="range" min={0} max={1} step={0.01} value={v} onChange={(e) => setV(+e.target.value)} aria-label="Reading: machine to human" />
          <span style={axes(0)}>human</span>
        </label>
      </div>
      <div className="tr-two__card" style={{ ['--v' as string]: v }}>
        <div className="tr-two__m" style={{ opacity: 1 - v * 0.85, ...axes(1) }}><Json value={f} /></div>
        <div className="tr-two__h" style={{ opacity: 0.15 + v * 0.85, ...axes(0, 0.15) }}>
          <span className="tr-tag">Moderate · evidence only</span>
          <h3>{f.title}</h3>
          <p className="tr-lead">{f.finding}</p>
          <p>{f.evidence} {f.modeling_impact}</p>
          <p><b>Review next.</b> {f.recommendation}</p>
        </div>
      </div>
    </section>
  );
}

function Facts() {
  const [ref, seen] = useInView<HTMLDivElement>();
  const [i, setI] = useState(0);
  useEffect(() => {
    if (!seen || reducedMotion()) return;
    const t = setInterval(() => setI((x) => (x + 1) % local.facts.length), 2600);
    return () => clearInterval(t);
  }, [seen]);
  return (
    <section className="tr-facts" id="local" ref={ref}>
      <h2 style={axes(0, 0.2)}>Measured on your machine, one fact at a time.</h2>
      <div className="tr-facts__row">
        {local.facts.map((f, k) => (
          <button key={f.label} className={`tr-fact ${k === i ? 'is-on' : ''}`} onClick={() => setI(k)} aria-pressed={k === i}>
            <b style={axes(k === i ? 0 : 1)}>{f.value}</b>
            <span>{f.label}</span>
          </button>
        ))}
      </div>
    </section>
  );
}
