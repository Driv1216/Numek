// Small shared readers for results pages. The fixed 14-module mosaic this file once fed is retired (dashboard redesign
// Stage 3); every workflow is drawn by its composition on the shared results shell.
import type { Finding, M3Mode } from '../api';
import routes from './finding-routes.json';

export type Tone = 'finding' | 'critical' | 'clear' | 'info';

export const date = (iso: string) => { const d = new Date(iso); return Number.isNaN(+d) ? iso : d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }); };

const narrativeOnly = new Set(routes.narrative_only);
/** A finding is evidence; "no major issues" is a narrative statement and is never counted as one. */
export const isFinding = (f: { code: string }) => !narrativeOnly.has(f.code);

/** The governing guardrail cap: the overall score is capped by the lowest triggered cap. */
export function governingCap(values: { guardrails?: { code: string; cap: number; explanation: string }[] } | null | undefined) {
  if (!values?.guardrails?.length) return null;
  const cap = Math.min(...values.guardrails.map((g) => g.cap));
  return { cap, governing: values.guardrails.filter((g) => g.cap === cap), also: values.guardrails.filter((g) => g.cap !== cap) };
}

export const m3Label: Record<M3Mode, string> = {
  annotation_classification: 'Classification · annotation expectations', annotation_regression: 'Regression · annotations or multiple outputs',
  multilabel_classification: 'Multilabel binary indicators', clustering: 'Clustering readiness', anomaly_detection: 'Anomaly-detection readiness', role_profile: 'Profiling with explicit roles',
};

export type { Finding };
