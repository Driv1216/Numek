import importlib.util
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest

from confidenceguard.feature_contracts import FeatureField
from confidenceguard.features import normalize
from confidenceguard.investigation_membership import seal,apply


def diagnostics():
    path=Path(__file__).resolve().parents[2]/'validation/cg4/qualification_diagnostics.py'
    spec=importlib.util.spec_from_file_location('_cg4_gate_diagnostics',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def test_frozen_surrogate_counts_keep_both_sources_of_unavailable_membership_visible():
    module=diagnostics();field=FeatureField('x','x')
    cells=[normalize(v,field) for v in ['yes','no','yes','yes','yes']];cells[3]={**cells[3],'state':'not_retained'}
    reps={'v':{'vectors':np.array([[0,0],[.5,0],[2,0],[0,0],[0,0]],float),'available':np.array([True]*4+[False])}}
    parameters={'transform':{'normalization':'none','mean':None,'components':None},'centers':[[0.,0.]],
        'radii':[1.],'inner':[0.],'components':[0],'threshold':.5,'neighbors':1,'bandwidth':1.,'support_radius':3.}
    artifact=seal('geometric',parameters,representation='v');gate=apply(artifact,{'x':cells},reps)
    candidate={'explanation':{'kind':'approximate','definition':{'clauses':[{'field':'x','op':'eq','value':'yes','kind':'categorical'}]}}}
    measured=module.explanation_fidelity(candidate,artifact,gate,{'x':cells},reps,{},lambda *args:None)
    assert measured['planned']==5 and measured['gate_available']==measured['surrogate_available']==4
    assert measured['jointly_available']==3 and measured['unavailable']==2 and measured['gate_members_without_surrogate']==1
    assert [measured[k] for k in ('true_positive','false_positive','false_negative','true_negative')]==[1,1,1,0]
    assert measured['precision']==measured['recall']==.5 and measured['disagreement_rate']==pytest.approx(2/3)
    assert not measured['defines_membership'] and measured['basis']=='frozen_D_fitted_surrogate'
    assert sum(measured['surrogate_unavailable_reasons'].values())==1


def test_exact_definition_and_missing_surrogate_do_not_invent_coverage_or_perfect_empty_accuracy():
    module=diagnostics();gate={'member':np.zeros(3,bool),'available':np.array([True,True,False]),'reason':['','','not_retained']}
    exact=module.explanation_fidelity({'explanation':{'kind':'exact_predicate'}},{'kind':'structured'},gate,{}, {},{},lambda *args:None)
    assert exact['defines_membership'] and exact['precision'] is exact['recall'] is None
    assert exact['jointly_available']==2 and exact['unavailable']==1
    absent=module.explanation_fidelity({'explanation':{'kind':'approximate','reason':'no_tabular_surrogate_features'}},{'kind':'geometric'},gate,{}, {},{},lambda *args:None)
    assert absent['status']=='unavailable' and absent['planned']==3 and 'precision' not in absent
    with pytest.raises(RuntimeError):module.explanation_fidelity({'explanation':{'kind':'exact_predicate'}},{'kind':'geometric'},gate,{}, {},{},lambda *args:None)


def test_retention_is_a_copy_of_selected_diagnostics_not_new_qualification():
    module=diagnostics();candidate={'id':'a','strategy':'structured','stability':{'results':[{'membership_IoU':.25}]},'explanation':{'kind':'exact_predicate'}}
    result=SimpleNamespace(data={'investigation':{'shortlist':['a'],'candidates':[candidate,{'id':'b'}],'overlap':{'pairs':[]}}})
    saved=module.snapshot(result)
    assert len(saved['selected_candidates'])==1 and saved['schema_version']==module.VERSION
    saved['selected_candidates'][0]['stability']['results'][0]['membership_IoU']=1.
    assert candidate['stability']['results'][0]['membership_IoU']==.25
