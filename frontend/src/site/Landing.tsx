import '@fontsource-variable/schibsted-grotesk';
import '@fontsource/ibm-plex-mono/400.css';
import '@fontsource/ibm-plex-mono/500.css';
import '../foundation/nk.css';
import { useEffect, useLayoutEffect, useRef, useState, type ReactElement } from 'react';
import { adult, local } from './content';
import cg from './content/cg1.generated.json';
import { reducedMotion } from '../foundation/motion';
import { Dim, Frame, Leader, Status, Wordmark, brackets, useDrawn } from '../foundation/system';
import { products, type ProductId } from '../products';
import { appHref, pageHref, useHashScroll } from './nav';
import { DataTrustPage } from './dtpage';
import { Sheet } from './principles';
import { ConfidenceWindow, DataTrustWindow, HallucinationWindow, cgFig } from './windows';


export function Header({ page }: { page?: 'datatrust' }) {
  return (
    <header className="nk-head">
      <a className="nk-head__wm" href={pageHref()} aria-label="NUMEK home"><Wordmark /></a>
      <nav aria-label="Products">
        {products.map((p) => (
          <a key={p.id} href={p.id === 'dt' ? pageHref('datatrust') : pageHref(undefined, `nk-band-${p.id}`)} aria-current={p.id === 'dt' && page === 'datatrust' ? 'page' : undefined}>
            <i className={`nk-dot nk-dot--${p.id}`} aria-hidden="true" />{p.name}
          </a>
        ))}
        <a href={pageHref(undefined, 'nk-principles')}>Principles</a>
      </nav>
      <a className="nk-btn nk-btn--sm" href={appHref()}>Open DataTrust</a>
    </header>
  );
}

/* ——— The camera tour ——— */

interface Stop { sel: string; k: string; t: string; b: string; hot?: boolean; tone?: ProductId }
const g = adult.conflicts[0];
const stops: Stop[] = [
  { sel: 'all', k: '', t: '', b: '' },
  { sel: 'dt', tone: 'dt', k: 'DataTrust · available', t: 'Dataset reliability, on your machine.', b: `Fourteen checks across tables, outcomes, time, text, images and documents. This is the Adult run: ${adult.rows.toLocaleString()} rows in ${adult.runtimeSeconds.toFixed(2)} seconds, nothing uploaded.` },
  { sel: 'dt-score', tone: 'dt', hot: true, k: 'DataTrust · score', t: 'A score only where it means something.', b: `Adult’s five measures average ${adult.evidenceScore}. Target balance is ${adult.subScores[2].value}, which is critical, so a guardrail holds the score at ${adult.finalScore.toFixed(1)}, ${adult.band}.` },
  { sel: 'dt-conflicts', tone: 'dt', hot: true, k: 'DataTrust · evidence', t: 'Down to the row.', b: `Rows ${g.rows.map((r) => r.toLocaleString()).join(' and ')} match on all fourteen features and disagree on the label. DataTrust shows them; it does not resolve them.` },
  { sel: 'cg', tone: 'cg', k: 'ConfidenceGuard · in development', t: 'The model, judged by its own predictions.', b: 'CG1 evaluates the predictions you already have (binary, multiclass, regression) against recorded outcomes. It never runs your model. Implemented, awaiting review.' },
  { sel: 'cg-recall', tone: 'cg', hot: true, k: 'ConfidenceGuard · evidence', t: `${Math.round(cg.measurements.accuracy.value * 100)}% accurate. ${cgFig.caught} of ${cg.bad} caught.`, b: `On ${cg.n} held-out German Credit applications the model is right ${Math.round(cg.measurements.accuracy.value * 100)}% of the time, but it catches only ${cgFig.caught} of the ${cg.bad} bad-credit cases. Every measure carries its population.` },
  { sel: 'hg', tone: 'hg', k: 'HallucinationGuard · research direction', t: 'Answers, checked against their sources.', b: 'A placeholder in this prototype. The direction is grounding: whether a generated answer is supported, cited or contradicted by its sources.' },
  { sel: 'all', k: 'NUMEK', t: 'Three moments. One standard of evidence.', b: 'Before training, during deployment, after generation: every finding names where it came from.' },
];
type Cam = { cx: number; cy: number; s: number };
type R = { x: number; y: number; w: number; h: number };
const smooth = (t: number) => t * t * (3 - 2 * t);

