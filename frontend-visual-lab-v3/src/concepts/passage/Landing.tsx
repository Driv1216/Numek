import '@fontsource-variable/hanken-grotesk';
import '@fontsource-variable/azeret-mono';
import './passage.css';
import { useEffect, useState } from 'react';
import { finance, formats, local, representations } from '../../fixture';
import { useScrollProgress } from '../../shell/motion';
import { href } from '../../shell/router';
import { Artefact, repColour, repInk } from './artefacts';
import { Header } from './chrome';

const checks = [
  ['Feature-identical rows that disagree on the label', 'tables'], ['Strong versus review-only leakage names', 'tables'],
  ['Transparent sub-scores with explained guardrails', 'tables'], ['Bounded copy, affine and two-feature-sum relationships', 'outcomes'],
  ['Repeated-input target variation', 'outcomes'], ['Exact clocks, declared availability and revisions', 'time'],
  ['Calibrated, bounded near-duplicate search', 'text'], ['Retrieval provenance and private evidence resolution', 'text'],
  ['Orientation and coordinate compatibility', 'images'], ['Segmentation integrity within work bounds', 'images'],
  ['Records reconciled against native PDF and DOCX', 'connected'], ['Competing evidence retained, never hidden', 'connected'],
] as const;

export default function Landing() {
  const [wrap, p] = useScrollProgress<HTMLDivElement>('pinned');
  const [vw, setVw] = useState(() => innerWidth);
  useEffect(() => { const on = () => setVw(innerWidth); addEventListener('resize', on); return () => removeEventListener('resize', on); }, []);
  const horizontal = vw > 900;
  const W = Math.min(vw * 0.6, 920);
  const PEEK = 64;
  const n = representations.length;
  const s = p * (n - 1) * W;

  return (
    <div className="ps ps--landing">
      <Header />
      <section className="ps-hero">
        <p className="ps-mono">NUMEK · DataTrust · AI reliability verification</p>
        <div className="ps-hero__top">
          <h1>One dataset is<br />never one thing.</h1>
          <ol className="ps-hero__trail" aria-label="One finding, followed from run to rows">
            {[['Run', 'Adult · 48,842 × 15'], ['Topic', 'Duplicate and feature evidence'], ['Finding', 'Potentially conflicting target labels'], ['Evidence', 'Group 1 · rows 16684 & 34343'], ['Row values', 'annual_income_over_50k  >50K / <=50K']].map(([k, v], i) => (
              <li key={k} style={{ ['--i' as string]: i }}><span className="ps-mono">{k}</span><b>{v}</b></li>
            ))}
          </ol>
        </div>
        <div className="ps-hero__foot">
          <p>DataTrust follows the evidence across tables, outcomes, time, text, images and the documents that connect them — and tells you, precisely, where each finding lives. On your own machine.</p>
          <div className="ps-actions"><a className="ps-btn" href={href('passage', 'results')}>Follow one finding</a><a className="ps-btn ps-btn--line" href={href('passage', 'app')}>Open DataTrust</a></div>
        </div>
        <div className="ps-hero__strip" aria-hidden="true">{representations.map((r) => <i key={r.id} style={{ background: repColour[r.id] }} />)}</div>
      </section>

      <section className="ps-pass" ref={wrap} style={horizontal ? { height: `calc(100vh + ${(n - 1) * W}px)` } : undefined} aria-label="Six representations">
        <div className="ps-pass__stage">
          {representations.map((r, i) => {
            const x = horizontal ? Math.max(i * W - s, i * PEEK) + 24 : 0;
            return (
              <article key={r.id} className="ps-panel" style={horizontal ? { transform: `translateX(${x}px)`, width: W, zIndex: i + 1 } : undefined}>
                <div className="ps-panel__art"><Artefact rep={r.id} /></div>
                <div className="ps-panel__body" style={{ background: repColour[r.id], color: repInk[r.id] }}>
                  <span className="ps-panel__ix">{i + 1}/{n}</span>
                  <h2>{r.name}</h2>
                  <ul>{r.checks.map((c) => <li key={c}>{c}</li>)}</ul>
                  <span className="ps-panel__ex">{r.example}</span>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      <section className="ps-conn">
        <div className="ps-conn__head">
          <p className="ps-mono">6/6 · Connected</p>
          <h2>Where the representations meet, disagreement is kept.</h2>
        </div>
        <div className="ps-conn__body">
          <ol className="ps-tally">
            <li><b>{finance.records}</b><span>records</span></li>
            <li><b>{finance.documents}</b><span>native PDFs</span></li>
            <li><b>{finance.agreements}</b><span>agreements</span></li>
            <li className="is-amber"><b>{finance.discrepancies}</b><span>discrepancy</span></li>
            <li className="is-red"><b>{finance.conflicts}</b><span>conflict · both documents kept</span></li>
          </ol>
          <p>In the guided finance story DataTrust reconciles twenty structured records against twenty-one native documents through one reusable mapping. Each result carries an exact locator — file, page, table, row — that resolves privately on your machine. {finance.note}</p>
        </div>
      </section>

      <section className="ps-index" aria-labelledby="ix-h">
        <div className="ps-index__head"><h2 id="ix-h">Index of checks</h2><p className="ps-mono">A selection · 12 of many</p></div>
        <ol>
          {checks.map(([c, rep], i) => (
            <li key={c} style={{ ['--c' as string]: repColour[rep], ['--ci' as string]: repInk[rep] }}>
              <span className="ps-index__n">{String(i + 1).padStart(2, '0')}</span>
              <span className="ps-index__t">{c}</span>
              <span className="ps-index__r">{representations.find((r) => r.id === rep)!.name}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="ps-local">
        <h2>The passage never leaves the machine.</h2>
        <ul>{local.facts.map((f) => <li key={f.label}><b>{f.value}</b><span>{f.label}</span></li>)}</ul>
      </section>

      <footer className="ps-foot">
        <div className="ps-foot__formats">{formats.map((f) => <div key={f.name}><b>{f.name}</b><span>{f.note}</span></div>)}</div>
        <h2>Start where your data is.</h2>
        <code>$ {local.commands[1]}</code>
        <a className="ps-btn ps-btn--light" href={href('passage', 'app')}>Open DataTrust</a>
        <p className="ps-foot__fine">NUMEK · AI reliability verification. DataTrust is the product; model-confidence and LLM-grounding work are research directions.</p>
      </footer>
    </div>
  );
}
