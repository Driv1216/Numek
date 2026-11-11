// The DataTrust hero: every one of Adult's 48,842 rows as a dot, in file order. A scan passes once,
// then the rows behind each finding light up in coral, from each row's real flags. A Markup leader
// runs from the callout to a lit row. Conflicting rows are few, so each gets its own bracket.
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { adult, decodeRows } from '../../fixture';
import { reducedMotion } from '../../shell/motion';

type L = 'conflict' | 'gaps' | 'outside' | 'minority';
const layers: { id: L; chip: string; count: string; label: string; effect: string; hot: boolean }[] = [
  { id: 'conflict', chip: 'Conflicting labels', count: '10', label: 'rows sit in 5 groups that match on all 14 features but disagree on the answer', effect: 'Evidence only · shown for review', hot: true },
  { id: 'gaps', chip: 'Gaps', count: '3,620', label: 'rows have at least one empty cell, in workclass, occupation or native_country', effect: 'No finding · completeness 99.12', hot: false },
  { id: 'outside', chip: 'Unusual values', count: '13,496', label: 'rows have hours_per_week outside the normal range of 32.5 to 52.5', effect: 'Moderate · lowers a sub-score', hot: true },
  { id: 'minority', chip: 'Imbalance', count: '11,687', label: 'rows are >50K, so one answer fills 76.07% of the target', effect: 'Critical · holds the score at 69', hot: true },
];
const INK = [15, 27, 34], CORAL = [229, 85, 59], TIDE = [44, 110, 142];

