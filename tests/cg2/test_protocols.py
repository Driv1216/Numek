import copy
import numpy as np
import pytest
from confidenceguard import study,fit_methods,evaluate,EvaluationResult,EvaluationError
from confidenceguard.inference import smooth_bootstrap
from confidenceguard.method_contracts import InferenceSpec
from .test_integrity import rewrite
from .test_methods import binary_spec


def test_membership_sidecar_detects_relabelled_fit_events(tmp_path):
    spec=binary_spec(tmp_path);fitted=fit_methods(spec)
    assert fitted.private['membership_sidecars']
    spec['methods']=[];spec['fitted_methods']=fitted.private['fitted_methods'];spec['membership_sidecars']=fitted.private['membership_sidecars']
    rewrite(tmp_path/'predictions.csv',lambda rows:[row.update(role='E') for row in rows])
    result=evaluate(spec)
    assert result.data['cg2']['prior_membership_checks']['beta']['status']=='contradicted'
    assert result.data['cg2']['assessments']==[]
    assert result.data['cg2']['evidence_views']['beta']['application_state']=='applied_unvalidated'
    # Omitting sidecars does not manufacture an observable membership check.
    spec['membership_sidecars']=[]
    result=evaluate(spec)
    assert result.data['cg2']['prior_membership_checks']['beta']['status']=='unavailable'
    assert result.data['cg2']['assessments']==[]
    assert not result.data['cg2']['applications']['beta']['assessment_eligible']
    assert result.data['cg2']['evidence_views']['beta']['application_state']=='applied_unvalidated'


@pytest.mark.parametrize('include_membership',[True,False])
def test_upstream_overlap_blocks_new_conformal_assessment(tmp_path,include_membership):
    spec=binary_spec(tmp_path);fitted=fit_methods(spec)
    spec['methods']=[{'id':'lac','kind':'lac','run':'original','parent':'beta'}]
    spec['fitted_methods']=fitted.private['fitted_methods'];spec['membership_sidecars']=fitted.private['membership_sidecars'] if include_membership else []
    rewrite(tmp_path/'predictions.csv',lambda rows:[row.update(role='E') for row in rows if row['role']=='F'])
    result=study(spec)
    assert result.data['cg2']['prior_membership_checks']['lac']['status']==('contradicted' if include_membership else 'unavailable')
    assert result.data['cg2']['assessments']==[]
    assert not result.data['cg2']['applications']['lac']['assessment_eligible']


@pytest.mark.parametrize('membership',['missing','other_namespace','matching'])
def test_imported_assessment_requires_observed_historical_separation(tmp_path,membership):
    spec=binary_spec(tmp_path);fitted=fit_methods(spec)
    spec['methods']=[];spec['fitted_methods']=fitted.private['fitted_methods']
    spec['membership_sidecars']=[] if membership=='missing' else fitted.private['membership_sidecars']
    if membership=='other_namespace':spec['roles']['namespace']='unmatched-events'
    spec['inference']={'mode':'independent_rows','metrics':['brier'],'replicates':2000,'seed':37}
    result=evaluate(spec);cg=result.data['cg2'];passed=membership=='matching'
    assert cg['prior_membership_checks']['beta']['status']==('passed' if passed else 'unavailable')
    assert cg['applications']['beta']['assessment_eligible'] is passed
    assert bool(cg['assessments']) is passed
    assert cg['evidence_views']['beta']['method_state']==('independently_evaluated' if passed else 'fitted_only')
    assert cg['evidence_views']['beta']['application_state']==('independently_evaluated' if passed else 'applied_unvalidated')
    assert result.private['fitted_methods']==fitted.private['fitted_methods']
    assert any(m['run']=='beta' and m['metric']=='brier' and m['denominator']==60 and m['value_state']=='finite' for m in result.data['measurements'])
    if passed:
        assert cg['assessments'][0]['qualifications']['base_prediction_independence']=='declared'
    else:
        assert cg['inference']['contrasts']
        assert all(c['reasons']==['prior_membership_unavailable'] for c in cg['inference']['contrasts'])
        assert any(f['code']=='independent_evaluation_unestablished' for f in result.data['findings'])
        assert result.to_dict()['cg2']['methods'][0]['application_evidence_state']=='applied_unvalidated'
    EvaluationResult.from_dict(result.to_private_dict(),private=result.private)


