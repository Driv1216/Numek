import csv
from dataclasses import replace
from confidenceguard.contracts import (EvaluationSpec,TaskDefinition,PredictionRunSpec,ModelIdentity,SourceSpec,ProbabilitySpec,OutcomeSnapshotSpec)
from confidenceguard.method_contracts import RoleSpec
from confidenceguard.policy_contracts import PolicySpec,PolicyInputSpec,PolicyStudySpec,PolicyMetricSpec,PolicyFamilySpec,PolicyParameter


def evidence(tmp_path,n=80):
    tmp_path.mkdir(parents=True,exist_ok=True)
    path=tmp_path/'predictions.csv'
    with path.open('w',newline='') as stream:
        writer=csv.writer(stream); writer.writerow(['id','p','y','role','group'])
        for i in range(n): writer.writerow([i,(i%10+.5)/10,'yes' if i%10>=6 else 'no','S' if i<n//2 else 'E','a' if i%2 else 'b'])
    task=TaskDefinition('binary_classification','event',('no','yes'),'yes')
    evaluation=EvaluationSpec(task,(SourceSpec('data',str(path)),),
        (PredictionRunSpec('model','data',ModelIdentity('supplied','v1'),key_columns=('id',),probabilities=ProbabilitySpec('p')),),
        OutcomeSnapshotSpec('data','y',('id',)))
    return PolicyInputSpec(RoleSpec('test-'+tmp_path.name,column='role'),evaluation=evaluation)


def threshold(task,cut=.5):
    return PolicySpec(task,'model',{'root':{'kind':'accept','when':{'kind':'compare','value':{'kind':'probability','target':'yes'},'op':'ge','constant':cut},'accepted':'yes','rejected':'no'},
        'yes':{'kind':'action','action':{'kind':'label','label':'yes'}},'no':{'kind':'action','action':{'kind':'label','label':'no'}}},
        'root',{'kind':'abstain'},{'kind':'abstain'})


def study(tmp_path,backend='sweep'):
    inp=evidence(tmp_path); template=threshold(inp.evaluation.task).to_dict()
    template['nodes']['root']['when']['constant']={'parameter':'cut'}
    family=PolicyFamilySpec('threshold',template,(PolicyParameter('cut','cutpoints',value={'kind':'probability','target':'yes'}),),kind='threshold',backend=backend)
    return PolicyStudySpec(inp,(PolicyMetricSpec('accuracy','issued_accuracy','maximize'),),families=(family,),baselines=(threshold(inp.evaluation.task,.5),))
