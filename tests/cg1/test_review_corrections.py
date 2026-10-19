"""Regression cases for the first independent CG1 review; independent populations/privacy oracles."""
from dataclasses import replace
import json
from pathlib import Path
import pytest
from confidenceguard import *
from confidenceguard.analytics import Evidence
from confidenceguard.artifacts import render_report
from confidenceguard.contracts import digest
from .test_analysis import spec,core,measurement
from .test_semantics_controls import paired


def assert_ledger(result):
    pops={p['id']:p for p in result.data['coverage']['populations']}
    for m in result.data['measurements']:
        p=pops[m['population_id']]
        assert (p['run'],p['scope'],p['denominator'])==(m['run'],m['scope'],m['denominator'])
    return pops


def test_conditional_population_eligibility_and_high_confidence(tmp_path,monkeypatch):
    # Three top-class errors, only one in the two-record high-confidence subset.
    s=spec(tmp_path,'id,y,p,q\na,0,1,.95\nb,0,0,.6\nc,1,1,.2\nd,1,0,.85\ne,1,1,.95\n',prediction='p',probabilities=ProbabilitySpec('q'))
    observed={};original=Evidence.population
    def capture(self,run,scope,where,n,denominator_kind='eligible_records'):
        pid=original(self,run,scope,where,n,denominator_kind)
        observed[pid]={x[0] for x in self.con.execute(f'SELECT ordinal FROM {self.table} WHERE {where}').fetchall()}
        return pid
    monkeypatch.setattr(Evidence,'population',capture)
    r=core(s);pops=assert_ledger(r)
    expected={'accuracy':{1,2,3,4,5},'precision':{1,3,5},'recall':{3,4,5},'specificity':{1,2},'high_confidence_top_class_error_rate':{1,5},'share_of_top_class_errors_high_confidence':{1,2,3}}
    for metric,rows in expected.items():
        m=measurement(r,metric)
        assert observed[m['population_id']]==rows
        assert m['denominator']==len(rows)
    assert len({measurement(r,m)['population_id'] for m in expected})==len(expected)
    for c in measurement(r,'per_class')['data']['classes']:
        assert pops[c['precision_population_id']]['denominator']==c['predicted']
        assert pops[c['recall_population_id']]['denominator']==c['support']
    # Reopening enforces the new additive contract, including nested references.
    EvaluationResult.from_dict(r.to_private_dict(),private=r.private)
    public=r.to_dict(disclosure=DisclosureSpec(policy='exact_aggregates_v1'));public['measurements'][0]['denominator']+=1
    public['projection_digest']=digest({k:v for k,v in public.items() if k!='projection_digest'})
    with pytest.raises(EvaluationError,match='population'):EvaluationResult.from_dict(public)


def test_paired_equal_size_distinct_intersections_and_conditional_deltas(tmp_path,monkeypatch):
    left='id,y,p,q,s\na,0,0,,10\nb,1,1,,20\nc,0,1,.3,\nd,1,0,.7,\ne,0,,.4,30\nf,1,,.6,40\n'
    right='id,y,p,q,s\nf,1,,.6,40\ne,0,,.4,30\nd,1,1,.7,\nc,0,1,.3,\nb,1,1,,20\na,0,0,,10\n'
    s=paired(tmp_path,left,right,probabilities=ProbabilitySpec('q'),score=ScoreSpec('s'))
    observed={};original=Evidence.population
    def capture(self,run,scope,where,n,denominator_kind='eligible_records'):
        pid=original(self,run,scope,where,n,denominator_kind)
        if self.relations[self.table]['kind']=='paired_projection':
            # Stable event keys, independent of shuffled input order or physical ordinals.
            observed[pid]={json.loads(x[0])[0] for x in self.con.execute(f'SELECT event_key FROM {self.table} WHERE {where}').fetchall()}
        return pid
    monkeypatch.setattr(Evidence,'population',capture)
    r=core(s);pops=assert_ledger(r)
    metrics={'accuracy':{'a','b','c','d'},'brier':{'c','d','e','f'},'roc_auc':{'a','b','e','f'}}
    ids=[]
    for metric,events in metrics.items():
        m=measurement(r,metric,'paired')
        assert m['denominator']==4
        assert observed[m['population_id']]==events
        ids.append(m['population_id'])
    assert len(set(ids))==3
    d=measurement(r,'precision_right_minus_left','paired','right')
    assert d['value']==pytest.approx(2/3-1/2)
    assert d['denominator']==4 and d['denominator_kind']=='paired_base_support'
    assert (d['data']['left_denominator'],d['data']['right_denominator'])==(2,3)
    assert pops[d['data']['left_population_id']]['denominator']==2
    assert pops[d['data']['right_population_id']]['denominator']==3
    EvaluationResult.from_dict(r.to_private_dict(),private=r.private)


