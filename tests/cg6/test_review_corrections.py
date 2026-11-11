"""Bounded regressions for the independent CG6 review, R1–R6."""
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock
import csv

import numpy as np
import pytest

from confidenceguard import (
    AuxiliaryArtifact, ClockSpec, DecisionSpec, DeviceSpec, EvaluationConfig,
    EvaluationError, ExecutionLimits, FeatureField, OutputBinding,
    RobustnessAssessmentSpec, RobustnessClaim, RobustnessSpec, ScenarioSpec,
    TransformationSpec, apply_auxiliary, assess_auxiliary,
)
from confidenceguard.robustness.contracts import FrozenRobustnessProtocol
from .helpers import execution, CFG


def auxiliary(spec, field):
    member = replace(spec.predictors[0], id='member', inputs=(field,),
        outputs=(OutputBinding('scale'),), preprocessing={'kind':'numeric','fill':[2.]},
        architecture={'values':{'output':2.}})
    return AuxiliaryArtifact.create(id='scale', kind='scale', predictors=(member,),
        parent_digest=spec.predictors[0].predictor_digest,
        target={'failure':'error','levels':[.1,.5,.9],'members':[{'start':0,'count':1}]},
        membership={'namespace':spec.namespace,'F_events':[],'S_events':[],
                    'F_units':[],'S_units':[]}, selection={})


@pytest.mark.parametrize('assess', [False, True])
def test_r1_additional_auxiliary_feature_is_projected(tmp_path, assess):
    spec = execution(tmp_path, regression=True, n=8)
    artifact = auxiliary(spec, FeatureField('z','z','float',role='model_input'))
    result = assess_auxiliary(spec, artifact, CFG) if assess else apply_auxiliary(spec, artifact, CFG, role='E')
    assert result.private['output_rows']
    assert all('z' in row['input_record'] for row in result.private['output_rows'])
    assert all(row['channels']['scale']==2. for row in result.private['output_rows'])


@pytest.mark.parametrize('column', ['id', 'entity', 'role', 'y'])
def test_r1_prohibited_artifact_inputs_refuse_before_preparation(tmp_path, monkeypatch, column):
    spec = execution(tmp_path, regression=True, n=8)
    artifact = auxiliary(spec, FeatureField('bad',column,'float',role='model_input'))
    prepared = Mock(side_effect=AssertionError('source preparation must not start'))
    monkeypatch.setattr('confidenceguard.execution.services.PreparedExecution', prepared)
    with pytest.raises(EvaluationError) as error:
        apply_auxiliary(spec, artifact, CFG)
    assert error.value.code=='outcome_input'
    prepared.assert_not_called()


