// The fourteen modules of DataTrust as NUMEK presents them here. Every number is
// read from the shared fixture (validation evidence, reports, M9 story); nothing
// below adds a capability the product does not have.
import { adult, bike, finance, local } from '../content';

export type ModId = 'score' | 'gaps' | 'dups' | 'conflicts' | 'imbalance' | 'leakage' | 'outliers' | 'relations' | 'time' | 'text' | 'images' | 'docs' | 'local' | 'reports';
export type Effect = 'score' | 'evidence' | 'none-defined' | 'guardrail' | 'property';

export interface Mod {
  id: ModId;
  n: string;
  name: string;
  /** Tile background and whether its ink is light. */
  bg: string;
  light?: boolean;
  /** Where it sits in the 6 × 5 desktop mosaic. */
  area: string;
  rep: string;
  line: string;
  /** A short real figure shown on the tile. */
  figure: string;
  figureNote: string;
  body: string;
  facts: [string, string][];
  effect: Effect;
  effectNote: string;
  not: string;
}

const pct = (a: number, b: number) => ((a / b) * 100).toFixed(2);
const h = adult.hours;

export const mods: Mod[] = [
  {
    id: 'score', n: '01', name: 'Score', bg: '#1d2440', light: true, area: 's', rep: 'Classification',
    line: 'A score, only where one is defined.',
    figure: adult.finalScore.toFixed(1), figureNote: `Adult · ${adult.band}`,
    body: `For classification tables, five sub-scores are averaged into an evidence score — ${adult.evidenceScore} for Adult. Guardrails then cap it: any sub-score at or below 50 holds the result at 69. Target balance is ${adult.subScores[2].value}, so Adult ends at ${adult.finalScore.toFixed(1)}, ${adult.band}. Regression, time, text, image and document runs report evidence without a universal score.`,
    facts: [['Evidence score', String(adult.evidenceScore)], ['Guardrail', 'Critical sub-score → cap 69'], ['Final', `${adult.finalScore.toFixed(1)} · ${adult.band}`], ['Bands', '≥85 Low · 70–84 Moderate · 50–69 Elevated · <50 High']],
    effect: 'guardrail', effectNote: 'The score is the sum of what the other modules found — and the caps they trigger.',
    not: 'No score is invented for regression, time, text, images or documents.',
  },
  {
    id: 'gaps', n: '02', name: 'Gaps', bg: '#f5b83d', area: 'g', rep: 'Tables',
    line: 'Where values are missing, and how many rows it touches.',
    figure: `${adult.missing.rowRate}%`, figureNote: 'of Adult rows have a gap',
    body: `${adult.missing.cells.toLocaleString()} cells are empty — ${adult.missing.cellRate}% of feature cells — across three columns. They touch ${(adult.missing.rows.one + adult.missing.rows.two + adult.missing.rows.three_plus).toLocaleString()} rows. Each dot below is one real row of Adult, in file order; hollow dots have at least one gap.`,
    facts: [['workclass', `${adult.missing.byColumn.workclass.toLocaleString()} missing`], ['occupation', `${adult.missing.byColumn.occupation.toLocaleString()} missing`], ['native_country', `${adult.missing.byColumn.native_country.toLocaleString()} missing`], ['Completeness', String(adult.subScores[0].value)]],
    effect: 'score', effectNote: 'Feeds the completeness sub-score.',
    not: 'DataTrust does not impute or fill anything.',
  },
  {
    id: 'dups', n: '03', name: 'Duplicates', bg: '#e3ddcf', area: 'd', rep: 'Tables',
    line: 'Rows that appear more than once.',
    figure: String(adult.duplicates.repeated_rows), figureNote: 'repeated rows',
    body: `${adult.duplicates.groups} groups of exact duplicates hold ${adult.duplicates.rows_in_groups} rows; ${adult.duplicates.repeated_rows} of them are repeats. The largest group has ${adult.duplicates.largest} copies.`,
    facts: [['Groups', String(adult.duplicates.groups)], ['Repeated rows', String(adult.duplicates.repeated_rows)], ['Largest group', String(adult.duplicates.largest)], ['Uniqueness', String(adult.subScores[1].value)]],
    effect: 'score', effectNote: 'Feeds the uniqueness sub-score.',
    not: 'Duplicates are reported, never removed.',
  },
  {
    id: 'conflicts', n: '04', name: 'Conflicts', bg: '#ef5b3c', area: 'c', rep: 'Tables',
    line: 'Identical features, different labels.',
    figure: String(adult.conflicts.length), figureNote: 'groups disagree',
    body: `${adult.conflicts.length} groups of rows share all fourteen features yet carry different labels — ${adult.conflicts.reduce((s, g) => s + g.rows.length, 0)} rows in total. Rows ${adult.conflicts[0].rows.map((r) => r.toLocaleString()).join(' and ')} are the first pair.`,
    facts: [['Groups', String(adult.conflicts.length)], ['Rows', String(adult.conflicts.reduce((s, g) => s + g.rows.length, 0))], ['Features equal', '14 of 14'], ['Severity', 'Moderate']],
    effect: 'evidence', effectNote: 'Evidence only — this finding does not change any score or guardrail.',
    not: 'It cannot say which label is right. It asks a person to look.',
  },
  {
    id: 'imbalance', n: '05', name: 'Imbalance', bg: '#c9bdf5', area: 'i', rep: 'Classification',
    line: 'One class dominating the target.',
    figure: `${adult.majorityBaseline}%`, figureNote: 'majority class',
    body: `${adult.classes.le50k.toLocaleString()} rows at ≤50K, ${adult.classes.gt50k.toLocaleString()} above — a ${adult.ratio} ratio. The target-balance sub-score falls to ${adult.subScores[2].value}, which is critical and caps the dataset at 69.`,
    facts: [['≤50K', adult.classes.le50k.toLocaleString()], ['>50K', adult.classes.gt50k.toLocaleString()], ['Ratio', adult.ratio], ['Target balance', `${adult.subScores[2].value} · critical`]],
    effect: 'guardrail', effectNote: 'Changes the score and triggers the critical-sub-score guardrail.',
    not: 'It does not resample or reweight.',
  },
  {
    id: 'leakage', n: '06', name: 'Leakage', bg: '#2a2a2e', light: true, area: 'l', rep: 'Tables · Outcomes',
    line: 'Columns that may know the answer.',
    figure: '1', figureNote: 'review-only prompt',
    body: 'Strong leakage evidence — a column that copies or reconstructs the target — caps the score at 49. Names alone are weaker: marital_status in Adult is a review-only prompt and changes nothing. In Bike, casual and registered are declared unavailable at prediction time.',
    facts: [['Adult', 'marital_status · review only'], ['Leakage risk', String(adult.subScores[4].value)], ['Bike', bike.declaredUnavailable.join(', ') + ' · declared unavailable'], ['Strong evidence', 'caps at 49']],
    effect: 'evidence', effectNote: 'Review-only prompts are evidence; strong evidence would cap the score.',
    not: 'A column name is never treated as proof.',
  },
  {
    id: 'outliers', n: '07', name: 'Outliers', bg: '#bfe0a0', area: 'o', rep: 'Tables · Outcomes',
    line: 'Values far outside the middle half.',
    figure: `${pct(h.outliers, adult.rows)}%`, figureNote: 'hours_per_week outside fences',
    body: `Quartiles at ${h.q1} and ${h.q3} hours put the 1.5 × IQR fences at ${h.lower} and ${h.upper}. ${h.outliers.toLocaleString()} rows sit outside — ${h.below.toLocaleString()} below, ${h.above.toLocaleString()} above. Every bar below is one real hour value, 1 to 99.`,
    facts: [['Fences', `${h.lower} – ${h.upper}`], ['Below', h.below.toLocaleString()], ['Above', h.above.toLocaleString()], ['Feature usability', String(adult.subScores[3].value)]],
    effect: 'score', effectNote: 'Reduces the feature-usability score at the current thresholds.',
    not: 'Nothing is deleted or clipped.',
  },
  {
    id: 'relations', n: '08', name: 'Relationships', bg: '#1f6f6a', light: true, area: 'r', rep: 'Outcomes',
    line: 'A target that is already inside the features.',
    figure: 'cnt =', figureNote: 'casual + registered',
    body: `In the Bike sharing hourly data, ${bike.relationship} holds on all ${bike.rows.toLocaleString()} rows. DataTrust tests bounded copy, affine and two-feature-sum relationships against declared targets. Here are 48 real hours, stacked.`,
    facts: [['Relationship', bike.relationship], ['Holds on', `${bike.rows.toLocaleString()} of ${bike.rows.toLocaleString()} rows`], ['Declared unavailable', bike.declaredUnavailable.join(', ')], ['Score', 'none defined for regression']],
    effect: 'none-defined', effectNote: 'Regression has no universal score — the finding stands on its own.',
    not: 'It does not search for arbitrary formulas.',
  },
  {
    id: 'time', n: '09', name: 'Time', bg: '#f6c9c0', area: 't', rep: 'Time',
    line: 'When each value became known.',
    figure: 't₀', figureNote: 'declared availability',
    body: 'For temporal CSV and Parquet, DataTrust checks exact clocks, declared availability, coverage, schedules and panel populations, feature-bound timing, revisions, and supplied evaluation plans.',
    facts: [['Clocks', 'exact, declared'], ['Availability', 'per feature'], ['Revisions', 'tracked'], ['Plans', 'supplied evaluation plans']],
    effect: 'none-defined', effectNote: 'No universal score; findings are evidence.',
    not: 'It does not forecast or detect drift.',
  },
  {
    id: 'text', n: '10', name: 'Text', bg: '#cfe0ea', area: 'x', rep: 'Text',
    line: 'Near-duplicate sentences, found with bounds.',
    figure: '5,574', figureNote: 'SMS records',
    body: 'Corpus, annotation, QA and conversation datasets. Near-duplicate candidates come from a calibrated, bounded MinHash search; retrieval provenance and private evidence are resolved locally.',
    facts: [['Records', '5,574'], ['Search', 'calibrated MinHash, bounded'], ['Provenance', 'retrieval sources'], ['Score', 'none defined']],
    effect: 'none-defined', effectNote: 'Candidates for review, not a score.',
    not: 'It does not judge whether a text is true.',
  },
  {
    id: 'images', n: '11', name: 'Images', bg: '#dcd5c5', area: 'm', rep: 'Images',
    line: 'Coordinates, orientation and masks that agree.',
    figure: '128', figureNote: 'images · 875 objects',
    body: 'On a 128-image COCO val2017 subset with 875 objects, DataTrust checks coordinate and orientation compatibility and bounded segmentation integrity. 61 ICC-bearing images are excluded from default visual methods and said so.',
    facts: [['Images', '128'], ['Objects', '875'], ['ICC-bearing, excluded', '61'], ['Models', 'optional, pinned, offline']],
    effect: 'none-defined', effectNote: 'Perceptual candidates are review items.',
    not: 'It does not download models at runtime.',
  },
  {
    id: 'docs', n: '12', name: 'Documents', bg: '#f5b83d', area: 'p', rep: 'Connected',
    line: 'Records reconciled against their documents.',
    figure: `${finance.agreements}/${finance.records}`, figureNote: 'records agree',
    body: `${finance.records} finance records against ${finance.documents} native PDFs: ${finance.agreements} agree, ${finance.discrepancies} disagrees, ${finance.conflicts} has documents that support different values. Each comes with an exact page, table and cell locator. ${finance.note}`,
    facts: [['Agreements', String(finance.agreements)], ['Discrepancy', String(finance.discrepancies)], ['Conflict', String(finance.conflicts)], ['Locators', 'page · table · cell']],
    effect: 'none-defined', effectNote: 'Competing evidence is retained, never hidden.',
    not: 'It does not decide which document wins.',
  },
  {
    id: 'local', n: '13', name: 'Local', bg: '#ef5b3c', area: 'k', rep: 'All',
    line: 'Runs on your machine.',
    figure: '0', figureNote: 'network calls at analysis time',
    body: `The browser UI binds to ${local.host} only. Nothing is uploaded; models are never fetched at runtime. Adult — 48,842 rows — was audited in 0.18 seconds, recorded locally.`,
    facts: local.facts.map((f) => [f.label, f.value] as [string, string]),
    effect: 'property', effectNote: 'A property of every run, whatever the data.',
    not: 'There is no hosted service and no monitoring.',
  },
  {
    id: 'reports', n: '14', name: 'Reports', bg: '#2a2a2e', light: true, area: 'f', rep: 'All',
    line: 'HTML, PDF and JSON from the same evidence.',
    figure: '3', figureNote: 'formats · 8 topics',
    body: 'A canonical standalone HTML report in eight topics, a PDF with portrait decision pages and a landscape technical appendix, and strict JSON with every computed value.',
    facts: [['HTML', 'canonical, eight topics'], ['PDF', 'decision pages + appendix'], ['JSON', 'strict, complete'], ['CLI', 'datatrust audit … --json-out']],
    effect: 'property', effectNote: 'Every report carries its limits.',
    not: 'Reports support review; they are not certification.',
  },
];