@pytest.mark.parametrize('membership_status',['unavailable','missing'])
def test_rehashed_import_cannot_claim_assessment_without_membership_check(tmp_path,membership_status):
    from confidenceguard.contracts import digest
    from confidenceguard.methods import assessment_basis
    spec=binary_spec(tmp_path);fitted=fit_methods(spec)
    spec['methods']=[];spec['fitted_methods']=fitted.private['fitted_methods'];spec['membership_sidecars']=fitted.private['membership_sidecars']
    result=evaluate(spec);raw=result.to_private_dict();private=copy.deepcopy(result.private)
    assert raw['cg2']['assessments']
    if membership_status=='missing':raw['cg2']['prior_membership_checks'].pop('beta')
    else:raw['cg2']['prior_membership_checks']['beta']={'status':'unavailable','reason':'matching_prior_membership_not_supplied'}
    basis=assessment_basis({k:v for k,v in raw.items() if k not in {'execution','binding'}})
    raw['cg2']['assessment_basis_digest']=basis
    for record in raw['cg2']['assessments']:
        record['evaluation_digest']=basis
        record['qualifications']['prior_membership']={'status':'unavailable'}
        record['assessment_digest']=digest({k:v for k,v in record.items() if k!='assessment_digest'})
    raw['binding']['analysis_digest']=digest({k:v for k,v in raw.items() if k!='binding'})
    private['analysis_digest']=raw['binding']['analysis_digest'];raw['binding']['private_manifest_digest']=digest(private)
    with pytest.raises(EvaluationError,match='prior membership'):EvaluationResult.from_dict(raw,private=private)


def test_membership_sidecar_roundtrip_and_tamper(tmp_path):
    result=study(binary_spec(tmp_path));bundle=result.generate_artifacts(tmp_path/'report.html',audience='local')
    from confidenceguard.method_cli import collection
    from pathlib import Path
    methods,sidecars=collection(Path(bundle.fitted_methods_path).read_bytes(),with_membership=True)
    assert methods==result.private['fitted_methods'] and sidecars==result.private['membership_sidecars']
    EvaluationResult.from_dict(result.to_private_dict(),private=result.private)
    bad=copy.deepcopy(sidecars[0]);bad['rows'][0][2]='E'
    from confidenceguard.membership import validate
    from confidenceguard.method_contracts import MethodLimits
    with pytest.raises(EvaluationError):validate(bad,MethodLimits())


def test_pilot_thresholds_discarded_and_e_labels_sealed(tmp_path):
    spec=binary_spec(tmp_path,[{'id':'lac','kind':'lac','run':'original'},
                              {'id':'aps','kind':'aps','run':'original'}])
    spec['selections']=[{'id':'sets','candidates':['lac','aps'],'objective':'efficiency','coverage_tolerance':.2}]
    first=study(spec)
    selection=first.data['cg2']['selections'][0]
    assert selection['pilot_calibration']['lineage']['role']=='S'
    assert all(v['provenance']['calibration_population']['lineage']['role']=='C' for v in first.private['fitted_methods'])
    rewrite(tmp_path/'predictions.csv',lambda rows:[row.update(y=str(1-int(row['y']))) for row in rows if row['role']=='E'])
    second=study(spec)
    assert first.private['fitted_methods']==second.private['fitted_methods']


def test_cluster_bootstrap_keeps_event_weighting_and_paired_units():
    # Independent clusters have unequal sizes; the estimand is an event-weighted ratio.
    rng=np.random.default_rng(11);sizes=np.arange(1,41)%7+1
    effects=.3+rng.normal(0,.1,len(sizes))
    values=np.c_[np.zeros(len(sizes)),sizes,effects*sizes,sizes]
    request=InferenceSpec(mode='independent_clusters',replicates=3000,metrics=['bias'],seed=9)
    result=smooth_bootstrap(values,request,family_size=1,check=lambda *a:None)
    assert result['status']=='available' and result['lower']>0
    assert result['estimate']==pytest.approx(np.sum(effects*sizes)/sizes.sum())
    # Exactly the same paired contrast represented as summed rows has the same interval.
    assert result==smooth_bootstrap(values.copy(),request,family_size=1,check=lambda *a:None)


def test_training_manifest_invalid_key_is_explicit(tmp_path):
    spec=binary_spec(tmp_path)
    membership=tmp_path/'training.csv';membership.write_text('id\n""\n')
    spec['evaluation']['sources'].append({'id':'training','path':str(membership)})
    spec['separation']['training_partitions']=[{'source':'training','role':'F','key_columns':['id']}]
    with pytest.raises(EvaluationError) as error:study(spec)
    assert error.value.code=='invalid_training_membership'