function Tour() {
  const sec = useRef<HTMLElement>(null), stage = useRef<HTMLDivElement>(null), tilt = useRef<HTMLDivElement>(null), canvas = useRef<HTMLDivElement>(null);
  const svg = useRef<SVGSVGElement>(null), lead = useRef<SVGPathElement>(null), box = useRef<SVGPathElement>(null), dot = useRef<SVGCircleElement>(null);
  const caps = useRef<HTMLDivElement>(null);
  const cams = useRef<Cam[]>([]), rects = useRef<(R | null)[]>([]);
  const [active, setActive] = useState(0);
  const [intro, setIntro] = useState(1);

  useLayoutEffect(() => {
    const measure = () => {
      const c = canvas.current!, st = stage.current!;
      const prev = c.style.transform, prevTilt = tilt.current!.style.transform;
      c.style.transform = 'none'; tilt.current!.style.transform = 'none';
      const base = c.getBoundingClientRect();
      const VW = st.clientWidth, VH = st.clientHeight, narrow = VW < 900;
      rects.current = stops.map((s) => {
        if (s.sel === 'all') return null;
        const el = c.querySelector(`[data-cam="${s.sel}"]`)!.getBoundingClientRect();
        return { x: el.left - base.left, y: el.top - base.top, w: el.width, h: el.height };
      });
      cams.current = stops.map((_, i) => {
        const r = rects.current[i];
        // Opening shot: the windows run large and bleed off the right edge, left-aligned to the page margin.
        if (i === 0) { const s0 = (VW * (narrow ? 2.1 : 1.22)) / base.width; return { cx: (VW * 0.5 - (narrow ? 16 : 40)) / s0, cy: base.height / 2, s: s0 }; }
        if (!r) return { cx: base.width / 2, cy: base.height / 2, s: Math.min((VW * 0.92) / base.width, (VH * 0.56) / base.height) };
        const pad = 30, w = r.w + pad * 2, h = r.h + pad * 2;
        return { cx: r.x + r.w / 2, cy: r.y + r.h / 2, s: Math.min((VW * (narrow ? 0.94 : 0.56)) / w, (VH * (narrow ? 0.5 : 0.72)) / h, narrow ? 1.5 : 1.15) };
      });
      c.style.transform = prev; tilt.current!.style.transform = prevTilt;
      apply();
    };
    const apply = () => {
      const el = sec.current, c = canvas.current, st = stage.current;
      if (!el || !c || !st || !cams.current.length) return;
      const r = el.getBoundingClientRect();
      const p = Math.min(1, Math.max(0, -r.top / Math.max(1, r.height - innerHeight)));
      const settle = Math.min(1, p / 0.07);
      const f = Math.max(0, (p - 0.07) / 0.93) * (stops.length - 1);
      const i = Math.min(stops.length - 2, Math.floor(f));
      const raw = f - i, rm = reducedMotion();
      const t = rm ? (raw < 0.5 ? 0 : 1) : smooth(Math.min(1, Math.max(0, (raw - 0.3) / 0.7)));
      const a = cams.current[i], b = cams.current[i + 1];
      const cam = { cx: a.cx + (b.cx - a.cx) * t, cy: a.cy + (b.cy - a.cy) * t, s: Math.exp(Math.log(a.s) + (Math.log(b.s) - Math.log(a.s)) * t) };
      const VW = st.clientWidth, VH = st.clientHeight, narrow = VW < 900;
      const fxOf = (k: number) => (stops[k].sel === 'all' || narrow ? 0.5 : 0.64);
      const fyOf = (k: number) => (k === 0 ? (narrow ? 0.76 : 0.72) : narrow ? 0.34 : 0.5);
      const fx = fxOf(i) + (fxOf(i + 1) - fxOf(i)) * t, fy = fyOf(i) + (fyOf(i + 1) - fyOf(i)) * t;
      const tx = VW * fx - cam.cx * cam.s, ty = VH * fy - cam.cy * cam.s;
      c.style.transform = `translate(${tx}px, ${ty}px) scale(${cam.s})`;
      const k = smooth(settle);
      if (tilt.current) tilt.current.style.transform = rm ? 'none' : `translateY(${(1 - k) * 5}vh) rotateX(${(1 - k) * 20}deg) scale(${0.94 + 0.06 * k})`;
      setIntro(1 - settle);
      const act = p < 0.07 ? 0 : Math.min(stops.length - 1, Math.round(i + t));
      setActive(act);
      // The leader: from the caption to the object the camera is looking at, only once the camera has settled.
      const rr = rects.current[act], capEl = caps.current?.querySelector<HTMLElement>('.nk-cap.is-on h2');
      const settled = rm ? 1 : Math.pow(1 - 2 * Math.min(t, 1 - t), 2);
      if (svg.current && lead.current && box.current && dot.current) {
        if (!rr || !capEl || narrow) { svg.current.style.opacity = '0'; return; }
        const sb = st.getBoundingClientRect(), cb = capEl.getBoundingClientRect();
        const X = tx + rr.x * cam.s, Y = ty + rr.y * cam.s, W = rr.w * cam.s, H = rr.h * cam.s;
        const ax = cb.right - sb.left + 18, ay = cb.top - sb.top + cb.height / 2;
        const ex = X - 16, ey = Math.max(Y + 18, Math.min(Y + H - 18, ay));
        lead.current.setAttribute('d', `M${ax} ${ay} H${ax + (ex - ax) * 0.45} L${ex} ${ey} H${X}`);
        dot.current.setAttribute('cx', String(ax)); dot.current.setAttribute('cy', String(ay));
        box.current.setAttribute('d', brackets(X - 8, Y - 8, W + 16, H + 16, 16));
        svg.current.style.opacity = String(settled);
      }
    };
    measure();
    let raf = 0;
    const on = () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(apply); };
    const ro = new ResizeObserver(() => measure());
    ro.observe(stage.current!);
    addEventListener('scroll', on, { passive: true });
    return () => { ro.disconnect(); removeEventListener('scroll', on); cancelAnimationFrame(raf); };
  }, []);

  // Re-draw the leader each time the camera arrives somewhere new.
  useEffect(() => {
    if (reducedMotion()) return;
    [lead.current, box.current].forEach((el) => { if (!el) return; el.classList.remove('is-draw'); void el.getBoundingClientRect(); el.classList.add('is-draw'); });
  }, [active]);

  // Light what the camera is looking at; dim the rest.
  useEffect(() => {
    const c = canvas.current; if (!c) return;
    const sel = stops[active].sel;
    c.classList.toggle('is-focus', sel !== 'all');
    c.classList.toggle('is-deep', sel.includes('-'));
    c.querySelectorAll('[data-cam]').forEach((n) => {
      const id = n.getAttribute('data-cam')!;
      n.classList.toggle('is-lit', id === sel || (sel.startsWith(id + '-')));
    });
  }, [active]);

  const s = stops[active];
  return (
    <section ref={sec} className="nk-tour" style={{ height: `${stops.length * 105 + 80}vh` }} aria-label="NUMEK products, toured">
      <div ref={stage} className="nk-stage">
        <div className="nk-hero" style={{ opacity: intro, transform: `translateY(${(1 - intro) * -40}px)`, visibility: intro < 0.02 ? 'hidden' : 'visible' }}>
          <p className="nk-kicker">NUMEK · AI reliability verification</p>
          <h1>Evidence for every<br />AI decision.</h1>
          <p className="nk-hero__sub">NUMEK is building verification for the data AI learns from, the predictions it makes and the answers it writes. Every finding comes with the evidence behind it.</p>
          <ul className="nk-hero__status">{products.map((p) => <li key={p.id}><i className={`nk-dot nk-dot--${p.id}`} />{p.name} · {p.status.split(' · ')[0].toLowerCase()}</li>)}</ul>
          <div className="nk-hero__cta"><a className="nk-btn" href={pageHref('datatrust')}>Explore DataTrust</a><span className="nk-mono">Scroll to tour the products ↓</span></div>
        </div>
        <div className="nk-persp">
          <div ref={tilt} className="nk-tilt">
            <div ref={canvas} className="nk-canvas" aria-hidden="true">
              {products.map((p) => (
                <div key={p.id} className={`nk-slot nk-slot--${p.id}`}>
                  <div className="nk-wl"><i className="nk-wl__line" /><span className="nk-wl__k">{p.moment}</span><b>{p.name}</b><Status tone={p.statusTone}>{p.status}</Status></div>
                  {p.id === 'dt' ? <DataTrustWindow /> : p.id === 'cg' ? <ConfidenceWindow /> : <HallucinationWindow />}
                </div>
              ))}
            </div>
          </div>
        </div>
        <svg ref={svg} className={`nk-lead ${s.hot ? 'is-hot' : ''}`} aria-hidden="true" style={{ opacity: 0 }}>
          <path ref={lead} className="nk-lead__p" pathLength={1} /><path ref={box} className="nk-lead__b" pathLength={1} /><circle ref={dot} r={4} className="nk-lead__d" />
        </svg>
        <div ref={caps} className="nk-caps" aria-live="polite" style={{ opacity: 1 - intro }}>
          {stops.map((x, i) => i === 0 ? null : (
            <div key={i} className={`nk-cap ${i === active ? 'is-on' : ''} ${x.tone ? `nk-cap--${x.tone}` : ''}`} aria-hidden={i !== active}>
              <span className="nk-cap__k"><i className={`nk-dot nk-dot--${x.tone ?? 'ink'}`} />{String(i).padStart(2, '0')} · {x.k}</span>
              <h2>{x.t}</h2>
              <p>{x.b}</p>
            </div>
          ))}
          <div className="nk-ticks" aria-hidden="true">{stops.slice(1).map((x, i) => <i key={i} className={`${i + 1 === active ? 'is-on' : i + 1 < active ? 'is-past' : ''} nk-tick--${x.tone ?? 'ink'}`} />)}</div>
        </div>
      </div>
    </section>
  );
}

