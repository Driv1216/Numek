from dataclasses import replace

import pytest

from confidenceguard import (ClockSpec,EvaluationError,SourceSpec,investigate,freeze_hypotheses)
from confidenceguard.confirmation import _input
from confidenceguard.contracts import digest
from confidenceguard.investigation_contracts import (FrozenHypothesisSet,ConfirmationSpec,
    confirmation_family_digest,observation_policy)
from .test_outcome_observation import selective
from .test_history import retained


@pytest.fixture(scope='module')
def supplied(tmp_path_factory):
    spec=selective(tmp_path_factory.mktemp('frozen-observation-policy'))
    result=investigate(spec)
    return spec,result,freeze_hypotheses(result)


@pytest.mark.parametrize('change',['statuses','status_column','label_column','keys','availability','due','target','feature_view'])
def test_supplied_policy_changes_refuse_before_any_H_worker(supplied,change,monkeypatch):
    spec,_,family=supplied;outcome=spec.evaluation.outcomes
    changes={'statuses':{'status_values':{**outcome.status_values,'pending':'final'}},
        'status_column':{'status_column':None},'label_column':{'column':'decision'},
        'keys':{'key_columns':('entity',)},'availability':{'available_at':replace(outcome.available_at,encoding='epoch',epoch_unit='ns')},
        'due':{'due_at':ClockSpec('available')},'target':{'target_at':ClockSpec('available')}}
    revised=replace(spec,feature_time_view='retrospective') if change=='feature_view' else replace(spec,
        evaluation=replace(spec.evaluation,outcomes=replace(outcome,**changes[change])))
    def unexpected(*args,**kwargs):raise AssertionError('Revised observation policy reached a worker/H admission')
    monkeypatch.setattr('confidenceguard.execution_context.ctx.run',unexpected)   # no phase may execute
    from confidenceguard import inspect_confirmation
    with pytest.raises(EvaluationError) as caught:inspect_confirmation(family,confirmation_input=revised)
    assert caught.value.code=='confirmation_observation_policy'


def test_future_source_rebinding_preserves_policy_without_reading_unavailable_files(supplied,tmp_path):
    spec,_,family=supplied;source=SourceSpec('future',str(tmp_path/'not-yet-acquired.csv'))
    future=replace(spec,evaluation=replace(spec.evaluation,sources=(source,),
        runs=(replace(spec.evaluation.runs[0],source='future'),),
        outcomes=replace(spec.evaluation.outcomes,source='future',snapshot_name='prospective snapshot'),
        as_of='2026-04-01T00:00:00Z'))
    # Actual H sources/snapshot cutoffs are bound by confirmation inspection;
    # this pure contract check does not open them or change status/clock meaning.
    assert _input(family,future)[1]==future
    assert observation_policy(future)==observation_policy(spec)
    switched=replace(spec,evaluation=None,history={'workspace_path':str(tmp_path/'not-opened'),
        'selection':{'namespace':spec.roles.namespace,'variants':['model'],'as_of':'2026-04-01T00:00:00Z',
            'windows':[{'id':'future','start':'2026-01-01T00:00:00Z','end':'2026-02-01T00:00:00Z'}]}})
    with pytest.raises(EvaluationError) as caught:_input(family,switched)
    assert caught.value.code=='confirmation_identity'