def test_cluster_inference_uses_declared_whole_entities(tmp_path):
    spec=binary_spec(tmp_path)
    rewrite(tmp_path/'predictions.csv',lambda rows:[row.update(entity='cluster-'+str(int(row['id'])//2)) for row in rows])
    spec['evaluation']['runs'][0]['entity_columns']=['entity'];spec['roles']['unit']='entity'
    spec['inference']={'mode':'independent_clusters','metrics':['brier'],'replicates':3000,'seed':21}
    result=study(spec)
    contrast=result.data['cg2']['inference']['contrasts'][0]
    assert contrast['independent_units']==30 and contrast['evaluation_records']==60
    assert contrast['sampling_unit']=='cluster'
    assert contrast['cluster_concentration']['largest_cluster_fraction']==pytest.approx(1/30)
    assert contrast['status'] in {'available','unavailable'}
    spec['inference']['mode']='independent_rows'
    blocked=study(spec).data['cg2']['inference']['contrasts'][0]
    assert blocked['status']=='not_admitted' and 'known_repeated_entities' in blocked['reasons']


def test_cohort_planned_support_is_scope_specific(tmp_path):
    spec=binary_spec(tmp_path)
    rewrite(tmp_path/'predictions.csv',lambda rows:[row.update(cohort='A' if int(row['id'])%2 else 'B') for row in rows])
    spec['evaluation']['cohorts']=[{'id':'cohort','column':'cohort','categories':['A','B']}]
    result=study(spec)
    contrasts=[m for m in result.data['measurements'] if m['family']=='comparison' and m['scope'].startswith('cohort_') and m['metric']=='brier_right_minus_left']
    assert len(contrasts)==2
    assert all(m['denominator']==m['data']['planned_common_input_support']==30 for m in contrasts)


def test_dependency_exclusion_precedes_common_population(tmp_path,monkeypatch):
    spec=binary_spec(tmp_path,[{'id':'platt','kind':'platt','run':'original','input':'score'}, {'id':'isotonic','kind':'isotonic','run':'original'}])
    spec['selections']=[{'id':'choose','candidates':['platt','isotonic']}]
    rewrite(tmp_path/'predictions.csv',lambda rows:rows[61].update(score=''))
    import confidenceguard.methods as methods
    monkeypatch.setattr(methods,'_dependency_exclusions',lambda _: {'platt':'statistics_unavailable'})
    from confidenceguard.methods import _execute2,_arguments2
    s,c,roots=_arguments2(spec,None,None);result=_execute2(s,c,roots,'study',None)
    selection=result.data['cg2']['selections'][0]
    assert selection['common_population']['denominator']==60
    assert selection['candidates']['platt']['status']=='disqualified'
    artifact=next(m for m in result.private['fitted_methods'] if m['id']=='isotonic')
    assert artifact['provenance']['selection_history'][0]['common_population']['denominator']==60


def test_failed_fit_does_not_shrink_inference_family(tmp_path,monkeypatch):
    spec=binary_spec(tmp_path,[{'id':'beta','kind':'beta','run':'original'}, {'id':'platt','kind':'platt','run':'original','input':'score'}])
    spec['inference']={'mode':'independent_rows','metrics':['brier'],'replicates':2000,'adjustment':'bonferroni'}
    import confidenceguard.methods as methods
    original=methods.fit_calibrator
    from confidenceguard.calibration import MethodUnavailable
    def fit(method,*args,**kwargs):
        if method.id=='beta':raise MethodUnavailable('Injected fit failure.','fit_nonconvergence')
        return original(method,*args,**kwargs)
    monkeypatch.setattr(methods,'fit_calibrator',fit)
    s,c,roots=methods._arguments2(spec,None,None);result=methods._execute2(s,c,roots,'study',None)
    intervals=result.data['cg2']['inference']['contrasts']
    assert len(intervals)==2 and all(v['family_size']==2 for v in intervals)
    assert any(v.get('right')=='beta' and v['reasons']==['comparison_unavailable'] for v in intervals)
    assert result.data['cg2']['comparison_requests'][0]['execution']=='not_run'


def test_cg2_shareable_projection_hides_method_identity_and_membership(tmp_path):
    import json
    sentinel='PRIVATE_METHOD_SENTINEL'
    spec=binary_spec(tmp_path,[{'id':sentinel,'kind':'beta','run':'original'}])
    result=study(spec,{'disclosure':{'minimum_component':1,'minimum_denominator':1}})
    public=result.to_dict()
    assert any('candidate_failures' in m['data'] for m in public['measurements'])
    assert sentinel not in json.dumps(public)
    assert 'membership_sidecars' not in json.dumps(public)
    artifact=result.generate_artifacts(tmp_path/'shareable.html',audience='shareable')
    from pathlib import Path
    assert sentinel not in Path(artifact.html_path).read_text()


def test_inspection_rejects_incompatible_import_before_application(tmp_path):
    from confidenceguard import inspect
    spec=binary_spec(tmp_path);fitted=fit_methods(spec)
    spec['methods']=[];spec['fitted_methods']=fitted.private['fitted_methods']
    checked=inspect(spec)
    assert checked['method_compatibility'][0]['status']=='compatible'
    spec['evaluation']['runs'][0]['model']['version']='different'
    with pytest.raises(EvaluationError) as error:inspect(spec)
    assert error.value.code=='incompatible_method'


def test_rehashed_report_cannot_upgrade_fitted_only_evidence(tmp_path):
    from confidenceguard.contracts import digest
    from confidenceguard.methods import assessment_basis
    result=fit_methods(binary_spec(tmp_path));raw=result.to_private_dict();private=copy.deepcopy(result.private)
    raw['cg2']['evidence_views']['beta']['method_state']='independently_evaluated'
    raw['cg2']['assessment_basis_digest']=assessment_basis({k:v for k,v in raw.items() if k not in {'execution','binding'}})
    raw['binding']['analysis_digest']=digest({k:v for k,v in raw.items() if k!='binding'})
    private['analysis_digest']=raw['binding']['analysis_digest'];raw['binding']['private_manifest_digest']=digest(private)
    with pytest.raises(EvaluationError,match='Evidence state'):EvaluationResult.from_dict(raw,private=private)
