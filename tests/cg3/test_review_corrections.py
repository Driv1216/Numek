"""R1–R3 regression controls: interpretation, dimensional completeness, priority."""
import copy
from types import SimpleNamespace
import pytest
from confidenceguard import EvaluationError, LongitudinalSpec, ReliabilityWorkspace, WorkspaceConfig
from confidenceguard.history_metrics import materiality, metric_key, prioritize_drift
from confidenceguard.longitudinal import _lookup
from validation.cg3.fixtures import create, specification


@pytest.mark.parametrize('metric,left,right,adverse', [
    ('accuracy', .8, .7, .1), ('accuracy', .7, .8, -.1),
    ('balanced_accuracy', .8, .7, .1), ('balanced_accuracy', .7, .8, -.1),
    ('macro_f1_observed_classes', .8, .7, .1), ('macro_f1_observed_classes', .7, .8, -.1),
    ('support_weighted_f1', .8, .7, .1), ('support_weighted_f1', .7, .8, -.1),
    ('brier', .1, .2, .1), ('brier', .2, .1, -.1),
    ('log_loss', .1, .2, .1), ('mae', 2., 1., -1.),
    ('bias', .1, -.1, 0.), ('bias', .01, -.4, .39), ('bias', -.4, -.01, -.39),
    ('interval_coverage@0.9', .95, .97, 0.), ('interval_coverage@0.9', .89, .85, .04),
    ('set_coverage@0.9', .85, .95, -.05), ('set_coverage@0.9', .99, .89, .01),
])
def test_materiality_uses_metric_semantics(metric, left, right, adverse):
    a={'value':left,'data':{'nominal':.9}};b={'value':right,'data':{'nominal':'.90'}}
    contrast={'metric':metric,'value':right-left,'value_state':'finite'}
    materiality(contrast,a,b,{metric:.02},kind='temporal')
    result=contrast['practical_assessment']
    assert result['status']=='available'
    assert result['observed_adverse_difference']==pytest.approx(adverse)
    assert result['material_observed_change']==(adverse>.02)
    assert result['statistical_confirmation'] is False


def test_unsupported_and_unsigned_materiality_never_invent_degradation():
    def evaluate(metric, left=.1, right=.4, data=None, kind='temporal'):
        contrast={'metric':metric,'value':right-left,'value_state':'finite'}
        materiality(contrast,{'value':left,'data':data or {}},{'value':right,'data':data or {}},{metric:.02},kind=kind)
        return contrast['practical_assessment']
    assert evaluate('unregistered_metric')['reason']=='materiality_interpretation_unspecified'
    assert evaluate('interval_coverage')['reason']=='compatible_nominal_level_required'
    assert evaluate('bias',kind='contrast_change')['reason']=='unsupported_materiality_for_contrast_change'
    unsigned=evaluate('eligible_label_observation_rate')
    assert unsigned['interpretation']=='absolute_change' and unsigned['observed_absolute_difference']==pytest.approx(.3)
    assert 'observed_adverse_difference' not in unsigned


def test_measurement_keys_bind_definitions_not_observed_bins():
    base={'metric':'frozen_bin_ece','family':'calibration_diagnostics','method_version':'1','units':None,
          'data':{'target':'class:a','edges':[0,.5,1],'bins':[{'count':3}],'artifact_digest':'abc'}}
    changed=copy.deepcopy(base);changed['data']['bins']=[{'count':900}]
    assert metric_key(base)==metric_key(changed)
    for dimension,value in [('target','class:b'),('edges',[0,.1,1]),('artifact_digest','def')]:
        changed=copy.deepcopy(base);changed['data'][dimension]=value
        assert metric_key(base)!=metric_key(changed)
    store=SimpleNamespace(evidence=SimpleNamespace(measurements=[{**base,'scope':'overall','value':.1,'value_state':'finite'},
                                                                {**base,'scope':'overall','value':.2,'value_state':'finite'}]))
    with pytest.raises(EvaluationError) as error:_lookup(store)
    assert error.value.code=='historical_metric_identity_conflict'


