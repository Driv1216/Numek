// "What it checks": Modules' fourteen tiles in DataTrust's shades. A tile grows into its chapter
// (clip-path from the tile's rectangle to the whole mosaic), as in Modules.
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { effectLabel, mods, runStates, type ModId } from '../modules/data';
import { Viz } from '../modules/viz';
import { reducedMotion } from '../../shell/motion';
import { shade } from './windows';

/** `result` shows Adult's run exactly as the Modules app did: all fourteen tiles in their original
 *  places, each with the run's state, emerging one after another. */
export function Checks({ result = false }: { result?: boolean }) {
  const list = mods;
  const st = runStates.adult;
  const grid = useRef<HTMLDivElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const closeBtn = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState<ModId | null>(null);
  const [shown, setShown] = useState<ModId | null>(null);

  const inset = (id: ModId) => {
    const g = grid.current!, t = g.querySelector<HTMLElement>(`[data-mod="${id}"]`);
    if (!t) return 'inset(0 round 18px)';
    const gb = g.getBoundingClientRect(), tb = t.getBoundingClientRect();
    return `inset(${tb.top - gb.top}px ${gb.right - tb.right}px ${gb.bottom - tb.bottom}px ${tb.left - gb.left}px round 12px)`;
  };

  // Grow from the tile on open; shrink back into it on close.
  useLayoutEffect(() => {
    const p = panel.current; if (!p) return;
    if (open) {
      if (reducedMotion()) { p.style.clipPath = 'inset(0 round 18px)'; return; }
      p.style.transition = 'none'; p.style.clipPath = inset(open);
      void p.offsetWidth;
      p.style.transition = 'clip-path .7s cubic-bezier(.7, 0, .18, 1)'; p.style.clipPath = 'inset(0 round 18px)';
    }
  }, [open]);
  useEffect(() => { if (open) closeBtn.current?.focus(); }, [open]);
  const openCh = (id: ModId) => { setShown(id); setOpen(id); };

  const close = () => {
    const p = panel.current, id = shown;
    if (!p || !id) { setOpen(null); return; }
    const done = () => { setOpen(null); setShown(null); grid.current?.querySelector<HTMLElement>(`[data-mod="${id}"]`)?.focus(); };
    if (reducedMotion()) { done(); return; }
    p.style.clipPath = inset(id);
    setTimeout(done, 650);
  };
  const step = (d: number) => { const i = list.findIndex((m) => m.id === shown); const n = list[(i + d + list.length) % list.length].id; setShown(n); };
  useEffect(() => {
    if (!open) return;
    const on = (e: KeyboardEvent) => { if (e.key === 'Escape') close(); if (e.key === 'ArrowRight') step(1); if (e.key === 'ArrowLeft') step(-1); };
    addEventListener('keydown', on); return () => removeEventListener('keydown', on);
  });

  const m = mods.find((x) => x.id === shown);
  return (
    <div className="nk-checks">
      <div ref={grid} className={`nk-mosaic nk-mosaic--big ${result ? 'nk-mosaic--run' : ''}`}>
        {list.map((x, i) => {
          const [bg, light] = shade[x.id];
          const s = result ? st[x.id] : undefined;
          const dim = result && !s;
          return (
            <div key={x.id} className="nk-slot2" style={{ gridArea: x.area, ['--d' as string]: i }}>
              <button type="button" data-mod={x.id} className={`nk-tile nk-tile--btn ${light ? 'is-light' : ''} ${dim ? 'is-dim' : ''}`} style={{ ['--bg' as string]: bg }} onClick={() => openCh(x.id)} aria-label={`${x.name}: ${s ? s.label : x.line} Open`}>
                <span className="nk-tile__top"><span className="nk-tile__name">{x.name}</span><span className="nk-tile__n">{x.n}</span></span>
                {result
                  ? <span className="nk-tile__fig nk-tile__fig--state"><b className={s && (s.tone === 'critical' || s.tone === 'finding') ? `is-${s.tone}` : ''}>{s ? s.label : 'Not for this data'}</b><span>{s ? s.detail : x.line}</span></span>
                  : <span className="nk-tile__fig"><b>{x.figure}</b><span>{x.figureNote}</span></span>}
                {(!result || s) && <span className="nk-tile__viz"><Viz id={x.id} /></span>}
                <span className="nk-tile__open" aria-hidden="true">Open ↗</span>
              </button>
            </div>
          );
        })}
        {open && m && (
          <div ref={panel} className={`nk-ch ${shade[m.id][1] ? 'is-light' : ''}`} style={{ ['--bg' as string]: shade[m.id][0] }} role="dialog" aria-modal="false" aria-label={`${m.name} chapter`}>
            <div className="nk-ch__bar">
              <span className="nk-ch__n">{m.n} / 14 · {m.rep}</span>
              <div>
                <button type="button" onClick={() => step(-1)} aria-label="Previous check">←</button>
                <button type="button" onClick={() => step(1)} aria-label="Next check">→</button>
                <button ref={closeBtn} type="button" onClick={close} aria-label="Close chapter">Close ✕</button>
              </div>
            </div>
            <div className="nk-ch__in" key={m.id}>
              <div className="nk-ch__text">
                <h3>{m.name}</h3>
                {result && <div className="nk-ch__run"><span>In Adult</span><b>{st[m.id] ? st[m.id]!.label : 'Not for this data'}</b><p>{st[m.id] ? st[m.id]!.detail : `${m.name} reads ${m.rep.toLowerCase()} data; Adult is a table.`}</p></div>}
                <p className="nk-ch__line">{m.line}</p>
                <p>{m.body}</p>
                <span className="nk-ch__eff">{m.effectNote.startsWith(effectLabel[m.effect]) ? m.effectNote : `${effectLabel[m.effect]} · ${m.effectNote}`}</span>
                <dl>{m.facts.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
                <p className="nk-ch__not">{m.not}</p>
              </div>
              <div className="nk-ch__viz"><Viz id={m.id} big /></div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
