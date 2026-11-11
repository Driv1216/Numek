import copy
import importlib.util
from pathlib import Path
import sys
import pytest


def tool():
    directory=Path(__file__).resolve().parents[2]/'validation/cg4';sys.path.insert(0,str(directory))
    try:
        spec=importlib.util.spec_from_file_location('_cg4_null_summary',directory/'summarize_null.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
    finally:sys.path.pop(0)


def audit():return tool().assessment_audit


def test_frozen_family_keeps_unavailable_claim_in_allocation():
    objective={'metric':'error_rate','comparator':'complement','direction':'higher'}
    claim={'hypothesis_id':'first','objective':objective,'practical_threshold':0.,'state':'confirmed',
        'interval':{'lower':.01,'upper':.3,'family_size':2,'confidence':.95,'adjustment':'bonferroni'},
        'inference':{'allocated_alpha':.025,'elementary_intervals':2}}
    unavailable={'hypothesis_id':'second','objective':objective,'practical_threshold':0.,'state':'statistically_inadmissible'}
    row={'assessments':[claim,unavailable],'false_confirmation_under_complete_null':True}
    measured=audit()(row)
    assert measured['family_size']==2 and measured['available_intervals']==1
    assert measured['false_confirmation'] and measured['family_noncoverage']
    for field,value in [('family_size',1),('confidence',.90)]:
        changed=copy.deepcopy(row);changed['assessments'][0]['interval'][field]=value
        with pytest.raises(RuntimeError):audit()(changed)
    changed=copy.deepcopy(row);changed['false_confirmation_under_complete_null']=False
    with pytest.raises(RuntimeError):audit()(changed)


def test_zero_claim_trial_is_retained_and_does_not_invent_an_interval():
    measured=audit()({'assessments':[],'false_confirmation_under_complete_null':False})
    assert measured['family_size']==measured['available_intervals']==0
    assert not measured['false_confirmation'] and not measured['family_noncoverage']


def complete(panel,count,start,failures):
    return {'panel':panel,'completed_trials':count,'expected_seeds':[start,start+count-1],
        'false_confirmation_families':failures,
        'trials':[{'seed':start+i,'false_confirmation':i<failures} for i in range(count)]}


def test_joint_null_diagnostic_keeps_panels_and_applies_predeclared_Holm():
    from scipy.stats import binomtest
    module=tool();a=complete(module.PANELS[0],2000,130000,125);b=complete(module.PANELS[1],200,140000,18)
    measured=module.joint_diagnostic(a,b);rows=measured['diagnostics']
    p=[binomtest(k,n,.05,alternative='greater').pvalue for k,n in [(125,2000),(18,200)]]
    order=sorted(range(2),key=lambda i:p[i]);expected={order[0]:min(1,2*p[order[0]])}
    expected[order[1]]=max(expected[order[0]],p[order[1]])
    assert [r['trials'] for r in rows]==[2000,200]
    assert [r['Holm_adjusted_diagnostic_p'] for r in rows]==pytest.approx([expected[i] for i in range(2)])
    assert all(r['false_confirmation_MC95'][0]<r['false_confirmation_families']/r['trials']<r['false_confirmation_MC95'][1] for r in rows)
    assert measured['diagnostic_rejections']==[r['panel'] for r in rows if expected[rows.index(r)]<.05]


def test_joint_null_diagnostic_refuses_missing_duplicate_or_miscounted_evidence():
    module=tool();a=complete(module.PANELS[0],2000,130000,1);b=complete(module.PANELS[1],200,140000,0)
    for corrupt in ('incomplete','duplicate','miscount'):
        bad=copy.deepcopy(b)
        if corrupt=='incomplete':bad['trials'].pop()
        elif corrupt=='duplicate':bad['trials'][-1]['seed']=bad['trials'][0]['seed']
        else:bad['false_confirmation_families']=1
        with pytest.raises(RuntimeError):module.joint_diagnostic(a,bad)
    with pytest.raises(RuntimeError):module.joint_diagnostic(b,a)


def test_revised_null_panel_keeps_same_diagnostic_and_refuses_cross_version_pooling():
    module=tool();a=complete(module.PANELS[0],2000,330000,1);b=complete(module.PANELS[1],200,340000,0)
    revised=module.joint_diagnostic(a,b)
    old=module.joint_diagnostic(complete(module.PANELS[0],2000,130000,1),complete(module.PANELS[1],200,140000,0))
    assert revised==old  # same mathematics, separately identified evidence
    with pytest.raises(RuntimeError,match='mix'):
        module.joint_diagnostic(a,complete(module.PANELS[1],200,140000,0))
