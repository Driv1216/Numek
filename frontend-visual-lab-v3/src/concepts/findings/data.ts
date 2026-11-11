// Every finding from every local run, flattened into one table. Values come from the fixture.
import { adult, runFindings, runs, type Severity } from '../../fixture';

export type Effect = 'score' | 'evidence' | 'none-defined';
export interface Row { id: string; run: string; runName: string; rep: string; title: string; severity: Severity; evidence: string; effect: Effect; raw?: (typeof adult.findings)[number] }

export const rows: Row[] = runs.flatMap((r) => (runFindings[r.id] ?? []).map((f, i) => ({
  id: `${r.id}-${i}`, run: r.id, runName: r.name, rep: r.rep, title: f.title, severity: f.severity, evidence: f.evidence, effect: f.effect,
  raw: r.id === 'adult' ? adult.findings[i] : undefined,
})));

export const effectLabel: Record<Effect, string> = { score: 'Changes the score', evidence: 'Evidence only', 'none-defined': 'No score defined' };
export const sevRank: Record<Severity, number> = { High: 0, Moderate: 1, Low: 2 };
