"""Bounded developer profiling, never method-qualification evidence."""
import argparse
import cProfile
import hashlib
import json
from pathlib import Path
import pstats
import tempfile

from qualify_pipeline import generate, identity


def worker(spec, *, progress=None):
    from confidenceguard.investigation import _discover, arguments
    from confidenceguard.result import Inspection
    spec, config, roots = arguments(spec, None, None)
    profiler = cProfile.Profile()
    result = profiler.runcall(_discover, spec, config, roots, None, progress=progress)
    rows = []
    for (filename, line, function), (primitive, calls, own, cumulative, _) in pstats.Stats(profiler).stats.items():
        rows.append({'file': filename, 'line': line, 'function': function, 'primitive_calls': primitive,
                     'calls': calls, 'own_seconds': own, 'cumulative_seconds': cumulative})
    return Inspection({'top_cumulative': sorted(rows, key=lambda r: -r['cumulative_seconds'])[:60],
                       'top_own': sorted(rows, key=lambda r: -r['own_seconds'])[:40],
                       'candidates': len(result.data['investigation']['candidates'])}, result.execution)


def main():
    from confidenceguard import compat, EvaluationConfig
    parser = argparse.ArgumentParser(); parser.add_argument('--out', required=True); args = parser.parse_args()
    sources = identity()
    with tempfile.TemporaryDirectory(prefix='numek-cg4-profile-', dir='/private/tmp') as root:
        spec, _, _ = generate(Path(root), 0, 6000, 'interaction_without_marginals')
        measured = compat.supervise(worker, (spec,), EvaluationConfig())
    record = {'schema_version': 'numek.cg4_development_profile/1.0', 'source_sha256': sources,
              'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'result': measured.to_dict(),
              'status': 'completed' if sources == identity() else 'source_changed',
              'scope': 'Developer CPU profile under concurrent load and profiler overhead; not a recovery or capacity qualification.'}
    with Path(args.out).open('x') as stream: json.dump(record, stream, sort_keys=True, indent=2); stream.write('\n')


if __name__ == '__main__':
    main()