/* ——— Principles ——— */

function Principles() {
  return (
    <section id="nk-principles" className="nk-sec nk-principles" aria-labelledby="nk-pr-h">
      <div className="nk-sec__h"><span className="nk-label">Principles</span><h2 id="nk-pr-h" className="nk-h2">One standard of evidence, marked on the evidence.</h2></div>
      <Sheet />
    </section>
  );
}

/* ——— Product bands: each previews its product page hero, drawn in Markup's line language ——— */

function DataDrawing({ on }: { on: boolean }) {
  // 15 column strips standing on the row base; notches where a column has gaps; the target split to scale.
  const cols = adult.header, gaps = new Set(['workclass', 'occupation', 'native_country']);
  const x0 = 40, w = 22, gap = 8, base = 230, top = 70, maj = adult.majorityBaseline / 100;
  const tx = x0 + 14 * (w + gap);
  return (
    <svg viewBox="0 0 560 320" className={`nk-draw ${on ? 'is-on' : ''}`} role="img" aria-label="Adult drawn as fifteen column strips with notches for gaps and the target split 76 to 24">
      {cols.map((c, i) => {
        const x = x0 + i * (w + gap), isT = i === 14;
        return isT ? (
          <g key={c}><rect x={x} y={top} width={w} height={(base - top) * maj} className="nk-d-ink" /><rect x={x} y={top + (base - top) * maj} width={w} height={(base - top) * (1 - maj)} className="nk-d-hot" /></g>
        ) : (
          <g key={c}><rect x={x} y={top} width={w} height={base - top} className="nk-d-ghost" />{gaps.has(c) && <rect x={x + 4} y={top + 40 + (i % 3) * 22} width={w - 8} height={12} className="nk-d-ink" />}</g>
        );
      })}
      <Dim x0={x0} x1={tx + w} y={top - 26} label="15 columns · 48,842 rows" />
      <Leader from={[x0 + 1 * (w + gap) + w / 2, top + 46]} to={[x0 + 2 * (w + gap), 272]} label="gaps in 3 columns" sub="3,620 rows · 7.41%" i={1} />
      <Leader from={[tx + w / 2, base]} to={[tx - 120, 292]} label="target 76.07 / 23.93" sub="balance 47.86 → cap 69" hot i={2} />
    </svg>
  );
}
function ModelDrawing({ on }: { on: boolean }) {
  const C = 12, s = 26, x0 = 40, y0 = 70, missed = cg.bad - cgFig.caught;
  return (
    <svg viewBox="0 0 560 300" className={`nk-draw ${on ? 'is-on' : ''}`} role="img" aria-label={`${cg.bad} bad-credit cases: ${cgFig.caught} caught and ${missed} missed`}>
      {Array.from({ length: cg.bad }, (_, i) => <circle key={i} cx={x0 + (i % C) * s} cy={y0 + Math.floor(i / C) * s} r={8} className={i < cgFig.caught ? 'nk-d-inkc' : 'nk-d-ring'} />)}
      <path d={brackets(x0 - 14, y0 + s - 14, (C - 1) * s + 28, 4 * s - 0, 12)} className="nk-d-br" pathLength={1} />
      <Dim x0={x0 - 8} x1={x0 + (C - 1) * s + 8} y={y0 - 34} label={`${cg.bad} bad-credit applications`} />
      <Leader from={[x0 + (C - 1) * s + 8, y0]} to={[x0 + (C - 1) * s + 46, y0 - 14]} label={`${cgFig.caught} caught`} i={1} />
      <Leader from={[x0 + 6 * s, y0 + 4 * s + 12]} to={[x0 + 9 * s, 280]} label={`${missed} missed`} sub="recall 21.7%" hot i={2} />
    </svg>
  );
}
function OutputDrawing({ on }: { on: boolean }) {
  const lines = [[0.94], [0.88], [0.32, 0.38, 0.18], [0.8], [0.52]];
  return (
    <svg viewBox="0 0 560 300" className={`nk-draw ${on ? 'is-on' : ''}`} role="img" aria-label="Lines of a generated answer with one claim bracketed. Placeholder.">
      {lines.map((segs, r) => { let x = 40; return segs.map((w, j) => { const el = <rect key={`${r}-${j}`} x={x} y={70 + r * 36} width={w * 440 - 8} height={12} className={r === 2 && j === 1 ? 'nk-d-ink' : 'nk-d-ghost'} />; x += w * 440; return el; }); })}
      <path d={brackets(40 + 0.32 * 440 - 10, 70 + 2 * 36 - 10, 0.38 * 440 + 12, 32, 9)} className="nk-d-br" pathLength={1} />
      <Leader from={[40 + 0.5 * 440, 70 + 2 * 36 + 22]} to={[40 + 0.62 * 440, 280]} label="contradicted by its source" sub="placeholder" hot i={1} />
    </svg>
  );
}

