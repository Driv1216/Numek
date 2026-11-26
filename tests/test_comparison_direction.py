"""Stage 6A (J1): direction-preserving missingness and non-finite change in comparisons (m4_local_2026_11_25).

- increases at or beyond the threshold keep the existing finding exactly;
- decreases at or beyond it are recorded as a material change (evidence only): never a finding or warning;
- every column records its signed change, direction and magnitude;
- the v1 methodology (m4_local_2026_10_10) remains selectable and reproduces v1 output, with no direction fields.
"""
import numpy as np
import pandas as pd
import pytest

from datatrust import ComparisonSpec, DatasetInput, DatasetSpec, TaskSpec
from datatrust.m4_contracts import ComparisonConfig
from datatrust.m4_worker import compare

N = 400


def files(tmp_path, *, age_before, age_after, income_before=0.0, income_after=0.0, ratio_inf_before=0.0, ratio_inf_after=0.0):
    rng = np.random.default_rng(1)

    def frame(age_missing, income_missing, inf_share):
        d = pd.DataFrame({'id': range(N), 'age': rng.integers(18, 80, N).astype(float), 'income': rng.normal(50, 10, N),
                          'ratio': rng.normal(1, .1, N), 'city': rng.choice(list('abc'), N)})
        d.loc[: int(age_missing * N) - 1, 'age'] = np.nan
        d.loc[: int(income_missing * N) - 1, 'income'] = np.nan
        d.loc[: int(inf_share * N) - 1, 'ratio'] = np.inf
        return d
    paths = (tmp_path / 'reference.csv', tmp_path / 'current.csv')
    frame(age_before, income_before, ratio_inf_before).to_csv(paths[0], index=False)
    frame(age_after, income_after, ratio_inf_after).to_csv(paths[1], index=False)
    return paths


def run(paths, methodology=None):
    task = TaskSpec('dataset_profile')
    spec = ComparisonSpec('versions', (DatasetInput('source1', 'reference', DatasetSpec(str(paths[0])), task),
                                       DatasetInput('source2', 'current', DatasetSpec(str(paths[1])), task)))
    config = ComparisonConfig(**({'methodology': methodology} if methodology else {}))
    result = compare(spec, config)
    value = result.to_dict()
    measurements = value['coverage']['measurements']
    populations = measurements['source1:source2.populations']['columns']
    return value, {c['column']: c for c in populations}, measurements.get('source1:source2.material_changes')


def titles(value):
    return {f['title'] for f in value['findings']}


def test_a_decrease_is_a_material_change_not_a_finding(tmp_path):
    value, cols, material = run(files(tmp_path, age_before=.30, age_after=0.0))
    assert value['methodology_id'] == 'm4_local_2026_11_25' and value['execution']['method_version'] == 'm4_local_2026_11_25'
    assert cols['age']['missingness_direction'] == 'decrease' and cols['age']['missingness_magnitude'] == pytest.approx(.30)
    assert cols['age']['missingness_material_decrease'] and not cols['age']['missingness_review']
    assert material['evidence_type'] == 'material_change' and material['changes'] == [
        {'column': 'age', 'measure': 'missingness', 'from_share': .30, 'to_share': 0.0, 'direction': 'decrease', 'magnitude': pytest.approx(.30)}]
    assert 'Supported input or annotation populations differ' not in titles(value)
    assert 'not a defect' in material['meaning']


def test_an_increase_keeps_the_existing_finding_and_both_directions_coexist(tmp_path):
    value, cols, material = run(files(tmp_path, age_before=.30, age_after=0.0, income_before=0.0, income_after=.30))
    assert cols['income']['missingness_direction'] == 'increase' and cols['income']['missingness_review']
    assert 'Supported input or annotation populations differ' in titles(value)
    assert [c['column'] for c in material['changes']] == ['age']


def test_non_finite_decreases_follow_the_same_rule(tmp_path):
    value, cols, material = run(files(tmp_path, age_before=0, age_after=0, ratio_inf_before=.20, ratio_inf_after=0.0))
    assert cols['ratio']['nonfinite_direction'] == 'decrease' and cols['ratio']['nonfinite_material_decrease']
    assert material['changes'][0]['measure'] == 'nonfinite' and 'Supported input or annotation populations differ' not in titles(value)


def test_small_changes_and_no_change_record_direction_only(tmp_path):
    value, cols, material = run(files(tmp_path, age_before=.02, age_after=0.0))
    assert cols['age']['missingness_direction'] == 'decrease' and not cols['age']['missingness_material_decrease'] and material is None
    assert cols['city']['missingness_direction'] == 'none'


def test_the_v1_methodology_reproduces_v1_output(tmp_path):
    paths = files(tmp_path, age_before=.30, age_after=0.0, income_before=0.0, income_after=.30)
    value, cols, material = run(paths, 'm4_local_2026_10_10')
    assert value['methodology_id'] == 'm4_local_2026_10_10' and material is None
    assert not any(k.endswith(('_direction', '_magnitude', '_material_decrease')) for c in cols.values() for k in c)
    assert 'Supported input or annotation populations differ' in titles(value)
    with pytest.raises(ValueError, match='Unknown comparison methodology'):
        ComparisonConfig(methodology='m4_local_2099_01_01')


def test_the_interpretation_names_material_decreases_with_traceable_numbers(tmp_path):
    import re
    from datatrust.interpretation import interpret, resolve_fact
    value, _, _ = run(files(tmp_path, age_before=.30, age_after=0.0))
    sentence = next(s for s in interpret(value, 'm4')['summary'] if 'material' in s['text'])
    assert sentence['text'].startswith('1 material decrease (missing values in age)') and 'not a defect' in sentence['text']
    facts = {str(f['value']) for f in sentence['facts']}
    assert all(resolve_fact(value, f) == f['value'] for f in sentence['facts'])
    assert set(re.findall(r'\d[\d,]*(?:\.\d+)?', sentence['text'])) <= facts


def test_segment_material_changes_stay_in_their_scope_and_the_methodology_is_checked(tmp_path):
    with pytest.raises(ValueError, match='Unknown comparison methodology'):
        ComparisonConfig(methodology=['m4_local_2026_11_25'])
    from datatrust.interpretation import interpret
    value, _, material = run(files(tmp_path, age_before=.30, age_after=0.0))
    value['coverage']['measurements']['source1:source2:segment1:web.material_changes'] = dict(material)
    sentences = [s['text'] for s in interpret(value, 'm4')['summary'] if 'material' in s['text']]
    assert len(sentences) == 1
