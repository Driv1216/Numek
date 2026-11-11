// Questions the instrument can be asked, per run. Every answer line is a real value.
import { adult, bike, runFindings } from '../../fixture';
import type { Mode } from './dial';

export interface Q { q: string; mode: Mode; answer: [string, string][]; note: string; marks?: number[]; json?: string }

const allConflictRows = adult.conflicts.flatMap((g) => g.rows);
const ce = Object.fromEntries(adult.columnEvidence.map((c) => [c.name, c]));

export const questions: Record<string, Q[]> = {
  adult: [
    { q: 'What held the score at 69?', mode: 'target', answer: [['target_balance', '47.86 ≤ 50'], ['guardrail', 'critical_sub_score'], ['evidence', '89.15'], ['final', '69.0 · Elevated']], note: 'The target sector: 37,155 rows at ≤50K, 11,687 above. A 76.07% majority sets target balance at 47.86 — critical — so the final score is capped.', json: 'guardrail code · critical_sub_score · cap 69.0' },
    { q: 'Which rows disagree on the label?', mode: 'conflict', answer: adult.conflicts.map((g) => [`group ${g.id}`, g.rows.map((r) => r.toLocaleString()).join(' · ')] as [string, string]), note: '5 feature-identical groups, 10 rows. Each pair agrees on all fourteen features and carries different labels. Evidence only — no score changes.', marks: allConflictRows, json: 'finding code · conflicting_target_labels' },
    { q: 'What sits outside the fences?', mode: 'outliers', answer: ['age', 'final_weight', 'education_years', 'hours_per_week'].map((n) => [n, ce[n].outliers] as [string, string]), note: 'Red rings lie beyond 1.5 × IQR. Only hours_per_week passes the 5% threshold for a finding (27.63%); capital_gain and capital_loss have an IQR of 0, so no fence is drawn.', json: 'finding code · numeric_outlier_concentration' },
    { q: 'Where are values missing?', mode: 'missing', answer: Object.entries(adult.missing.byColumn).map(([k, v]) => [k, `${v.toLocaleString()} · ${((v / adult.rows) * 100).toFixed(2)}%`] as [string, string]), note: `${adult.missing.cells.toLocaleString()} empty cells touch ${(adult.missing.rows.one + adult.missing.rows.two + adult.missing.rows.three_plus).toLocaleString()} rows (${adult.missing.rowRate}%). Completeness 99.12 — no finding.` },
    { q: 'Which names need review?', mode: 'leak', answer: [['marital_status', 'review only'], ['leakage risk', '100'], ['strong evidence', 'would cap at 49']], note: 'A status-like name is a prompt to confirm when the value becomes known. It changes no score.', json: 'finding code · leakage_review_prompts' },
    { q: 'How was the score made?', mode: 'score', answer: adult.subScores.map((s) => [s.label, String(s.value)] as [string, string]), note: 'Evidence is the mean of five sub-scores: 89.15. Any sub-score at or below 50 caps the result at 69.' },
  ],
  german: [
    { q: 'Was any cap applied?', mode: 'score', answer: [['Completeness', '100'], ['Uniqueness', '100'], ['Target balance', '60'], ['Feature usability', '99.2'], ['Leakage risk', '100']], note: 'No sub-score at or below 50, so no guardrail: the final score is the evidence mean, 91.8 · Low.' },
    { q: 'What sits outside the fences?', mode: 'outliers', answer: [['fields', 'duration_months, credit_amount']], note: runFindings.german[0].evidence },
    { q: 'Which names need review?', mode: 'leak', answer: [['review only', '5 columns']], note: runFindings.german[1].evidence },
  ],
  bank: [
    { q: 'What held the score at 69?', mode: 'target', answer: [['majority', '88.3%'], ['ratio', '7.55 : 1'], ['target balance', '23.4 · critical'], ['final', '69.0 · Elevated']], note: runFindings.bank[0].evidence },
    { q: 'What sits outside the fences?', mode: 'outliers', answer: [['fields', 'balance, duration, campaign']], note: runFindings.bank[1].evidence },
    { q: 'Which names need review?', mode: 'leak', answer: [['previous_campaign_outcome', 'review only']], note: runFindings.bank[2].evidence },
  ],
  bike: [
    { q: 'Is the target inside the features?', mode: 'relation', answer: [['relationship', bike.relationship], ['holds on', '17,379 / 17,379 rows'], ['score', 'none defined']], note: 'casual and registered add up to cnt on every row, and both are declared unavailable at prediction time. Regression has no universal score, so the score dial stays empty.' },
    { q: 'What sits outside the fences?', mode: 'outliers', answer: [['casual', '1,192 of 17,379 (6.86%)']], note: 'IQR review candidates in casual. Reported, not removed.' },
  ],
};