const pc1 = (v: number) => `${(v * 100).toFixed(1)}%`;
const bands: { id: ProductId; body: string; credits: [string, string][]; stats: [string, string][]; Draw: (p: { on: boolean }) => ReactElement; Win: () => ReactElement; cmd?: string }[] = [
  { id: 'dt', Draw: DataDrawing, Win: DataTrustWindow, cmd: 'datatrust audit adult.csv --target annual_income_over_50k',
    body: 'Reads tables, outcomes, time series, text, images and records against their documents, on your machine. Scores classification datasets transparently; reports evidence everywhere else.',
    credits: [['Moment', 'Before training'], ['Reads', 'Six kinds of data'], ['Runs', 'Locally · 127.0.0.1'], ['Reports', 'HTML · PDF · JSON']],
    stats: [[adult.finalScore.toFixed(1), `final · ${adult.band}`], [String(adult.evidenceScore), 'evidence score'], ['14', 'checks'], [`${adult.runtimeSeconds.toFixed(2)} s`, `${adult.rows.toLocaleString()} rows`]] },
  { id: 'cg', Draw: ModelDrawing, Win: ConfidenceWindow, cmd: 'confidenceguard evaluate --spec evaluation.json',
    body: 'Evaluates the predictions you already have (binary, multiclass and regression) against recorded outcomes. Calibration, high-confidence errors, cohorts and paired comparisons. It never runs your model.',
    credits: [['Moment', 'During deployment'], ['Reads', 'Supplied predictions'], ['Score', 'None universal, by design'], ['Status', 'CG1 · awaiting review']],
    stats: [[pc1(cg.measurements.accuracy.value), 'accuracy'], [pc1(cg.measurements.recall.value), 'recall · bad credit'], [`${cgFig.caught} / ${cg.bad}`, 'bad credit caught'], [String(cg.n), 'held-out predictions']] },
  { id: 'hg', Draw: OutputDrawing, Win: HallucinationWindow,
    body: 'The direction: whether a generated answer is supported by its sources, what it cites, and where it contradicts them. Shown here as a placeholder.',
    credits: [['Moment', 'After generation'], ['Reads', 'Answers and sources'], ['Status', 'Research direction'], ['Here', 'Placeholder']],
    stats: [['Supported', 'claim → source'], ['Cited', 'citation quality'], ['Contradicted', 'claim vs source'], ['—', 'not yet a product']] },
];

