// Test entry for the dashboard compositions: build each Dashboard from canonical JSON and the companion, and reduce it
// to plain data (tile faces, ledger rows, statement, coverage) that Python can compare with the recorded values.
import { classificationDashboard } from '../frontend/src/app/results/compositions/classification';
import { profileDashboard } from '../frontend/src/app/results/compositions/profile';
import { numericDashboard } from '../frontend/src/app/results/compositions/numeric';
import { annotationDashboard } from '../frontend/src/app/results/compositions/annotation';
import { multilabelDashboard } from '../frontend/src/app/results/compositions/multilabel';
import { readinessDashboard } from '../frontend/src/app/results/compositions/readiness';
import { resolveComposition } from '../frontend/src/app/results/resolve';
import type { Companion, Dashboard } from '../frontend/src/app/results/model';

type Doc = Record<string, unknown>;

function plain(d: Dashboard) {
  return {
    composition: d.composition, variant: d.variant, identity: d.identity, statement: d.statement ?? null, state: d.state, unknowns: d.unknowns,
    tiles: d.tiles.map((t) => ({ id: t.id, name: t.name, label: t.label, detail: t.detail, tone: t.tone, hero: !!t.hero })),
    findings: d.findings.map((f) => ({ index: f.index, ref: f.ref, title: f.title, rank: f.rank, scope: f.scope ?? null, tile: f.tile, locator: f.locator, context: !!f.context })),
    coverage: d.coverage, interpretation: d.interpretation ?? null,
  };
}

export const classification = (a: Doc, c: Companion | null) => plain(classificationDashboard(a, c, false));
export const profile = (a: Doc, c: Companion | null) => plain(profileDashboard(a, c, false));
export const numeric = (a: Doc, c: Companion | null) => plain(numericDashboard(a, c, false, resolveComposition(a).variant));
export const annotation = (a: Doc, c: Companion | null) => plain(annotationDashboard(a, c, false));
export const multilabel = (a: Doc, c: Companion | null) => plain(multilabelDashboard(a, c, false));
export const readiness = (a: Doc, c: Companion | null) => plain(readinessDashboard(a, c, false, resolveComposition(a).variant));

import { m4Dashboard } from '../frontend/src/app/results/roles';
import type { M4Analysis } from '../frontend/src/app/api';
export const comparison = (a: Doc, c: Companion | null) => plain(m4Dashboard(a as unknown as M4Analysis, c, false));
export const structure = comparison;

import { temporalDashboard } from '../frontend/src/app/results/compositions/temporal';
export const temporal = (a: Doc, c: Companion | null) => plain(temporalDashboard(a, c, false));

import { textDashboard } from '../frontend/src/app/results/compositions/text';
import { imageDashboard } from '../frontend/src/app/results/compositions/image';
import { crossDashboard } from '../frontend/src/app/results/compositions/cross';
export const text = (a: Doc, c: Companion | null) => plain(textDashboard(a, c, false));
export const image = (a: Doc, c: Companion | null) => plain(imageDashboard(a, c, false));
export const cross = (a: Doc, c: Companion | null) => plain(crossDashboard(a, c, false));

export { outcome } from '../frontend/src/app/results/outcome';
