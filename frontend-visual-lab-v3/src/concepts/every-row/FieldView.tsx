import { useEffect, useMemo, useRef, useState } from 'react';
import { adult } from '../../fixture';
import { UnitField, type Label } from './field';
import { D, N, build, delays, type Arrangement, type Rect } from './layouts';

interface Props {
  arrangement: Arrangement;
  /** Region of the canvas the marks may occupy. */
  area: (w: number, h: number) => Rect;
  hover?: boolean;
  className?: string;
  label?: string;
}

const H = adult.header;

export function FieldView({ arrangement, area, hover = true, className = '', label }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const field = useRef<UnitField | null>(null);
  const [labels, setLabels] = useState<Label[]>([]);
  const [tip, setTip] = useState<{ x: number; y: number; i: number } | null>(null);
  const [failed, setFailed] = useState(false);
  const d = useMemo(delays, []);
  const areaRef = useRef(area); areaRef.current = area;
  const arrRef = useRef(arrangement);

  useEffect(() => {
    const f = new UnitField(canvas.current!, N, d);
    if (!f.ok) { setFailed(true); return; }
    field.current = f;
    const apply = (animate: boolean) => {
      const { w, h } = f.resize();
      const L = build(arrRef.current, areaRef.current(w, h));
      setLabels(L.labels);
      f.set(L, animate);
    };
    apply(false);
    const ro = new ResizeObserver(() => apply(false));
    ro.observe(canvas.current!);
    return () => { ro.disconnect(); f.dispose(); field.current = null; };
  }, [d]);

  useEffect(() => {
    arrRef.current = arrangement;
    const f = field.current; if (!f) return;
    const r = canvas.current!.getBoundingClientRect();
    const L = build(arrangement, areaRef.current(r.width, r.height));
    setLabels(L.labels);
    f.set(L, true);
    setTip(null);
  }, [arrangement]);

  const onMove = (e: React.PointerEvent) => {
    if (!hover || !field.current) return;
    const r = canvas.current!.getBoundingClientRect();
    const x = e.clientX - r.left, y = e.clientY - r.top;
    const i = field.current.pick(x, y, arrangement === 'conflicts' ? 22 : 5);
    setTip(i >= 0 ? { x, y, i } : null);
  };

  return (
    <div className={`er-field ${className}`} onPointerMove={onMove} onPointerLeave={() => setTip(null)}>
      <canvas ref={canvas} role="img" aria-label={label ?? `All ${N.toLocaleString()} rows of adult.csv arranged by ${arrangement}.`} />
      {failed && <p className="er-field__fail">WebGL is unavailable here; the arrangement is described in the text.</p>}
      <div className="er-labels" aria-hidden="true">
        {labels.map((l, k) => (
          <div key={`${arrangement}${k}`} className={`er-lab er-lab--${l.tone ?? 'ink'}`} style={{ left: l.x, top: l.y }}>
            <b>{l.text}</b>{l.sub && <span>{l.sub}</span>}
          </div>
        ))}
      </div>
      {tip && (
        <div className="er-tip" style={{ left: tip.x + 14, top: tip.y + 14 }}>
          <b>Row {(tip.i + 1).toLocaleString()}</b>
          <span>{H[0]} {D.age[tip.i]} · {H[12]} {D.hours[tip.i]}</span>
          <span>{D.cls[tip.i] ? '>50K' : '≤50K'}{D.miss[tip.i] ? ` · ${D.miss[tip.i]} missing` : ''}{D.dup[tip.i] ? ' · duplicate' : ''}{D.conflict[tip.i] ? ` · conflict group ${D.conflict[tip.i]}` : ''}{D.hoursOut[tip.i] ? ' · hours outside fences' : ''}</span>
        </div>
      )}
    </div>
  );
}