@pytest.mark.parametrize('availability,available', [('2026-01-02T00:00:00Z',False),('',False),('invalid',False),('2025-12-31T00:00:00Z',True)])
def test_r1_auxiliary_availability_is_enforced(tmp_path, availability, available):
    spec = execution(tmp_path, regression=True, n=8)
    with open(spec.sources[0].path) as stream: records=list(csv.DictReader(stream))
    for row in records: row.update(available=availability, cutoff='2026-01-01T00:00:00Z')
    with open(spec.sources[0].path,'w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    spec=replace(spec,information_cutoff=ClockSpec('cutoff'))
    artifact=auxiliary(spec,FeatureField('z','z','float',role='model_input',available_at=ClockSpec('available')))
    result=apply_auxiliary(spec,artifact,CFG,role='E')
    assert all(('scale' in r['channels'])==available for r in result.private['output_rows'])
    if not available:assert all(r['channel_failures'] for r in result.private['output_rows'])
    assert all('point' in r['channels'] for r in result.private['output_rows'])


def test_r1_dated_artifact_requires_cutoff_and_alias_outcomes_refuse(tmp_path):
    from confidenceguard import SourceSpec,OutcomeSnapshotSpec
    spec=execution(tmp_path,regression=True,n=8)
    dated=auxiliary(spec,FeatureField('z','z','float',available_at=ClockSpec('available')))
    with pytest.raises(EvaluationError) as error:apply_auxiliary(spec,dated,CFG)
    assert error.value.code=='input_availability'
    aliased=replace(spec,sources=(*spec.sources,SourceSpec('labels',spec.sources[0].path)),
                    outcomes=OutcomeSnapshotSpec('labels','y',('id',)))
    artifact=auxiliary(aliased,FeatureField('target_alias','y','float'))
    with pytest.raises(EvaluationError) as error:apply_auxiliary(aliased,artifact,CFG)
    assert error.value.code=='outcome_input'


def frozen_ensemble(spec):
    a=spec.predictors[0]
    spec=replace(spec,predictors=(a,replace(a,id='b',architecture={'values':{'output':1.}}),
                                  replace(a,id='c',architecture={'values':{'output':100.}})),
                 ensembles=({'id':'mean','members':[a.id,'b']},))
    study=RobustnessSpec(spec,(ScenarioSpec('identity',(TransformationSpec('same','identity'),)),),role='S')
    protocol=FrozenRobustnessProtocol.create(study=study,
        claims=[RobustnessClaim('delta','mean','identity','point_delta','le',1.,bounds=(-100.,100.))],
        development_events=[],development_units=[])
    return spec,protocol


@pytest.mark.parametrize('change', ['member','order','decision'])
def test_r2_frozen_ensemble_changes_refuse(tmp_path, change):
    spec,protocol=frozen_ensemble(execution(tmp_path,regression=True))
    group={'id':'mean','members':['model','b']}
    if change=='member':group['members']=['model','c']
    elif change=='order':group['members']=['b','model']
    else:group['decision']={'tie_policy':'class_order'}
    with pytest.raises(EvaluationError) as error:
        RobustnessAssessmentSpec(protocol,replace(spec,ensembles=(group,)))
    assert error.value.code=='robustness_assessment_binding'


def test_r2_effective_default_decision_is_canonical(tmp_path):
    spec,protocol=frozen_ensemble(execution(tmp_path,regression=True))
    explicit={**spec.ensembles[0],'decision':DecisionSpec().to_dict()}
    RobustnessAssessmentSpec(protocol,replace(spec,ensembles=(explicit,)))


def test_r2_service_rejects_before_evidence_reservation(tmp_path, monkeypatch):
    from confidenceguard.execution.services import service
    spec,protocol=frozen_ensemble(execution(tmp_path,regression=True))
    changed=replace(spec,ensembles=({'id':'mean','members':['model','c']},))
    reserve=Mock(side_effect=AssertionError('E must not be reserved'))
    monkeypatch.setattr('confidenceguard.execution.exposure.reserve',reserve)
    with pytest.raises(EvaluationError) as error:
        service(changed,CFG,operation='robustness_assess',options={'protocol':protocol.to_dict()})
    assert error.value.code=='robustness_assessment_binding'
    reserve.assert_not_called()


@pytest.mark.parametrize('status', [None,'unavailable','contradicted','passed'])
def test_r3_imported_membership_uses_cg2_eligibility(monkeypatch, status):
    from confidenceguard.execution.provenance import assessment_reasons
    from confidenceguard.membership import assessment_membership_passed
    methods=[{'id':'cal','definition':{'run':'base','parent':None}},
             {'id':'child','definition':{'run':'base','parent':'cal'}}]
    checks={} if status is None else {'cal':{'status':status}}
    checks['child']={'status':'passed'}
    spec=SimpleNamespace(namespace='review',predictors=[SimpleNamespace(id='base',provenance={})],
                         auxiliaries=[],ensembles=[],fitted_methods=methods)
    prepared=SimpleNamespace(spec=spec,con=None,original_table='unused',method_membership=checks)
    monkeypatch.setattr('confidenceguard.execution.provenance.rows',lambda *a,**k:iter([('event','entity')]))
    reasons=assessment_reasons(prepared)
    fitted={m['id']:m for m in methods}
    for mid in fitted:
        eligible=assessment_membership_passed(mid,fitted,set(fitted),checks)
        assert (mid not in reasons)==eligible


@pytest.mark.parametrize('membership', ['missing','passed','contradicted'])
def test_r3_real_imported_method_claims_preserve_family_allocation(tmp_path, membership):
    from confidenceguard import (SourceSpec, execute_predictor, as_reliability_spec,
        MethodSpec,fit_methods,run_robustness,freeze_robustness,assess_robustness)
    from confidenceguard.contracts import digest
    from confidenceguard.membership import key_digest
    from confidenceguard.sources import key
    spec=execution(tmp_path,n=120)
    # Generate the CG2 artifact on development records only; E has not been
    # executed or disclosed. No exposure ledger is cleared or bypassed.
    with open(spec.sources[0].path) as stream:records=list(csv.DictReader(stream))
    path=tmp_path/'development.csv'
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(records[0]));writer.writeheader()
        writer.writerows(r for r in records if r['role']!='E')
    development=execute_predictor(replace(spec,sources=(SourceSpec('input',str(path)),)),CFG)
    linked=as_reliability_spec(development,directory=tmp_path/'bridge')
    fitted=fit_methods(replace(linked,methods=(MethodSpec('cal','identity','model'),)),CFG)
    sidecars=[] if membership=='missing' else fitted.private['membership_sidecars']
    if membership=='contradicted':
        sidecars=__import__('copy').deepcopy(sidecars)
        row=next(r for r in records if r['role']=='E')
        sidecars[0]['rows'].append([key_digest(spec.namespace,key(row,('id',),None)),
            key_digest(spec.namespace,key(row,('entity',),None)),'F'])
        sidecars[0]['content_digest']=digest({k:v for k,v in sidecars[0].items() if k!='content_digest'})
    spec=replace(spec,fitted_methods=tuple(fitted.private['fitted_methods']),membership_sidecars=tuple(sidecars))
    scenario=ScenarioSpec('same',(TransformationSpec('same','identity'),),outcome_relation='label_preserving',outcome_reason='Identity control')
    selected=run_robustness(RobustnessSpec(spec,(scenario,),role='S'),CFG)
    protocol=freeze_robustness(selected,
        [RobustnessClaim('base','model','same','confidence_delta','le',.6),
         RobustnessClaim('derived','cal','same','confidence_delta','le',.6)],
        upstream_independence='declared_independent',external_exposure='declared_unexposed')
    result=assess_robustness(RobustnessAssessmentSpec(protocol,spec),CFG)
    claims={c['id']:c for c in result.data['cg6']['claims']}
    assert claims['base']['state']=='supported',claims
    assert claims['derived']['state']==('supported' if membership=='passed' else 'refused'),claims
    assert all(c['allocated_alpha']==pytest.approx(.025) for c in claims.values())
    assert any(r['predictor']=='cal' for r in result.private['output_rows'])


