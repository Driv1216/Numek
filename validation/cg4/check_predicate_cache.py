"""Check current cached/uncached proposals and legacy ternary membership."""
import hashlib
import json
from pathlib import Path
from types import ModuleType, SimpleNamespace
import zipfile

import numpy as np

from confidenceguard import FeatureField, InvestigationLimits
from confidenceguard import discovery_rules
from confidenceguard.features import normalize
from confidenceguard.investigation_membership import apply


def legacy(archive, name):
    module = ModuleType('confidenceguard._cg4_reference_'+name)
    module.__package__ = 'confidenceguard'
    raw = archive.read('src/confidenceguard/'+name+'.py')
    exec(compile(raw, 'captured-pre-cache/'+name+'.py', 'exec'), module.__dict__)
    return module


def population(seed):
    rng = np.random.default_rng(seed); n = 1200
    columns = {'cat': ('categorical', ['1', '01', '1.0', 'é', 'e\u0301', ' ', None]),
               'bool': ('boolean', ['true', 'false', '1', '0', 'invalid', None]),
               'integer': ('integer', [str(2**60+i) for i in range(17)]),
               'decimal': ('decimal', [str(i)+'.000000000000000001' for i in range(17)]),
               'float': ('float', [repr(i/13) for i in range(25)]),
               'time': ('timestamp', [f'2026-01-{i:02d}T00:00:00Z' for i in range(1, 20)])}
    data = {}
    for name, (kind, vocabulary) in columns.items():
        field = FeatureField(name, name, kind); cells = [normalize(vocabulary[i], field) for i in rng.integers(0, len(vocabulary), n)]
        for i in range(0, n, 37): cells[i] = {**cells[i], 'state': 'unavailable' if i%2 else 'not_retained'}
        data[name] = cells
    return data, rng.random(n) > .2, rng


def main():
    root = Path(__file__).with_name('results'); captured = root/'pre-predicate-cache-runtime-v1.zip'
    with zipfile.ZipFile(captured) as archive:
        old_membership = legacy(archive, 'investigation_membership')
    d, eligible, rng = population(6721); s, _, _ = population(6722); cache = {'_structured_masks_enabled': True}
    limits = InvestigationLimits(max_nodes=20000, max_depth=3, candidates_per_strategy=32)
    records = []
    for label, target in (('bernoulli', rng.integers(0, 2, len(eligible)).astype(float)), ('signed_mean', rng.normal(0, 1, len(eligible)))):
        objective = SimpleNamespace(spec=SimpleNamespace(direction='higher', metric='error_rate' if label == 'bernoulli' else 'bias'), identity={'test_objective': label})
        uncached = discovery_rules.propose(d, eligible, target, objective, limits)
        cached = discovery_rules.propose(d, eligible, target, objective, limits, predicate_cache=cache)
        assert uncached == cached
        expected = uncached
        masks = 0
        for proposal in expected[0]:
            for data in (d, s):
                original = old_membership.apply(proposal['artifact'], data, {})
                measured = apply(proposal['artifact'], data, {}, cache=cache)
                repeated = apply(proposal['artifact'], data, {}, cache=cache)
                for key in ('member', 'available', 'reason'):
                    assert np.array_equal(original[key], measured[key]) and np.array_equal(original[key], repeated[key])
                masks += 1
        records.append({'objective': label, 'exact_proposal_and_status_parity': True, 'membership_populations_compared': masks,
                        'artifact_digests': [p['artifact']['artifact_digest'] for p in expected[0]]})
    assert cache['_structured_mask_bytes'] <= 32*1024**2
    result = {'schema_version': 'numek.cg4_predicate_cache_parity/2.0', 'reference_archive': str(captured),
              'reference_sha256': hashlib.sha256(captured.read_bytes()).hexdigest(), 'panels': records,
              'retained_mask_bytes': cache['_structured_mask_bytes'], 'ceiling_bytes': 32*1024**2,
              'scope': 'Current observation-frequency quantile vocabulary: cached and uncached proposal/status/artifact parity; legacy ternary D/S membership parity. The old unique-value numeric vocabulary is intentionally not treated as the current proposal reference. Full-pipeline/resource evidence remains separate.'}
    with (root/'predicate-cache-parity-v2.json').open('x') as stream: json.dump(result, stream, sort_keys=True, indent=2); stream.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'panels'}))


if __name__ == '__main__':
    main()
