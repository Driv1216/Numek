from dataclasses import replace
from confidenceguard import (OutputBinding,DecisionSpec,AuxiliaryStudySpec,AuxiliaryCandidate,fit_auxiliary,apply_auxiliary,
    as_reliability_spec,PolicyInputSpec,PolicySpec,PolicyApplicationSpec,PolicyMetricSpec,replay_policy)
from .helpers import execution,CFG


def test_failure_risk_does_not_replace_primary_native_score(tmp_path):
    s=execution(tmp_path,n=120)
    p=replace(s.predictors[0],outputs=(*s.predictors[0].outputs,OutputBinding('score','native')),
        architecture={'values':{'output':[.7,.3],'native':-.3}},decision=DecisionSpec(rule='score_threshold',threshold=0))
    s=replace(s,predictors=(p,))
    fitted=fit_auxiliary(AuxiliaryStudySpec(s,'failure_risk','model',candidates=(AuxiliaryCandidate('constant','constant'),)),CFG)
    applied=apply_auxiliary(s,fitted.private['auxiliary_artifacts'][0],CFG,role='E')
    assert all(o['channels']['score']==-.3 and o['channels']['risk']==0 and o['decision']=='no' for o in applied.private['output_rows'])
    log=next(m for m in applied.data['measurements'] if m['metric']=='failure_log_loss')
    assert log['value_state']=='positive_infinity'
    bridge=as_reliability_spec(applied,scope='auxiliary_application',directory=tmp_path/'bridge')
    run=bridge.evaluation.runs[0]
    assert run.score.column=='cg6_score' and run.selection.column=='cg6_risk'
    inp=PolicyInputSpec(bridge.roles,evaluation=bridge.evaluation)
    policy=PolicySpec(s.task,run.id,{'root':{'kind':'accept','when':{'kind':'compare','value':{'kind':'selector'},'op':'le','constant':.5},'accepted':'use','rejected':'skip'},
        'use':{'kind':'action','action':{'kind':'supplied'}},'skip':{'kind':'action','action':{'kind':'defer','queue':'review'}}},'root',{'kind':'abstain'},{'kind':'unavailable'})
    result=replay_policy(PolicyApplicationSpec(inp,policy,metrics=(PolicyMetricSpec('accuracy','issued_accuracy','maximize'),)),CFG)
    assert any(m['metric']=='issued_accuracy' and m['value']==0 for m in result.data['measurements'])
