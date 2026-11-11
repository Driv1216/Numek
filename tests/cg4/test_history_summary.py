import copy
import importlib.util
from pathlib import Path
import sys

import pytest


def tool():
    directory = Path(__file__).resolve().parents[2]/'validation/cg4'; sys.path.insert(0, str(directory))
    try:
        spec = importlib.util.spec_from_file_location('_cg4_history_summary', directory/'summarize_history.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
    finally:
        sys.path.pop(0)


def evidence():
    objective = {'metric': 'error_rate', 'comparator': 'reference_period', 'reference_period': 'reference',
                 'current_period': 'current', 'practical_threshold': .15, 'direction': 'higher', 'units': 'fraction'}
    def metric(correct, errors):
        return {'support': correct+errors, 'value': errors/(correct+errors), 'value_state': 'finite',
                'objective_identity': objective.copy(), 'measurement': {'metric': 'accuracy',
                'value': correct/(correct+errors), 'value_state': 'finite',
                'denominator': correct+errors, 'sensitive_counts': [correct, errors]}}
    # Two observations per entity; the effect denominator is each period's ten
    # members, not all twenty member events or the planned one hundred events.
    return {'planned': 100, 'available': 100, 'unavailable': 0, 'members': 20, 'nonmembers': 80,
            'conditional_members': 10, 'conditional_nonmembers': 10,
            'member_metric': metric(6, 4), 'comparator_metric': metric(9, 1),
            'effect': .3, 'effect_state': 'finite'}


def test_history_audit_references_period_counts_not_learner_scores_or_all_events():
    module = tool(); original = evidence()
    assert module.native_effect_audit(original, 100) == pytest.approx(.3)
    for target, key, value in [('outer', 'effect', -.3), ('outer', 'conditional_members', 20),
                               ('outer', 'unavailable', 1), ('member', 'value', .6),
                               ('measurement', 'sensitive_counts', [4, 6]),
                               ('objective', 'comparator', 'complement')]:
        bad = copy.deepcopy(original)
        destination = {'outer': bad, 'member': bad['member_metric'],
                       'measurement': bad['member_metric']['measurement'],
                       'objective': bad['member_metric']['objective_identity']}[target]
        destination[key] = value
        with pytest.raises(RuntimeError):
            module.native_effect_audit(bad, 100)


def test_history_audit_does_not_relabel_recovery_as_confirmation():
    module = tool()
    row = {'status': 'completed', 'seed': 120000, 'scenario': 'current_risk_shift',
           'independent_entities': 40000, 'events': 80000, 'formal_confirmation_performed': True}
    with pytest.raises(RuntimeError, match='confirmation claim'):
        module.trial_audit(row, 120000, 'current_risk_shift', {'independent_entities': 40000})
