import numpy as np

from confidenceguard import FeatureField
from confidenceguard.features import normalize, predicate_masks
from confidenceguard.investigation_membership import apply, seal
from confidenceguard.discovery_rules import numeric_cuts


def test_cached_masks_preserve_lexical_states_and_population_identity():
    field = FeatureField('cat', 'cat')
    cells = [normalize(v, field) for v in ('1', '01', '1.0', None, '1')]
    cells[-1] = {**cells[-1], 'state': 'unavailable'}
    clause = {'field': 'cat', 'op': 'eq', 'value': '1', 'kind': 'categorical'}
    gate = seal('structured', {'clauses': [clause]}, features=['cat'], objective={})
    cache = {'_structured_masks_enabled': True}
    for _ in range(2):
        measured = apply(gate, {'cat': cells}, {}, cache=cache)
        assert measured['member'].tolist() == [True, False, False, False, False]
        assert measured['available'].tolist() == [True, True, True, True, False]
    other = list(reversed(cells))
    measured = apply(gate, {'cat': other}, {}, cache=cache)
    assert measured['member'].tolist() == [False, False, False, False, True]
    assert measured['available'].tolist() == [False, True, True, True, True]
    valid, mask = predicate_masks(cells, clause, cache)
    assert not valid.flags.writeable and not mask.flags.writeable


def test_mask_retention_budget_does_not_change_uncached_membership():
    cells = [normalize(str(i), FeatureField('n', 'n', 'integer')) for i in range(100)]
    clause = {'field': 'n', 'op': 'gt', 'value': '50', 'kind': 'integer'}
    full = {'_structured_mask_bytes': 32*1024**2}
    before = set(full)
    valid, mask = predicate_masks(cells, clause, full)
    assert set(full) == before and full['_structured_mask_bytes'] == 32*1024**2
    assert valid.all() and np.array_equal(mask, np.arange(100) > 50)


def test_numeric_vocabulary_uses_observation_frequencies_and_exact_order_statistics():
    from decimal import Decimal
    observed = [Decimal('0')]*900 + [Decimal(i) for i in range(1, 101)]
    assert numeric_cuts(observed, 16) == [Decimal('0'), Decimal('37')]
    assert numeric_cuts(list(reversed(observed)), 16) == [Decimal('0'), Decimal('37')]
    assert numeric_cuts([2**60+i for i in range(17)], 4) == [2**60+4, 2**60+8, 2**60+12]
    assert numeric_cuts([Decimal('1.000000000000000001')]*100, 16) == [Decimal('1.000000000000000001')]


def test_cg4_result_defaults_preserve_earlier_defaults_and_explicit_caller_budgets():
    from confidenceguard import EvaluationConfig
    from confidenceguard.investigation import configuration
    assert EvaluationConfig().result_bytes == 32*1024**2
    assert configuration().result_bytes == configuration({}).result_bytes == 256*1024**2
    assert configuration({'result_bytes':1024**2}).result_bytes == 1024**2
    supplied = EvaluationConfig(result_bytes=64*1024**2)
    assert configuration(supplied) is supplied
