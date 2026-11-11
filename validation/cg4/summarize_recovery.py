"""Aggregate one complete predeclared recovery panel without rerunning trials."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.stats import binomtest

from run_locked_qualification import ROOT, snapshot, sha


def audit_runner(profile, capsule, *, required=False):
    for field, name in [('diagnostics_harness_sha256', 'qualification_diagnostics.py'),
                        ('parallel_seed_runner_sha256', 'parallel_qualification.py')]:
        if field in profile:
            if profile[field] != sha(capsule/'validation/cg4'/name):
                raise RuntimeError('Recorded qualification helper differs from its capsule.')
        elif required:
            raise RuntimeError('Current qualification profile lacks a required helper identity.')


def captured_protocol(capsule,recorded_digest):
    """Select only an explicitly recorded, verified immutable protocol."""
    matches=[capsule/'validation/cg4'/name for name in ('qualification_protocol_v2.json','qualification_protocol_v3.json')
             if (capsule/'validation/cg4'/name).is_file() and sha(capsule/'validation/cg4'/name)==recorded_digest]
    if len(matches)!=1:raise RuntimeError('Recorded qualification protocol is missing or ambiguous.')
    return matches[0]


def recover_panel(directory):
    directory = Path(directory).resolve()
    binding_path = directory.with_name(directory.name+'.source-capsule.json')
    binding = json.loads(binding_path.read_text())
    if binding['script'] != 'qualify_pipeline.py': raise RuntimeError('This aggregator accepts pipeline recovery panels only.')
    capsule, identity = snapshot(binding['source_identity'])
    if sha(capsule/'source-manifest.json') != binding['source_manifest_sha256']: raise RuntimeError('Source binding changed.')
    args = binding['arguments']
    if args[args.index('--panel')+1] != 'recovery_qualification': raise RuntimeError('Do not qualify development or null panels as recovery anchors.')
    archetype = args[args.index('--archetype')+1]
    first=next(iter(sorted(directory.glob(f'recovery_qualification-{archetype}-*.json'))),None)
    if first is None:raise RuntimeError('No completed qualification evidence to audit.')
    protocol_path = captured_protocol(capsule,json.loads(first.read_text())['profile']['protocol_sha256'])
    protocol = json.loads(protocol_path.read_text()); seed_spec = protocol['seed_panels']['recovery_qualification']
    anchor = protocol['strong_signal_anchor']; rows = []; profile = None
    for seed in range(seed_spec['start'], seed_spec['start']+seed_spec['count']):
        path = directory/f'recovery_qualification-{archetype}-{seed}.json'; row = json.loads(path.read_text())
        if row['status'] != 'completed' or row['seed'] != seed or row['panel'] != 'recovery_qualification' or row['archetype'] != archetype or row['null'] or row['n'] != anchor['independent_units']:
            raise RuntimeError('Incomplete, failed or mismatched locked trial; preserve it and resolve before aggregation.')
        if profile is None: profile = row['profile']
        if row['profile'] != profile: raise RuntimeError('Mixed runtime/method profiles require a separately justified reuse audit.')
        if profile['protocol_sha256'] != sha(protocol_path) or profile['harness_sha256'] != sha(capsule/'validation/cg4/qualify_pipeline.py'):
            raise RuntimeError('Trial is not bound to the recorded protocol and harness.')
        audit_runner(profile,capsule,required=protocol_path.name=='qualification_protocol_v3.json')
        for name, digest in profile['source_sha256'].items():
            if sha(capsule/name) != digest: raise RuntimeError('Recorded analytical source differs from source capsule.')
        recovery = {role: row['recovery'][role]['primary_selected_union'] for role in ('D', 'S', 'H')}
        h = recovery['H']; success = h['precision'] >= anchor['required_precision'] and h['recall'] >= anchor['required_recall']
        rows.append({'seed': seed, 'path': str(path.relative_to(ROOT)), 'sha256': sha(path),
            'input_sha256': row['input_sha256'], 'recovery': recovery, 'success': bool(success),
            'seconds': row['seconds'], 'assessment_states': [a['state'] for a in row['assessments']]})
    successes = sum(r['success'] for r in rows); interval = binomtest(successes, len(rows)).proportion_ci(method='exact')
    return {'schema_version': 'numek.cg4_recovery_anchor_summary/1.1', 'archetype': archetype,
        'source_identity': identity, 'source_binding_sha256': sha(binding_path), 'protocol_sha256': sha(protocol_path),
        'expected_seeds': [seed_spec['start'], seed_spec['start']+seed_spec['count']-1], 'trials': rows,
        'successes': successes, 'success_fraction_MC95': [float(interval.low), float(interval.high)],
        'required_successes': anchor['required_successes_of_40'],
        'anchor_criterion_met': bool(successes >= anchor['required_successes_of_40']),
        'role_medians': {role: {metric: float(np.median([r['recovery'][role][metric] for r in rows]))
            for metric in ('precision', 'recall', 'IoU')} for role in ('D', 'S', 'H')},
        'H_unavailable': {'total': sum(r['recovery']['H']['unavailable'] for r in rows),
                          'oracle_members': sum(r['recovery']['H']['unavailable_oracle_members'] for r in rows)},
        'scope': 'This declared archetype, generator, S selection and operating profile only. Planned H membership remains the recall denominator. No oracle-guided selection, strategy-specific qualification, landmark superiority, universal recovery, resource-comparison or complete-milestone claim.'}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--directory', required=True); parser.add_argument('--out', required=True); args = parser.parse_args()
    result = recover_panel(args.directory); result['aggregation_source_sha256'] = sha(Path(__file__))
    path = Path(args.out)
    if path.exists() and json.loads(path.read_text()) != result: raise RuntimeError('Preserve prior summary; do not overwrite different evidence.')
    if not path.exists(): path.write_text(json.dumps(result, sort_keys=True, indent=2, allow_nan=False)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'trials'}, sort_keys=True))


if __name__ == '__main__':
    main()
