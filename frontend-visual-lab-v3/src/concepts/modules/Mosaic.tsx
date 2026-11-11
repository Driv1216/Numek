import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { reducedMotion } from '../../shell/motion';
import { effectLabel, mods, type Mod, type ModId, type State } from './data';
import { Viz } from './viz';

export const ease = 'cubic-bezier(.7, 0, .18, 1)';

/** Clip-path inset that matches `r` inside a box of size w × h. */
function insetOf(r: DOMRect, box: { left: number; top: number; width: number; height: number }) {
  const t = r.top - box.top, l = r.left - box.left;
  return `inset(${t}px ${box.width - l - r.width}px ${box.height - t - r.height}px ${l}px round 10px)`;
}

export function Tile({ m, onOpen, state, dim, children }: { m: Mod; onOpen: (id: ModId) => void; state?: State; dim?: boolean; children?: ReactNode }) {
  return (
    <button
      type="button"
      data-mod={m.id}
      data-area={m.area}
      className={`md-tile ${m.light ? 'is-light' : ''} ${dim ? 'is-dim' : ''}`}
      style={{ gridArea: m.area, ['--bg' as string]: m.bg }}
      onClick={() => onOpen(m.id)}
      aria-label={`${m.name}: ${m.line} Open`}
    >
      <span className="md-tile__top">
        <span className="md-tile__name">{m.name}</span>
        <span className="md-tile__n">{m.n}</span>
      </span>
      {children ?? (
        <>
          <span className="md-tile__fig"><b>{m.figure}</b><span>{m.figureNote}</span></span>
          <span className="md-tile__viz"><Viz id={m.id} /></span>
        </>
      )}
      {state !== undefined && (
        <span className={`md-state md-state--${state ? state.tone : 'na'}`}>{state ? state.label : 'Not for this data'}</span>
      )}
      <span className="md-tile__open" aria-hidden="true">Open</span>
    </button>
  );
}

/**
 * Grows an on-screen origin element into a full panel (FLIP via clip-path) and shrinks back on close.
 * `within` keeps the panel inside a container (the app) instead of the viewport.
 */
