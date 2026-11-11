// adult.csv as a physical stack of sheets. Every proportion is real: 40 sheets ≈ 1,221 rows each;
// the target split, the hollow band of rows with gaps and the bands outside the fences are to scale.
import type { CSSProperties } from 'react';
import { adult } from '../../fixture';

export type State = 'hero' | 'read' | 'split' | 'disagree' | 'gaps' | 'fences' | 'score' | 'reports';
const N = 40;
const share = {
  maj: adult.classes.le50k / adult.rows,
  gaps: (adult.missing.rows.one + adult.missing.rows.two + adult.missing.rows.three_plus) / adult.rows,
  below: adult.hours.below / adult.rows,
  above: adult.hours.above / adult.rows,
};

export function Stack({ state, label = adult.file, compact = false }: { state: State; label?: string; compact?: boolean }) {
  const majN = Math.round(N * share.maj);
  const gapN = Math.max(1, Math.round(N * share.gaps));
  const belowN = Math.round(N * share.below), aboveN = Math.round(N * share.above);
  return (
    <div className={`fl-obj s-${state} ${compact ? 'is-compact' : ''}`} aria-hidden="true">
      <div className="fl-guides"><i /><i /><i /><i /><span className="fl-dim fl-dim--h">48,842 rows</span><span className="fl-dim fl-dim--w">15 columns</span></div>
      <div className="fl-iso">
        {Array.from({ length: N }, (_, i) => {
          const cls = ['fl-sheet'];
          if (state === 'split' && i >= majN) cls.push('is-min');
          if (state === 'gaps' && i >= N - gapN - 6 && i < N - 6) cls.push('is-hollow');
          if (state === 'fences' && (i < belowN || i >= N - aboveN)) cls.push('is-out');
          if (state === 'score' && i === Math.round(N * 0.69)) cls.push('is-cap');
          if (state === 'disagree' && (i === 17 || i === 28)) cls.push('is-pulled', i === 17 ? 'is-a' : 'is-b');
          return <i key={i} className={cls.join(' ')} style={{ ['--i' as string]: i } as CSSProperties} />;
        })}
        <span className="fl-spine">{label}{state !== 'hero' && <em>sha256 {adult.sha256.slice(0, 10)}…</em>}</span>
      </div>
      {state === 'disagree' && (
        <div className="fl-pair">
          {adult.conflicts[0].rows.map((r, k) => (
            <div key={r} className="fl-face"><b>row {r.toLocaleString()}</b><span>46 · Private · 235646 · HS-grad · 9 · Married-civ-spouse · Craft-repair · Husband · White · Male · 0 · 0 · 40 · United-States</span><mark>{adult.conflicts[0].labels[k]}</mark></div>
          ))}
        </div>
      )}
      {state === 'score' && (
        <div className="fl-ruler"><span style={{ bottom: '50%' }}>50 · critical</span><span className="is-cap" style={{ bottom: '69%' }}>69 · cap</span><span style={{ bottom: '89.15%' }}>89.15 · evidence</span></div>
      )}
      {state === 'reports' && (
        <div className="fl-docs">{[['adult.html', 'eight topics'], ['adult.pdf', 'decision pages + appendix'], ['adult.json', 'strict, complete']].map(([n, d], k) => <div key={n} className="fl-doc" style={{ ['--k' as string]: k } as CSSProperties}><b>{n}</b><span>{d}</span></div>)}</div>
      )}
    </div>
  );
}

export const states: { id: State; k: string; title: string; figure: string; caption: string; note?: string }[] = [
  { id: 'hero', k: 'adult.csv', title: 'It isn’t just a CSV.', figure: '48,842 × 15', caption: 'It is a public dataset that a model might be trained on. DataTrust reads it on this machine and tells you what is in it.', note: '* UCI Adult, prepared validation corpus.' },
  { id: 'read', k: '01 · Read', title: 'Read where it sits.', figure: '0.18 s', caption: 'Fingerprinted and profiled locally. Nothing is uploaded; the browser interface binds to 127.0.0.1.', note: `sha256 ${adult.sha256.slice(0, 24)}…` },
  { id: 'split', k: '02 · Split', title: 'The stack parts by the answer.', figure: '37,155 / 11,687', caption: 'Three quarters of rows are ≤50K. Target balance falls to 47.86 — critical.', note: `Majority ${adult.majorityBaseline}% · ${adult.ratio}` },
  { id: 'disagree', k: '03 · Disagree', title: 'Two sheets, one difference.', figure: '14 of 14', caption: 'Rows 16,684 and 34,343 match on every feature and disagree on the label. Five such groups; evidence only.' },
  { id: 'gaps', k: '04 · Gaps', title: 'A hollow band.', figure: '3,620 rows', caption: `${adult.missing.cells.toLocaleString()} empty cells in workclass, occupation and native_country — ${adult.missing.rowRate}% of rows. No finding; completeness 99.12.` },
  { id: 'fences', k: '05 · Fences', title: 'Beyond the fences, top and bottom.', figure: '13,496', caption: `hours_per_week outside 32.5 – 52.5: ${adult.hours.below.toLocaleString()} below, ${adult.hours.above.toLocaleString()} above. Reported, not removed.` },
  { id: 'score', k: '06 · Score', title: 'Measured against the cap.', figure: '69.0', caption: 'Evidence 89.15 — the mean of five measures. Target balance at or below 50 holds the result at 69, Elevated.', note: 'Bands: ≥85 Low · 70–84 Moderate · 50–69 Elevated · <50 High' },
  { id: 'reports', k: '07 · Reports', title: 'Folded into three documents.', figure: 'HTML · PDF · JSON', caption: 'The same evidence, three ways: a canonical report, decision pages for people, strict JSON for systems.' },
];
