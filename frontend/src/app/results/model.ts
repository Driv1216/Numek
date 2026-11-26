// The results dashboard's shared model: what every workflow composition hands the shared ResultsShell.
// Values are read from the canonical analysis JSON and the presentation companion (dashboard_companion_v1); a
// composition selects, orders and formats them, and never computes new evidence.
import type { ReactNode } from 'react';
import type { Tile } from './Tiles';

export type Composition = 'classification' | 'numeric' | 'profile' | 'annotation' | 'multilabel' | 'readiness' | 'comparison' | 'structure'
  | 'temporal' | 'text' | 'image' | 'cross' | 'generic';

/** A priority recorded by the workflow, or the evidence meaning the text and image workflows record instead. */
export interface Rank { kind: 'priority' | 'evidence_meaning'; value: string; label: string; order: number }

/** Where a finding lives in the served report, verified against that report's own bytes by the companion. */
export interface Locator { kind: 'anchor' | 'section' | 'index_position' | 'none'; value: string | number | null; of?: number; checked?: string; reason?: string }

export interface Companion {
  companion: string; family: string | null; methodology_id: string | null; schema_version: string | null; view_error: string | null;
  report: null | { presentation_id: string | null; presentation_source: 'report' | 'manifest' | 'current' | null; print_profile: string | null;
    finding_index: boolean; finding_index_rows: number; sections: string[] };
  findings: { index: number; ref: string | null; title: string; rank: Rank; effect: string | null; locator: Locator }[];
  actions: null | ({ family?: string; meaning?: string | null; action?: string | null; evidence_ids?: string[]; observations?: string[]; title?: string; facts?: string[] })[];
  concepts: { id: string; term: string; definition: string; means: string | null; does_not_mean: string | null; methodology_ref: string | null; anchor: string | null }[];
  /** The report's own names for what the tiles show; null where the report projection could not be read. */
  names?: null | { families?: Record<string, string>; meanings?: Record<string, string>; populations?: Record<string, string>; statuses?: Record<string, string>; explanations?: Record<string, string> };
  /** interpretation_v1 (src/datatrust/interpretation.py): the one interpretation shared with the reports. */
  interpretation?: Interpretation | null;
}

/** The recorded finding_guidance_v1 entry for one finding, re-exposed by interpretation_v1. */
export interface GuidanceItem {
  ref: string; catalogue: string; title: string; context?: boolean;
  observed: string[]; impact: string[]; investigate: string[]; unknowns: string[];
  options: { option: string; prerequisites: string; avoid_when: string; verify: string }[];
}

export interface Interpretation {
  version: string; family: string; guidance_recorded: boolean;
  summary: { text: string; facts: { pointer: string; derived: string; value: unknown }[] }[];
  findings: Record<string, GuidanceItem>;
  more_conclusive: { key: string; label: string; why: string; resolves: string[]; pointer: string }[];
  clean: null | { checks_completed: number; checks_recorded: number; thresholds: { rule: string; threshold: string; effect: string }[]; not_established: string[] };
  states: { state: string; label: string; meaning: string }[];
}

export interface LedgerFinding {
  /** Position in the canonical findings list: the stable key. */
  index: number; ref: string | null; title: string; rank: Rank;
  scope?: string; statement?: string; nextAction?: string; limitations?: string; context?: boolean;
  /** The tile whose chapter holds this finding's evidence; null when no tile does. */
  tile: string | null; locator: Locator;
}

export interface CoverageItem { text: string; reason?: string }
/** The coverage ledger, most consequential first. Not completed and bounded groups open by default when non-empty. */
export interface Coverage {
  notCompleted: CoverageItem[]; bounded: CoverageItem[]; excluded: CoverageItem[]; notApplicable: CoverageItem[];
  /** Recorded only: an optional capability the configuration left off. Never inferred. */
  notRequested: CoverageItem[];
  /** Methodology notes, the recorded no-score reason first where a workflow defines no score. */
  methodology: CoverageItem[];
  completed?: string;
}

export interface ResultState {
  run: 'completed' | 'partial'; findings: number; bounded: boolean; saved: boolean;
  chip: 'findings' | 'clean' | 'partial';
  historical: string[];
}

export interface Identity {
  name: string; sources: string; workflow: string; variant?: string; when: string | null; methodology: string | null; schema: string | null; scale?: string;
}

export interface Dashboard {
  composition: Composition; variant: string; identity: Identity; state: ResultState;
  /** The recorded statement the outcome band leads with (narrative, executive summary or scope conclusion). */
  statement?: string; unknowns: string[]; findings: LedgerFinding[]; tiles: Tile[]; coverage: Coverage;
  /** Shown above the mosaic when the result is drawn without a workflow composition. */
  notice?: ReactNode;
  /** interpretation_v1 from the companion; null when it could not be read (older or unknown results). */
  interpretation?: Interpretation | null;
}
