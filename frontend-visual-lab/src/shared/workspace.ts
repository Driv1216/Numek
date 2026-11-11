// Workspace content shared by the round-two dashboards. Audit rows reuse
// shared/data.ts; open findings come from validation/results/validation_summary.json
// and the engine run of the planted-leakage mutation.
export { audits } from './data';

export interface OpenFinding {
  audit: string;
  auditId: string;
  title: string;
  severity: 'High' | 'Moderate' | 'Low';
  detail: string;
}

export const openFindings: OpenFinding[] = [
  { audit: 'Adult with planted leakage', auditId: 'adult-leak', title: 'Possible target leakage', severity: 'High', detail: 'post_income_outcome looks outcome-like. Score capped at 49.' },
  { audit: 'Adult', auditId: 'adult', title: 'Potentially conflicting target labels', severity: 'Moderate', detail: '5 feature-identical groups, 10 rows' },
  { audit: 'Adult', auditId: 'adult', title: 'Target imbalance', severity: 'Moderate', detail: 'Majority baseline 76.07%, 3.18 : 1' },
  { audit: 'Bank Marketing', auditId: 'bank', title: 'Target imbalance', severity: 'Moderate', detail: 'Target balance sub-score 23.4' },
  { audit: 'Adult', auditId: 'adult', title: 'Numeric outlier concentration', severity: 'Moderate', detail: 'hours_per_week, 27.63% outside 1.5 × IQR' },
  { audit: 'German Credit', auditId: 'german', title: 'Numeric outlier concentration', severity: 'Moderate', detail: 'One numeric feature above the review rate' },
  { audit: 'Adult', auditId: 'adult', title: 'Prediction-time availability needs review', severity: 'Low', detail: 'marital_status, name-based prompt only' },
];

export const lastRun: Record<string, string> = {
  adult: 'Oct 15',
  bank: 'Aug 12',
  german: 'Aug 12',
  'adult-leak': 'Oct 15',
  bike: 'Oct 9',
  concrete: 'Oct 9',
  m9: 'Oct 13',
};
