// Shared, design-neutral content. Every value is taken from preserved repository
// evidence (validation reports, results JSON and milestone docs); generated parts
// come from scripts/extract_fixture.py. Concepts may present this differently but
// must not invent capabilities or numbers.
import generated from './adult.generated.json';
import rowsPacked from './adult-rows.generated.json';

export type Severity = 'High' | 'Moderate' | 'Low';

export interface Finding {
  code: string;
  title: string;
  severity: Severity;
  finding: string;
  evidence: string;
  impact: string;
  review: string;
  scoreEffect: string;
  /** Where the evidence lives in the dataset, for concepts that point at it. */
  locus: { kind: 'rows' | 'column' | 'target'; columns: string[]; rows?: number[] };
}

export const adult = {
  name: 'Adult',
  file: 'adult.csv',
  sha256: '2449271dcce75712f6143b8c84267d8efe4c8ecda53dbf7a92b47cc292fbc049',
  source: 'UCI Adult (prepared, public validation corpus)',
  generatedAt: '2026-08-13 01:08:11',
  task: 'Classification · binary',
  target: 'annual_income_over_50k',
  rows: generated.rows,
  columns: generated.columns,
  featureColumns: 14,
  numericFeatures: 6,
  nonNumericFeatures: 8,
  runtimeSeconds: 0.18444,
  evidenceScore: 89.15,
  finalScore: 69.0,
  band: 'Elevated',
  guardrail: {
    code: 'critical_sub_score',
    label: 'Critical sub-score',
    cap: 69.0,
    explanation: 'The target balance sub-score is 47.86, indicating a critical weakness.',
  },
  subScores: [
    { key: 'completeness', label: 'Completeness', value: 99.12 },
    { key: 'uniqueness', label: 'Uniqueness', value: 99.89 },
    { key: 'target_balance', label: 'Target balance', value: 47.86, critical: true },
    { key: 'feature_usability', label: 'Feature usability', value: 98.86 },
    { key: 'leakage_risk', label: 'Leakage risk', value: 100.0 },
  ],
  classes: generated.classes,
  majorityBaseline: 76.07,
  ratio: '3.18 : 1',
  missing: {
    cells: 6465,
    featureCells: 683788,
    cellRate: 0.95,
    reportCellRate: 0.88,
    rowRate: 7.41,
    rows: generated.missing_rows,
    byColumn: generated.missing_by_col as Record<string, number>,
  },
  duplicates: generated.duplicates,
  conflicts: generated.conflicts as { id: number; rows: number[]; features: Record<string, string | number | null>; labels: string[] }[],
  hours: generated.hours,
  age: generated.age,
  columnEvidence: generated.column_evidence,
  sampleRows: generated.sample_rows as string[][],
  header: ['age', 'workclass', 'final_weight', 'education', 'education_years', 'marital_status', 'occupation', 'relationship', 'race', 'sex', 'capital_gain', 'capital_loss', 'hours_per_week', 'native_country', 'annual_income_over_50k'],
  narrative:
    'The final reliability score is 69.0 (Elevated Risk) under the current DataTrust methodology. Evidence score 89.15 → final score 69.0 after applied guardrails: the target balance sub-score is 47.86, indicating a critical weakness. 5 feature-identical groups contain more than one non-missing target label.',
  nextAction: 'Fix the highlighted issues before using this dataset for high-stakes decisions.',
  limits:
    'Findings support human review; they do not prove causation or prescribe automatic cleaning. Not included: label-noise estimation, drift, fairness, calibration, semantic date validation, fuzzy category normalization, feature correlation, compliance, or certification.',
  topics: [
    'Decision Summary', 'Priority Actions', 'Dataset Overview', 'Target and Label Evidence',
    'Missingness Evidence', 'Duplicate and Feature Evidence', 'Scoring, Methodology, and Limitations', 'Technical Appendix',
  ],
  findings: [
    {
      code: 'conflicting_target_labels',
      title: 'Potentially conflicting target labels',
      severity: 'Moderate',
      finding: '5 feature-identical groups contain more than one non-missing target label.',
      evidence: '10 labeled rows are included in these groups.',
      impact: 'Inconsistent labels for identical recorded features can introduce irreducible ambiguity or reveal missing time/entity context.',
      review: 'Review whether these are label errors, repeated entities over time, target updates, or omitted distinguishing features.',
      scoreEffect: 'Evidence only; this finding does not change any score or guardrail.',
      locus: { kind: 'rows', columns: ['annual_income_over_50k'], rows: (generated.conflicts as { rows: number[] }[]).flatMap((g) => g.rows) },
    },
    {
      code: 'target_imbalance',
      title: 'Target imbalance',
      severity: 'Moderate',
      finding: 'The target is dominated by one class, so headline accuracy may hide poor minority-class performance.',
      evidence: 'The majority-class baseline is 76.07%; majority-to-minority ratio: 3.18:1.',
      impact: 'A model may favor the majority class and underperform on less common outcomes.',
      review: 'Use class-sensitive metrics and consider resampling, weighting, or collecting more minority examples.',
      scoreEffect: 'Reduces the target-balance score and may trigger the critical-sub-score guardrail.',
      locus: { kind: 'target', columns: ['annual_income_over_50k'] },
    },
    {
      code: 'numeric_outlier_concentration',
      title: 'Numeric outlier concentration',
      severity: 'Moderate',
      finding: '1 numeric feature has notable IQR-based outlier rates.',
      evidence: 'Affected fields: hours_per_week.',
      impact: 'Extreme values can dominate some model families or indicate collection and unit inconsistencies.',
      review: 'Inspect the outlier rows and confirm whether they are real edge cases or data entry errors.',
      scoreEffect: 'Reduces the feature-usability score at the current outlier thresholds.',
      locus: { kind: 'column', columns: ['hours_per_week'] },
    },
    {
      code: 'leakage_review_prompts',
      title: 'Leakage review prompts',
      severity: 'Low',
      finding: 'Columns such as marital_status have generic status or target-related names, but their names alone are not strong leakage evidence.',
      evidence: '1 review-only candidate: marital_status.',
      impact: 'If a field is only available after the outcome, offline validation may not represent deployment.',
      review: 'Confirm when these values become available; this review prompt does not reduce the leakage score or cap the overall score.',
      scoreEffect: 'Evidence only; review-only leakage prompts do not change a score or guardrail.',
      locus: { kind: 'column', columns: ['marital_status'] },
    },
  ] as Finding[],
};

