// One outcome per saved or live analysis, for the history rail, sheet and list: worded for its workflow. A
// classification score and risk band appear only where a score was recorded (classification, and the standalone
// score of an M4 advanced analysis); otherwise the recorded findings and how many are High, a partial run, or no
// threshold-level finding. An unscored workflow is never described by the score it does not have.

export interface Outcome { text: string; cls: 'is-low' | 'is-elev' | 'is-find' }

const fmt = (v: number) => v.toLocaleString('en-US');

export function outcome(p: { score?: number | null; risk?: string | null; findings: { severity?: string | null; code?: string }[]; status?: string | null }): Outcome {
  const fs = p.findings.filter((f) => f.code !== 'no_major_issues'), high = fs.filter((f) => f.severity === 'High').length;
  const count = fs.length ? `${fmt(fs.length)} finding${fs.length === 1 ? '' : 's'}${high ? ` · ${fmt(high)} High` : ''}` : '';
  if (p.status === 'partial') return { text: `Partial${count ? ` · ${count}` : ''}`, cls: 'is-elev' };
  if (p.score != null) return { text: `Score ${p.score.toFixed(1)} · ${p.risk ?? 'risk band not recorded'}`, cls: p.risk === 'Low' ? 'is-low' : 'is-elev' };
  if (fs.length) return { text: count, cls: high ? 'is-elev' : 'is-find' };
  return { text: 'No threshold-level findings', cls: 'is-low' };
}

/** History filters: the index's workflow values. The classification risk band exists only for tabular and M4 runs. */
export const WORKFLOWS: [string, string][] = [['', 'All workflows'], ['core', 'Tabular datasets'], ['m4', 'Comparisons and advanced'], ['m5', 'Temporal'], ['m6', 'Text'], ['m7', 'Images'], ['m9', 'Records ↔ documents']];
export const RISK_BAND = new Set(['', 'core', 'm4']);
