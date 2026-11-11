// A seven-segment readout drawn as SVG, so numbers look like a real display
// rather than a font imitating one. Unlit segments stay faintly visible.

const MAP: Record<string, string> = {
  '0': 'abcdef',
  '1': 'bc',
  '2': 'abged',
  '3': 'abgcd',
  '4': 'fgbc',
  '5': 'afgcd',
  '6': 'afgedc',
  '7': 'abc',
  '8': 'abcdefg',
  '9': 'abcdfg',
  '-': 'g',
  ' ': '',
  E: 'afged',
  L: 'fed',
  H: 'fbgec',
  o: 'gcde',
  n: 'egc',
  r: 'eg',
  A: 'afbgec',
};

const W = 44;
const H = 78;
const T = 7.5; // segment thickness
const G = 1.6; // gap at joints

function hseg(x: number, y: number, len: number) {
  const h = T / 2;
  return `${x + G},${y} ${x + G + h},${y - h} ${x + len - G - h},${y - h} ${x + len - G},${y} ${x + len - G - h},${y + h} ${x + G + h},${y + h}`;
}
function vseg(x: number, y: number, len: number) {
  const h = T / 2;
  return `${x},${y + G} ${x + h},${y + G + h} ${x + h},${y + len - G - h} ${x},${y + len - G} ${x - h},${y + len - G - h} ${x - h},${y + G + h}`;
}

const L = T / 2 + 1;
const R = W - T / 2 - 1;
const TOP = T / 2 + 1;
const MID = H / 2;
const BOT = H - T / 2 - 1;
const SEG: Record<string, string> = {
  a: hseg(L, TOP, R - L),
  b: vseg(R, TOP, MID - TOP),
  c: vseg(R, MID, BOT - MID),
  d: hseg(L, BOT, R - L),
  e: vseg(L, MID, BOT - MID),
  f: vseg(L, TOP, MID - TOP),
  g: hseg(L, MID, R - L),
};

export function Segments({
  value,
  digits,
  height = 80,
  on = 'var(--seg-on)',
  off = 'var(--seg-off)',
  label,
}: {
  value: string;
  digits?: number;
  height?: number;
  on?: string;
  off?: string;
  label?: string;
}) {
  // Decimal points attach to the preceding character.
  const chars: { c: string; dot: boolean }[] = [];
  for (const ch of value) {
    if (ch === '.' && chars.length) chars[chars.length - 1].dot = true;
    else chars.push({ c: ch, dot: false });
  }
  while (digits && chars.length < digits) chars.unshift({ c: ' ', dot: false });
  const step = W + 14;
  const width = chars.length * step;
  return (
    <svg
      viewBox={`-6 -2 ${width + 4} ${H + 4}`}
      style={{ height, width: 'auto', overflow: 'visible' }}
      role="img"
      aria-label={label ?? value}
    >
      {chars.map(({ c, dot }, i) => {
        const lit = MAP[c] ?? '';
        return (
          <g key={i} transform={`translate(${i * step} 0) skewX(-6)`}>
            {Object.entries(SEG).map(([k, pts]) => (
              <polygon key={k} points={pts} fill={lit.includes(k) ? on : off} />
            ))}
            <circle cx={W + 5} cy={BOT} r={T / 2} fill={dot ? on : off} />
          </g>
        );
      })}
    </svg>
  );
}
