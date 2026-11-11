import csv
from collections import Counter
from dataclasses import replace

import numpy as np
import pytest

from confidenceguard import ClockSpec,EvaluationError,OutcomeSnapshotSpec,investigate,freeze_hypotheses,confirm_investigation
from confidenceguard.investigation import arguments,prepared
from confidenceguard.investigation_objectives import bind
from confidenceguard.investigation_membership import seal
from confidenceguard.feature_contracts import FeatureViewSpec,FeatureField
from confidenceguard.features import outcome_bound_fields
from .helpers import binary
from .test_confirmation import declared


def selective(tmp_path):
    spec=binary(tmp_path);path=tmp_path/'predictions.csv'
    with path.open() as stream:rows=list(csv.DictReader(stream))
    states=['pending','withdrawn','invalid','provisional','conflicting'];missing=0
    for row in rows:
        error=row['decision']!=row['y'];status='final'
        if row['role']=='H' and error:
            status=states[missing%len(states)];missing+=1
        row.update(status=status,available='2026-01-01T00:00:00Z')
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
    outcome=replace(spec.evaluation.outcomes,status_column='status',
        status_values={v:v for v in ['final',*states]},available_at=ClockSpec('available'))
    objective=replace(spec.objectives[0],comparator='ceiling',ceiling=.1)
    return replace(spec,evaluation=replace(spec.evaluation,outcomes=outcome,as_of='2026-01-02T00:00:00Z'),
        features=(),objectives=(objective,))


@pytest.mark.parametrize('scope',['observed_labels','complete_population'])
def test_selective_outcomes_keep_states_and_cannot_establish_full_population(tmp_path,scope):
    result=investigate(selective(tmp_path))
    family=freeze_hypotheses(result,confirmation=replace(declared(),outcome_scope=scope))
    assessment=confirm_investigation(family);rows=assessment.data['investigation']['assessments']
    assert len(rows)==1
    claim=rows[0]
    assert claim['support']['planned']==claim['support']['members']==240
    assert claim['support']['conditional_members']==120
    assert claim['outcome_status_states']=={'final':120,**{v:24 for v in ['pending','withdrawn','invalid','provisional','conflicting']}}
    assert assessment.data['outcomes']=={'scope':scope,'no_selective_label_correction':True}
    if scope=='complete_population':
        assert claim['state']=='statistically_inadmissible'
        assert claim['reason']=='incomplete_outcomes_for_full_population_claim' and 'interval' not in claim
    else:
        # Observed labels deliberately omit every error. This narrow claim must
        # never be presented as evidence of reliability on the unobserved half.
        assert claim['state']=='unreproduced' and claim['effect']==-.1
        assert claim['member_metric']['support']==120
    shared=assessment.to_dict()['investigation']['assessments'][0]
    assert shared['outcome_status_states']==claim['outcome_status_states']
    assert assessment.to_dict()['outcomes']['scope']==scope


@pytest.mark.parametrize('immature',[False,True])
def test_future_status_is_not_disclosed_at_earlier_asof(tmp_path,immature):
    spec=selective(tmp_path);path=tmp_path/'predictions.csv'
    with path.open() as stream:rows=list(csv.DictReader(stream))
    next(row for row in rows if row['role']=='S').update(status='withdrawn',available='2026-01-03T00:00:00Z')
    if immature:
        for row in rows:row['due']='2026-01-01T00:00:00Z'
        next(row for row in rows if row['role']=='S')['due']='2026-01-03T00:00:00Z'
        spec=replace(spec,evaluation=replace(spec.evaluation,outcomes=replace(spec.evaluation.outcomes,due_at=ClockSpec('due'))))
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
    s,c,roots=arguments(spec,None,None)
    with prepared(s,c,roots) as p:
        indices,_,_=p.role_data('S');artifact=seal('structured',{'clauses':[]})
        measured=p.evaluate(bind(s.objectives[0],p.store),'S',indices,
            {'member':np.ones(len(indices),bool),'available':np.ones(len(indices),bool),'reason':['']*len(indices)},artifact)
        assert measured['outcome_status_states']=={'final':239,'unavailable_as_of':1}
        assert measured['conditional_members']==239 and measured['planned']==240
        assert measured['outcome_observation_states']['unresolved_or_immature_outcome' if immature else 'outcome_not_available_as_of']==1
        assert all('outcome_status' not in record for record in p.records)