def attack_adapter(spec, *, mapped, regression=False):
    """Equivalent complete pipelines, with an unrelated raw head when mapped."""
    import torch
    from confidenceguard.execution.adapters import normalize_outputs
    from confidenceguard import ArtifactFile
    named=mapped=='named'
    p=replace(spec.predictors[0],adapter='torch',files=(ArtifactFile('unused','/unused','0'*64),),
        entry='unused',preprocessing={'kind':'numeric'},
        outputs=(OutputBinding('point',source='heads' if named else 'output',indices=(1,)),) if regression and mapped else
                (OutputBinding('point'),) if regression else
                (OutputBinding('probabilities',source='heads' if named else 'output',
                               indices=(1,0) if mapped in {'indexed','named'} else (),
                               classes=('yes',) if mapped=='binary' else ('yes','no') if mapped=='classes' else ('no','yes'),
                               activation='sigmoid' if mapped=='binary' else 'none' if mapped=='probabilities' else 'softmax'),))
    class Adapter:
        def __init__(self):self.spec=p;self.realization={'kind':'cpu'}
        def prepare(self,records):return np.asarray([[float(r['x'])] for r in records],np.float32)
        def predict_raw(self,values,gradients=False):
            x=torch.tensor(values,requires_grad=gradients)
            v=torch.cat((-100*x,x),1) if regression and mapped else x if regression else 2*x if mapped=='binary' else torch.cat((x,-x) if mapped in {'indexed','named','classes'} else (-x,x),1)
            if mapped=='probabilities':v=torch.softmax(v,dim=1)
            raw={'heads':v} if named else v
            if gradients:return raw,x
            return {k:t.detach().numpy() for k,t in raw.items()} if isinstance(raw,dict) else {'output':v.detach().numpy()}
        def predict(self,records):return self.predict_raw(self.prepare(records))
    adapter=Adapter()
    baseline=normalize_outputs(adapter.predict([{'x':.2}]),p,1,1e-6)[0]
    return adapter,baseline


