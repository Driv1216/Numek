import { useEffect, useRef } from 'react';
import { useInView } from '../../shell/motion';

/** Small canvas waffle for a count of units in a given shape. */
export function UnitStrip({ count, shape, color, cols, size = 6, gap = 2, label }: {
  count: number; shape: 'square' | 'dash' | 'frame'; color: (k: number) => string; cols: number; size?: number; gap?: number; label: string;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const [wrap, seen] = useInView<HTMLDivElement>();
  useEffect(() => {
    const c = ref.current!; const dpr = Math.min(2, devicePixelRatio || 1);
    const w = shape === 'dash' ? size * 2.2 : size;
    const pw = w + gap, ph = size + gap;
    const rows = Math.ceil(count / cols);
    c.width = cols * pw * dpr; c.height = rows * ph * dpr;
    c.style.width = `${cols * pw}px`; c.style.aspectRatio = `${cols * pw} / ${rows * ph}`;
    const g = c.getContext('2d')!; g.scale(dpr, dpr);
    let k = 0; let raf = 0;
    const step = () => {
      const until = seen ? Math.min(count, k + Math.ceil(count / 40)) : 0;
      for (; k < until; k++) {
        const x = (k % cols) * pw, y = Math.floor(k / cols) * ph;
        g.fillStyle = color(k); g.strokeStyle = color(k);
        if (shape === 'frame') { g.lineWidth = 1; g.strokeRect(x + 0.5, y + 0.5, size - 1, size - 1); g.fillRect(x + size * 0.3, y + size * 0.3, size * 0.4, size * 0.4); }
        else if (shape === 'dash') g.fillRect(x, y + size * 0.35, w, size * 0.3);
        else g.fillRect(x, y, size, size);
      }
      if (k < count && seen) raf = requestAnimationFrame(step);
    };
    step();
    return () => cancelAnimationFrame(raf);
  }, [count, shape, color, cols, size, gap, seen]);
  return <div ref={wrap} className="er-strip"><canvas ref={ref} role="img" aria-label={label} /></div>;
}

/** 20 records reconciled against 21 documents: the conflicting record has two. */
export function PairsGlyph() {
  const rows = Array.from({ length: 20 }, (_, i) => i);
  return (
    <svg viewBox="0 0 300 250" className="er-pairs" role="img" aria-label="20 records linked to 21 documents: 18 agreements, 1 discrepancy, 1 conflict where two documents disagree.">
      {rows.map((i) => {
        const y = 10 + i * 11.5;
        const kind = i === 12 ? 'disc' : i === 16 ? 'conf' : 'ok';
        return (
          <g key={i} className={`er-pairs__${kind}`}>
            <rect x={20} y={y - 3.5} width={7} height={7} />
            <path d={`M30 ${y} C120 ${y} 150 ${y} 236 ${y}`} />
            <rect x={240} y={y - 4} width={10} height={8} className="doc" />
            {kind === 'conf' && <><path d={`M250 ${y} H256`} /><rect x={256} y={y - 4} width={10} height={8} className="doc" /></>}
          </g>
        );
      })}
    </svg>
  );
}
