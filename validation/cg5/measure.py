"""Three declared engineering workloads; no capacity or scientific promotion."""
import argparse,csv,json,platform,sys,time,hashlib
from pathlib import Path
from dataclasses import replace
from confidenceguard import *
from confidenceguard.method_contracts import RoleSpec
from confidenceguard.contracts import ModelIdentity,ProbabilitySpec,SourceSpec,OutcomeSnapshotSpec
from confidenceguard.policy_solver import availability

def fixture(root,kind,n=1200):
    root.mkdir(parents=True,exist_ok=True);path=root/'predictions.csv';classes=('no','yes') if kind=='binary_classification' else ('a','b','c') if kind=='multiclass_classification' else ()
    with path.open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['id','p','p_a','p_b','p_c','prediction','y','role','when','available'])
        for i in range(n):
            p=(i%100+.5)/100;point=(i%10)+.2
            if kind=='binary_classification': prediction='yes' if p>=.5 else 'no';y='yes' if p>=.6 else 'no';probs=(0,0,0)
            elif kind=='multiclass_classification':
                target=i%3;high=(i//3)%2==0;confidence=.85 if high else .55;probs=tuple(confidence if c==target else (1-confidence)/2 for c in range(3));prediction=classes[target];y=classes[target if i%10<(9 if high else 6) else (target+1)%3]
            else: prediction=point;y=float(i%10);probs=(0,0,0)
            w.writerow([i,p,*probs,prediction,y,'S' if i<n//2 else 'E','2026-01-01T00:00:00Z' if i<n//2 else '2026-02-01T00:00:00Z','2026-02-02T00:00:00Z'])
    task=TaskDefinition(kind,'Synthetic engineering outcome',classes,'yes' if kind=='binary_classification' else None,units='items' if kind=='regression' else None)
    probabilities=ProbabilitySpec('p') if kind=='binary_classification' else ProbabilitySpec(columns={c:'p_'+c for c in classes}) if classes else None
    run=PredictionRunSpec('model','data',ModelIdentity('synthetic','v1'),key_columns=('id',),prediction='prediction',probabilities=probabilities)
    evaluation=EvaluationSpec(task,(SourceSpec('data',str(path.resolve())),),(run,),OutcomeSnapshotSpec('data','y',('id',)))
    inp=PolicyInputSpec(RoleSpec('cg5-'+root.parent.name+'-'+kind,column='role'),evaluation=evaluation)
    leaf=lambda action:{'kind':'action','action':action}
    base={'task':task.to_dict(),'run':'model','root':'root','fallback':{'kind':'abstain'},'unavailable':{'kind':'unavailable'}}
    if kind=='binary_classification':
        base['nodes']={'root':{'kind':'accept','when':{'kind':'compare','value':{'kind':'probability','target':'yes'},'op':'ge','constant':{'parameter':'cut'}},'accepted':'yes','rejected':'no'},'yes':leaf({'kind':'label','label':'yes'}),'no':leaf({'kind':'label','label':'no'})}
        families=(PolicyFamilySpec('score_groups',base,(PolicyParameter('cut','cutpoints',value={'kind':'probability','target':'yes'}),),kind='threshold',backend='sweep'),)
        objectives=(PolicyMetricSpec('accuracy','issued_accuracy','maximize'),)
        constraints=();costs={}
    elif kind=='multiclass_classification':
        base['nodes']={'root':{'kind':'rules','rules':[{'when':{'kind':'compare','value':{'kind':'argmax_class'},'op':'eq','constant':c},'then':c} for c in classes[:-1]],'otherwise':classes[-1]},**{c:{'parameter':c} for c in classes},'emit':leaf({'kind':'argmax'}),'reject':leaf({'kind':'abstain'})}
        options=lambda c:[{'kind':'accept','when':{'kind':'compare','value':{'kind':'probability','target':c},'op':'ge','constant':v},'accepted':'emit','rejected':'reject'} for v in (.5,.8)]
        families=(PolicyFamilySpec('class_acceptance',base,tuple(PolicyParameter(c,'node',options(c)) for c in classes),kind='fixed_cells',backend='milp'),)
        objectives=(PolicyMetricSpec('correct','correct_issue_rate','maximize'),)
        constraints=(PolicyConstraint('minimum_coverage',PolicyMetricSpec('coverage','issued_coverage','maximize'),'ge',.5),PolicyConstraint('a_precision',PolicyMetricSpec('a_precision','precision','maximize',target='a'),'ge',.7))
        costs={}
    else:
        base['nodes']={'root':{'parameter':'action'}}
        families=(PolicyFamilySpec('quantities',base,(PolicyParameter('action','node',[leaf({'kind':'numeric','value':v}) for v in (2.,4.,6.,8.)]),),backend='enumerate'),)
        objectives=(PolicyMetricSpec('quantity_cost','empirical_cost',cost='quantity',units='cost_units',bounds=(0,10)),)
        constraints=();costs={'quantity':{'kind':'numeric_loss','loss':'pinball','level':.8,'nonissued':{'abstained':3,'unavailable':5}}}
    return PolicyStudySpec(inp,objectives,families=families,constraints=constraints,evaluation_costs=costs,name='Synthetic '+kind+' policy record')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);args=parser.parse_args();root=Path(args.out).resolve();root.mkdir(parents=True,exist_ok=True)
    source_root=Path(__file__).resolve().parents[2]/'src'
    identity=lambda:{str(p.relative_to(source_root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source_root.rglob('*.py'))}
    initial_identity=identity()
    config=EvaluationConfig(free_disk_bytes=1);rows=[];specs={}
    for kind in ('binary_classification','multiclass_classification','regression'):
        study=fixture(root/kind/'data',kind,4000 if kind=='binary_classification' else 1200);specs[kind]=study
        started=time.perf_counter();result=optimize_policies(study,config)
        row={'workload':kind,'planned':4000 if kind=='binary_classification' else 1200,'selection_seconds':time.perf_counter()-started,'execution':result.execution,'searches':result.data['policy']['searches'],'nomination':result.data['policy']['nomination']}
        assert row['nomination'] is not None
        for audience in ('local','shareable'):
            result.generate_artifacts(root/kind/(audience+'.pdf'),format='pdf',json_path=root/kind/(audience+'.json'),audience=audience)
        (root/kind/'study.json').write_text(json.dumps(study.to_dict(),sort_keys=True,indent=2))
        rows.append(row)
    study=specs['binary_classification'];raw=study.input.evaluation.to_dict();raw['runs'][0]['prediction_at']={'column':'when'};raw['outcomes']['available_at']={'column':'available'}
    ws=ReliabilityWorkspace.initialize(root/'history'/'workspace',WorkspaceConfig(saving=True,free_disk_bytes=1))
    ws.ingest({'namespace':'cg5-history-measure','outcome_definition_version':'v1','evaluation':raw,'bindings':[{'run':'model'}]})
    variant=ws.models()[0]['id'];selection={'namespace':'cg5-history-measure','variants':[variant],'as_of':'2026-03-01T00:00:00Z','windows':[{'id':'jan','start':'2026-01-01T00:00:00Z','end':'2026-02-01T00:00:00Z'},{'id':'feb','start':'2026-02-01T00:00:00Z','end':'2026-03-01T00:00:00Z'}]}
    inp=PolicyInputSpec(RoleSpec('cg5-history-measure',proportions={'E':1}),history={'workspace_path':str(ws.path),'selection':selection})
    task=study.input.evaluation.task;p=PolicySpec(task,variant,{'root':{'kind':'action','action':{'kind':'threshold','source':{'kind':'probability','target':'yes'},'threshold':.6}}},'root',{'kind':'abstain'},{'kind':'unavailable'})
    application=PolicyApplicationSpec(inp,p,metrics=(PolicyMetricSpec('accuracy','issued_accuracy','maximize'),))
    started=time.perf_counter();history=analyze_policy_history(application,config);ws.save_assessment(history)
    assert ws.open(history.data['analysis_id']).to_private_dict()==history.to_private_dict()
    rows.append({'workload':'immutable_history_two_windows','planned':4000,'seconds':time.perf_counter()-started,'execution':history.execution,'timeline':history.data['policy']['timeline'],'drift_rows':len(history.data['policy']['drift'])})
    final_identity=identity()
    receipt={'source_files':initial_identity,'source_unchanged_during_measurement':initial_identity==final_identity,'environment':{'python':sys.version,'platform':platform.platform(),'solver':availability()},'scope':'One grouped sweep, one contextual fixed-cell MILP, one finite regression family and one two-window historical replay. No general capacity or population qualification.','workloads':rows}
    if initial_identity!=final_identity:raise RuntimeError('Source changed during measurement; do not transfer this workload receipt.')
    (root/'measurements.json').write_text(json.dumps(receipt,sort_keys=True,indent=2,allow_nan=False)+'\n');print(json.dumps({'receipt':str(root/'measurements.json'),'workloads':len(rows)}))
if __name__=='__main__':main()
