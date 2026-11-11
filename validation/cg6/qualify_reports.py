"""Representative final canonical reports; every PDF page requires visual QA."""
from pathlib import Path
from dataclasses import replace
from collections import defaultdict
import json,hashlib
from unittest.mock import patch
from confidenceguard import *
from confidenceguard.contracts import digest
from tests.cg6.helpers import execution

ROOT=Path(__file__).resolve().parent/'results'/'reports'
CFG={'free_disk_bytes':1,'max_seconds':180,'max_details':4}


def fixture(name,regression=False,n=120):
    d=ROOT/name;d.mkdir(parents=True,exist_ok=True);return d,execution(d,regression=regression,n=n)


def main():
    records=[]
    d,s=fixture('classification')
    other=replace(s.predictors[0],id='other',architecture={'values':{'output':[.75,.25]}})
    scenarios=(ScenarioSpec('measurement_noise',(TransformationSpec('noise','noise',('x',),parameters={'scale':.1}),),outcome_relation='label_preserving',outcome_reason='Synthetic measurement corruption'),
        ScenarioSpec('unknown_outage',(TransformationSpec('outage','missing',('x',),parameters={'rate':.25}),)))
    classification=run_robustness(RobustnessSpec(replace(s,predictors=(*s.predictors,other)),scenarios,comparisons=({'left':'model','right':'other'},)),CFG)
    records.append(('classification',classification))
    d,s=fixture('regression',True)
    fit=fit_auxiliary(AuxiliaryStudySpec(s,'scale','model',candidates=(AuxiliaryCandidate('scale','constant'),)),CFG)
    applied=apply_auxiliary(s,fit.private['auxiliary_artifacts'][0],CFG)
    bridge=as_reliability_spec(applied,scope='auxiliary_application',directory=d/'bridge')
    method=fit_methods(replace(bridge,methods=(MethodSpec('normalized','normalized','scale',input='normalized',levels=('.9',)),)),CFG)
    bound=replace(s,auxiliaries=(fit.private['auxiliary_artifacts'][0],),fitted_methods=tuple(method.private['fitted_methods']),membership_sidecars=tuple(method.private['membership_sidecars']))
    scenario=ScenarioSpec('measurement_noise',(TransformationSpec('noise','noise',('x',),parameters={'scale':.1}),),outcome_relation='label_preserving',outcome_reason='Synthetic measurement corruption')
    regression=run_robustness(RobustnessSpec(bound,(scenario,),role='E'),CFG);records.append(('regression',regression))
    d,s=fixture('risk')
    fit=fit_auxiliary(AuxiliaryStudySpec(s,'failure_risk','model',candidates=(AuxiliaryCandidate('baseline','constant'),AuxiliaryCandidate('risk','logistic'))),CFG)
    risk=assess_auxiliary(s,fit.private['auxiliary_artifacts'][0],CFG);records.append(('risk',risk))
    d,s=fixture('policy',n=40);s=replace(s,context_fields=(FeatureField('batch','batch','categorical'),))
    completed=execute_predictor(s,CFG);bridge=as_reliability_spec(completed,directory=d/'bridge');members=defaultdict(list)
    for row in completed.private['output_rows']:members[row['input_record']['batch']].append(row['event_key'])
    batches=({'id':'day','field':'batch.id','closed_at':'2026-11-07T00:00:00Z','members':{k:{'count':len(v),'digest':digest(sorted(v))} for k,v in members.items()}},)
    features=(FeatureViewSpec('batch',(FeatureField('id','batch','categorical'),),availability='at_decision'),)
    inp=PolicyInputSpec(bridge.roles,evaluation=bridge.evaluation,features=features,batches=batches)
    nodes={'root':{'kind':'capacity','batch':'day','ranking':{'kind':'probability','target':'yes'},'budget':5,'admitted':'yes','overflow':'skip'},'yes':{'kind':'action','action':{'kind':'label','label':'yes'}},'skip':{'kind':'action','action':{'kind':'abstain'}}}
    policy=PolicySpec(s.task,'model',nodes,'root',{'kind':'abstain'},{'kind':'unavailable'})
    application=PolicyApplicationSpec(inp,policy,metrics=(PolicyMetricSpec('issued','issued_coverage',basis='operational'),),role='all')
    baseline=replay_policy(application,CFG);application=replace(application,policy=PolicySpec.from_dict(next(iter(baseline.private['policies'].values()))))
    scenario=ScenarioSpec('measurement_shift',(TransformationSpec('shift','noise',('x',),parameters={'scale':.1}),))
    stress=stress_policy(PolicyStressSpec(RobustnessSpec(s,(scenario,)),application.to_dict(),'batch'),CFG);records.append(('policy',stress))
    receipts=[]
    for name,result in records:
        restored=EvaluationResult.from_dict(result.to_private_dict(),private=result.private)
        for audience in ('local','shareable'):
            destination=ROOT/name/(audience+'.pdf')
            with patch('confidenceguard.execution.adapters.Adapter',side_effect=AssertionError('Report must not load a model')):
                output=restored.generate_artifacts(destination,format='pdf',json_path=destination.with_suffix('.json'),audience=audience)
            receipts.append({'case':name,'audience':audience,'pdf':str(destination),'sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),'binding':result.binding,'model_loading_during_export':False})
    (ROOT/'receipt.json').write_text(json.dumps({'reports':receipts,'visual_page_inspection':'pending'},indent=2)+'\n')

if __name__=='__main__':main()