/** Packed per-row data for unit visualisations: 5 bytes per row in source order. */
export function decodeRows() {
  const bin = atob(rowsPacked.data);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const S = rowsPacked.stride;
  const n = bytes.length / S;
  const cls = new Uint8Array(n), miss = new Uint8Array(n), dup = new Uint8Array(n), hoursOut = new Uint8Array(n);
  const age = new Uint8Array(n), hours = new Uint8Array(n), conflict = new Uint8Array(n), dupGroup = new Uint8Array(n);
  for (let i = 0; i < n; i++) {
    const f = bytes[i * S];
    cls[i] = f & 1; miss[i] = (f >> 1) & 3; dup[i] = (f >> 3) & 1; hoursOut[i] = (f >> 4) & 1;
    age[i] = bytes[i * S + 1]; hours[i] = bytes[i * S + 2]; conflict[i] = bytes[i * S + 3]; dupGroup[i] = bytes[i * S + 4];
  }
  return { n, cls, miss, dup, hoursOut, age, hours, conflict, dupGroup };
}

export type Representation = 'tables' | 'outcomes' | 'time' | 'text' | 'images' | 'connected';

/** Local runs shown in every dashboard. Only classification runs carry a score. */
export const runs = [
  { id: 'adult', name: 'Adult', file: 'adult.csv', rep: 'tables' as Representation, task: 'Classification · binary', size: '48,842 × 15', score: 69.0, band: 'Elevated', findings: 4, when: '13 Aug 2026', runtime: '0.18 s', lead: '5 feature-identical groups disagree on the label' },
  { id: 'german', name: 'German Credit', file: 'german_credit.csv', rep: 'tables' as Representation, task: 'Classification · binary', size: '1,000 × 21', score: 91.84, band: 'Low', findings: 2, when: '13 Aug 2026', runtime: '0.03 s', lead: 'No guardrail applied; five review-only name prompts' },
  { id: 'bank', name: 'Bank Marketing', file: 'bank_marketing.csv', rep: 'tables' as Representation, task: 'Classification · binary', size: '45,211 × 17', score: 69.0, band: 'Elevated', findings: 3, when: '13 Aug 2026', runtime: '0.18 s', lead: 'Target balance 23.4 caps the score; prior-campaign outcome is review-only' },
  { id: 'bike', name: 'Bike sharing · hourly', file: 'bike_hour.csv', rep: 'outcomes' as Representation, task: 'Regression · single target', size: '17,379 × 17', score: null, band: null, findings: 4, when: '9 Oct 2026', runtime: '0.23 s', lead: 'cnt = casual + registered, both declared unavailable at prediction time' },
  { id: 'sms', name: 'SMS collection', file: 'sms.jsonl', rep: 'text' as Representation, task: 'Text corpus · labels', size: '5,574 records', score: null, band: null, findings: null, when: '11 Oct 2026', runtime: '—', lead: 'Near-duplicate candidates via calibrated MinHash search' },
  { id: 'coco', name: 'COCO val2017 subset', file: 'images/', rep: 'images' as Representation, task: 'Images · detection & segmentation', size: '128 images · 875 objects', score: null, band: null, findings: null, when: '12 Oct 2026', runtime: '—', lead: '61 ICC-bearing images excluded from default visual methods' },
  { id: 'finance', name: 'Finance records ↔ PDFs', file: 'records.csv + 21 PDFs', rep: 'connected' as Representation, task: 'Cross-representation', size: '20 records · 21 documents', score: null, band: null, findings: 2, when: '13 Oct 2026', runtime: '—', lead: '18 agreements · 1 discrepancy · 1 conflict with exact page locators' },
];

