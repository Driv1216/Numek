// Which composition renders a result, decided by what the analysis recorded (methodology, and the M4 comparison
// preset or mode), never by the mode a job or saved entry was opened with. Anything unknown renders as recorded.
import type { Composition } from './model';

type Doc = Record<string, unknown>;

const BY_METHOD: Record<string, [Composition, string]> = {
  classification_legacy_2026_08_13: ['classification', 'classification'],
  tabular_regression_v1: ['numeric', 'single'],
  tabular_annotation_regression_v1: ['numeric', 'annotation'],
  tabular_multioutput_regression_v1: ['numeric', 'multioutput'],
  unlabeled_csv_profile_v1: ['profile', 'unlabeled'],
  tabular_role_profile_v1: ['profile', 'roles'],
  tabular_partial_classification_v1: ['annotation', 'classification'],
  tabular_multilabel_v1: ['multilabel', 'multilabel'],
  tabular_clustering_readiness_v1: ['readiness', 'clustering'],
  tabular_anomaly_readiness_v1: ['readiness', 'anomaly'],
  tabular_clustering_readiness_v2: ['readiness', 'clustering'],
  tabular_anomaly_readiness_v2: ['readiness', 'anomaly'],
  temporal_reliability_v1: ['temporal', 'temporal'],
  text_reliability_v1: ['text', 'text'],
  image_reliability_v1: ['image', 'image'],
  cross_representation_reliability_v1: ['cross', 'records_documents'],
};

export function resolveComposition(a: Doc): { composition: Composition; variant: string } {
  const method = String(a.methodology_id ?? '');
  if (method === 'm4_local_2026_10_10' || method === 'm4_local_2026_11_25') {  // comparisons; 11_25 is direction-preserving (Stage 6A)
    const comparison = (a.comparison as Doc | undefined) ?? {};
    const variant = String(comparison.preset ?? comparison.mode ?? '');
    return variant ? { composition: 'comparison', variant } : { composition: 'structure', variant: 'advanced' };
  }
  const known = BY_METHOD[method];
  return known ? { composition: known[0], variant: known[1] } : { composition: 'generic', variant: method || 'unrecorded' };
}