export function Field() {
  const wrap = useRef<HTMLDivElement>(null), cv = useRef<HTMLCanvasElement>(null), lead = useRef<SVGPathElement>(null), dotEl = useRef<SVGCircleElement>(null), box = useRef<HTMLDivElement>(null);
  const [act, setAct] = useState(0);
  const [auto, setAuto] = useState(true);
  const geo = useRef({ W: 0, H: 0, p: 3, cols: 1 });
  const scan = useRef(reducedMotion() ? 1 : 0);
  const fade = useRef({ from: 0, to: 0, t: 1 });

  const rows = useMemo(() => decodeRows(), []);
  const masks = useMemo(() => {
    const n = rows.n, m: Record<L, Uint8Array> = { conflict: new Uint8Array(n), gaps: new Uint8Array(n), outside: new Uint8Array(n), minority: new Uint8Array(n) };
    for (let i = 0; i < n; i++) { m.conflict[i] = rows.conflict[i] ? 1 : 0; m.gaps[i] = rows.miss[i] ? 1 : 0; m.outside[i] = rows.hoursOut[i]; m.minority[i] = rows.cls[i]; }
    return m;
  }, [rows]);

  const pos = useCallback((i: number) => { const { p, cols } = geo.current; return [(i % cols) * p + p / 2, Math.floor(i / cols) * p + p / 2] as const; }, []);

  const draw = useCallback(() => {
    const c = cv.current; if (!c) return;
    const ctx = c.getContext('2d')!; const { W, H, p } = geo.current; const dpr = devicePixelRatio || 1;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, W, H);
    const s = p * 0.62, sx = scan.current * W, { from, to, t } = fade.current;
    const a = masks[layers[from].id], b = masks[layers[to].id];
    for (let i = 0; i < rows.n; i++) {
      const [x, y] = pos(i); if (x > sx) continue;
      const lit = (a[i] ? 1 - t : 0) + (b[i] ? t : 0);
      if (lit > 0.02) { const col = (t > 0.5 ? layers[to] : layers[from]).hot ? CORAL : TIDE; ctx.fillStyle = `rgba(${col.join(',')},${(0.25 + 0.75 * lit).toFixed(3)})`; ctx.fillRect(x - s / 2, y - s / 2, s, s); }
      else { ctx.fillStyle = `rgba(${INK.join(',')},0.2)`; ctx.fillRect(x - s / 2, y - s / 2, s, s); }
    }
    // The ten conflicting rows are too few to see as dots: each gets a bracketed ring.
    const cl = (from === 0 ? 1 - t : 0) + (to === 0 ? t : 0);
    if (cl > 0.02) {
      ctx.strokeStyle = `rgba(${CORAL.join(',')},${cl})`; ctx.lineWidth = 1.5;
      for (let i = 0; i < rows.n; i++) if (masks.conflict[i]) {
        const [x, y] = pos(i); if (x > sx) continue; const r = 7, k = 4;
        ctx.beginPath();
        ctx.moveTo(x - r, y - r + k); ctx.lineTo(x - r, y - r); ctx.lineTo(x - r + k, y - r);
        ctx.moveTo(x + r - k, y - r); ctx.lineTo(x + r, y - r); ctx.lineTo(x + r, y - r + k);
        ctx.moveTo(x - r, y + r - k); ctx.lineTo(x - r, y + r); ctx.lineTo(x - r + k, y + r);
        ctx.moveTo(x + r - k, y + r); ctx.lineTo(x + r, y + r); ctx.lineTo(x + r, y + r - k);
        ctx.stroke();
      }
    }
    if (scan.current < 1) { ctx.fillStyle = `rgba(${CORAL.join(',')},0.9)`; ctx.fillRect(sx, 0, 1.5, H); }
  }, [masks, pos, rows]);

  // The leader: from the callout to one lit row near the upper right of the field.
  const placeLeader = useCallback(() => {
    const w = wrap.current, bx = box.current, c = cv.current; if (!w || !bx || !c || !lead.current || !dotEl.current) return;
    const m = masks[layers[act].id], { W, H } = geo.current;
    const tx = W * 0.78, ty = H * 0.22; let best = -1, bd = Infinity;
    for (let i = 0; i < rows.n; i++) if (m[i]) { const [x, y] = pos(i); const d = (x - tx) ** 2 + (y - ty) ** 2; if (d < bd) { bd = d; best = i; } }
    if (best < 0) return;
    const wb = w.getBoundingClientRect(), cb = c.getBoundingClientRect(), bb = bx.getBoundingClientRect();
    const [x, y] = pos(best); const ex = cb.left - wb.left + x, ey = cb.top - wb.top + y;
    const sx0 = bb.left - wb.left + 18, sy0 = bb.bottom - wb.top;
    lead.current.setAttribute('d', `M${sx0} ${sy0}V${sy0 + 14}L${ex} ${ey - 10}V${ey - 4}`);
    dotEl.current.setAttribute('cx', String(ex)); dotEl.current.setAttribute('cy', String(ey));
    lead.current.classList.remove('is-draw'); void lead.current.getBoundingClientRect(); lead.current.classList.add('is-draw');
  }, [act, masks, pos, rows]);

  useLayoutEffect(() => {
    const c = cv.current, w = wrap.current; if (!c || !w) return;
    const fit = () => {
      const W = c.parentElement!.clientWidth, narrow = W < 700;
      const target = W * (narrow ? 1.25 : 0.24);
      const p = Math.max(1.6, Math.sqrt((W * target) / rows.n));
      const cols = Math.floor(W / p), H = Math.ceil(rows.n / cols) * p;
      geo.current = { W, H, p, cols };
      const dpr = devicePixelRatio || 1; c.width = Math.round(W * dpr); c.height = Math.round(H * dpr); c.style.height = `${H}px`;
      draw(); placeLeader();
    };
    fit(); const ro = new ResizeObserver(fit); ro.observe(c.parentElement!); return () => ro.disconnect();
  }, [draw, placeLeader, rows]);

  // The scan, once, when the field first comes into view (refs keep it from restarting on a new finding).
  const drawRef = useRef(draw), leadRef = useRef(placeLeader);
  drawRef.current = draw; leadRef.current = placeLeader;
  useEffect(() => {
    if (reducedMotion()) return;
    let raf = 0, started = false;
    const io = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting || started) return; started = true; io.disconnect();
      const t0 = performance.now();
      const tick = (t: number) => { scan.current = Math.min(1, (t - t0) / 1500); drawRef.current(); if (scan.current < 1) raf = requestAnimationFrame(tick); else leadRef.current(); };
      raf = requestAnimationFrame(tick);
    }, { threshold: 0.3 });
    if (cv.current) io.observe(cv.current);
    return () => { io.disconnect(); cancelAnimationFrame(raf); };
  }, []);

  // Crossfade between findings.
  const prev = useRef(0);
  useEffect(() => {
    fade.current = { from: prev.current, to: act, t: reducedMotion() ? 1 : 0 }; prev.current = act;
    placeLeader();
    if (reducedMotion()) { draw(); return; }
    let raf = 0; const t0 = performance.now();
    const tick = (t: number) => { fade.current.t = Math.min(1, (t - t0) / 380); draw(); if (fade.current.t < 1) raf = requestAnimationFrame(tick); };
    raf = requestAnimationFrame(tick); return () => cancelAnimationFrame(raf);
  }, [act, draw, placeLeader]);

  // Auto-cycle after the scan until someone picks a finding.
  useEffect(() => {
    if (!auto || reducedMotion()) return;
    const id = setInterval(() => { if (scan.current >= 1) setAct((a) => (a + 1) % layers.length); }, 3200);
    return () => clearInterval(id);
  }, [auto]);

  const L0 = layers[act];
  return (
    <div ref={wrap} className="nk-field">
      <i className="nk-field__x" aria-hidden="true" /><i className="nk-field__x" aria-hidden="true" /><i className="nk-field__x" aria-hidden="true" /><i className="nk-field__x" aria-hidden="true" />
      <div className="nk-field__top">
        <div className="nk-field__chips" role="group" aria-label="Show a finding">
          {layers.map((l, i) => <button key={l.id} type="button" aria-pressed={i === act} className={i === act ? 'is-on' : ''} onClick={() => { setAuto(false); setAct(i); }}>{l.chip}</button>)}
        </div>
        <div ref={box} className={`nk-field__call ${L0.hot ? 'is-hot' : ''}`} aria-live="polite">
          <b>{L0.count}</b><span>{L0.label}</span><em>{L0.effect}</em>
        </div>
      </div>
      <div className="nk-field__cv"><canvas ref={cv} role="img" aria-label={`All ${rows.n.toLocaleString()} rows of adult.csv as dots in file order; ${L0.count} ${L0.label} are lit.`} /></div>
      <svg className="nk-field__lead" aria-hidden="true"><path ref={lead} pathLength={1} className={L0.hot ? 'is-hot' : ''} /><circle ref={dotEl} r={4} /></svg>
      <div className="nk-field__foot">
        <span>adult.csv · {rows.n.toLocaleString()} rows · one dot per row, in file order</span>
        <span className="nk-field__score">evidence {adult.evidenceScore} → <b>{adult.finalScore.toFixed(1)} · {adult.band}</b>, held by target balance {adult.subScores[2].value}</span>
      </div>
    </div>
  );
}
