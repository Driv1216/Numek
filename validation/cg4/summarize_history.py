"""Audit a complete locked historical recovery panel without reusing H for selection.

Event recovery, native period effects and formal confirmation are separate evidence.
This tool never fits a gate, reconstructs missing diagnostics or performs inference
on the paired observations. Read-only trial auditing can precede panel completion.
"""
import argparse
import ast
import json
import math
from pathlib import Path

import numpy as np
from scipy.stats import binomtest

from run_locked_qualification import ROOT, snapshot, sha
from summarize_baselines import recovery_audit
from summarize_recovery import audit_runner


def recorded_protocol(capsule):
    tree = ast.parse((capsule/'validation/cg4/qualify_history.py').read_text())
    assignments = [node.value for node in tree.body if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == 'PROTOCOL' for t in node.targets)]
    if len(assignments) != 1:
        raise RuntimeError('Historical protocol must be an explicit frozen declaration.')
    protocol = ast.literal_eval(assignments[0])
    expected={'numek.cg4_historical_recovery_protocol/1.1':[120000,120039],
              'numek.cg4_historical_recovery_protocol/1.2':[320000,320039]}
    if (protocol['schema_version'] not in expected
            or protocol['seeds']['qualification'] != expected.get(protocol['schema_version'])
            or protocol['independent_entities'] != 40000 or protocol['events_per_entity'] != 2
            or protocol['criterion'] != {'H_precision': .7, 'H_recall': .7, 'minimum_successes_of_40': 32}
            or protocol['practical_threshold'] != .15):
        raise RuntimeError('Changed protocol requires a separate reviewed qualification audit.')
    return protocol


def native_effect_audit(evidence, planned):
    """Reference this panel's error-rate contrast to retained accuracy counts."""
    if evidence['planned'] != planned or evidence['available'] + evidence['unavailable'] != planned:
        raise RuntimeError('Native evidence lost the planned population.')
    if evidence['members'] + evidence['nonmembers'] != evidence['available']:
        raise RuntimeError('Native membership counts contradict applicable support.')
    values = []
    for key, conditional, period in [('member_metric', 'conditional_members', 'current'),
                                     ('comparator_metric', 'conditional_nonmembers', 'reference')]:
        metric = evidence[key]; measurement = metric['measurement']; objective = metric['objective_identity']
        if (objective['metric'] != 'error_rate' or objective['comparator'] != 'reference_period'
                or objective['reference_period'] != 'reference' or objective['current_period'] != 'current'
                or objective['practical_threshold'] != .15 or objective['direction'] != 'higher'
                or objective['units'] != 'fraction' or measurement['metric'] != 'accuracy'
                or metric['value_state'] != 'finite' or measurement['value_state'] != 'finite'):
            raise RuntimeError('Historical native objective or metric identity changed.')
        support = metric['support']; counts = measurement['sensitive_counts']
        if (type(support) is not int or support <= 0 or evidence[conditional] != support
                or measurement['denominator'] != support or len(counts) != 2
                or any(type(c) is not int or c < 0 for c in counts) or sum(counts) != support):
            raise RuntimeError('Period-specific metric denominator/counts disagree.')
        # CG1 accuracy retains [correct, incorrect]. Historical error is exactly
        # its registered one-minus transform, not a diagnostic learner score.
        error = counts[1]/support
        if (not math.isclose(measurement['value'], counts[0]/support, abs_tol=1e-14)
                or not math.isclose(metric['value'], error, abs_tol=1e-14)):
            raise RuntimeError('Historical reducer disagrees with retained confusion counts.')
        values.append(error)
    effect = values[0] - values[1]
    if evidence['effect_state'] != 'finite' or not math.isclose(evidence['effect'], effect, abs_tol=1e-14):
        raise RuntimeError('Historical deterioration is not current-minus-reference error.')
    return effect


def trial_audit(row, seed, scenario, protocol):
    if (row['status'] != 'completed' or row['seed'] != seed or row['scenario'] != scenario
            or row['independent_entities'] != protocol['independent_entities']
            or row['events'] != 2*protocol['independent_entities']
            or row['formal_confirmation_performed'] is not False):
        raise RuntimeError('Incomplete/mismatched historical trial or misleading confirmation claim.')
    selected = row['shortlist']
    if not selected or len(set(selected)) != len(selected):
        raise RuntimeError('Missing or duplicated selected gate identities.')
    recovery = {}; effects = {}; total = 0
    for role in ('D', 'S', 'H'):
        role_data = row['recovery'][role]; recovery[role] = role_data['primary_selected_union']
        recovery_audit(recovery[role]); total += recovery[role]['planned']
        records = role_data['selected_native_effects']
        if len(records) != len(selected) or {r['id'] for r in records} != set(selected):
            raise RuntimeError('Native effects do not cover exactly the frozen selected gates.')
        effects[role] = [native_effect_audit(r['native_evidence'], recovery[role]['planned']) for r in records]
    if total != row['events']:
        raise RuntimeError('Historical D/S/H support lost or duplicated events.')
    h = recovery['H']; criterion = protocol['criterion']
    success = h['precision'] >= criterion['H_precision'] and h['recall'] >= criterion['H_recall']
    if row['anchor_success'] is not success:
        raise RuntimeError('Stored recovery success differs from the locked criterion.')
    return {'recovery': recovery, 'success': success, 'selected_native_effects': effects}