def test_status_bound_membership_is_known_outcome_information_and_legacy_defaults_unchanged(tmp_path):
    spec=selective(tmp_path);evaluation=spec.evaluation
    view=FeatureViewSpec('status_view',(FeatureField('status','status'),),source='copy',availability='at_decision')
    identities={'data':{'sha256':'a'*64,'bytes':12},'copy':{'sha256':'a'*64,'bytes':12}}
    assert outcome_bound_fields(evaluation,[view],identities)=={'status_view.status'}
    # Default accepted CG1 requests retain exactly their original serialized map.
    assert OutcomeSnapshotSpec('data','y').status_values=={
        'final':'final','observed':'observed','provisional':'provisional','invalid':'invalid','conflicting':'conflicting'}
    with pytest.raises(EvaluationError):replace(evaluation.outcomes,status_values={'custom':'invented'})


def test_outcome_status_can_be_explored_but_cannot_define_confirmable_membership(tmp_path):
    spec=binary(tmp_path);path=tmp_path/'predictions.csv'
    with path.open() as stream:rows=list(csv.DictReader(stream))
    for row in rows:row['status']='observed' if row['decision']!=row['y'] else 'final'
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
    spec=replace(spec,evaluation=replace(spec.evaluation,outcomes=replace(spec.evaluation.outcomes,status_column='status')),
        features=(FeatureViewSpec('context',(FeatureField('status','status'),),availability='at_decision'),))
    result=investigate(spec)
    assert result.data['investigation']['shortlist']
    assert result.private['known_outcome_features']==['context.status']
    with pytest.raises(EvaluationError) as caught:freeze_hypotheses(result,confirmation=declared())
    assert caught.value.code=='outcome_derived_membership'


def test_new_status_mapping_survives_immutable_historical_capture(tmp_path):
    from confidenceguard import ReliabilityWorkspace,WorkspaceConfig,InvestigationSpec
    spec=selective(tmp_path);path=tmp_path/'predictions.csv'
    with path.open() as stream:rows=list(csv.DictReader(stream))
    for row in rows:row['when']='2026-01-01T00:00:00Z'
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
    evaluation=replace(spec.evaluation,runs=(replace(spec.evaluation.runs[0],prediction_at=ClockSpec('when')),))
    ws=ReliabilityWorkspace.initialize(tmp_path/'workspace',WorkspaceConfig(saving=True,free_disk_bytes=1))
    ws.ingest({'evaluation':evaluation.to_dict(),'namespace':spec.roles.namespace,
        'outcome_definition_version':'v1','bindings':[{'run':'model'}]})
    variant=ws.models()[0]['id']
    historical=InvestigationSpec.from_dict({'roles':{'namespace':spec.roles.namespace,'unit':'entity'},
        'objectives':[replace(spec.objectives[0],run=variant).to_dict()],
        'history':{'workspace_path':str(ws.path),'selection':{'namespace':spec.roles.namespace,'variants':[variant],
            'as_of':'2026-01-02T00:00:00Z','windows':[{'id':'jan','start':'2026-01-01T00:00:00Z','end':'2026-01-02T00:00:00Z'}]}}})
    s,c,roots=arguments(historical,None,None)
    with prepared(s,c,roots) as p:
        states=Counter(r['outcome_reason'] or 'observed_eligible' for r in p.records)
        assert states=={'observed_eligible':600,**{'outcome_'+v:24 for v in ['pending','withdrawn','invalid','provisional','conflicting']}}