export const representations: { id: Representation; name: string; unit: string; checks: string[]; example: string }[] = [
  { id: 'tables', name: 'Tables', unit: 'row', checks: ['Profiling, missingness, duplicates', 'Conflicting labels for identical features', 'Name-based leakage: strong vs review-only', 'Transparent sub-scores and guardrails (classification)'], example: 'Adult · 48,842 × 15' },
  { id: 'outcomes', name: 'Outcomes', unit: 'value', checks: ['Explicit numerical targets and constraints', 'Bounded copy / affine / two-feature-sum relationships', 'Repeated-input target variation', 'No regression score, by design'], example: 'Bike hourly · cnt = casual + registered' },
  { id: 'time', name: 'Time', unit: 'event', checks: ['Exact clocks and declared availability', 'Coverage, schedules and panel populations', 'Feature-bound timing and revisions', 'Supplied evaluation plans'], example: 'Temporal CSV / Parquet' },
  { id: 'text', name: 'Text', unit: 'sentence', checks: ['Corpus, annotation, QA and conversations', 'Calibrated bounded near-duplicate search', 'Retrieval provenance', 'Private evidence resolution'], example: 'SMS · 5,574 records' },
  { id: 'images', name: 'Images', unit: 'image', checks: ['Coordinate and orientation compatibility', 'Bounded segmentation integrity', 'Perceptual candidates as review items', 'Optional pinned offline models'], example: 'COCO subset · 128 images, 875 objects' },
  { id: 'connected', name: 'Connected', unit: 'pair', checks: ['Records reconciled against native PDF/DOCX', 'Exact page / cell locators', 'Competing evidence retained, never hidden', 'Independent reviewer snapshots'], example: '20 records ↔ 21 PDFs' },
];

/** The guided M9 story counts come from docs/M9 and the master context; the `example` record is illustrative, shaped like the authored finance layout. */
export const finance = {
  records: 20, documents: 21, agreements: 18, discrepancies: 1, conflicts: 1,
  note: 'Agreement never hides conflicting evidence.',
  example: { entity: 'Entity 07', period: 'FY2025 Q2', record: 'revenue 41,250,000 INR', document: 'statement_07_q2.pdf · p.2 · table “Metric / Period / Value” · row Revenue', status: 'discrepancy' },
};

export const bike = {
  rows: 17379, columns: 17, relationship: 'cnt = casual + registered', declaredUnavailable: ['casual', 'registered'],
  outlier: 'casual: 1192 of 17379 finite values (6.86%)', nearConstant: 'holiday: 2 observed values, 97.12% top share', runtime: 0.2316,
};

