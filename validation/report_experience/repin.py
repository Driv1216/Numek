"""Re-pin presentation-only fixtures after a deliberate report-presentation change (plan I.2).

Usage: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. .venv/bin/python -B -m validation.report_experience.repin

For every golden case it first re-asserts the analytical result against the fixture exactly as the pinning tests do,
then records only the new html_sha256; any other field differing aborts. It also regenerates the per-workflow
presentation identities and prints which families changed. Name the re-pin in CURRENT_STATE in the same change.
"""
import copy
import hashlib
import json
import sys
import tempfile
from pathlib import Path

import pandas as pd

from datatrust import AnalysisConfig, DataTrust, DatasetSpec, RegressionOptions, TaskSpec
from datatrust.renderer import render_analysis_result
from datatrust.report_identity import FAMILIES, PRINT_POLICY_VERSION, identity

ROOT = Path(__file__).resolve().parents[2]


def repin(path, compute):
    path = ROOT / path
    text = path.read_text()
    cases = json.loads(text)
    new = {name: compute(name, case) for name, case in cases.items()}
    for name, case in cases.items():
        if text.count(case['html_sha256']) != 1:
            raise SystemExit(f'{path}: {name} hash is not unique in the file.')
        text = text.replace(case['html_sha256'], new[name])
    after = json.loads(text)
    for name in after:
        if {k: v for k, v in after[name].items() if k != 'html_sha256'} != {k: v for k, v in cases[name].items() if k != 'html_sha256'}:
            raise SystemExit(f'{path}: {name} changed beyond html_sha256.')
    path.write_text(text)
    changed = sum(new[n] != cases[n]['html_sha256'] for n in cases)
    print(f'{path.relative_to(ROOT)}: {changed} of {len(cases)} html_sha256 values changed')


def m2(name, case):
    result = DataTrust.from_spec(DatasetSpec(**case['dataset']), TaskSpec('regression', case['target']),
                                 AnalysisConfig(regression=RegressionOptions.from_dict(case['options']))).analyze_result()
    result.generated_at = '2026-10-09T00:00:00+00:00'
    result.execution['elapsed_seconds'] = 0
    golden = copy.deepcopy(result)
    golden.execution['frame_bytes'] = case['result']['execution']['frame_bytes']
    if golden.to_dict() != case['result']:
        raise SystemExit(f'm2 {name}: analytical result differs; not re-pinning.')
    return hashlib.sha256(render_analysis_result(golden).encode()).hexdigest()


def unlabeled(folder):
    def compute(name, case):
        source = folder / 'source.csv'
        source.write_text(case['raw'])
        result = DataTrust.from_spec(DatasetSpec(source, dataset_name='M1 parity'), TaskSpec('dataset_profile')).analyze_result()
        result.generated_at = '2026-10-09T00:00:00+00:00'
        result.execution['elapsed_seconds'] = 0
        value = result.to_dict()
        if {k: value[k] for k in case['result']} != case['result']:
            raise SystemExit(f'unlabeled {name}: analytical result differs; not re-pinning.')
        frame = pd.read_csv(source)
        measured = int(frame.memory_usage(index=True, deep=True).sum())
        if sys.version_info >= (3, 12):
            strings = [v for column in frame for v in frame[column] if isinstance(v, str)]
            result.execution['frame_bytes'] = measured + 8 * len(strings)
        return hashlib.sha256(render_analysis_result(result).encode()).hexdigest()
    return compute


def main():
    with pd.option_context('mode.string_storage', 'python'), tempfile.TemporaryDirectory() as folder:
        repin('tests/fixtures/m2_baseline.json', m2)
        repin('tests/fixtures/m1_unlabeled_baseline.json', unlabeled(Path(folder)))
    path = ROOT / 'tests/fixtures/presentation_identities.json'
    pins = json.loads(path.read_text())
    old = pins['families']
    pins['print_policy'] = PRINT_POLICY_VERSION
    pins['families'] = {family: identity(family)['presentation_id'] for family in FAMILIES}
    path.write_text(json.dumps(pins, indent=1) + '\n')
    print('presentation identities changed:', sorted(f for f in pins['families'] if old.get(f) != pins['families'][f]) or 'none')


if __name__ == '__main__':
    main()