def test_new_and_legacy_family_identities_remain_readable_and_guarded(supplied):
    spec,result,family=supplied;packet=family.to_dict();h=packet['hypotheses'][0]
    assert h['definition_version']=='frozen_failure_hypothesis_v2'
    assert h['population_policy']['observation_policy']==observation_policy(spec)
    # Construct the prior documented identity format from the same D/S evidence.
    # Old bytes remain unchanged/readable; current admission still derives the
    # effective old observation interpretation from the original stored spec.
    for claim in packet['hypotheses']:
        claim['definition_version']='frozen_failure_hypothesis_v1'
        claim['population_policy']['observation_policy']=spec.evaluation.outcomes.to_dict()
        claim['id']=digest({k:v for k,v in claim.items() if k!='id'})
    packet['family_digest']=confirmation_family_digest(packet['hypotheses'],ConfirmationSpec.from_dict(packet['confirmation_spec']))
    packet['content_digest']=digest({k:v for k,v in packet.items() if k!='content_digest'})
    legacy=FrozenHypothesisSet(packet)
    assert legacy.to_dict()==packet and _input(legacy)[1]==spec
    changed=replace(spec,evaluation=replace(spec.evaluation,outcomes=replace(spec.evaluation.outcomes,status_column=None)))
    with pytest.raises(EvaluationError):_input(legacy,changed)
    bad=family.to_dict();bad['hypotheses'][0]['population_policy']['observation_policy']['binding']['status_values']['pending']='final'
    for claim in bad['hypotheses']:claim['id']=digest({k:v for k,v in claim.items() if k!='id'})
    bad['family_digest']=confirmation_family_digest(bad['hypotheses'],ConfirmationSpec.from_dict(bad['confirmation_spec']))
    bad['content_digest']=digest({k:v for k,v in bad.items() if k!='content_digest'})
    with pytest.raises(EvaluationError,match='interpretation disagree'):FrozenHypothesisSet(bad)


def test_inline_authority_and_retrospective_cutoff_are_explicit(supplied):
    spec,_,_=supplied
    evaluation=replace(spec.evaluation,outcomes=None,as_of=None,
        runs=(replace(spec.evaluation.runs[0],inline_outcome='y'),))
    inline=replace(spec,evaluation=evaluation,feature_time_view='retrospective',as_of='2026-01-02T00:00:00Z')
    policy=observation_policy(inline)
    assert policy['binding']['column']=='y' and policy['binding']['key_columns']==['id']
    assert policy['binding']['status_column'] is None and policy['retrospective_feature_cutoff_ns'] is not None
    assert observation_policy(replace(inline,as_of='2026-01-01T19:00:00-05:00'))==policy
    assert observation_policy(replace(inline,as_of='2026-01-03T00:00:00Z'))!=policy


def test_historical_authority_maturity_and_context_cannot_drift(tmp_path):
    workspace,spec=retained(tmp_path);result=workspace.investigate(spec);family=freeze_hypotheses(result)
    spec=_input(family)[1]
    for change in ({'authority':'different_authority'},{'maturity':'observed'},{'followup_ns':'1000'},
                   {'context_view':'revised'},{'outcome_only':True},{'roles':['production']}):
        revised=replace(spec,history={**spec.history,'selection':{**spec.history['selection'],**change}})
        with pytest.raises(EvaluationError) as caught:_input(family,revised)
        assert caught.value.code=='confirmation_observation_policy'
    future=replace(spec,history={**spec.history,'selection':{**spec.history['selection'],
        'as_of':'2026-04-01T00:00:00Z','catalog_sequence':None}})
    assert _input(family,future)[1]==future  # fresh snapshot, unchanged interpretation


def test_retrospective_feature_cutoff_is_guarded_before_H_loading(tmp_path,monkeypatch):
    spec=replace(selective(tmp_path),feature_time_view='retrospective',as_of='2026-01-02T00:00:00Z')
    family=freeze_hypotheses(investigate(spec))
    equivalent=replace(spec,as_of='2026-01-01T19:00:00-05:00')
    assert _input(family,equivalent)[1]==equivalent
    from confidenceguard import inspect_confirmation
    def unexpected(*args,**kwargs):raise AssertionError('Changed retrospective feature cutoff reached H')
    monkeypatch.setattr('confidenceguard.execution_context.ctx.run',unexpected)   # no phase may execute
    with pytest.raises(EvaluationError) as caught:inspect_confirmation(family,confirmation_input=replace(spec,as_of='2026-01-03T00:00:00Z'))
    assert caught.value.code=='confirmation_observation_policy'
