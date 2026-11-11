"""Read-only D-target/native-metric parity, not recovery qualification."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
OLD = '59f6784386f6a7b1db909ddb59f564f5154283198175d2c8f32cf0489078955c'
NEW = '587d12d2bee5fe896f5f071c41e3f3961164b07ea81e33f02d8f33bb9846e980'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', choices=[OLD, NEW], required=True)
    parser.add_argument('--fixtures', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    import confidenceguard
    from confidenceguard.investigation import arguments, prepared
    from confidenceguard.investigation_objectives import bind
    expected = ROOT/'validation/cg4/source-capsules.nosync'/args.source/'src'
    assert Path(confidenceguard.__file__).resolve().is_relative_to(expected)
    # The same unchanged locked generator supplies both implementations.
    sys.path.insert(0, str(ROOT/'validation/cg4/source-capsules.nosync'/OLD/'validation/cg4'))
    from qualify_objectives import PANELS, generate
    records = {}
    for panel in PANELS:
        directory = Path(args.fixtures)/panel
        directory.mkdir(parents=True, exist_ok=True)
        spec, _ = generate(directory, 7, 1200, panel)
        s, c, roots = arguments(spec, None, None)
        with prepared(s, c, roots) as p:
            objective = bind(s.objectives[0], p.store)
            keys, eligible, target = objective.training('D')
            native = objective.evaluate("cg4_role='D'", 'native_D_parity')
            records[panel] = {
                'input_sha256': hashlib.sha256((directory/'predictions.csv').read_bytes()).hexdigest(),
                'objective_identity': objective.identity,
                'key_sha256': hashlib.sha256(json.dumps(keys).encode()).hexdigest(),
                'eligible_sha256': hashlib.sha256(eligible.tobytes()).hexdigest(),
                'D_target_sha256': hashlib.sha256(np.asarray(target, dtype='<f8').tobytes()).hexdigest(),
                'binary': objective.binary, 'bounds': list(objective.bounded),
                'native_D': {key: native[key] for key in ['value', 'value_state', 'support', 'metric_identity']},
            }
    result = {'source_identity': args.source, 'import_origin': confidenceguard.__file__,
        'development_seed': 7, 'units': 1200, 'H_outcomes_evaluated': False,
        'records': records, 'scope': 'One deterministic D/native-metric regression fixture per existing campaign objective. No discovery fit, selection, H reduction, method qualification, or claim that old source is the new source.'}
    with Path(args.out).open('x') as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')
    print('Recorded', len(records), 'objective contracts and D targets for', args.source)


if __name__ == '__main__':
    main()
