// The Evidence Mark: four corner brackets and a numbered tag, drawn exactly around the thing being
// verified. It is NUMEK's logo, illustration style, finding pattern and report annotation at once.
import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode, type RefObject } from 'react';
import { reducedMotion } from '../../shell/motion';

const Corners = () => <><i className="em-c em-c--tl" /><i className="em-c em-c--tr" /><i className="em-c em-c--bl" /><i className="em-c em-c--br" /></>;

/** Wraps content; when `on`, the corners snap in from outside and the tag slides out. */
export function Mark({ n, on, note, block = false, tone, className = '', children }: { n?: string; on: boolean; note?: string; block?: boolean; tone?: 'ink' | 'paper'; className?: string; children: ReactNode }) {
  const T = block ? 'div' : 'span';
  return (
    <T className={`em-mark ${block ? 'em-mark--block' : ''} ${on ? 'is-on' : ''} ${tone ? `em-mark--${tone}` : ''} ${className}`}>
      {children}
      <span className="em-mark__f" aria-hidden="true"><Corners />{n && <b className="em-tag">{n}</b>}{note && <em className="em-note">{note}</em>}</span>
    </T>
  );
}

/** A free mark that travels between targets inside a positioned container. */
export function FloatMark({ rect, n, note }: { rect: { x: number; y: number; w: number; h: number } | null; n: string; note?: string }) {
  const style = rect ? ({ transform: `translate(${rect.x}px, ${rect.y}px)`, width: rect.w, height: rect.h } as CSSProperties) : { opacity: 0 };
  return (
    <span className="em-float is-on" style={style} aria-hidden="true">
      <span className="em-mark__f"><Corners /><b className="em-tag" key={n}>{n}</b>{note && <em className="em-note" key={note}>{note}</em>}</span>
    </span>
  );
}

/** Measures the union of the elements matching `selector` inside `box`, relative to `box`. */
export function useRegion(box: RefObject<HTMLElement | null>, selector: string, pad = 4) {
  const [rect, setRect] = useState<{ x: number; y: number; w: number; h: number } | null>(null);
  useLayoutEffect(() => {
    const el = box.current; if (!el) return;
    const measure = () => {
      const b = el.getBoundingClientRect();
      const hits = [...el.querySelectorAll<HTMLElement>(selector)].map((x) => x.getBoundingClientRect()).filter((r) => r.width > 0);
      if (!hits.length) { setRect(null); return; }
      const x0 = Math.min(...hits.map((r) => r.left)), y0 = Math.min(...hits.map((r) => r.top));
      const x1 = Math.max(...hits.map((r) => r.right)), y1 = Math.max(...hits.map((r) => r.bottom));
      setRect({ x: x0 - b.left - pad, y: y0 - b.top - pad, w: x1 - x0 + pad * 2, h: y1 - y0 + pad * 2 });
    };
    measure();
    const ro = new ResizeObserver(measure); ro.observe(el);
    addEventListener('resize', measure);
    return () => { ro.disconnect(); removeEventListener('resize', measure); };
  }, [box, selector, pad]);
  return rect;
}

/** True once the element is well inside the viewport; marks snap on then. */
export function useSnap<T extends Element>(margin = '0px 0px -30% 0px') {
  const ref = useRef<T>(null);
  const [on, setOn] = useState(false);
  useEffect(() => {
    const el = ref.current; if (!el) return;
    if (reducedMotion()) { setOn(true); return; }
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setOn(true); io.disconnect(); } }, { rootMargin: margin });
    io.observe(el); return () => io.disconnect();
  }, [margin]);
  return [ref, on] as const;
}

/** Steps 0..n on a timer after mount (immediately complete under reduced motion). */
export function useSequence(n: number, start = 450, gap = 650) {
  const [k, setK] = useState(() => (reducedMotion() ? n : 0));
  useEffect(() => {
    if (reducedMotion()) return;
    const ts = Array.from({ length: n }, (_, i) => setTimeout(() => setK(i + 1), start + i * gap));
    return () => ts.forEach(clearTimeout);
  }, [n, start, gap]);
  return k;
}

/** NUMEK, framed by the mark. */
export function Wordmark({ big = false }: { big?: boolean }) {
  return <span className={`em-wm ${big ? 'em-wm--big' : ''}`}><span className="em-wm__t">NUMEK</span><span className="em-mark__f" aria-hidden="true"><Corners /><b className="em-wm__dot" /></span></span>;
}