function Band({ b, i }: { b: (typeof bands)[number]; i: number }) {
  const p = products.find((x) => x.id === b.id)!;
  const [ref, on] = useDrawn<HTMLDivElement>();
  const ui = useRef<HTMLDivElement>(null);
  // Scale the real product window so its full width fits the frame.
  useLayoutEffect(() => {
    const el = ui.current; if (!el) return;
    const fit = () => { const win = el.querySelector<HTMLElement>('.nk-win'); if (win) el.style.setProperty('--uis', String(el.clientWidth / win.offsetWidth)); };
    fit(); const ro = new ResizeObserver(fit); ro.observe(el); return () => ro.disconnect();
  }, []);
  return (
    <article id={`nk-band-${b.id}`} className={`nk-card nk-card--${b.id}`} style={{ ['--n' as string]: i }} aria-labelledby={`nk-band-${b.id}-h`}>
      <header className="nk-card__h">
        <div>
          <span className="nk-card__k">0{i + 1} · {p.moment}</span>
          <h3 id={`nk-band-${b.id}-h`}>{p.name}</h3>
          <Status tone={p.statusTone}>{p.status}</Status>
        </div>
        <dl className="nk-card__credits">{b.credits.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
      </header>
      <div className="nk-card__b">
        <div ref={ui} className="nk-card__ui" aria-hidden="true"><div className="nk-card__ui-in"><b.Win /></div></div>
        <div ref={ref} className="nk-card__draw"><b.Draw on={on} /><p>{b.body}</p></div>
      </div>
      <footer className="nk-card__f">
        <ul className="nk-card__stats">{b.stats.map(([v, k]) => <li key={k}><b className={/\d/.test(v) ? '' : 'is-word'}>{v}</b><span>{k}</span></li>)}</ul>
        <div className="nk-card__go">{b.cmd && <code><i>$</i> {b.cmd}</code>}{b.id === 'dt' ? <a className="nk-card__link" href={pageHref('datatrust')}>Explore DataTrust →</a> : <span>{p.name} · {p.status}</span>}</div>
      </footer>
    </article>
  );
}

function Products() {
  const wrap = useRef<HTMLDivElement>(null);
  // As each card slides over the one before, the covered card settles back slightly.
  useEffect(() => {
    if (reducedMotion()) return;
    let raf = 0;
    const on = () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(() => {
      const cards = [...(wrap.current?.querySelectorAll<HTMLElement>('.nk-card') ?? [])];
      cards.forEach((c, i) => {
        const next = cards[i + 1];
        if (!next) { c.style.setProperty('--k', '0'); return; }
        const r = c.getBoundingClientRect(), nr = next.getBoundingClientRect();
        c.style.setProperty('--k', String(Math.min(1, Math.max(0, (r.bottom - nr.top) / r.height))));
      });
    }); };
    on(); addEventListener('scroll', on, { passive: true }); addEventListener('resize', on);
    return () => { removeEventListener('scroll', on); removeEventListener('resize', on); cancelAnimationFrame(raf); };
  }, []);
  return (
    <section className="nk-sec nk-products" aria-labelledby="nk-products-h">
      <div className="nk-sec__h"><span className="nk-label">Products</span><h2 id="nk-products-h" className="nk-h2">Three moments where an AI decision can go wrong.</h2></div>
      <div ref={wrap} className="nk-cards">{bands.map((b, i) => <Band key={b.id} b={b} i={i} />)}</div>
    </section>
  );
}

