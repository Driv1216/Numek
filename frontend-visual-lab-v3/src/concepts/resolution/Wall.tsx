import { useEffect, useMemo, useRef, useState } from 'react';
import { reducedMotion } from '../../shell/motion';
import { runColour, type Tile } from './tiles';

const TW = 280, TH = 220, GAP = 14, COLS = 6;

/** A coarse veil of blocks that dissolves in random order: the tile resolves from coarse to exact. */
function Veil({ colour, seed }: { colour: string; seed: number }) {
  const order = useMemo(() => Array.from({ length: 48 }, (_, i) => i).sort((a, b) => ((a * 9301 + seed * 49297) % 233280) - ((b * 9301 + seed * 49297) % 233280)), [seed]);
  return <div className="rs-veil" aria-hidden="true">{order.map((k, i) => <i key={k} style={{ gridArea: `${Math.floor(k / 8) + 1} / ${(k % 8) + 1}`, background: i % 3 ? colour : '#151515', animationDelay: `${120 + i * 14}ms` }} />)}</div>;
}

export function TileCard({ t, onOpen, active }: { t: Tile; onOpen: (t: Tile) => void; active?: boolean }) {
  return (
    <button type="button" className={`rs-tile ${active ? 'is-on' : ''}`} style={{ ['--c' as string]: runColour[t.run] }} onClick={() => onOpen(t)} aria-label={`${t.title}, ${t.caption}`}>
      <div className="rs-tile__body">{t.body}</div>
      <span className="rs-tile__cap"><b>{t.title}</b><em>{t.caption}</em></span>
    </button>
  );
}

/** An infinite wall: the tile set repeats in both directions; drag (or use the arrow keys) to travel. */
export function Wall({ list, onOpen, active }: { list: Tile[]; onOpen: (t: Tile) => void; active?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [off, setOff] = useState({ x: -60, y: -40 });
  const [size, setSize] = useState({ w: 1200, h: 800 });
  const drag = useRef<{ x: number; y: number; ox: number; oy: number; moved: number } | null>(null);
  const vel = useRef({ x: 0, y: 0 });
  const seen = useRef(new Map<string, number>());

  useEffect(() => {
    const el = ref.current; if (!el) return;
    const ro = new ResizeObserver(() => setSize({ w: el.clientWidth, h: el.clientHeight }));
    ro.observe(el); return () => ro.disconnect();
  }, []);
  // Inertia after a drag.
  useEffect(() => {
    if (reducedMotion()) return;
    let raf = 0;
    const tick = () => {
      if (!drag.current && (Math.abs(vel.current.x) > 0.1 || Math.abs(vel.current.y) > 0.1)) {
        setOff((o) => ({ x: o.x + vel.current.x, y: o.y + vel.current.y }));
        vel.current = { x: vel.current.x * 0.93, y: vel.current.y * 0.93 };
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick); return () => cancelAnimationFrame(raf);
  }, []);

  const rows = Math.ceil(list.length / COLS);
  const cells: { t: Tile; x: number; y: number; key: string }[] = [];
  if (list.length) {
    const c0 = Math.floor(-off.x / (TW + GAP)) - 1, c1 = c0 + Math.ceil(size.w / (TW + GAP)) + 2;
    const r0 = Math.floor(-off.y / (TH + GAP)) - 1, r1 = r0 + Math.ceil(size.h / (TH + GAP)) + 2;
    for (let r = r0; r <= r1; r++) for (let c = c0; c <= c1; c++) {
      const i = (((r % rows) + rows) % rows) * COLS + (((c % COLS) + COLS) % COLS);
      // Offset alternate columns for a less mechanical wall.
      const t = list[i % list.length];
      cells.push({ t, x: c * (TW + GAP) + off.x, y: r * (TH + GAP) + off.y + ((((c % 2) + 2) % 2) ? 40 : 0), key: `${r}:${c}` });
    }
  }

  return (
    <div ref={ref} className="rs-wall" tabIndex={0} aria-label="Wall of artefacts. Drag or use arrow keys to move."
      onPointerDown={(e) => { drag.current = { x: e.clientX, y: e.clientY, ox: off.x, oy: off.y, moved: 0 }; vel.current = { x: 0, y: 0 }; }}
      onPointerMove={(e) => {
        const d = drag.current; if (!d) return;
        const nx = d.ox + e.clientX - d.x, ny = d.oy + e.clientY - d.y;
        vel.current = { x: nx - off.x, y: ny - off.y };
        d.moved = Math.max(d.moved, Math.abs(e.clientX - d.x) + Math.abs(e.clientY - d.y));
        if (d.moved > 4) (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
        setOff({ x: nx, y: ny });
      }}
      onPointerUp={() => { const moved = drag.current?.moved ?? 0; drag.current = null; if (moved > 4) { (window as unknown as { __rsDragged: number }).__rsDragged = Date.now(); } }}
      onKeyDown={(e) => { const s = 120; if (e.key === 'ArrowLeft') setOff((o) => ({ ...o, x: o.x + s })); if (e.key === 'ArrowRight') setOff((o) => ({ ...o, x: o.x - s })); if (e.key === 'ArrowUp') setOff((o) => ({ ...o, y: o.y + s })); if (e.key === 'ArrowDown') setOff((o) => ({ ...o, y: o.y - s })); }}>
      {cells.map(({ t, x, y, key }) => {
        // Keep the veil for the length of its dissolve after a tile first comes into view.
        const now = performance.now();
        if (!seen.current.has(key)) seen.current.set(key, now);
        const fresh = now - seen.current.get(key)! < 1100;
        const seed = [...key].reduce((a, ch) => a * 31 + ch.charCodeAt(0), 7) % 9973;
        return (
          <div key={key} className="rs-slot" style={{ transform: `translate(${x}px, ${y}px)`, width: TW, height: TH }}>
            <TileCard t={t} active={active === t.id} onOpen={(tt) => { const w = window as unknown as { __rsDragged?: number }; if (w.__rsDragged && Date.now() - w.__rsDragged < 250) return; onOpen(tt); }} />
            {fresh && !reducedMotion() && <Veil colour={runColour[t.run]} seed={seed} />}
          </div>
        );
      })}
    </div>
  );
}
