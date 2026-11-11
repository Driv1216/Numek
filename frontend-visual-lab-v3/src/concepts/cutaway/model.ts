// DataTrust's published scoring rules, used for the "what if" control. This is a calculation shown
// next to the drawing, not a product feature: evidence = mean of five sub-scores; binary target
// balance = 100 − (majority − 50) / 50 × 100; any sub-score ≤ 50 caps the final score at 69.
import { adult, runs, runFindings, subScoresByRun } from '../../fixture';

export const SUBS = adult.subScores.map((s) => ({ label: s.label, value: s.value }));

export function whatIf(majorityPct: number) {
  const balance = Math.round((100 - ((majorityPct - 50) / 50) * 100) * 100) / 100;
  const subs = SUBS.map((s) => (s.label === 'Target balance' ? { ...s, value: balance } : s));
  const evidence = Math.round((subs.reduce((a, s) => a + s.value, 0) / subs.length) * 100) / 100;
  const capped = subs.some((s) => s.value <= 50);
  const final = capped ? Math.min(evidence, 69) : evidence;
  const band = final >= 85 ? 'Low' : final >= 70 ? 'Moderate' : final >= 50 ? 'Elevated' : 'High';
  return { balance, subs, evidence, capped, final, band, finding: majorityPct >= 75 };
}

export const SCENARIOS: [string, number][] = [['As recorded', adult.majorityBaseline], ['70 / 30', 70], ['60 / 40', 60], ['50 / 50', 50]];

export const tabular = ['adult', 'german', 'bank', 'bike'];
export { runs, runFindings, subScoresByRun };
