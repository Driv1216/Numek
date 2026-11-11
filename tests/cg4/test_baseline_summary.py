import copy
import importlib.util
from pathlib import Path
import sys

import pytest


def tool():
    directory=Path(__file__).resolve().parents[2]/'validation/cg4';sys.path.insert(0,str(directory))
    try:
        spec=importlib.util.spec_from_file_location('_cg4_baseline_summary',directory/'summarize_baselines.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
    finally:sys.path.pop(0)


def test_baseline_audit_recomputes_heldout_counts_and_keeps_unknown_support():
    row={'true_positive':6,'false_positive':2,'false_negative':4,'planned':20,
        'unavailable':4,'unavailable_oracle_members':2,'precision':.75,'recall':.6,'IoU':.5}
    module=tool();module.recovery_audit(row)
    for key,value in [('IoU',.7),('precision',1.),('recall',1.),('unavailable',13),
        ('unavailable_oracle_members',5),('true_positive','6')]:
        bad=copy.deepcopy(row);bad[key]=value
        with pytest.raises(RuntimeError):module.recovery_audit(bad)