export const byId = Object.fromEntries(mods.map((m) => [m.id, m])) as Record<ModId, Mod>;

export const effectLabel: Record<Effect, string> = {
  score: 'Changes a sub-score',
  guardrail: 'Can cap the score',
  evidence: 'Evidence only',
  'none-defined': 'No score defined',
  property: 'Every run',
};

/** How each module turned out in each local run. `null` = the module does not apply to that representation. */
export type State = { tone: 'finding' | 'critical' | 'clear' | 'info'; label: string; detail: string } | null;

export const runStates: Record<string, Partial<Record<ModId, State>>> = {
  adult: {
    score: { tone: 'critical', label: '69.0 · Elevated', detail: 'Evidence 89.15, capped by the critical target-balance sub-score.' },
    gaps: { tone: 'info', label: 'Completeness 99.12', detail: '6,465 empty cells in workclass, occupation, native_country. No finding.' },
    dups: { tone: 'info', label: 'Uniqueness 99.89', detail: '49 groups, 52 repeated rows. No finding.' },
    conflicts: { tone: 'finding', label: 'Moderate', detail: '5 feature-identical groups, 10 rows. Evidence only.' },
    imbalance: { tone: 'critical', label: 'Moderate · critical', detail: 'Majority 76.07%, balance 47.86 → cap 69.' },
    leakage: { tone: 'finding', label: 'Low · review', detail: 'marital_status, review only. Leakage risk 100.' },
    outliers: { tone: 'finding', label: 'Moderate', detail: 'hours_per_week, 13,496 rows outside 32.5 – 52.5.' },
    local: { tone: 'info', label: '0.18 s', detail: '48,842 rows, on this machine.' },
    reports: { tone: 'info', label: '3 reports', detail: 'HTML · PDF · JSON · 13 Aug 2026 01:08:11.' },
  },
  german: {
    score: { tone: 'clear', label: '91.8 · Low', detail: 'No guardrail applied.' },
    gaps: { tone: 'clear', label: 'Completeness 100', detail: 'No missing values.' },
    dups: { tone: 'clear', label: 'Uniqueness 100', detail: 'No duplicate rows.' },
    conflicts: { tone: 'clear', label: 'No finding', detail: 'Not among this run’s findings.' },
    imbalance: { tone: 'info', label: 'Balance 60', detail: 'Below the 75% majority threshold for a finding.' },
    leakage: { tone: 'finding', label: 'Low · review', detail: '5 review-only name prompts.' },
    outliers: { tone: 'finding', label: 'Moderate', detail: 'duration_months, credit_amount.' },
    local: { tone: 'info', label: '0.03 s', detail: '1,000 rows.' },
    reports: { tone: 'info', label: '3 reports', detail: 'HTML · PDF · JSON · 13 Aug 2026.' },
  },
  bank: {
    score: { tone: 'critical', label: '69.0 · Elevated', detail: 'Capped: target balance 23.4 is critical.' },
    gaps: { tone: 'clear', label: 'Completeness 100', detail: 'No missing values.' },
    dups: { tone: 'clear', label: 'Uniqueness 100', detail: 'No duplicate rows.' },
    conflicts: { tone: 'clear', label: 'No finding', detail: 'Not among this run’s findings.' },
    imbalance: { tone: 'critical', label: 'Moderate · critical', detail: 'Majority 88.3%, ratio 7.55:1, balance 23.4.' },
    leakage: { tone: 'finding', label: 'Low · review', detail: 'previous_campaign_outcome, review only.' },
    outliers: { tone: 'finding', label: 'Moderate', detail: 'balance, duration, campaign.' },
    local: { tone: 'info', label: '0.18 s', detail: '45,211 rows.' },
    reports: { tone: 'info', label: '3 reports', detail: 'HTML · PDF · JSON · 13 Aug 2026.' },
  },
  bike: {
    score: { tone: 'info', label: 'No score defined', detail: 'Regression has no universal score, by design.' },
    relations: { tone: 'critical', label: 'High', detail: 'cnt = casual + registered on all 17,379 rows.' },
    leakage: { tone: 'critical', label: 'High', detail: 'casual, registered declared unavailable at prediction time.' },
    outliers: { tone: 'finding', label: 'Moderate · Low', detail: 'casual 6.86% IQR candidates; holiday near-constant (97.12%).' },
    local: { tone: 'info', label: '0.23 s', detail: '17,379 rows.' },
    reports: { tone: 'info', label: '3 reports', detail: 'HTML · PDF · JSON · 9 Oct 2026.' },
  },
  sms: {
    score: { tone: 'info', label: 'No score defined', detail: 'Text runs report evidence.' },
    text: { tone: 'finding', label: 'Candidates', detail: 'Near-duplicate candidates from calibrated MinHash search.' },
    local: { tone: 'info', label: 'Local', detail: '5,574 records.' },
    reports: { tone: 'info', label: '3 reports', detail: 'HTML · PDF · JSON · 11 Oct 2026.' },
  },
  coco: {
    score: { tone: 'info', label: 'No score defined', detail: 'Image runs report evidence.' },
    images: { tone: 'finding', label: '61 excluded', detail: '61 ICC-bearing images excluded from default visual methods.' },
    local: { tone: 'info', label: 'Offline', detail: '128 images, 875 objects.' },
    reports: { tone: 'info', label: '3 reports', detail: 'HTML · PDF · JSON · 12 Oct 2026.' },
  },
  finance: {
    score: { tone: 'info', label: 'No score defined', detail: 'Cross-representation runs report evidence.' },
    docs: { tone: 'critical', label: 'High · 2', detail: '18 agree · 1 discrepancy · 1 conflict, with page locators.' },
    local: { tone: 'info', label: 'Local', detail: '20 records, 21 PDFs.' },
    reports: { tone: 'info', label: '3 reports', detail: 'HTML · PDF · JSON · 13 Oct 2026.' },
  },
};
