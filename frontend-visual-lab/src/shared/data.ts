// Shared product content for all five concepts. Every figure here comes from
// stored repository evidence, so the concepts differ only in visual language.
//   Adult, Bank Marketing, German Credit, strong-leakage mutation:
//     validation/results/validation_summary.json
//   Adult rows, class counts, missingness, hour bins, conflicting pair:
//     frontend-design-lab/src/fixtures/classification.json (extracted from the pinned CSV)
//   Concrete, Bike hour: validation/regression/results/verification.json
//   Connected evidence: validation/m9/results/reports/final/bounded.json
import adultRaw from './adult.json';

export type Severity = 'High' | 'Moderate' | 'Low';

export interface Finding {
  code: string;
  title: string;
  severity: Severity;
  finding: string;
  evidence: string;
  impact: string;
  next: string;
  scoreEffect: string;
}

const a = adultRaw as unknown as {
  row_count: number;
  column_count: number;
  overall: number;
  risk_level: string;
  runtime_seconds: number;
  missing_feature_row_rate: number;
  duplicate_group_count: number;
  conflicting_label_group_count: number;
  sub_scores: Record<string, number>;
  class_counts: Record<string, number>;
  missingness: { field: string; count: number }[];
  hour_bins: { label: string; lower: number; upper: number; counts: Record<string, number> }[];
  conflict_example: Record<string, string | number>[];
  guardrails: { cap: number; code: string; explanation: string }[];
  risks: {
    code: string;
    title: string;
    severity: Severity;
    finding: string;
    evidence: string;
    modeling_impact: string;
    recommendation: string;
    score_effect: string;
  }[];
};

export const adult = {
  name: 'Adult',
  file: 'adult.csv',
  task: 'Binary classification',
  target: 'annual_income_over_50k',
  rows: a.row_count,
  columns: a.column_count,
  score: a.overall,
  band: a.risk_level,
  runtime: a.runtime_seconds,
  missingRowRate: a.missing_feature_row_rate,
  duplicateGroups: a.duplicate_group_count,
  conflictGroups: a.conflicting_label_group_count,
  conflictRows: 10,
  guardrail: {
    cap: a.guardrails[0].cap,
    text: a.guardrails[0].explanation,
  },
  subScores: [
    { key: 'completeness', label: 'Completeness', value: a.sub_scores.completeness },
    { key: 'uniqueness', label: 'Uniqueness', value: a.sub_scores.uniqueness },
    { key: 'feature_usability', label: 'Feature usability', value: a.sub_scores.feature_usability },
    { key: 'leakage_risk', label: 'Leakage risk', value: a.sub_scores.leakage_risk },
    { key: 'target_balance', label: 'Target balance', value: a.sub_scores.target_balance },
  ],
  classes: [
    { label: '≤50K', count: a.class_counts['<=50K'] },
    { label: '>50K', count: a.class_counts['>50K'] },
  ],
  missingness: a.missingness.filter((m) => m.count > 0),
  hourBins: a.hour_bins.map((b) => ({
    label: b.label,
    low: b.counts['<=50K'],
    high: b.counts['>50K'],
  })),
  conflictPair: a.conflict_example.map((r) => ({
    row: Number(r.row),
    age: String(r.age),
    education: String(r.education),
    hours: String(r.hours_per_week),
    label: String(r.annual_income_over_50k).replace('<=', '≤'),
  })),
  findings: a.risks.map<Finding>((r) => ({
    code: r.code,
    title: r.title,
    severity: r.severity,
    finding: r.finding,
    evidence: r.evidence,
    impact: r.modeling_impact,
    next: r.recommendation,
    scoreEffect: r.score_effect,
  })),
};

/** Mean of the five transparent sub-scores, before the guardrail cap applies. */
export const evidenceScore =
  Math.round((adult.subScores.reduce((s, x) => s + x.value, 0) / adult.subScores.length) * 100) / 100;

export const majorityShare = adult.classes[0].count / adult.rows; // 0.7607
export const imbalanceRatio = adult.classes[0].count / adult.classes[1].count; // 3.18

export type AuditKind = 'Classification' | 'Regression' | 'Connected evidence' | 'Controlled mutation';