def test_policies_and_nonprediction_intervals_have_honest_support(tmp_path):
    s=spec(tmp_path,'id,y,p,l,u,s\na,1,1,0,2,9\nb,2,2,1,3,\nc,,3,2,4,7\n','regression',prediction='p',intervals=(PredictionIntervalSpec('mean','l','u',.9,meaning='mean_confidence'),),selection=ScoreSpec('s',meaning='selection'))
    s=replace(s,policies=(DecisionPolicySpec('select','model','selection_abstention'),DecisionPolicySpec('cost','model','supplied_cost')))
    r=core(s);assert_ledger(r)
    assert measurement(r,'policy_curve')['denominator']==2
    assert measurement(r,'empirical_cost')['denominator']==0
    assert measurement(r,'interval_coverage')['denominator_kind']=='not_evaluated'


def sizeable_binary(tmp_path):
    # All scores are unique; the retained ROC/PR curve includes a singleton cutoff.
    text='id,y,p,q\n'+''.join(f'{i},{i%2},{int(i%7>2)},{.001234567+(i+1)*.0019:.9f}\n' for i in range(500))
    return core(spec(tmp_path,text,prediction='p',probabilities=ProbabilitySpec('q')))


def test_conservative_unique_scores_do_not_escape_in_portable_charts(tmp_path):
    r=sizeable_binary(tmp_path);local=measurement(r,'roc_pr_curve')
    assert local['denominator']==500
    first=local['data']['points'][1]
    assert round(first['tpr']*250)+round(first['fpr']*250)==1
    assert any(1<=round(p['tpr']*250)+round(p['fpr']*250)<=9 for p in local['data']['points'][1:])
    shared=r.to_dict();exact=r.to_dict(disclosure=DisclosureSpec(policy='exact_aggregates_v1'))
    assert any(m['metric']=='roc_pr_curve' for m in exact['measurements'])
    assert not any(m['metric'] in {'roc_pr_curve','ranking_score'} for m in shared['measurements'])
    for metric in ('roc_auc','average_precision'):
        assert next(m['value'] for m in shared['measurements'] if m['metric']==metric)==measurement(r,metric)['value']
    html=render_report(shared)
    assert str(first['threshold']) not in json.dumps(shared)
    assert str(first['threshold']) not in html
    assert 'polyline' not in html and 'FPR / TPR' not in html
    assert measurement(r,'roc_pr_curve')==local
    EvaluationResult.from_dict(shared)


def test_safe_findings_checks_and_blockers_survive_without_sensitive_details(tmp_path):
    left='id,y,p,q,g,entity\n'+''.join(f'{i},{i%2},{i%2},{1.2 if i==0 else .8},{"SECRET_CATEGORY" if i==0 else "COMMON"},same\n' for i in range(40))
    right=left.replace('0,0,0,1.2','0,1,0,1.2')
    s=paired(tmp_path,left,right,probabilities=ProbabilitySpec('q'),inline_outcome='y',entity_columns=('entity',),role='train')
    s=replace(s,cohorts=(CohortSpec('SECRET_DECLARATION','g',categories=('SECRET_CATEGORY','COMMON')),))
    r=core(s,EvaluationConfig(sampling=SamplingSpec('independent_rows')))
    r.data['findings'].append({'code':'unknown_private','message':'SECRET_SOURCE_VALUE','count':1})
    r.data['checks'].append({'id':'unknown','reason':'SECRET_SOURCE_VALUE'})
    r.seal();shared=r.to_dict();text=json.dumps(shared);html=render_report(shared)
    codes={f['code'] for f in shared['findings']}
    assert {'not_held_out','inference_blocked','paired_comparison_blocked','invalid_probabilities','inline_conflicts'}<=codes
    assert 'conflicting_asserted_outcome_copy' in shared['comparison']['blocked_reasons']
    assert shared['checks'] and all('count' not in c and 'data' not in c for c in shared['checks'])
    assert all('count' not in f for f in shared['findings'])
    for secret in ('SECRET_CATEGORY','SECRET_DECLARATION','SECRET_SOURCE_VALUE',str(tmp_path)):
        assert secret not in text and secret not in html
    assert shared['coverage']['limitations'] and not shared['coverage']['sampling']['inference_enabled']
    assert 'not held out' in html and 'probability_quality:run_1' in html
    assert 'Observed labels need not represent unobserved cases.' in html