def summarize(directory):
    directory = Path(directory).resolve(); binding_path = directory.with_name(directory.name+'.source-capsule.json')
    binding = json.loads(binding_path.read_text()); args = binding['arguments']
    if binding['script'] != 'qualify_history.py' or args[args.index('--panel')+1] != 'qualification':
        raise RuntimeError('Only the original complete historical qualification panel is admitted.')
    scenario = args[args.index('--scenario')+1]; capsule, identity = snapshot(binding['source_identity'])
    if sha(capsule/'source-manifest.json') != binding['source_manifest_sha256']:
        raise RuntimeError('Historical source binding changed.')
    protocol = recorded_protocol(capsule)
    if scenario not in protocol['scenarios']:
        raise RuntimeError('Scenario outside the locked protocol.')
    profile = None; rows = []
    start,end=protocol['seeds']['qualification']
    for seed in range(start,end+1):
        path = directory/f'{seed}.json'; row = json.loads(path.read_text())
        if profile is None:
            profile = row['profile']
        if (row['profile'] != profile or profile['protocol'] != protocol
                or profile['scenario'] != scenario or profile['panel'] != 'qualification'
                or profile['strategies'] is not None or profile['full_profile'] is not False
                or profile['harness_sha256'] != sha(capsule/'validation/cg4/qualify_history.py')):
            raise RuntimeError('Altered/mixed historical profiles cannot be silently pooled.')
        for name, digest in profile['source_sha256'].items():
            if sha(capsule/name) != digest:
                raise RuntimeError('Recorded analytical source differs from its capsule.')
        if 'diagnostics_harness_sha256' in profile and profile['diagnostics_harness_sha256'] != sha(capsule/'validation/cg4/qualification_diagnostics.py'):
            raise RuntimeError('Recorded diagnostics harness changed.')
        audit_runner(profile,capsule,required=protocol['schema_version']=='numek.cg4_historical_recovery_protocol/1.2')
        audited = trial_audit(row, seed, scenario, protocol)
        rows.append({'seed': seed, 'path': str(path.relative_to(ROOT)), 'sha256': sha(path),
                     'input_sha256': row['input_sha256'], 'capture_digest': row['capture_digest'],
                     'seconds': row['seconds'], 'execution': row['execution'], **audited,
                     'product_diagnostics_recorded': 'investigation_diagnostics' in row})
    successes = sum(r['success'] for r in rows); interval = binomtest(successes, len(rows)).proportion_ci(method='exact')
    h_effects = [v for r in rows for v in r['selected_native_effects']['H']]
    return {'schema_version': 'numek.cg4_historical_recovery_summary/1.0', 'scenario': scenario,
            'source_identity': identity, 'source_binding_sha256': sha(binding_path), 'profile': profile,
            'trials': rows, 'successes': successes, 'required_successes': 32,
            'anchor_criterion_met': successes >= 32, 'success_fraction_MC95': [float(interval.low), float(interval.high)],
            'role_medians': {role: {metric: float(np.median([r['recovery'][role][metric] for r in rows]))
                for metric in ('precision', 'recall', 'IoU')} for role in ('D', 'S', 'H')},
            'H_unavailable': {'total': sum(r['recovery']['H']['unavailable'] for r in rows),
                              'oracle_members': sum(r['recovery']['H']['unavailable_oracle_members'] for r in rows)},
            'H_selected_native_effects': {'count': len(h_effects), 'minimum': min(h_effects),
                                         'median': float(np.median(h_effects)), 'maximum': max(h_effects)},
            'diagnostics_recorded_trials': sum(r['product_diagnostics_recorded'] for r in rows),
            'scope': 'This frozen scenario and whole-entity D/S/H allocation only. Recovery is event-weighted; paired observations are not independent row replicates. H native effects are descriptive, overlapping and not selected using H. No formal confirmation, temporal inference, individual-strategy qualification or controlled concurrent-host resource comparison. Missing historical diagnostics remain unrecorded.'}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--directory', required=True); parser.add_argument('--out', required=True)
    args = parser.parse_args(); result = summarize(args.directory); result['aggregation_source_sha256'] = sha(Path(__file__))
    with Path(args.out).open('x') as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False); stream.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k not in {'trials', 'profile'}}, sort_keys=True))


if __name__ == '__main__':
    main()
