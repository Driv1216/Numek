"""Computational replay of a prior valid-vector case; never new evidence."""
import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import qualify_pipeline as pipeline


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--prior', required=True); parser.add_argument('--out', required=True)
    args = parser.parse_args(); path = Path(args.prior); prior = json.loads(path.read_text())
    admitted = {'curved_region', 'disconnected_regions', 'heterogeneous_density', 'overlapping_mechanisms', 'high_dimensional_nuisance'}
    if prior['status'] != 'completed' or prior['panel'] != 'recovery_qualification' or prior['archetype'] not in admitted or prior['n'] != 40000:
        raise RuntimeError('Only an original completed geometry-only reference case is admitted for this replay.')
    sources = pipeline.identity(); started_harness = pipeline.sha(Path(pipeline.__file__))
    trial = SimpleNamespace(panel='recovery_qualification', seed=prior['seed'], archetype=prior['archetype'], strategies=None, full_profile=False)
    measured = pipeline.trial(trial)
    fields = ('state', 'effect', 'effect_state', 'practical_threshold', 'support', 'interval', 'strength', 'reason')
    numeric = lambda row: [{k: item.get(k) for k in fields} for item in row['assessments']]
    comparison = {'D_S_H_membership_recovery_equal': prior['recovery'] == measured['recovery'],
                  'selected_candidate_ids_equal': prior['shortlist'] == measured['shortlist'],
                  'native_confirmation_outputs_equal': numeric(prior) == numeric(measured),
                  'vector_input_sha256_equal': prior['input_sha256']['vectors'] == measured['input_sha256']['vectors']}
    record = {'schema_version': 'numek.cg4_geometric_computational_replay/1.0', 'reference': str(path),
              'reference_sha256': pipeline.sha(path), 'replay_only': True, 'counts_as_new_qualification_trial': False,
              'fresh_independent_evidence': False, 'scope': 'Reproduce an original synthetic procedure in isolation. '
                  'The original CSV x/y columns were excluded from these tabular views; vector data were valid. '
                  'Reproduced finding states are numerical outputs, not new independent claims.',
              'comparison': comparison, 'replay': measured, 'source_sha256': sources,
              'pipeline_harness_sha256': started_harness,
              'status': 'matched' if all(comparison.values()) else 'mismatch'}
    if sources != pipeline.identity() or started_harness != pipeline.sha(Path(pipeline.__file__)):
        record['status'] = 'source_changed'
    with Path(args.out).open('x') as stream: json.dump(record, stream, sort_keys=True, indent=2); stream.write('\n')
    print(json.dumps({'status': record['status'], 'comparison': comparison}))


if __name__ == '__main__':
    main()
