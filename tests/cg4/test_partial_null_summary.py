import copy
import importlib.util
from pathlib import Path
import sys

import pytest


def tool():
    directory=Path(__file__).resolve().parents[2]/'validation/cg4';sys.path.insert(0,str(directory))
    try:
        spec=importlib.util.spec_from_file_location('_cg4_partial_summary',directory/'summarize_partial_null.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
    finally:sys.path.pop(0)


def example():
    claim={'hypothesis_id':'a','truth':{'numerator':0,'denominator':1,'effect':0.,'null':True},
        'state':'confirmed','interval':{'lower':.01,'upper':.2,'family_size':2,'confidence':.95,'adjustment':'bonferroni'},
        'false_confirmation':True,'noncoverage':True}
    unavailable={'hypothesis_id':'b','truth':None,'state':'statistically_inadmissible','interval':None,
        'false_confirmation':False,'noncoverage':False}
    return {'actual_family':2,'claims':[claim,unavailable],'false_confirmation':True,'family_noncoverage':True}


def test_partial_null_audit_recomputes_exact_truth_coverage_and_states():
    module=tool();row=example()
    assert module.claim_audit(row)=={'false_confirmation':True,'family_noncoverage':True}
    for change in ('sign','rational','coverage','state','family','aggregate','duplicate'):
        bad=copy.deepcopy(row);a=bad['claims'][0]
        if change=='sign':a['truth']['null']=False
        elif change=='rational':a['truth']['denominator']=0
        elif change=='coverage':a['noncoverage']=False
        elif change=='state':a['state']='inconclusive'
        elif change=='family':a['interval']['family_size']=1
        elif change=='aggregate':bad['family_noncoverage']=False
        else:bad['claims'][1]['hypothesis_id']='a'
        with pytest.raises(RuntimeError):module.claim_audit(bad)


def test_partial_null_rational_endpoint_and_unavailable_denominators():
    row=example();a=row['claims'][0]
    a.update(truth={'numerator':1,'denominator':8,'effect':.125,'null':False},state='confirmed',
        false_confirmation=False,noncoverage=False)
    a['interval'].update(lower=.125,upper=.25)
    row.update(false_confirmation=False,family_noncoverage=False)
    assert tool().claim_audit(row)=={'false_confirmation':False,'family_noncoverage':False}
    assert tool().claim_audit({'actual_family':0,'claims':[],'false_confirmation':False,'family_noncoverage':False})=={'false_confirmation':False,'family_noncoverage':False}
