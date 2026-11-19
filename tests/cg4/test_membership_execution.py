import threading
from dataclasses import replace
import numpy as np
import pytest
from confidenceguard import MembershipArtifact,FeatureField,EvaluationError,investigate
from confidenceguard.features import normalize
from confidenceguard.investigation_membership import seal,apply,validate
from .helpers import binary


def gate():
    return seal('structured',{'clauses':[{'field':'x','kind':'categorical','op':'eq','value':'1'}]},features=['x'],objective={})


def test_public_frozen_application_is_supervised_and_preserves_ternary_membership():
    artifact=MembershipArtifact(gate());cells=[normalize(v,FeatureField('x','x')) for v in ['1','0',None]]
    cells.append({**cells[-1],'state':'not_retained'})
    original=apply(artifact.data,{'x':cells},{})
    measured=artifact.apply({'x':cells},config={'threads':1})
    for key in ('member','available','reason'):assert np.array_equal(measured[key],original[key])
    assert measured['execution']['status']=='completed' and measured['execution']['peak_worker_rss_bytes']>0
    cancelled=threading.Event();cancelled.set()
    with pytest.raises(EvaluationError) as interrupted:artifact.apply({'x':cells},cancel=cancelled)
    assert interrupted.value.code=='cancelled'


def test_bad_alignment_types_and_resource_requirements_refuse_before_native_worker(monkeypatch):
    artifact=MembershipArtifact(gate());cells=[normalize('1',FeatureField('x','x'))]
    def unexpected(*args,**kwargs):raise AssertionError('Malformed input reached the worker')
    monkeypatch.setattr('confidenceguard.execution_context.ctx.run',unexpected)   # no phase may execute
    with pytest.raises(EvaluationError):artifact.apply({'x':cells,'other':[]})
    with pytest.raises(EvaluationError):artifact.apply({'x':[{'kind':[], 'state':'observed'}]})
    with pytest.raises(EvaluationError) as kind:artifact.apply({'x':[normalize('1',FeatureField('x','x','integer'))]})
    assert kind.value.code=='membership_feature_contract'
    with pytest.raises(EvaluationError):artifact.apply({}, {'v':{'vectors':np.ones((2,3),object),'available':np.ones(2,bool)}})
    with pytest.raises(EvaluationError):artifact.apply({'x':cells},config={'max_rss_bytes':1024})


def test_tampered_dependencies_and_unrepresentable_geometric_parameters_refuse():
    assert MembershipArtifact(gate(),{'unused':'unrelated source data'}).models=={}
    packet=gate();packet['features']=['x','unused']
    from confidenceguard.contracts import digest
    packet['artifact_digest']=digest({k:v for k,v in packet.items() if k!='artifact_digest'})
    with pytest.raises(EvaluationError):validate(packet)
    parameters={'transform':{'normalization':'none','mean':None,'components':None},'centers':[[0.,0.]],
        'radii':[1e308],'inner':[0.],'components':[0],'threshold':.5,'neighbors':1,'bandwidth':1.,'support_radius':1.}
    with pytest.raises(EvaluationError) as overflow:seal('geometric',parameters,representation='v')
    assert overflow.value.code=='geometry_numeric_range'


def test_catboost_honors_single_thread_fit_and_frozen_application(tmp_path):
    result=investigate(binary(tmp_path,strategies=('catboost',)),config={'threads':1})
    fits=result.data['investigation']['strategies'][0]['fits']
    assert fits and all(f['threads']==1 for f in fits if f.get('execution')!='not_run')
    packet=next(iter(result.private['artifacts'].values()));artifact=MembershipArtifact(packet,result.private['models'])
    features={fid:[normalize(v,FeatureField(fid,fid)) for v in ['0','1','new',None]] for fid in packet['features']}
    single=artifact.apply(features,config={'threads':1})
    original=apply(packet,features,{},cache={'_models':result.private['models'],'_threads':2})
    for key in ('member','available','reason','margin'):assert np.array_equal(single[key],original[key],equal_nan=True) if key=='margin' else np.array_equal(single[key],original[key])


def test_fit_budget_includes_initial_training_and_is_not_silently_relaxed(tmp_path):
    spec=binary(tmp_path,strategies=('catboost',));spec=replace(spec,limits=replace(spec.limits,diagnostic_fits=1))
    from confidenceguard import inspect_investigation
    admission=inspect_investigation(spec)['diagnostic_fit_admission']
    assert admission['maximum_fits']==1 and admission['initial_fit_ceiling']==2 and admission['counts_stability_refits']
    with pytest.raises(EvaluationError) as exhausted:investigate(spec)
    assert exhausted.value.code=='diagnostic_fit_limit'