function Start() {
  return (
    <section id="nk-start" className="nk-sec nk-start" aria-labelledby="nk-start-h">
      <div>
        <span className="nk-label">Start with DataTrust</span>
        <h2 id="nk-start-h" className="nk-h2">Run it on your own data, on your own machine.</h2>
        <ul className="nk-facts">{local.facts.map((x) => <li key={x.label}><b>{x.value}</b><span>{x.label}</span></li>)}</ul>
      </div>
      <div className="nk-cmds">
        {[[local.commands[0], 'Audit a file: HTML, PDF and JSON'], [local.commands[1], 'Or open the guided app in your browser, on this machine']].map(([c, l]) => <div key={c}><span>{l}</span><code><i>$</i> {c}</code></div>)}
      </div>
    </section>
  );
}

export function Footer() {
  return (
    <footer className="nk-foot">
      <span className="nk-foot__wm"><Wordmark /></span>
      <div className="nk-foot__cols">
        <p>NUMEK · AI reliability verification</p>
        <ul>{products.map((p) => <li key={p.id}><i className={`nk-dot nk-dot--${p.id}`} aria-hidden="true" />{p.name} · {p.status}</li>)}</ul>
        <p>Reports support human review. They are not certification and do not establish compliance, fairness or safety.</p>
      </div>
    </footer>
  );
}

export default function Landing({ page }: { page: 'numek' | 'datatrust' }) {
  useHashScroll();
  return page === 'datatrust' ? <DataTrustPage /> : <NumekLanding />;
}

function NumekLanding() {
  return (
    <div className="nk">
      <Frame />
      <Header />
      <main>
        <Tour />
        <Principles />
        <Products />
        <Start />
      </main>
      <Footer />
    </div>
  );
}
