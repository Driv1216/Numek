// Real controlled runs of the Adult dataset from validation/results/validation_summary.json
// (the repository's mutation suite). Evidence score is the stored sub-score mean.
export interface Variant {
  id: string;
  label: string;
  change: string;
  rows: number;
  sub: Record<string, number>;
  evidence: number;
  score: number;
  band: string;
  guardrails: string[];
  headline: string;
}

export const variants: Variant[] = [
  {
    id: 'original',
    label: 'Original',
    change: 'The public Adult table, as prepared.',
    rows: 48842,
    sub: { completeness: 99.12, uniqueness: 99.89, feature_usability: 98.86, leakage_risk: 100, target_balance: 47.86 },
    evidence: 89.15,
    score: 69,
    band: 'Elevated',
    guardrails: ['Critical sub-score: target balance 47.86 caps at 69'],
    headline: 'Four findings. The imbalance alone holds the score at 69.',
  },
  {
    id: 'duplicates',
    label: 'Duplicates',
    change: 'The first 5,000 rows appended again.',
    rows: 53842,
    sub: { completeness: 99.11, uniqueness: 90.62, feature_usability: 98.86, leakage_risk: 100, target_balance: 47.94 },
    evidence: 87.31,
    score: 69,
    band: 'Elevated',
    guardrails: ['Critical sub-score: target balance 47.94 caps at 69'],
    headline: 'Uniqueness drops to 90.62 and a duplicate-records finding appears.',
  },
  {
    id: 'missing',
    label: 'Missing values',
    change: 'Every workclass value removed.',
    rows: 48842,
    sub: { completeness: 92.83, uniqueness: 99.88, feature_usability: 95.86, leakage_risk: 100, target_balance: 47.86 },
    evidence: 87.29,
    score: 69,
    band: 'Elevated',
    guardrails: ['Severe feature missingness: workclass caps at 69', 'Critical sub-score: target balance 47.86 caps at 69'],
    headline: 'A second guardrail fires: a feature with at least half its values missing.',
  },
  {
    id: 'imbalance',
    label: 'Imbalance',
    change: 'The >50K class cut to 500 rows.',
    rows: 37655,
    sub: { completeness: 98.98, uniqueness: 99.88, feature_usability: 97.71, leakage_risk: 100, target_balance: 2.66 },
    evidence: 79.85,
    score: 69,
    band: 'Elevated',
    guardrails: ['Critical sub-score: target balance 2.66 caps at 69'],
    headline: 'Target balance falls to 2.66. Target imbalance becomes a high-severity finding.',
  },
  {
    id: 'leakage',
    label: 'Leakage',
    change: 'A column named post_income_outcome planted.',
    rows: 48842,
    sub: { completeness: 99.17, uniqueness: 99.89, feature_usability: 98.93, leakage_risk: 60, target_balance: 47.86 },
    evidence: 81.17,
    score: 49,
    band: 'High',
    guardrails: ['Strong leakage: post_income_outcome caps at 49', 'Critical sub-score: target balance 47.86 caps at 69'],
    headline: 'An outcome-like column caps the score at 49. Do not rely on this dataset yet.',
  },
];
