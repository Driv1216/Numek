"""Read-only diagnostics for a complete, source-audited recovery panel.

Gates within a trial overlap; pooled gate summaries are descriptive, not independent
replicates or tests of algorithm superiority. Missing older diagnostics stay missing.
"""
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path

import numpy as np

from run_locked_qualification import ROOT, snapshot, sha
from summarize_recovery import recover_panel
from summarize_baselines import recovery_audit


def fidelity_audit(value):
    if value['status'] == 'unavailable':
        return
    if value['status'] != 'measured':
        raise RuntimeError('Unrecognized fidelity state.')
    names = ('planned', 'gate_available', 'surrogate_available', 'jointly_available', 'unavailable',
             'gate_members_without_surrogate', 'true_positive', 'false_positive', 'false_negative', 'true_negative')
    if any(type(value[k]) is not int or value[k] < 0 for k in names):
        raise RuntimeError('Invalid fidelity support counts.')
    n = value['planned']; joint = value['jointly_available']
    tp, fp, fn, tn = (value[k] for k in names[-4:])
    if (tp+fp+fn+tn != joint or joint+value['unavailable'] != n
            or not 0 <= joint <= min(value['gate_available'], value['surrogate_available']) <= n
            or value['gate_available']+value['surrogate_available']-joint > n
            or value['gate_members_without_surrogate'] > value['gate_available']-joint):
        raise RuntimeError('Fidelity lost unavailable observations or changed the joint denominator.')
    expected = {'precision': tp/(tp+fp) if tp+fp else None, 'recall': tp/(tp+fn) if tp+fn else None,
                'disagreement_rate': (fp+fn)/joint if joint else None}
    for key, reference in expected.items():
        if (reference is None and value[key] is not None
                or reference is not None and (value[key] is None or not math.isclose(value[key], reference, abs_tol=1e-14))):
            raise RuntimeError('Stored fidelity disagrees with frozen gate/surrogate counts.')
    if value['defines_membership'] and (fp or fn or value['gate_members_without_surrogate']):
        raise RuntimeError('An exact explanation disagrees with membership.')


def distribution(values):
    values = [v for v in values if v is not None]
    return {'recorded': len(values), 'minimum': min(values) if values else None,
            'median': float(np.median(values)) if values else None, 'maximum': max(values) if values else None}


