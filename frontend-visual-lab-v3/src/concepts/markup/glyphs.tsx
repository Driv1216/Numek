import type { Representation } from '../../fixture';

/** Small line drawings, one per representation, each carrying its own kind of mark. */
export function SheetGlyph({ rep }: { rep: Representation }) {
  return (
    <svg viewBox="0 0 240 150" className="mk-glyph" aria-hidden="true">
      {rep === 'tables' && <>
        <rect x="20" y="20" width="200" height="110" className="g" pathLength={1} />
        {[45, 70, 95, 120, 145, 170, 195].map((x) => <line key={x} x1={x} x2={x} y1={20} y2={130} className="g g--l" pathLength={1} />)}
        {[38, 54, 70, 86, 102, 118].map((y) => <line key={y} x1={20} x2={220} y1={y} y2={y} className="g g--l" pathLength={1} />)}
        <rect x="195" y="70" width="25" height="32" className="m" pathLength={1} />
        <circle cx="207" cy="62" r="6" className="m-dot" />
      </>}
      {rep === 'outcomes' && <>
        <line x1="20" x2="220" y1="125" y2="125" className="g" pathLength={1} />
        {[[30, 44], [70, 66], [110, 38], [150, 80]].map(([x, h], i) => <g key={i}><rect x={x} y={125 - h} width="22" height={h * 0.35} className="g" pathLength={1} /><rect x={x} y={125 - h * 0.65} width="22" height={h * 0.65} className="g g--l" pathLength={1} /></g>)}
        <text x="186" y="52" className="gt">cnt</text>
        <text x="182" y="72" className="gt">= a + b</text>
        <path d="M176 40 H222 V80 H176 Z" className="m" pathLength={1} />
        <circle cx="176" cy="40" r="6" className="m-dot" />
      </>}
      {rep === 'time' && <>
        <line x1="20" x2="220" y1="75" y2="75" className="g" pathLength={1} />
        {[40, 70, 100, 130, 160, 190].map((x, i) => <g key={x}><line x1={x} x2={x} y1={68} y2={82} className="g" pathLength={1} /><line x1={x + (i === 3 ? 26 : 8)} x2={x + (i === 3 ? 26 : 8)} y1={92} y2={104} className="g g--l" pathLength={1} /></g>)}
        <text x="20" y="58" className="gt">event</text>
        <text x="20" y="120" className="gt">available</text>
        <path d="M130 86 L156 98" className="m" pathLength={1} />
        <circle cx="156" cy="98" r="6" className="m-dot" />
      </>}
      {rep === 'text' && <>
        {[30, 46, 62, 78, 94, 110].map((y, i) => <line key={y} x1={24} x2={[200, 170, 214, 188, 214, 150][i]} y1={y} y2={y} className="g g--txt" pathLength={1} />)}
        <path d="M18 56 H12 V100 H18" className="m" pathLength={1} />
        <circle cx="12" cy="78" r="6" className="m-dot" />
        <text x="140" y="134" className="gt">near-duplicate</text>
      </>}
      {rep === 'images' && <>
        <rect x="30" y="18" width="180" height="114" className="g" pathLength={1} />
        <path d="M30 110 L80 70 L120 98 L160 60 L210 104" className="g g--l" pathLength={1} />
        <rect x="56" y="40" width="54" height="44" className="g" pathLength={1} />
        <rect x="132" y="34" width="58" height="50" className="m" pathLength={1} />
        <circle cx="190" cy="34" r="6" className="m-dot" />
      </>}
      {rep === 'connected' && <>
        <rect x="16" y="50" width="88" height="22" className="g" pathLength={1} />
        <line x1="50" x2="50" y1="50" y2="72" className="g g--l" pathLength={1} />
        <rect x="150" y="14" width="74" height="122" className="g" pathLength={1} />
        {[34, 46, 58, 70, 82, 94].map((y) => <line key={y} x1={160} x2={214} y1={y} y2={y} className="g g--l" pathLength={1} />)}
        <path d="M104 61 C128 61 132 70 158 70" className="m" pathLength={1} />
        <rect x="158" y="64" width="56" height="12" className="m" pathLength={1} />
        <circle cx="131" cy="65" r="6" className="m-dot" />
      </>}
    </svg>
  );
}
