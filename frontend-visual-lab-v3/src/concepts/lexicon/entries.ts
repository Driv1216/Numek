// Nine words for what DataTrust looks for, and one for what remains. Every
// fragment is a value from the fixture (reports, generated profiles, M9 story).
import bikeHours from '../../fixture/bike-hours.generated.json';
import { adult, bike, finance } from '../../fixture';

export type FragKind = 'num' | 'mono' | 'text' | 'row' | 'code';
export interface Frag { t: string; k: FragKind; cap?: string }
export interface Entry {
  id: string;
  word: string;
  pos: string;
  sense: string;
  def: string;
  in: { run: string; line: string }[];
  effect: string;
  frags: Frag[];
}

const g = adult.conflicts[0];
const csv = (vals: (string | number | null)[]) => vals.map((v) => String(v ?? '')).join(',');
const conflictLine = (label: string) => csv([...Object.values(g.features), label]);
const hr = (bikeHours.hours as { t: string; casual: number; registered: number; cnt: number }[]).find((h) => h.t === '2011-01-08 10:00')!;
const h = adult.hours;

export const entries: Entry[] = [
  {
    id: 'ambiguity', word: 'Ambiguity', pos: 'n.', sense: 'conflicting target labels',
    def: 'The state of two rows that agree on every feature and disagree on the answer.',
    in: [{ run: 'Adult', line: `${adult.conflicts.length} feature-identical groups, ${adult.conflicts.reduce((s, x) => s + x.rows.length, 0)} rows. Rows ${g.rows.map((r) => r.toLocaleString()).join(' and ')} are the first.` }],
    effect: 'Evidence only — no score or guardrail changes.',
    frags: [
      { t: conflictLine(g.labels[0]), k: 'row', cap: `row ${g.rows[0].toLocaleString()}` },
      { t: conflictLine(g.labels[1]), k: 'row', cap: `row ${g.rows[1].toLocaleString()}` },
      { t: '14 of 14', k: 'num', cap: 'features equal' },
      { t: `${g.labels[0]}  ≠  ${g.labels[1]}`, k: 'mono' },
      { t: '"code": "conflicting_target_labels"', k: 'code' },
      { t: String(adult.conflicts.length), k: 'num', cap: 'groups' },
      { t: 'Review whether these are label errors, repeated entities over time, target updates, or omitted distinguishing features.', k: 'text' },
      { t: 'Craft-repair · Husband · 40 h', k: 'mono' },
    ],
  },
  {
    id: 'imbalance', word: 'Imbalance', pos: 'n.', sense: 'target imbalance',
    def: 'A target in which one answer is so common that guessing it looks like skill.',
    in: [
      { run: 'Adult', line: `${adult.majorityBaseline}% majority, ${adult.ratio}. Target balance ${adult.subScores[2].value} is critical and caps the score at 69.` },
      { run: 'Bank Marketing', line: 'Majority 88.3%, 7.55 : 1. Target balance 23.4, capped at 69.' },
    ],
    effect: 'Changes the target-balance sub-score; can cap the final score.',
    frags: [
      { t: `${adult.majorityBaseline}%`, k: 'num', cap: 'majority baseline' },
      { t: adult.ratio, k: 'num', cap: 'majority : minority' },
      { t: adult.classes.le50k.toLocaleString(), k: 'num', cap: '≤50K' },
      { t: adult.classes.gt50k.toLocaleString(), k: 'num', cap: '>50K' },
      { t: `target_balance  ${adult.subScores[2].value}`, k: 'mono' },
      { t: '"code": "critical_sub_score", "cap": 69.0', k: 'code' },
      { t: 'Headline accuracy may hide poor minority-class performance.', k: 'text' },
      { t: '88.3%', k: 'num', cap: 'Bank Marketing' },
    ],
  },
  {
    id: 'absence', word: 'Absence', pos: 'n.', sense: 'missing values',
    def: 'A cell that should hold a value and holds nothing.',
    in: [{ run: 'Adult', line: `${adult.missing.cells.toLocaleString()} empty cells in three columns, touching ${(adult.missing.rows.one + adult.missing.rows.two + adult.missing.rows.three_plus).toLocaleString()} rows (${adult.missing.rowRate}%). No missingness finding in this run.` }],
    effect: 'Feeds the completeness sub-score (99.12).',
    frags: [
      { t: adult.missing.byColumn.occupation.toLocaleString(), k: 'num', cap: 'occupation' },
      { t: adult.missing.byColumn.workclass.toLocaleString(), k: 'num', cap: 'workclass' },
      { t: String(adult.missing.byColumn.native_country), k: 'num', cap: 'native_country' },
      { t: `${adult.missing.cellRate}%`, k: 'num', cap: 'of feature cells' },
      { t: 'workclass ,  , occupation ,  ', k: 'mono' },
      { t: `one gap ${adult.missing.rows.one} · two ${adult.missing.rows.two.toLocaleString()} · three+ ${adult.missing.rows.three_plus}`, k: 'mono' },
      { t: 'DataTrust does not impute or fill anything.', k: 'text' },
      { t: `completeness  ${adult.subScores[0].value}`, k: 'mono' },
    ],
  },
  {
    id: 'excess', word: 'Excess', pos: 'n.', sense: 'numeric outlier concentration',
    def: 'Values beyond the fences drawn one and a half interquartile ranges from the middle.',
    in: [
      { run: 'Adult', line: `hours_per_week: ${h.outliers.toLocaleString()} rows outside ${h.lower} – ${h.upper} (27.63%).` },
      { run: 'German Credit', line: 'duration_months, credit_amount.' },
      { run: 'Bike sharing', line: bike.outlier + '.' },
    ],
    effect: 'Reduces the feature-usability sub-score. Nothing is clipped or deleted.',
    frags: [
      { t: `${h.lower} – ${h.upper}`, k: 'num', cap: 'fences, hours' },
      { t: h.outliers.toLocaleString(), k: 'num', cap: 'rows outside' },
      { t: `Q1 ${h.q1} · Q3 ${h.q3}`, k: 'mono' },
      { t: `${h.below.toLocaleString()} below · ${h.above.toLocaleString()} above`, k: 'mono' },
      { t: '46.69%', k: 'num', cap: 'answer “40 hours”' },
      { t: 'Inspect the outlier rows and confirm whether they are real edge cases or data entry errors.', k: 'text' },
      { t: '"code": "numeric_outlier_concentration"', k: 'code' },
      { t: '6.86%', k: 'num', cap: 'casual, Bike' },
    ],
  },
  {
    id: 'hindsight', word: 'Hindsight', pos: 'n.', sense: 'leakage',
    def: 'A feature that is only known once the outcome has happened.',
    in: [
      { run: 'Adult', line: 'marital_status — a review-only name prompt. Leakage risk stays at 100.' },
      { run: 'Bank Marketing', line: 'previous_campaign_outcome — review only.' },
      { run: 'Bike sharing', line: `${bike.declaredUnavailable.join(', ')} — declared unavailable at prediction time. High.` },
    ],
    effect: 'Strong evidence caps the score at 49; a name alone is only a prompt.',
    frags: [
      { t: 'marital_status', k: 'mono', cap: 'review only' },
      { t: 'previous_campaign_outcome', k: 'mono', cap: 'review only' },
      { t: 'casual · registered', k: 'mono', cap: 'declared unavailable' },
      { t: '49', k: 'num', cap: 'cap on strong leakage' },
      { t: 'If a field is only available after the outcome, offline validation may not represent deployment.', k: 'text' },
      { t: '"code": "leakage_review_prompts"', k: 'code' },
      { t: '100', k: 'num', cap: 'leakage risk, Adult' },
    ],
  },
  {
    id: 'tautology', word: 'Tautology', pos: 'n.', sense: 'supported target relationship',
    def: 'A target that can be rebuilt, exactly, from the features beside it.',
    in: [{ run: 'Bike sharing', line: `${bike.relationship} holds on all ${bike.rows.toLocaleString()} rows.` }],
    effect: 'High finding. Regression has no universal score, so none is given.',
    frags: [
      { t: bike.relationship, k: 'num' },
      { t: `${hr.t}  ${hr.casual} + ${hr.registered} = ${hr.cnt}`, k: 'mono', cap: 'bike_hour.csv' },
      { t: `${bike.rows.toLocaleString()} / ${bike.rows.toLocaleString()}`, k: 'num', cap: 'rows where it holds' },
      { t: 'copy · affine · two-feature sum', k: 'mono', cap: 'bounded searches' },
      { t: 'No score defined.', k: 'text' },
      { t: '"task": "regression"', k: 'code' },
      { t: `${bike.declaredUnavailable.join(' + ')}`, k: 'mono', cap: 'unavailable at prediction' },
    ],
  },
  {
    id: 'repetition', word: 'Repetition', pos: 'n.', sense: 'duplicate rows',
    def: 'The same row, written down more than once.',
    in: [{ run: 'Adult', line: `${adult.duplicates.groups} groups, ${adult.duplicates.repeated_rows} repeated rows; the largest group has ${adult.duplicates.largest} copies.` }],
    effect: 'Feeds the uniqueness sub-score (99.89). Reported, never removed.',
    frags: [
      { t: String(adult.duplicates.repeated_rows), k: 'num', cap: 'repeated rows' },
      { t: String(adult.duplicates.groups), k: 'num', cap: 'groups' },
      { t: `× ${adult.duplicates.largest}`, k: 'num', cap: 'largest group' },
      { t: `uniqueness  ${adult.subScores[1].value}`, k: 'mono' },
      { t: `${adult.duplicates.rows_in_groups} rows in groups`, k: 'mono' },
      { t: 'Duplicates are reported, never removed.', k: 'text' },
    ],
  },
  {
    id: 'discrepancy', word: 'Discrepancy', pos: 'n.', sense: 'record and document disagree',
    def: 'A number in a table that its own source document does not say.',
    in: [{ run: 'Finance records ↔ PDFs', line: `${finance.records} records against ${finance.documents} PDFs: ${finance.agreements} agree, ${finance.discrepancies} disagrees, ${finance.conflicts} conflicts — each with a page locator.` }],
    effect: 'High. Competing evidence is retained, never hidden.',
    frags: [
      { t: `${finance.agreements}`, k: 'num', cap: 'agreements' },
      { t: `${finance.discrepancies}`, k: 'num', cap: 'discrepancy' },
      { t: `${finance.conflicts}`, k: 'num', cap: 'conflict' },
      { t: 'page · table · row · cell', k: 'mono', cap: 'locator' },
      { t: finance.note, k: 'text' },
      { t: `${finance.records} records ↔ ${finance.documents} PDFs`, k: 'mono' },
    ],
  },
  {
    id: 'constancy', word: 'Constancy', pos: 'n.', sense: 'near-constant field',
    def: 'A column that nearly always says the same thing, and so says little.',
    in: [
      { run: 'Adult', line: 'capital_loss — 95.33% one value.' },
      { run: 'Bike sharing', line: bike.nearConstant + '.' },
    ],
    effect: 'A feature-usability penalty in scored runs; Low elsewhere.',
    frags: [
      { t: '95.33%', k: 'num', cap: 'capital_loss = 0' },
      { t: '97.12%', k: 'num', cap: 'holiday' },
      { t: 'near_constant: Yes', k: 'code' },
      { t: '2 observed values', k: 'mono', cap: 'holiday' },
      { t: 'capital_loss  0 0 0 0 0 0 0 0 0 0', k: 'mono' },
    ],
  },
];

export const closing = {
  word: 'Reliability', pos: 'n.',
  def: 'What can be said about a dataset once each of the words above has been looked for — under a stated method, with its limits.',
  adult: `Adult: ${adult.finalScore.toFixed(1)}, ${adult.band} — evidence ${adult.evidenceScore}, held at the 69 cap.`,
  bike: 'Bike sharing: no score. Regression has no universal one, by design.',
  limits: adult.limits,
};