@pytest.mark.parametrize('regression,binding', [(False,b) for b in ('indexed','named','classes','binary','probabilities')]+[(True,'indexed'),(True,'named')])
@pytest.mark.parametrize('targeted', [False,True])
def test_r4_mapped_attacks_match_equivalent_complete_outputs(tmp_path, regression, binding, targeted):
    from confidenceguard import AttackSpec
    from confidenceguard.robustness.attacks import search,objective
    from confidenceguard.execution.services import predict_batch
    spec=execution(tmp_path,regression=regression)
    event={'event_key':'r','entity_key':'r','record':{'x':.2},'truth':{'valid':True,'value':0. if regression else 'yes'},'unavailable_fields':[]}
    attack=AttackSpec('fgsm',('x',),objective=('loss_increase' if targeted else 'output_change') if regression else ('targeted' if targeted else 'misclassification'),
                      target_class='no' if targeted and not regression else None,access='white_box',epsilon=.4,queries_per_root=4)
    results=[]
    for mapped in (False,binding):
        adapter,baseline=attack_adapter(spec,mapped=mapped,regression=regression)
        prepared=SimpleNamespace(spec=replace(spec,limits=ExecutionLimits(cache_bytes=0)),
            config=EvaluationConfig(),work=SimpleNamespace(check=lambda *a:None))
        best,record=search(event,baseline,attack,adapter,prepared,0)
        replay=predict_batch(adapter,[best],prepared)[0]
        value,success=objective(replay,baseline,event,attack,spec.task)
        assert record['best_objective']==pytest.approx(value)
        assert record['success']==success
        results.append((best['record']['x'],record['success'],record['best_objective']))
    assert results[0]==pytest.approx(results[1])
    assert results[0][1]


def test_r5_numeric_missing_sentinel_fit_statistics():
    from confidenceguard.auxiliary.fitting import preprocessing,matrix
    field=FeatureField('x','x','float',missing_values=('','-999'))
    events=[{'record':{'x':v}} for v in ['1','3','-999']]
    pre=preprocessing(events,(field,))
    assert pre['fill']==[2.] and pre['mean']==[2.] and pre['scale']==[1.]
    with pytest.raises(EvaluationError) as error:preprocessing([events[-1]],(field,))
    assert error.value.code=='auxiliary_features'


def test_r5_frozen_inference_uses_the_same_missing_policy(tmp_path):
    from confidenceguard.auxiliary.fitting import preprocessing,matrix
    spec=execution(tmp_path,regression=True,n=8)
    field=FeatureField('x','x','float',missing_values=('','-999'))
    events=[{'record':{'x':v}} for v in ['1','3','-999']]
    p=replace(spec.predictors[0],inputs=(field,),preprocessing=preprocessing(events,(field,)))
    np.testing.assert_allclose(matrix(events,p),[[-1.],[1.],[0.]])


@pytest.mark.parametrize('failure', ['missing_source','detached','shape','nonfinite','hard_only'])
def test_r4_unsupported_bound_paths_refuse(tmp_path, failure):
    import torch
    from confidenceguard.robustness.gradient_objectives import attack_objective
    from confidenceguard import AttackSpec
    spec=execution(tmp_path)
    p=spec.predictors[0]
    raw=torch.tensor([[.2,-.2]],requires_grad=True)
    if failure=='missing_source':p=replace(p,outputs=(replace(p.outputs[0],source='other'),))
    elif failure=='detached':raw=raw.detach()
    elif failure=='shape':raw=raw[:,:1]
    elif failure=='nonfinite':raw=raw*float('nan')
    else:p=replace(p,outputs=(OutputBinding('prediction'),))
    with pytest.raises(EvaluationError) as error:
        attack_objective(raw,p,AttackSpec('fgsm',('x',),access='white_box'),
            {'truth':{'valid':True,'value':'yes'}},{'decision':'yes'},1e-6)
    assert error.value.code=='gradient_unavailable'


