from dataclasses import replace
from collections import defaultdict
from confidenceguard import (execute_predictor,as_reliability_spec,FeatureField,FeatureViewSpec,
    PolicyInputSpec,PolicySpec,PolicyApplicationSpec,PolicyMetricSpec,replay_policy,RobustnessSpec,ScenarioSpec,
    TransformationSpec,PolicyStressSpec,stress_policy)
from confidenceguard.contracts import digest
from .helpers import execution,CFG


def test_frozen_complete_batch_worlds(tmp_path):
    s=execution(tmp_path,n=40);s=replace(s,context_fields=(FeatureField('batch','batch','categorical'),))
    completed=execute_predictor(s,CFG);bridge=as_reliability_spec(completed,directory=tmp_path/'bridge')
    members=defaultdict(list)
    for row in completed.private['output_rows']:members[row['input_record']['batch']].append(row['event_key'])
    batches=({'id':'day','field':'batch.id','closed_at':'2026-11-06T00:00:00Z','members':{k:{'count':len(v),'digest':digest(sorted(v))} for k,v in members.items()}},)
    features=(FeatureViewSpec('batch',(FeatureField('id','batch','categorical'),),availability='at_decision'),)
    inp=PolicyInputSpec(bridge.roles,evaluation=bridge.evaluation,features=features,batches=batches)
    nodes={'root':{'kind':'capacity','batch':'day','ranking':{'kind':'probability','target':'yes'},'budget':5,'admitted':'yes','overflow':'skip'},
        'yes':{'kind':'action','action':{'kind':'label','label':'yes'}},'skip':{'kind':'action','action':{'kind':'abstain'}}}
    policy=PolicySpec(s.task,'model',nodes,'root',{'kind':'abstain'},{'kind':'unavailable'})
    application=PolicyApplicationSpec(inp,policy,metrics=(PolicyMetricSpec('issued','issued_coverage',basis='operational'),),role='all')
    bound=replay_policy(application,CFG)
    frozen=PolicySpec.from_dict(next(iter(bound.private['policies'].values())))
    application=replace(application,policy=frozen)
    scenario=ScenarioSpec('partial_outage',(TransformationSpec('missing','missing',('x',),parameters={'rate':1.}),),filter={'field':'x','op':'lt','value':.2})
    shift=ScenarioSpec('partial_shift',(TransformationSpec('noise','noise',('x',),parameters={'scale':.1}),),filter={'field':'x','op':'lt','value':.2})
    result=stress_policy(PolicyStressSpec(RobustnessSpec(s,(scenario,shift)),application.to_dict(),'batch'),CFG)
    worlds=result.data['cg6']['policy_stress']['worlds']
    assert len(worlds)==3 and all(w['planned']==40 for w in worlds)
    assert all(all(c['complete'] for c in w['capacity']) for w in worlds if not w['scope'].startswith('partial_outage'))
    outage=next(w for w in worlds if w['scope'].startswith('partial_outage'))
    assert all(c['planned']==10 for c in outage['capacity'])
    assert outage['application_state']=='capacity_unavailable'
    assert all(w['policy_digest']==frozen.policy_digest for w in worlds)
