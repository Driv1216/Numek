import copy
import importlib.util
from pathlib import Path
import sys

import pytest


def tool():
    directory = Path(__file__).resolve().parents[2]/'validation/cg4'; sys.path.insert(0, str(directory))
    try:
        spec = importlib.util.spec_from_file_location('_cg4_gate_diagnostics_summary', directory/'summarize_gate_diagnostics.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
    finally:
        sys.path.pop(0)


def test_fidelity_uses_joint_support_without_losing_unknown_members():
    module = tool()
    # Three gate members have no applicable surrogate, and must remain visible
    # even though conditional recall among joint observations is 6/8.
    value = {'status': 'measured', 'planned': 20, 'gate_available': 18, 'surrogate_available': 16,
             'jointly_available': 14, 'unavailable': 6, 'gate_members_without_surrogate': 3,
             'true_positive': 6, 'false_positive': 2, 'false_negative': 2, 'true_negative': 4,
             'precision': .75, 'recall': .75, 'disagreement_rate': 4/14, 'defines_membership': False}
    module.fidelity_audit(value)
    for key, change in [('recall', 6/11), ('unavailable', 2), ('gate_members_without_surrogate', 5),
                        ('jointly_available', 18), ('defines_membership', True), ('true_negative', 5)]:
        bad = copy.deepcopy(value); bad[key] = change
        with pytest.raises(RuntimeError):
            module.fidelity_audit(bad)