export const local = {
  host: '127.0.0.1',
  uploadLimit: '100 MiB default',
  facts: [
    { value: '127.0.0.1', label: 'Browser UI binds to loopback only' },
    { value: '0', label: 'Network calls at analysis time; models are never downloaded at runtime' },
    { value: '0.18 s', label: 'Adult audit, 48,842 rows, recorded locally' },
    { value: '3', label: 'Report formats: canonical HTML, PDF, strict JSON' },
  ],
  commands: ['datatrust audit adult.csv --target annual_income_over_50k --out adult.pdf --format pdf --json-out adult.json', 'datatrust ui'],
  /** What the CLI prints for the command above (src/datatrust/cli.py _print_artifacts). */
  cliOutput: ['HTML report: adult.html', 'PDF report: adult.pdf', 'JSON report: adult.json'],
};

export const formats = [
  { name: 'HTML', note: 'Canonical, standalone eight-topic report' },
  { name: 'PDF', note: 'Portrait decision pages + landscape technical appendix' },
  { name: 'JSON', note: 'Strict, complete computed evidence' },
];

export const company = {
  name: 'NUMEK',
  line: 'AI reliability verification',
  product: 'DataTrust',
  productLine: 'Evidence-based reliability analysis for the datasets behind ML and AI systems.',
  direction: 'ConfidenceGuard and HallucinationGuard are research directions, not products.',
};

/** Findings per run, from validation_summary.json, the Bike hour JSON report and the M9 story. */
export const runFindings: Record<string, { title: string; severity: Severity; evidence: string; effect: 'score' | 'evidence' | 'none-defined' }[]> = {
  adult: adult.findings.map((f) => ({ title: f.title, severity: f.severity, evidence: f.evidence, effect: f.scoreEffect.startsWith('Evidence only') ? 'evidence' : 'score' })),
  german: [
    { title: 'Numeric outlier concentration', severity: 'Moderate', evidence: 'Affected fields: duration_months, credit_amount.', effect: 'score' },
    { title: 'Leakage review prompts', severity: 'Low', evidence: '5 review-only candidates: checking_account_status, credit_history, credit_amount, savings_status, personal_status_sex.', effect: 'evidence' },
  ],
  bank: [
    { title: 'Target imbalance', severity: 'Moderate', evidence: 'The majority-class baseline is 88.3%; majority-to-minority ratio: 7.55:1.', effect: 'score' },
    { title: 'Numeric outlier concentration', severity: 'Moderate', evidence: 'Affected fields: balance, duration, campaign.', effect: 'score' },
    { title: 'Leakage review prompts', severity: 'Low', evidence: '1 review-only candidate: previous_campaign_outcome.', effect: 'evidence' },
  ],
  bike: [
    { title: 'Columns declared unavailable at prediction time', severity: 'High', evidence: 'casual, registered', effect: 'none-defined' },
    { title: 'Supported target relationships', severity: 'High', evidence: 'cnt = casual + registered', effect: 'none-defined' },
    { title: 'IQR review candidates', severity: 'Moderate', evidence: 'casual: 1192 of 17379 finite values (6.86%)', effect: 'none-defined' },
    { title: 'Near-constant fields', severity: 'Low', evidence: 'holiday: 2 observed values, 97.12% top share', effect: 'none-defined' },
  ],
  finance: [
    { title: 'Record and document disagree', severity: 'High', evidence: '1 discrepancy with exact page and cell locator', effect: 'none-defined' },
    { title: 'Competing document evidence', severity: 'High', evidence: '1 conflict: documents support different values; both retained', effect: 'none-defined' },
  ],
};

export const subScoresByRun: Record<string, { label: string; value: number }[]> = {
  adult: adult.subScores,
  german: [{ label: 'Completeness', value: 100 }, { label: 'Uniqueness', value: 100 }, { label: 'Target balance', value: 60 }, { label: 'Feature usability', value: 99.2 }, { label: 'Leakage risk', value: 100 }],
  bank: [{ label: 'Completeness', value: 100 }, { label: 'Uniqueness', value: 100 }, { label: 'Target balance', value: 23.4 }, { label: 'Feature usability', value: 98.5 }, { label: 'Leakage risk', value: 100 }],
};