export interface Audit {
  id: string;
  name: string;
  kind: AuditKind;
  rows: number;
  columns?: number;
  /** null where the workflow intentionally defines no score */
  score: number | null;
  band: string;
  findings: number;
  runtime: number | null;
  note: string;
  /** completeness, uniqueness, feature usability, leakage risk, target balance */
  sub?: [number, number, number, number, number];
}

export const audits: Audit[] = [
  {
    id: 'adult',
    name: 'Adult',
    kind: 'Classification',
    rows: 48842,
    columns: 15,
    score: 69,
    band: 'Elevated',
    findings: 4,
    runtime: 0.18,
    note: 'Capped by the target-balance guardrail',
    sub: [99.12, 99.89, 98.86, 100, 47.86],
  },
  {
    id: 'bank',
    name: 'Bank Marketing',
    kind: 'Classification',
    rows: 45211,
    columns: 17,
    score: 69,
    band: 'Elevated',
    findings: 3,
    runtime: 0.18,
    note: 'Target balance sub-score 23.4',
    sub: [100, 100, 98.5, 100, 23.4],
  },
  {
    id: 'german',
    name: 'German Credit',
    kind: 'Classification',
    rows: 1000,
    columns: 21,
    score: 91.84,
    band: 'Low',
    findings: 2,
    runtime: 0.03,
    note: 'No guardrail triggered',
    sub: [100, 100, 99.2, 100, 60],
  },
  {
    id: 'adult-leak',
    name: 'Adult with planted leakage',
    kind: 'Controlled mutation',
    rows: 48842,
    columns: 16,
    score: 49,
    band: 'High',
    findings: 3,
    runtime: 0.2,
    note: 'post_income_outcome flagged as strong leakage',
    sub: [99.17, 99.89, 98.93, 60, 47.86],
  },
  {
    id: 'bike',
    name: 'Bike Sharing, hourly',
    kind: 'Regression',
    rows: 17379,
    columns: 17,
    score: null,
    band: 'No score defined',
    findings: 4,
    runtime: 0.23,
    note: 'Relationships unavailable at prediction time',
  },
  {
    id: 'concrete',
    name: 'Concrete strength',
    kind: 'Regression',
    rows: 1030,
    columns: 9,
    score: null,
    band: 'No score defined',
    findings: 3,
    runtime: 0.07,
    note: 'Repeated inputs with varying outcomes',
  },
  {
    id: 'm9',
    name: 'Company financial evidence',
    kind: 'Connected evidence',
    rows: 20,
    score: null,
    band: 'No overall score',
    findings: 2,
    runtime: null,
    note: '18 agree, 1 discrepancy, 1 competing source',
  },
];

export const capabilities = [
  { name: 'Classification', detail: 'Binary, multiclass and single-class targets with transparent sub-scores' },
  { name: 'Regression', detail: 'Declared outcome expectations and bounded arithmetic relationships' },
  { name: 'Without labels', detail: 'Profiling of every column, with no invented score' },
  { name: 'Annotations', detail: 'Multi-target, multilabel and partial annotation coverage' },
  { name: 'Time', detail: 'Exact clocks, revisions and availability at prediction time' },
  { name: 'Text', detail: 'Corpus, annotation, conversation and retrieval reliability' },
  { name: 'Images', detail: 'Local image integrity and bounded segmentation checks' },
  { name: 'Connected evidence', detail: 'Records reconciled against the documents that support them' },
];

export const principles = [
  {
    title: 'Runs where the data lives',
    body: 'Analysis executes on your machine. Nothing is uploaded, and no model endpoint is required.',
  },
  {
    title: 'Every finding shows its evidence',
    body: 'Each risk names the affected population, the modeling impact, and what to check next.',
  },
  {
    title: 'Severe risks stay visible',
    body: 'Guardrails cap the score when one weakness is critical, so a healthy average cannot hide it.',
  },
  {
    title: 'A report, not a certificate',
    body: 'Findings support a decision. They do not claim compliance, fairness or model correctness.',
  },
];

export const exportsList = ['HTML report', 'PDF report', 'JSON evidence'];

export const fmt = (n: number) => n.toLocaleString('en-US');
export const pct = (n: number, d = 2) => `${(n * 100).toFixed(d)}%`;
