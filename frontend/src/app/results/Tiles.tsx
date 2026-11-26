// The mosaic's tile and chapter mechanics for the workflow layouts (M4 to M9): one mosaic, anchored by a
// 2×2 hero tile, whose tiles emerge one after another and each grow into their chapter, as in Modules.
// The open chapter is remembered by its position (#t=<n>; the earlier #hero still opens the hero), so a reload or a
// shared link returns to it without putting any data value in the URL. The findings ledger opens a chapter through
// `request` and focuses the finding block whose data-ref matches.
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { reducedMotion } from '../../foundation/motion';
import { type Tone } from './adapter';

export interface Tile {
  id: string; name: string; n: string; kicker: string; bg: string; light: boolean; wide?: boolean;
  tone: Tone; label: string; detail: string; viz?: ReactNode; chapter: ReactNode; bigViz?: ReactNode; hero?: boolean;
}

export interface TileRequest { tile: string; ref: string | null; nonce: number }

export function Tiles({ tiles, label, request }: { tiles: Tile[]; label: string; request?: TileRequest | null }) {
  const grid = useRef<HTMLDivElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const closeBtn = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [shown, setShown] = useState<string | null>(null);

  const inset = (id: string) => {
    const g = grid.current!, t = g.querySelector<HTMLElement>(`[data-tile="${CSS.escape(id)}"]`);
    if (!t) return 'inset(0 round 18px)';
    const gb = g.getBoundingClientRect(), tb = t.getBoundingClientRect();
    return `inset(${tb.top - gb.top}px ${gb.right - tb.right}px ${gb.bottom - tb.bottom}px ${tb.left - gb.left}px round 12px)`;
  };
  useLayoutEffect(() => {
    const p = panel.current; if (!p || !open) return;
    if (reducedMotion()) { p.style.clipPath = 'inset(0 round 18px)'; return; }
    p.style.transition = 'none'; p.style.clipPath = inset(open);
    void p.offsetWidth;
    p.style.transition = 'clip-path .7s cubic-bezier(.7, 0, .18, 1)'; p.style.clipPath = 'inset(0 round 18px)';
  }, [open]);
  const focusRef = useRef<string | null>(null);
  useEffect(() => {
    if (!open) return;
    const ref = focusRef.current;
    focusRef.current = null;
    const target = ref ? panel.current?.querySelector<HTMLElement>(`[data-ref="${CSS.escape(ref)}"]`) : null;
    if (target) { target.tabIndex = -1; target.focus({ preventScroll: true }); target.scrollIntoView({ block: 'nearest', behavior: reducedMotion() ? 'auto' : 'smooth' }); target.classList.add('is-focus'); }
    else closeBtn.current?.focus();
  }, [open, shown]);
  const hero = tiles.find((x) => x.hero);
  useEffect(() => {
    const at = /^#t=(\d+)$/.exec(location.hash), pick = at ? tiles[Number(at[1]) - 1] : location.hash === '#hero' ? hero : undefined;
    if (pick) { setShown(pick.id); setOpen(pick.id); }
  }, []);
  useEffect(() => {
    const pos = open && shown ? tiles.findIndex((x) => x.id === shown) + 1 : 0;
    const want = pos ? `#t=${pos}` : '';
    if (location.hash !== want && (want || /^#(t=\d+|hero)$/.test(location.hash))) history.replaceState(history.state, '', location.pathname + location.search + want);
  }, [open, shown, tiles]);
  useEffect(() => {
    if (!request || !tiles.some((x) => x.id === request.tile)) return;
    focusRef.current = request.ref;
    setShown(request.tile); setOpen(request.tile);
    grid.current?.scrollIntoView({ block: 'start', behavior: reducedMotion() ? 'auto' : 'smooth' });
  }, [request?.nonce]);
  const openCh = (id: string) => { setShown(id); setOpen(id); };
  const close = () => {
    const p = panel.current, id = shown;
    if (!p || !id) { setOpen(null); return; }
    const done = () => { setOpen(null); setShown(null); grid.current?.querySelector<HTMLElement>(`[data-tile="${CSS.escape(id)}"]`)?.focus(); };
    if (reducedMotion()) { done(); return; }
    p.style.clipPath = inset(id); setTimeout(done, 650);
  };
  const step = (d: number) => { const i = tiles.findIndex((t) => t.id === shown); setShown(tiles[(i + d + tiles.length) % tiles.length].id); };
  useEffect(() => {
    if (!open) return;
    const on = (e: KeyboardEvent) => { if (e.key === 'Escape') close(); if (e.key === 'ArrowRight') step(1); if (e.key === 'ArrowLeft') step(-1); };
    addEventListener('keydown', on); return () => removeEventListener('keydown', on);
  });
  const t = tiles.find((x) => x.id === shown);
  return (
    <div className="nk-checks">
      <div ref={grid} className="nk-mosaic nk-mosaic--big nk-mosaic--run ap-tiles" aria-label={label}>
        {tiles.map((x, i) => (
          <div key={x.id} className={`nk-slot2 ${x.wide ? 'is-wide' : ''} ${x.hero ? 'is-hero' : ''}`} style={{ ['--d' as string]: i }}>
            <button type="button" data-tile={x.id} className={`nk-tile nk-tile--btn ${x.light ? 'is-light' : ''} ${x.hero ? 'nk-tile--hero' : ''}`} style={{ ['--bg' as string]: x.bg }} onClick={() => openCh(x.id)} aria-label={`${x.name}, ${x.kicker}: ${x.label}. Open`}>
              <span className="nk-tile__top"><span className="nk-tile__name">{x.name}</span><span className="nk-tile__n">{x.kicker}</span></span>
              <span className="nk-tile__fig nk-tile__fig--state"><b className={x.tone === 'critical' || x.tone === 'finding' ? `is-${x.tone}` : ''}>{x.label}</b><span>{x.detail}</span></span>
              {x.viz && <span className="nk-tile__viz">{x.viz}</span>}
              <span className="nk-tile__open" aria-hidden="true">Open ↗</span>
            </button>
          </div>
        ))}
        {open && t && (
          <div ref={panel} className={`nk-ch ${t.light ? 'is-light' : ''}`} style={{ ['--bg' as string]: t.bg }} role="dialog" aria-modal="false" aria-label={`${t.name} chapter`}>
            <div className="nk-ch__bar">
              <span className="nk-ch__n">{t.n} / {tiles.length} · {t.kicker}</span>
              <div>
                <button type="button" onClick={() => step(-1)} aria-label="Previous check">←</button>
                <button type="button" onClick={() => step(1)} aria-label="Next check">→</button>
                <button ref={closeBtn} type="button" onClick={close} aria-label="Close chapter">Close ✕</button>
              </div>
            </div>
            <div className="nk-ch__in" key={t.id}>
              <div className="nk-ch__text">{t.chapter}</div>
              <div className="nk-ch__viz">{t.bigViz ?? t.viz}</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
