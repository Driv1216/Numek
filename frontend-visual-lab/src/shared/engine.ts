// Round-two product content: real DataTrust engine output.
// Produced by `datatrust audit` (research/engine/*.json) and packed by
// research/extract_engine.py together with the actual conflicting CSV rows.
import raw from './engine.json';

export interface EngineFinding {
  code: string;
  title: string;
  finding: string;
  evidence: string;
  modeling_impact: string;
  recommendation: string;
  severity: 'High' | 'Moderate' | 'Low';
  score_effect: string;
}

export interface ColumnProfile {
  name: string;
  dtype: string;
  role: string;
  is_numeric: boolean;
  missing_count: number;
  missing_rate: number;
  unique_count: number;
  top_value: string;
  top_value_rate: number;
  outlier_count: number;
  outlier_rate: number;
  near_constant: boolean;
  high_cardinality: boolean;
  q?: [number, number, number, number, number];
  zero_rate?: number;
}

interface Run {
  name: string;
  rows: number;
  columns: number;
  score: number;
  evidence: number;
  band: string;
  action: string;
  sub: Record<string, number>;
  guardrails: { code: string; cap: number; explanation: string }[];
  findings: EngineFinding[];
  narrative: Record<string, string | number>;
  sha256: string;
  elapsed: number;
  methodology: string;
  generated: string;
  leakage: { column: string; classification: string; reason: string }[];
}

const r = raw as unknown as {
  adult: Run & {
    columns_profile: ColumnProfile[];
    checks: { id: string; execution: string; method: string; population: string; denominator: number | null; affected: number | null }[];
    coverage: { completed_applicable_checks: number; unsupported_capabilities: string[]; meaning: string };
    profile: Record<string, number> & { target_distribution: { label: string; count: number; percentage: number }[] };
    parsing_warning: string;
    source_bytes: number;
  };
  leak: Run;
  conflict_groups: Record<string, string>[][];
  sample_rows: Record<string, string>[];
};

export const run = r.adult;
export const leakRun = r.leak;
export const conflictGroups = r.conflict_groups;
export const sampleRows = r.sample_rows;
export const columnsProfile = r.adult.columns_profile;
export const checks = r.adult.checks;

export const SUB_LABELS: Record<string, string> = {
  completeness: 'Completeness',
  uniqueness: 'Uniqueness',
  feature_usability: 'Feature usability',
  leakage_risk: 'Leakage risk',
  target_balance: 'Target balance',
};
export const SUB_ORDER = ['completeness', 'uniqueness', 'feature_usability', 'leakage_risk', 'target_balance'];

export const CHECK_LABELS: Record<string, string> = {
  schema: 'Schema',
  missingness: 'Missingness',
  column_variation: 'Column variation',
  categorical_cardinality: 'Categorical cardinality',
  exact_duplicates: 'Exact duplicates',
  classification_target: 'Target distribution',
  label_conflicts: 'Label conflicts',
  target_leakage: 'Target leakage',
  numeric_summary: 'Numeric summary',
  numeric_outliers: 'Numeric outliers',
  classification_scoring: 'Scoring and guardrails',
  parsing_fidelity: 'Parsing fidelity',
};

/** 1.5 × IQR fences derived from the engine's own quartiles for a numeric column. */
export function fences(c: ColumnProfile) {
  if (!c.q) return null;
  const iqr = c.q[3] - c.q[1];
  return [c.q[1] - 1.5 * iqr, c.q[3] + 1.5 * iqr] as const;
}

export const hours = columnsProfile.find((c) => c.name === 'hours_per_week')!;
export const shortSha = run.sha256.slice(0, 12);

/** Real terminal transcript of the run used for this content. */
export const cliTranscript = [
  '$ datatrust audit adult.csv --target annual_income_over_50k \\',
  '    --out adult.html --json-out adult.json',
  'Parsing review: inspection_incomplete: Inspection stopped at record_limit;',
  '  absence of warnings does not establish losslessness.',
  'HTML report: adult.html',
  'JSON report: adult.json',
];

export const nf = (n: number) => n.toLocaleString('en-US');
export const pc = (n: number, d = 2) => `${n.toFixed(d)}%`;