export function Expand<T extends string>({ id, order, onClose, onNav, within, origin, fallback, bg, light, title, bar, children }: {
  id: T; order: T[]; onClose: () => void; onNav: (id: T) => void; within?: HTMLElement | null; origin: string; fallback?: string;
  bg: (id: T) => string; light: (id: T) => boolean; title: (id: T) => string; bar: (id: T) => ReactNode; children: (id: T) => ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const closeBtn = useRef<HTMLButtonElement>(null);
  const [shown, setShown] = useState(id);
  const box = useCallback(() => {
    if (!within) return { left: 0, top: 0, width: innerWidth, height: innerHeight };
    const r = within.getBoundingClientRect();
    return { left: r.left, top: r.top, width: r.width, height: r.height };
  }, [within]);
  const originEl = (k: T) => { const root = within ?? document; return root.querySelector<HTMLElement>(`[${origin}="${k}"]`) ?? (fallback ? root.querySelector<HTMLElement>(`[${fallback}="${k}"]`) : null); };
  // Only grow from (or shrink into) an origin that is actually on screen; otherwise fade.
  const originRect = (k: T) => { const r = originEl(k)?.getBoundingClientRect(); return r && r.bottom > 0 && r.top < innerHeight ? r : undefined; };

  useLayoutEffect(() => {
    const el = ref.current!; const r = originRect(id);
    if (!within) document.documentElement.classList.add('md-lock');
    closeBtn.current?.focus({ preventScroll: true });
    if (!reducedMotion()) {
      if (r) el.animate([{ clipPath: insetOf(r, box()) }, { clipPath: 'inset(0px 0px 0px 0px round 0px)' }], { duration: 720, easing: ease });
      else el.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 300 });
      el.querySelector('.md-ch__in')?.animate([{ opacity: 0, transform: 'translateY(24px)' }, { opacity: 1, transform: 'none' }], { duration: 520, delay: r ? 300 : 80, easing: 'cubic-bezier(.2,.8,.2,1)', fill: 'backwards' });
    }
    return () => document.documentElement.classList.remove('md-lock');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Moving between panels crossfades the content while the colour slides.
  useEffect(() => {
    if (shown === id) return;
    const el = ref.current?.querySelector('.md-ch__in');
    if (!el || reducedMotion()) { setShown(id); return; }
    el.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 160, fill: 'forwards' }).onfinish = () => {
      setShown(id);
      ref.current?.scrollTo({ top: 0 });
      el.animate([{ opacity: 0, transform: 'translateX(18px)' }, { opacity: 1, transform: 'none' }], { duration: 380, easing: 'cubic-bezier(.2,.8,.2,1)', fill: 'forwards' });
    };
  }, [id, shown]);

  const close = useCallback(() => {
    const el = ref.current; const r = originRect(id);
    const back = () => { onClose(); originEl(id)?.focus({ preventScroll: true }); };
    if (!el || reducedMotion()) return back();
    if (!r) { el.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 220, fill: 'forwards' }).onfinish = back; return; }
    el.querySelector('.md-ch__in')?.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 180, fill: 'forwards' });
    el.animate([{ clipPath: 'inset(0px 0px 0px 0px round 0px)' }, { clipPath: insetOf(r, box()) }], { duration: 560, easing: ease, fill: 'forwards' }).onfinish = back;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, onClose, within, box]);

  const i = order.indexOf(id);
  const go = useCallback((d: number) => onNav(order[(i + d + order.length) % order.length]), [i, order, onNav]);
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close();
      else if (e.key === 'ArrowRight') go(1);
      else if (e.key === 'ArrowLeft') go(-1);
    };
    addEventListener('keydown', k);
    return () => removeEventListener('keydown', k);
  }, [close, go]);

  return (
    <div ref={ref} data-ch={shown} className={`md-ch ${within ? 'md-ch--in' : ''} ${light(id) ? 'is-light' : ''}`} style={{ ['--bg' as string]: bg(id) }} role="dialog" aria-modal={!within} aria-label={title(shown)}>
      <div className="md-ch__bar">
        <span>{bar(shown)}</span>
        <span className="md-ch__nav">
          <button type="button" onClick={() => go(-1)} aria-label="Previous">←</button>
          <button type="button" onClick={() => go(1)} aria-label="Next">→</button>
          <button type="button" ref={closeBtn} onClick={close} className="md-ch__x">Close</button>
        </span>
      </div>
      <div className="md-ch__in">{children(shown)}</div>
    </div>
  );
}

const M = (id: ModId) => mods.find((x) => x.id === id)!;

/** A module tile grown into its chapter. */
export function Chapter({ id, onClose, onNav, within, order = mods.map((m) => m.id), extra, origin = 'data-mod' }: {
  id: ModId; onClose: () => void; onNav: (id: ModId) => void; within?: HTMLElement | null; order?: ModId[]; extra?: (m: Mod) => ReactNode; origin?: string;
}) {
  return (
    <Expand<ModId> id={id} order={order} onClose={onClose} onNav={onNav} within={within} origin={origin} fallback="data-mod"
      bg={(k) => M(k).bg} light={(k) => !!M(k).light} title={(k) => M(k).name}
      bar={(k) => `${M(k).n} / ${String(mods.length).padStart(2, '0')} · ${M(k).rep}`}>
      {(k) => {
        const s = M(k);
        return (
          <>
            <div className="md-ch__text">
              <h2>{s.name}</h2>
              <p className="md-ch__line">{s.line}</p>
              {extra?.(s)}
              <p className="md-ch__body">{s.body}</p>
              <dl className="md-ch__facts">{s.facts.map(([a, v]) => <div key={a}><dt>{a}</dt><dd>{v}</dd></div>)}</dl>
              <p className="md-ch__eff"><b>{effectLabel[s.effect]}</b> {s.effectNote}</p>
              <p className="md-ch__not">Not: {s.not}</p>
            </div>
            <div className="md-ch__viz"><Viz id={s.id} big /></div>
          </>
        );
      }}
    </Expand>
  );
}