def summarize(directory):
    anchor = recover_panel(directory); capsule, _ = snapshot(anchor['source_identity'])
    rows = []; by_strategy = defaultdict(list); missing = []; fidelity_states = Counter()
    for trial in anchor['trials']:
        path = ROOT/trial['path']; row = json.loads(path.read_text()); diagnostics = row.get('investigation_diagnostics')
        if diagnostics is None:
            missing.append(trial['seed']); continue
        expected = sha(capsule/'validation/cg4/qualification_diagnostics.py')
        if diagnostics['harness_sha256'] != expected or row['profile'].get('diagnostics_harness_sha256') != expected:
            raise RuntimeError('Recorded diagnostic source differs from the captured harness.')
        chosen = set(row['shortlist']); candidates = diagnostics['selected_candidates']
        if len(candidates) != len(chosen) or {c['id'] for c in candidates} != chosen:
            raise RuntimeError('Diagnostics do not cover exactly the frozen selected candidates.')
        gates = {role: {c['candidate_id']: c for c in row['recovery'][role]['selected_candidates']} for role in ('D', 'S', 'H')}
        if any(set(values) != chosen for values in gates.values()):
            raise RuntimeError('Held-out diagnostics lost selected gate identities.')
        retained = []
        for candidate in candidates:
            cid = candidate['id']; strategy = candidate['strategy']; roles = {}
            for role in ('D', 'S', 'H'):
                gate = gates[role][cid]; recovery_audit(gate)
                if gate['strategy'] != strategy or gate['planned'] != trial['recovery'][role]['planned']:
                    raise RuntimeError('Gate identity/planned population changed across roles.')
                fidelity = gate['frozen_explanation_fidelity']; fidelity_audit(fidelity)
                fidelity_states[(role, strategy, fidelity['status'])] += 1
                roles[role] = {'recovery': {k: gate[k] for k in ('precision', 'recall', 'IoU', 'planned', 'unavailable', 'unavailable_oracle_members')},
                               'fidelity': fidelity}
            stability = candidate.get('stability', {})
            replicates = stability.get('results', [])
            if stability.get('median_membership_IoU') is not None:
                scores = [v['membership_IoU'] for v in replicates]
                if (len(scores) != stability['replicates'] or any(not 0 <= v <= 1 for v in scores)
                        or not math.isclose(float(np.median(scores)), stability['median_membership_IoU'], abs_tol=1e-14)):
                    raise RuntimeError('Stability summary differs from its recorded perturbations.')
            record = {'id': cid, 'strategy': strategy, 'roles': roles,
                      'stability': stability, 'explanation_kind': candidate.get('explanation', {}).get('kind')}
            retained.append(record); by_strategy[strategy].append(record)
        overlap = diagnostics['overlap']
        if overlap['shortlist_union_support'] != sum(row['recovery']['S']['primary_selected_union'][k] for k in ('true_positive', 'false_positive')):
            raise RuntimeError('Unique S union differs from selected recovery; never sum overlap supports.')
        selected_pairs = [p for p in overlap['pairs'] if p['left'] in chosen and p['right'] in chosen]
        # The product retains intersecting pairs. A complete overlapping-pair
        # listing does not contain disjoint pairs and is not C(shortlist, 2).
        if len({tuple(sorted((p['left'], p['right']))) for p in selected_pairs}) != len(selected_pairs):
            raise RuntimeError('Duplicated selected overlapping pair.')
        for pair in selected_pairs:
            supports = [sum(gates['S'][cid][k] for k in ('true_positive', 'false_positive')) for cid in (pair['left'], pair['right'])]
            intersection = pair['intersection']; union = pair['union']
            if (type(intersection) is not int or not 0 < intersection <= min(supports)
                    or union != sum(supports)-intersection or not math.isclose(pair['jaccard'], intersection/union, abs_tol=1e-14)):
                raise RuntimeError('Overlap counts disagree with unique selected-gate support.')
        rows.append({'seed': trial['seed'], 'path': trial['path'], 'sha256': trial['sha256'], 'gates': retained,
                     'S_unique_union_support': overlap['shortlist_union_support'],
                     'S_shortlist_pair_Jaccard': distribution([p['jaccard'] for p in selected_pairs]),
                     'shortlist_pairs_complete': overlap.get('shortlist_pairs_complete', False),
                     'all_candidate_pairs_complete': overlap['pair_coverage_complete']})
    summaries = {}
    for strategy, records in sorted(by_strategy.items()):
        summaries[strategy] = {'selected_gate_occurrences': len(records),
            'D_perturbation_membership_IoU': distribution([r['stability'].get('median_membership_IoU') for r in records]),
            'roles': {role: {'oracle_recovery': {key: distribution([r['roles'][role]['recovery'][key] for r in records]) for key in ('precision', 'recall', 'IoU')},
                'frozen_explanation_fidelity': {key: distribution([r['roles'][role]['fidelity'].get(key) for r in records]) for key in ('precision', 'recall', 'disagreement_rate')},
                'fidelity_unavailable_records': sum(r['roles'][role]['fidelity'].get('unavailable', r['roles'][role]['fidelity']['planned']) for r in records),
                'membership_unavailable_records': sum(r['roles'][role]['recovery']['unavailable'] for r in records)} for role in ('D', 'S', 'H')}}
    return {'schema_version': 'numek.cg4_recovery_gate_diagnostics_summary/1.0', 'archetype': anchor['archetype'],
            'source_identity': anchor['source_identity'], 'source_binding_sha256': anchor['source_binding_sha256'],
            'anchor_successes': anchor['successes'], 'diagnostics_recorded_trials': len(rows),
            'unrecorded_trial_seeds': missing, 'trials': rows, 'strategy_descriptive_summaries': summaries,
            'fidelity_states': [{'role': role, 'strategy': strategy, 'status': status, 'count': count}
                                for (role, strategy, status), count in sorted(fidelity_states.items())],
            'scope': 'Complete source-audited recovery panel. Strategies are described only among S-selected gates; selection rates do not measure each strategy\'s independent recovery or complementary contribution. Gates and supports overlap, so totals are gate-occurrences, not unique observations or independent trials. No H selection, backfilled diagnostics, universal fidelity label, stability guarantee or algorithm promotion.'}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--directory', required=True); parser.add_argument('--out', required=True)
    args = parser.parse_args(); result = summarize(args.directory); result['aggregation_source_sha256'] = sha(Path(__file__))
    with Path(args.out).open('x') as stream:
        json.dump(result, stream, sort_keys=True, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'trials'}, sort_keys=True))


if __name__ == '__main__':
    main()
