import { adult, bike, finance, runFindings } from '../../fixture';

export interface Trace { title: string; severity: string; effect: string; steps: { k: string; v: string; o?: boolean }[] }

/** Evidence trails for each finding: every step is a fact from the run's report or source. */
export const traces: Record<string, Trace[]> = {
  adult: [
    { title: 'Potentially conflicting target labels', severity: 'Moderate', effect: 'Evidence only', steps: [
      { k: 'Source', v: 'adult.csv · lines 16,685 and 34,344 (and four more pairs)' },
      { k: 'Compare', v: 'Rows identical on all 14 features' },
      { k: 'Conflict', v: 'Labels >50K and <=50K · 5 groups · 10 rows', o: true },
      { k: 'Finding', v: 'conflicting_target_labels · no score or guardrail effect' },
      { k: 'Report', v: 'Priority action 1 · topic 6, Duplicate and Feature Evidence' },
    ] },
    { title: 'Target imbalance', severity: 'Moderate', effect: 'Lowers target balance', steps: [
      { k: 'Column', v: 'annual_income_over_50k · 37,155 / 11,687' },
      { k: 'Measure', v: 'Majority class 76.07% ≥ 75% threshold' },
      { k: 'Score', v: 'Target balance 100 − (76.07 − 50) / 50 × 100 = 47.86', o: true },
      { k: 'Guardrail', v: 'Sub-score ≤ 50 → critical_sub_score → cap 69.0' },
      { k: 'Report', v: 'Decision summary · topic 4, Target and Label Evidence' },
    ] },
    { title: 'Numeric outlier concentration', severity: 'Moderate', effect: 'Lowers feature usability', steps: [
      { k: 'Column', v: 'hours_per_week · quartiles 40 and 45' },
      { k: 'Fences', v: '1.5 × IQR → 32.5 and 52.5 hours' },
      { k: 'Measure', v: '13,496 values outside · 27.63% ≥ 5%', o: true },
      { k: 'Score', v: 'Usability penalty 8 (≥ 10%) · feature usability 98.86' },
      { k: 'Report', v: 'Priority action 3 · technical appendix' },
    ] },
    { title: 'Leakage review prompts', severity: 'Low', effect: 'Evidence only', steps: [
      { k: 'Column', v: 'marital_status' },
      { k: 'Name check', v: 'Generic status-like name · review only', o: true },
      { k: 'Score', v: 'No penalty · leakage risk stays 100' },
      { k: 'Report', v: 'Priority action 4 · topic 6' },
    ] },
  ],
  bike: [
    { title: 'Supported target relationship', severity: 'High', effect: 'No score defined', steps: [
      { k: 'Source', v: 'bike_hour.csv · 17,379 rows × 17 columns' },
      { k: 'Search', v: 'Bounded copy, affine and two-feature-sum relationships' },
      { k: 'Relationship', v: `${bike.relationship} · holds on every row`, o: true },
      { k: 'Context', v: 'casual and registered declared unavailable at prediction time' },
      { k: 'Report', v: 'High · verify availability; algebra alone does not prove leakage' },
    ] },
  ],
  finance: [
    { title: 'Record and document disagree', severity: 'High', effect: 'No score defined', steps: [
      { k: 'Source', v: `${finance.records} records · ${finance.documents} native PDFs` },
      { k: 'Mapping', v: 'Reusable table mapping: Metric · Period · Value' },
      { k: 'Reconcile', v: `${finance.agreements} agree · ${finance.discrepancies} discrepancy · ${finance.conflicts} conflict`, o: true },
      { k: 'Locate', v: 'Exact document · page · table · row, resolved privately' },
      { k: 'Report', v: 'Competing evidence retained; agreement never hides conflict' },
    ] },
  ],
};

export const traceCount = (id: string) => traces[id]?.length ?? (runFindings[id]?.length ?? 0);
export { adult };