def test_legacy_capture_metadata_identifies_status_origin_without_new_marker():
    from confidenceguard.investigation_history import captured_outcome_columns
    base={'runs':[{'source':'data','inline_outcome':'inline_y'}],
        'outcomes':{'source':'labels','column':'y','status_column':'status'}}
    metadata={'batch':{'evaluation':base},'variants':{'old_variant':{}},'sources':{'labels':{'sha256':'a'*64,'bytes':123}}}
    assert captured_outcome_columns(metadata,'old_variant')=={('a'*64,123,'y'),('a'*64,123,'status')}
    assert captured_outcome_columns(metadata,'different_variant')==set()
    metadata['batch']['evaluation']={'evaluation':base}
    assert ('a'*64,123,'status') in captured_outcome_columns(metadata,'old_variant')
    metadata['sources']['data']={'sha256':'b'*64,'bytes':456};base['outcomes']=None
    assert captured_outcome_columns(metadata,'old_variant')=={('b'*64,456,'inline_y')}


def test_implicit_single_run_inline_authority_is_also_outcome_bound(tmp_path):
    spec=binary(tmp_path);evaluation=replace(spec.evaluation,outcomes=None,
        runs=(replace(spec.evaluation.runs[0],inline_outcome='y'),))
    view=FeatureViewSpec('inline',(FeatureField('label','y'),),availability='at_decision')
    assert outcome_bound_fields(evaluation,[view])=={'inline.label'}
    assert evaluation.outcomes is None and evaluation.effective_outcomes.column=='y'
    assert 'effective_outcomes' not in evaluation.to_dict()


def test_legacy_context_origin_requires_all_possible_source_bytes_to_agree():
    from confidenceguard.investigation_history import captured_context_outcome_columns
    metadata={'batch':{'evaluation':{'runs':[{'source':'data'}],
        'outcomes':{'source':'labels','column':'y','status_column':'status'}}},
        'variants':{'v':{}},'sources':{'data':{'sha256':'a'*64,'bytes':123},'labels':{'sha256':'a'*64,'bytes':123}}}
    assert captured_context_outcome_columns(metadata,'v')=={'y','status'}
    metadata['sources']['data']['sha256']='b'*64
    assert captured_context_outcome_columns(metadata,'v')==set()
    metadata['sources']['data']['sha256']='a'*64
    metadata['batch']['evaluation']['context']={'source':'different_context'}
    assert captured_context_outcome_columns(metadata,'v')==set()


def test_legacy_source_origin_uses_exact_keys_namespaces_and_retained_file_identity():
    from confidenceguard.investigation_history import legacy_source_origin
    metadata={'batch':{'namespace':'events','outcome_definition_version':'v1','evaluation':{'runs':[{'id':'r','source':'data','key_columns':['id']}],
        'outcomes':{'source':'labels','column':'y'}},'bindings':[{'run':'r','entity_namespace':'patients'}]},
        'variants':{'v':{}},'sources':{'data':{'path':'/recorded/predictions.csv','signature':[1,2,3]},'labels':{'path':'/recorded/labels.csv','signature':[1,4,5]}}}
    target=['events',['01'],'v1',['default']];prediction={'normalized':{'entity_key':'["patients","[\\"A\\"]"]'}}
    origin=legacy_source_origin(metadata,'v',target,prediction)
    assert origin['event']=='["01"]' and origin['entity']=='["A"]'
    assert origin['sources']==[({'path':'/recorded/predictions.csv','signature':[1,2]},'["01"]','["A"]'),({'path':'/recorded/labels.csv','signature':[1,4]},'["01"]','["A"]')]
    assert legacy_source_origin(metadata,'v',['other',*target[1:]],prediction) is None
    assert legacy_source_origin(metadata,'v',[*target[:2],'other_version',target[3]],prediction) is None
    metadata['batch']['bindings'][0]['event_columns']=['different_key']
    assert legacy_source_origin(metadata,'v',target,prediction) is None
