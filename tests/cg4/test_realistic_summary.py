import copy
import importlib.util
from pathlib import Path

import pytest


def tool():
    path=Path(__file__).resolve().parents[2]/'validation/cg4/summarize_realistic.py'
    spec=importlib.util.spec_from_file_location('_cg4_realistic_summary',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def example():
    effect={'planned':1,'available':1,'unavailable':0,'effect':-.05}
    population={'planned':1,'members':1,'unavailable':0,'precision':.2,'recall':.3,'IoU':.1,
        'selected_native_effects':[effect]}
    journey={'kind':'natural','selected':1,'population_measurements':{role:copy.deepcopy(population) for role in ('D','S','H')},
        'assessments':[{'state':'statistically_inadmissible','strength':'descriptive',
            'reason':'external_exposure_unknown,upstream_independence_unknown'}],'execution':{'status':'completed'}}
    injected=copy.deepcopy(journey);injected['kind']='injected'
    return {'dataset':'bank','status':'completed','T_DSH_overlap':False,'T_count':2,'evaluation_count':3,
        'profile':{'bank_train':2,'bank_evaluate':3},'journeys':[journey,injected]}


def test_realistic_audit_preserves_negative_effects_and_weak_recovery():
    result=tool().audit(example())
    assert [j['kind'] for j in result]==['natural','injected']
    assert result[0]['H']['selected_native_effects'][0]['effect']==-.05
    assert result[1]['H']['precision']==.2 and result[1]['H']['recall']==.3


def test_realistic_audit_refuses_invalidated_missing_H_and_false_independence():
    for kind in ('invalidated','overlap','missing_H','lost_population','false_confirmation','wrong_refusal'):
        row=example();journey=row['journeys'][0]
        if kind=='invalidated':row['status']='invalidated_source_change'
        elif kind=='overlap':row['T_DSH_overlap']=True
        elif kind=='missing_H':journey['population_measurements']['H']['selected_native_effects']=[]
        elif kind=='lost_population':journey['population_measurements']['H']['selected_native_effects'][0]['unavailable']=1
        elif kind=='false_confirmation':journey['assessments'][0]['state']='confirmed'
        else:journey['assessments'][0]['reason']='joint_BCa_confirmation_qualification_unresolved'
        with pytest.raises(RuntimeError):tool().audit(row)
