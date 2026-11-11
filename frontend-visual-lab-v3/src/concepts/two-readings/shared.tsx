import type { CSSProperties, ReactNode } from 'react';
import { adult } from '../../fixture';
import { href } from '../../shell/router';

/** Recursive's MONO axis is the identity: 1 = machine reading, 0 = human reading. */
export const axes = (mono: number, casl = 0): CSSProperties => ({ fontVariationSettings: `'MONO' ${mono.toFixed(3)}, 'CASL' ${casl.toFixed(3)}` });

/** Pairs of the same fact in its two readings. Keys follow DataTrust's result summary fields. */
export const pairs: { m: string; h: ReactNode }[] = [
  { m: '"overall": 69.0,', h: <>Final score <b>69.0</b></> },
  { m: '"risk_level": "Elevated",', h: <>— <b>Elevated</b> risk —</> },
  { m: '"evidence_score": 89.15,', h: <>from an evidence score of 89.15,</> },
  { m: '"guardrails": [{ "code": "critical_sub_score", "cap": 69.0 }],', h: <>held at the cap because one sub-score is critical:</> },
  { m: '"sub_scores": { "target_balance": 47.86, … },', h: <>target balance, <b className="tr-amber">47.86</b>.</> },
  { m: '"conflicting_label_group_count": 5,', h: <><b>Five</b> identical groups of rows disagree on the label —</> },
  { m: '"score_effect": "evidence_only"', h: <>evidence for review, with no effect on the score.</> },
];

export function Wordmark({ mono = 1 }: { mono?: number }) {
  return <a className="tr-wm" href={href('two-readings', 'landing')} style={axes(mono)} aria-label="NUMEK home">NUMEK<span>_</span></a>;
}

export const findingJson = (code: string) => {
  const f = adult.findings.find((x) => x.code === code)!;
  return {
    code: f.code, severity: f.severity, title: f.title, finding: f.finding, evidence: f.evidence,
    modeling_impact: f.impact, recommendation: f.review, score_effect: f.scoreEffect,
  };
};

/** Minimal JSON syntax colouring. */
export function Json({ value, indent = 2 }: { value: unknown; indent?: number }) {
  // Python writes whole-number floats as 69.0; keep that for the score fields.
  const text = JSON.stringify(value, null, indent).replace(/("(?:overall|cap|final_score)": )(\d+)(?=[,\n}])/g, '$1$2.0');
  const parts = text.split(/("(?:[^"\\]|\\.)*"(?=\s*:)|"(?:[^"\\]|\\.)*"|-?\d+\.?\d*(?:e[+-]?\d+)?|true|false|null)/g);
  return (
    <pre className="tr-json">
      {parts.map((p, i) => {
        if (i % 2 === 0) return p;
        const isKey = /^"/.test(p) && text.slice(text.indexOf(p)).trimStart().startsWith(p) && parts[i + 1]?.trimStart().startsWith(':');
        const cls = isKey ? 'k' : /^"/.test(p) ? 's' : /true|false|null/.test(p) ? 'b' : 'n';
        return <span key={i} className={`tr-j-${cls}`}>{p}</span>;
      })}
    </pre>
  );
}