def test_safe_context_blocker_and_inventory_status_survive(tmp_path):
    s=paired(tmp_path,'id,y,p,g\na,1,1,SECRET\nb,0,0,COMMON\n','id,y,p,g\na,1,1,COMMON\nb,0,0,COMMON\n')
    s=replace(s,context=ContextSnapshotSpec('data',('id',),assertions={'right':{'g':'g'}}),cohorts=(CohortSpec('secret','g',categories=('SECRET','COMMON')),))
    shared=core(s).to_dict()
    assert any(c.get('reason')=='conflicting_canonical_context_assertion' for c in shared['checks'])
    assert any(c['id'].endswith(':inventory') for c in shared['checks'])
    assert 'SECRET' not in json.dumps(shared)


def test_legacy_shareable_reexport_hardened_without_mutating_stored_evidence():
    path=Path('validation/cg1/results/reports/binary-shareable.json');before=path.read_bytes()
    shared=EvaluationResult.from_dict(json.loads(before));after=shared.to_dict()
    assert not any(m['metric']=='roc_pr_curve' for m in after['measurements'])
    assert 'legacy_qualification' in after['coverage']
    assert after['origin_projection_digest']==json.loads(before)['projection_digest']
    assert shared.data==json.loads(before) and path.read_bytes()==before
    assert EvaluationResult.from_dict(after).to_dict()==after


def test_population_ledger_matches_all_measurement_denominators(tmp_path):
    s=spec(tmp_path,'id,y,p,q\na,0,1,.95\nb,0,0,.6\nc,1,1,.2\nd,1,0,.85\ne,1,1,.95\n',prediction='p',probabilities=ProbabilitySpec('q'))
    assert_ledger(core(s))


def test_population_count_assertion_rejects_wrong_reduction(tmp_path,monkeypatch):
    original=Evidence.add
    def wrong(self,run,scope,family,metric,value=None,n=0,**kwargs):
        if metric=='accuracy':n+=1
        return original(self,run,scope,family,metric,value,n,**kwargs)
    monkeypatch.setattr(Evidence,'add',wrong)
    s=spec(tmp_path,'id,y,p\na,0,0\nb,1,1\n',prediction='p')
    with pytest.raises(EvaluationError) as caught:core(s)
    assert isinstance(caught.value.__cause__,AssertionError)


def test_population_identity_binds_probability_normalization_settings(tmp_path):
    s=spec(tmp_path,'id,y,p,q0,q1\na,0,0,.4,.6000005\nb,1,1,.2,.8000005\n',prediction='p',probabilities=ProbabilitySpec(columns={'0':'q0','1':'q1'}))
    relaxed=core(s);strict=core(s,EvaluationConfig(probability_tolerance=1e-8))
    a=measurement(relaxed,'brier');b=measurement(strict,'brier')
    assert (a['denominator'],b['denominator'])==(2,0)
    assert a['population_id']!=b['population_id']
    assert_ledger(relaxed);assert_ledger(strict)


def test_paired_interval_remapping_does_not_alias_equal_sized_populations(tmp_path,monkeypatch):
    text='id,y,p,l1,u1,l2,u2\na,1,1,0,2,,\nb,2,2,1,3,,\nc,3,3,,,2,4\nd,4,4,,,3,5\ne,5,,4,6,4,6\nf,6,,5,7,5,7\n'
    s=paired(tmp_path,text,text,kind='regression',intervals=(PredictionIntervalSpec('x','l1','u1',.9),PredictionIntervalSpec('y','l2','u2',.9)))
    observed={};original=Evidence.population
    def capture(self,run,scope,where,n,denominator_kind='eligible_records'):
        pid=original(self,run,scope,where,n,denominator_kind)
        if self.relations[self.table]['kind']=='paired_projection':observed[pid]={json.loads(x[0])[0] for x in self.con.execute(f'SELECT event_key FROM {self.table} WHERE {where}').fetchall()}
        return pid
    monkeypatch.setattr(Evidence,'population',capture)
    r=core(s);assert_ledger(r)
    point=measurement(r,'mae','paired')
    intervals=[m for m in r.data['measurements'] if m['run']=='model' and m['scope']=='paired' and m['metric']=='interval_coverage']
    assert observed[point['population_id']]=={'a','b','c','d'}
    expected={'x':{'a','b','e','f'},'y':{'c','d','e','f'}}
    for m in intervals:
        assert m['denominator']==4
        assert observed[m['population_id']]==expected[m['data']['interval']]
    assert len({point['population_id'],*(m['population_id'] for m in intervals)})==3
    # Stable IDs depend on lineage, not the sequence-numbered transient table names.
    again=core(s)
    assert [m['population_id'] for m in r.data['measurements']]==[m['population_id'] for m in again.data['measurements']]
