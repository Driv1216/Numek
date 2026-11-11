"""References for oracle truth; no simulated H outcomes define null status."""
from fractions import Fraction
import importlib.util
from pathlib import Path
import sys
import numpy as np


def module():
    directory=Path(__file__).resolve().parents[2]/'validation/cg4'
    # Benchmark tools are not installed product modules.
    sys.path.insert(0,str(directory))
    try:
        spec=importlib.util.spec_from_file_location('_cg4_partial_null_panel',directory/'qualify_partial_null.py')
        loaded=importlib.util.module_from_spec(spec);spec.loader.exec_module(loaded)
        return loaded
    finally:sys.path.pop(0)


def test_population_null_status_is_exact_on_overlapping_and_nonnull_gates():
    panel=module();indices=np.arange(8);all_available=np.ones(8,bool)
    hot=((indices&1)>0)!=((indices&2)>0)
    assert panel.exact_effect(hot,all_available)==Fraction(3,10)
    assert panel.exact_effect(~hot,all_available)==Fraction(-3,10)
    # Every a/b/c marginal is exactly null despite overlapping a genuine failure.
    for bit in (1,2,4):assert panel.exact_effect((indices&bit)>0,all_available)==0
    assert panel.exact_effect(np.ones(8,bool),all_available) is None
    assert panel.exact_effect(hot,np.array([False]+[True]*7)) is None


def test_panel_locks_family_cycle_and_fresh_qualification_seeds():
    protocol=module().PROTOCOL
    assert protocol['seeds']['qualification']==[170000,170999]
    assert protocol['requested_families']==[1,10,32]
    assert protocol['delta']==0. and protocol['alpha']==.05
    assert 'actual family' in protocol['family_selection'] and 'No H or oracle selection' in protocol['family_selection']