def test_r4_image_mapping_and_exact_pixel_replay(tmp_path):
    import torch
    from PIL import Image
    from confidenceguard import AttackSpec,ArtifactFile
    from confidenceguard.execution.adapters import Adapter
    from confidenceguard.execution.services import predict_batch
    from confidenceguard.robustness.attacks import search,objective
    spec=execution(tmp_path,n=8)
    path=tmp_path/'pixels.png';Image.fromarray(np.full((4,4,3),153,np.uint8)).save(path)
    event={'event_key':'r','entity_key':'r','record':{'x':str(path)},
           'truth':{'valid':True,'value':'yes'},'unavailable_fields':[]}
    attack=AttackSpec('fgsm',('x',),objective='misclassification',access='white_box',
                      stage='canonical_image',epsilon=.2,queries_per_root=4)
    class Model(torch.nn.Module):
        def __init__(self,mapped):super().__init__();self.mapped=mapped
        def forward(self,values):
            x=values.mean((1,2,3))[:,None]-.5
            return torch.cat((x,-x) if self.mapped else (-x,x),dim=1)
    answers=[]
    for mapped in (False,True):
        root=tmp_path/str(mapped);root.mkdir()
        prepared=SimpleNamespace(spec=replace(spec,limits=ExecutionLimits(cache_bytes=0)),config=EvaluationConfig(),
            assets={str(path):str(path)},work=SimpleNamespace(root=root,check=lambda *a:None))
        adapter=object.__new__(Adapter)
        adapter.spec=replace(spec.predictors[0],adapter='torch',inputs=(FeatureField('x','x','asset'),),
            files=(ArtifactFile('unused','/unused','0'*64),),entry='unused',
            preprocessing={'kind':'image'},outputs=(OutputBinding('probabilities',classes=('no','yes'),activation='softmax',indices=(1,0) if mapped else ()),))
        adapter.device_spec=DeviceSpec();adapter.config=prepared.config;adapter.limits=prepared.spec.limits
        adapter.work=prepared.work;adapter.asset_snapshots=prepared.assets;adapter.model=Model(mapped)
        adapter.realization={'kind':'cpu','torch_device':'cpu','batches':0,'rows':0,'allocator_peaks':{}}
        baseline=predict_batch(adapter,[event],prepared)[0]
        best,record=search(event,baseline,attack,adapter,prepared,0)
        replay=predict_batch(adapter,[best],prepared)[0]
        score,success=objective(replay,baseline,event,attack,spec.task)
        assert record['success'] and success and record['best_objective']==pytest.approx(score)
        with Image.open(best['record']['x']) as image:
            pixels=np.asarray(image,dtype=float)/255.
        assert np.max(np.abs(pixels-.6))<=.2+1e-7
        answers.append(replay['channels']['probabilities'])
    np.testing.assert_allclose(*answers,atol=1e-7)


@pytest.mark.parametrize('setting', [None,'',':1:1',':4096:8',':16:8'])
def test_r6_cuda_startup_prerequisite_before_native_calls(monkeypatch, setting):
    import torch
    from confidenceguard.execution.devices import configure_torch
    if setting is None:monkeypatch.delenv('CUBLAS_WORKSPACE_CONFIG',raising=False)
    else:monkeypatch.setenv('CUBLAS_WORKSPACE_CONFIG',setting)
    calls=[]
    cuda=SimpleNamespace(**{k:Mock(return_value=v) for k,v in {
        'device_count':1,'set_device':None,'manual_seed_all':None,'set_per_process_memory_fraction':None,
        'get_device_properties':SimpleNamespace(total_memory=1024**3)}.items()})
    monkeypatch.setattr(torch,'cuda',cuda)
    for name in ('set_num_threads','manual_seed','use_deterministic_algorithms'):
        monkeypatch.setattr(torch,name,Mock(side_effect=lambda *a,n=name,**k:calls.append(n)))
    spec=DeviceSpec('cuda')
    if setting in {':4096:8',':16:8'}:
        assert configure_torch(spec,EvaluationConfig(),{'kind':'cuda','index':0})==torch.float32
        cuda.set_device.assert_called_once_with(0)
    else:
        with pytest.raises(EvaluationError) as error:configure_torch(spec,EvaluationConfig(),{'kind':'cuda','index':0})
        assert error.value.code=='device_profile'
        assert not calls
        cuda.set_device.assert_not_called()


def test_r6_profile_failure_does_not_silently_disable_determinism(tmp_path, monkeypatch):
    from confidenceguard.execution.services import _worker
    spec=replace(execution(tmp_path),device=DeviceSpec('cuda',allow_cpu_fallback=True))
    worker=Mock(side_effect=EvaluationError('Invalid startup configuration.','device_profile'))
    monkeypatch.setattr('confidenceguard.execution.services._worker_once',worker)
    with pytest.raises(EvaluationError) as error:
        _worker(spec,EvaluationConfig(),(),'',None,str(tmp_path),{},{})
    assert error.value.code=='device_profile'
    assert worker.call_count==1
