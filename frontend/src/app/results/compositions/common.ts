// Assemble one workflow's Dashboard from its canonical JSON, its presentation companion and the composition's own
// choices (identity, statement, hero and tiles, where each finding's evidence lives, bounds and notes).
import type { Companion, Composition, Coverage, Dashboard, Identity } from '../model';
import type { Tile } from '../Tiles';
import { coverage, defaultExtract, ledger, resultState, unknowns, type Check, type Extract } from '../normalize';

type Doc = Record<string, unknown>;

export interface Parts {
  composition: Composition; variant: string; identity: Identity; statement?: string; tiles: Tile[];
  tileOf: (f: Doc, index: number) => string | null; extract?: Extract; coverage?: Partial<Coverage>; checkName?: (c: Check) => string; saved: boolean;
}

export function buildDashboard(a: Doc, companion: Companion | null, p: Parts): Dashboard {
  const findings = ledger(a, companion, p.tileOf, p.extract ?? defaultExtract);
  const cov = coverage(a, companion, p.coverage, p.checkName);
  const report = companion?.report;
  if (report) {
    cov.methodology.push({ text: `Report: print profile ${report.print_profile ?? 'not recorded'}`,
      reason: report.presentation_id ? `presentation ${report.presentation_id} (${report.presentation_source === 'report' ? 'printed in the report' : report.presentation_source === 'manifest' ? 'recorded when it was saved' : 'this build'})` : 'presentation identity not recorded for this report' });
  } else if (companion === null) {
    cov.methodology.push({ text: 'Report links not verified', reason: 'the report-owned names and links could not be read for this result; canonical titles are shown' });
  }
  return { composition: p.composition, variant: p.variant, identity: p.identity, state: resultState(a, findings.length, cov, p.saved),
           statement: p.statement, unknowns: unknowns(a), findings, tiles: p.tiles.map((t, i) => ({ ...t, n: String(i + 1).padStart(2, '0') })), coverage: cov,
           interpretation: companion?.interpretation ?? null };
}

export const base = (s: unknown) => { const t = String(s ?? ''); return t.split(/[\\/]/).pop() ?? t; };
