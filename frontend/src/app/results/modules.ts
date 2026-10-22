// The fourteen DataTrust modules as the approved mosaic presents them: what each one is, where it sits,
// and its shade. Everything a run says about a module comes from that run's canonical JSON (adapter.ts).

export type ModId = 'score' | 'gaps' | 'dups' | 'conflicts' | 'imbalance' | 'leakage' | 'outliers' | 'relations' | 'time' | 'text' | 'images' | 'docs' | 'local' | 'reports';
export type Effect = 'score' | 'evidence' | 'none-defined' | 'guardrail' | 'property';

export interface Mod { id: ModId; n: string; name: string; area: string; rep: string; line: string; effect: Effect; effectNote: string; not: string; elsewhere?: string }

export const mods: Mod[] = [
  { id: 'score', n: '01', name: 'Score', area: 's', rep: 'Classification', line: 'A score, only where one is defined.', effect: 'guardrail', effectNote: 'The mean of five sub-scores, then capped by the lowest triggered guardrail. A heuristic review policy, not a validated probability.', not: 'No score is invented for regression, time, text, images or documents.' },
  { id: 'gaps', n: '02', name: 'Gaps', area: 'g', rep: 'Tables', line: 'Where values are missing, and how many rows it touches.', effect: 'score', effectNote: 'Feeds the completeness sub-score.', not: 'DataTrust does not impute or fill anything.' },
  { id: 'dups', n: '03', name: 'Duplicates', area: 'd', rep: 'Tables', line: 'Rows that appear more than once.', effect: 'score', effectNote: 'Feeds the uniqueness sub-score.', not: 'Duplicates are reported, never removed.' },
  { id: 'conflicts', n: '04', name: 'Conflicts', area: 'c', rep: 'Tables', line: 'Identical features, different labels.', effect: 'evidence', effectNote: 'Evidence only: this finding does not change any score or guardrail.', not: 'It cannot say which label is right. It asks a person to look.' , elsewhere: 'Not part of this analysis. Conflicts need a target or annotations.' },
  { id: 'imbalance', n: '05', name: 'Imbalance', area: 'i', rep: 'Classification', line: 'One class dominating the target.', effect: 'guardrail', effectNote: 'Changes the score and can trigger the critical-sub-score guardrail.', not: 'It does not resample or reweight.' , elsewhere: 'Not part of this analysis. Imbalance applies to a classification target.' },
  { id: 'leakage', n: '06', name: 'Leakage', area: 'l', rep: 'Tables · Outcomes', line: 'Columns that may know the answer.', effect: 'evidence', effectNote: 'Review-only prompts are evidence; strong evidence would cap the score.', not: 'A column name is never treated as proof.' , elsewhere: 'Not part of this analysis. Leakage checks need a target.' },
  { id: 'outliers', n: '07', name: 'Outliers', area: 'o', rep: 'Tables · Outcomes', line: 'Values far outside the middle half.', effect: 'score', effectNote: 'Reduces the feature-usability score at the current thresholds.', not: 'Nothing is deleted or clipped.' },
  { id: 'relations', n: '08', name: 'Relationships', area: 'r', rep: 'Outcomes', line: 'A target that is already inside the features.', effect: 'none-defined', effectNote: 'Regression has no universal score; the finding stands on its own.', not: 'It does not search for arbitrary formulas.' , elsewhere: 'Not part of this analysis. Target relationships are searched for regression targets.' },
  { id: 'time', n: '09', name: 'Time', area: 't', rep: 'Time', line: 'When each value became known.', effect: 'none-defined', effectNote: 'No universal score; findings are evidence.', not: 'It does not forecast or detect drift.' , elsewhere: 'Not part of this analysis. Time evidence comes from the Temporal workflow (M5), which needs a time column and declared availability rules.' },
  { id: 'text', n: '10', name: 'Text', area: 'x', rep: 'Text', line: 'Near-duplicate sentences, found with bounds.', effect: 'none-defined', effectNote: 'Candidates for review, not a score.', not: 'It does not judge whether a text is true.' , elsewhere: 'Not part of this analysis. Text evidence comes from the Text workflow (M6), which reads text fields or files you map.' },
  { id: 'images', n: '11', name: 'Images', area: 'm', rep: 'Images', line: 'Coordinates, orientation and masks that agree.', effect: 'none-defined', effectNote: 'Perceptual candidates are review items.', not: 'It does not download models at runtime.' , elsewhere: 'Not part of this analysis. Image evidence comes from the Images workflow (M7), which reads image folders and manifests.' },
  { id: 'docs', n: '12', name: 'Documents', area: 'p', rep: 'Connected', line: 'Records reconciled against their documents.', effect: 'none-defined', effectNote: 'Competing evidence is retained, never hidden.', not: 'It does not decide which document wins.' , elsewhere: 'Not part of this analysis. Document evidence comes from the Records ↔ documents workflow (M9), which reconciles records against documents.' },
  { id: 'local', n: '13', name: 'Local', area: 'k', rep: 'All', line: 'Runs on your machine.', effect: 'property', effectNote: 'A property of every run, whatever the data.', not: 'There is no hosted service and no monitoring.' },
  { id: 'reports', n: '14', name: 'Reports', area: 'f', rep: 'All', line: 'HTML, PDF and JSON from the same evidence.', effect: 'property', effectNote: 'Every report carries its limits.', not: 'Reports support review; they are not certification.' },
];

export const effectLabel: Record<Effect, string> = {
  score: 'Changes a sub-score', guardrail: 'Can cap the score', evidence: 'Evidence only', 'none-defined': 'No score defined', property: 'Every run',
};

/** DataTrust shades per module: [background, light ink]. */
export const shade: Record<ModId, [string, boolean]> = {
  score: ['#163F52', true], gaps: ['#D5E4EB', false], dups: ['#FBFAF7', false], conflicts: ['#2C6E8E', true], imbalance: ['#D5E4EB', false],
  leakage: ['#163F52', true], outliers: ['#BCD3DE', false], relations: ['#FBFAF7', false], time: ['#D5E4EB', false], text: ['#2C6E8E', true],
  images: ['#FBFAF7', false], docs: ['#BCD3DE', false], local: ['#163F52', true], reports: ['#D5E4EB', false],
};