def test_multiclass_targets_survive_temporal_matched_and_shareable_views(tmp_path):
    packet=create(tmp_path/'inputs',kind='multiclass_classification',events=365,classes=5)
    candidate=copy.deepcopy(packet['evaluation']['runs'][0]);candidate['id']='candidate';candidate['model']['version']='2'
    packet['evaluation']['runs'].append(candidate);packet['bindings'].append({'run':'candidate','features':{'region':'categorical','feature':'numeric'}})
    ws=ReliabilityWorkspace.initialize(tmp_path/'workspace',WorkspaceConfig(saving=True,free_disk_bytes=1));ws.ingest(packet)
    spec=specification(ws.models());a,b=spec['variants']
    spec['comparisons'].append({'id':'matched','kind':'matched','reference_window':'reference','current_window':'reference','reference_variant':a,'current_variant':b})
    spec['material_thresholds']={m:.01 for m in ['balanced_accuracy','macro_f1_observed_classes','support_weighted_f1']}
    result=ws.analyze(spec)
    temporal=[v for v in result.data['history']['temporal'] if v['variant']==a and v['metric']=='frozen_bin_ece']
    assert len(temporal)==5 and len({v['metric_key'] for v in temporal})==5
    assert {v['metric_identity']['dimensions']['target'] for v in temporal}=={'class:class-'+str(i) for i in range(5)}
    for edge in result.data['history']['comparisons']:
        eces=[m for m in edge['metrics'] if m['metric']=='frozen_bin_ece' and m['scope']=='overall']
        assert len(eces)==5
        for m in eces:
            assert m['metric_key'] in {v['metric_key'] for v in temporal}
            assert 'target=class:' in m['metric_label']
    for m in result.data['history']['comparisons'][0]['metrics']:
        if m['metric'] in spec['material_thresholds']:
            assert m['practical_assessment']['observed_adverse_difference']==pytest.approx(-m['value'])
    assert all(d['prioritization']['status']=='no_threshold_declared' for d in result.data['history']['drift'])
    assert not any(f['code']=='distribution_change' for f in result.data['findings'])
    public=result.to_dict()
    assert all('metric_identity' not in m and 'target=class:' not in m.get('metric_label','') for m in public['measurements'])
    assert all((v['variant'],v.get('metric_key',v['metric'])) in {(m['run'],m.get('metric_key',m['metric'])) for m in public['measurements']} for v in public['history']['temporal'])
    html=result.generate_artifacts(tmp_path/'targets.html',audience='local')
    text=open(html.html_path).read()
    assert all('target=class:class-'+str(i) in text for i in range(5))


def test_multiple_interval_definitions_and_nominal_levels_remain_distinct(tmp_path):
    packet=create(tmp_path/'inputs',kind='regression',events=365)
    packet['evaluation']['runs'][0]['intervals'].append({'id':'supplied80','lower':'q05','upper':'q95','coverage':.8})
    candidate=copy.deepcopy(packet['evaluation']['runs'][0]);candidate['id']='candidate';candidate['model']['version']='2'
    candidate['intervals'].append({'id':'unrelated70','lower':'q05','upper':'q95','coverage':.7})
    packet['evaluation']['runs'].append(candidate);packet['bindings'].append({'run':'candidate','features':{'region':'categorical','feature':'numeric'}})
    ws=ReliabilityWorkspace.initialize(tmp_path/'workspace',WorkspaceConfig(saving=True,free_disk_bytes=1));ws.ingest(packet)
    spec=specification(sorted(ws.models(),key=lambda m:m['run']['model']['version']),cohort=False);spec['material_thresholds']={'interval_coverage':.01,'bias':.01}
    a,b=spec['variants'];spec['comparisons'].append({'id':'matched','kind':'matched','reference_window':'reference','current_window':'reference','reference_variant':a,'current_variant':b})
    spec['drift_thresholds']={'feature:feature':{'ks_distance':0.}}
    result=ws.analyze(spec)
    for metric in ['interval_coverage','interval_width','central_interval_score']:
        series=[v for v in result.data['history']['temporal'] if v['metric']==metric and v['variant']==a]
        contrasts=[m for m in result.data['history']['comparisons'][0]['metrics'] if m['metric']==metric]
        assert len(series)==len(contrasts)==2
        assert len({v['metric_key'] for v in series})==2
        matched=[m for m in result.data['history']['comparisons'][1]['metrics'] if m['metric']==metric]
        assert len(matched)==2 and all(m['value']==pytest.approx(0,abs=1e-12) and m['reference_support']==181 for m in matched)
    assert {m['practical_assessment']['target'] for m in result.data['history']['comparisons'][0]['metrics'] if m['metric']=='interval_coverage'}=={.8,.9}
    findings=[f for f in result.data['findings'] if f['code']=='distribution_change']
    assert len(findings)==1 and findings[0]['field']=='feature:feature'
    assert findings[0]['prioritization']['statistical_confirmation'] is False


def test_drift_priority_requires_declared_matching_effect_thresholds():
    item={'field':'feature:age','status':'completed','ks_distance':.0001,'wasserstein_1':.01}
    assert not prioritize_drift(item,{}) and item['prioritization']['status']=='no_threshold_declared'
    assert not prioritize_drift(item,{'feature:age':{'ks_distance':.05}})
    assert prioritize_drift(item,{'feature:age':{'wasserstein_1':.005}})
    assert not prioritize_drift(item,{'feature:age':{'total_variation':.1}})
    assert item['prioritization']['status']=='unavailable'
    base={'namespace':'events','windows':[{'id':'w','start':'2026-01-01T00:00:00Z','end':'2026-02-01T00:00:00Z'}]}
    for invalid in [{'x':{'psi':.2}},{'x':{'ks_distance':-1}},{'x':{'ks_distance':True}},{'x':{}}]:
        with pytest.raises(EvaluationError):LongitudinalSpec.from_dict({**base,'drift_thresholds':invalid})
