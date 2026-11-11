"""Fixed small end-to-end finite-claim regression diagnostics, not promotion research."""
from pathlib import Path
from dataclasses import replace
import argparse,csv,json
import numpy as np
from confidenceguard import *
from confidenceguard.contracts import ModelIdentity,SourceSpec,OutcomeSnapshotSpec
from confidenceguard.method_contracts import RoleSpec

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);args=parser.parse_args();root=Path(args.out).resolve();root.mkdir(parents=True,exist_ok=True)
    rows=[];config=EvaluationConfig(free_disk_bytes=1)
    for scenario,rate in [('null',.6),('power',.85)]:
        for trial in range(6):
            directory=root/'data'/(scenario+'-'+str(trial));directory.mkdir(parents=True,exist_ok=True);path=directory/'outcomes.csv';rng=np.random.default_rng(1700+trial)
            with path.open('w',newline='') as f:
                writer=csv.writer(f);writer.writerow(['id','y','role'])
                writer.writerows((i,'yes' if rng.random()<rate else 'no','S' if i<400 else 'E') for i in range(800))
            task=TaskDefinition('binary_classification','Independent synthetic Bernoulli outcome',('no','yes'),'yes')
            evaluation=EvaluationSpec(task,(SourceSpec('data',str(path)),),(PredictionRunSpec('model','data',ModelIdentity('constant','v1'),key_columns=('id',)),),OutcomeSnapshotSpec('data','y',('id',)))
            inp=PolicyInputSpec(RoleSpec(scenario+'-'+str(trial),column='role'),evaluation=evaluation)
            policy=PolicySpec(task,'model',{'root':{'kind':'action','action':{'kind':'label','label':'yes'}}},'root',{'kind':'abstain'},{'kind':'unavailable'})
            metric=PolicyMetricSpec('accuracy','issued_accuracy','maximize');selected=optimize_policies(PolicyStudySpec(inp,(metric,),candidates=(policy,)),config)
            key=selected.data['policy']['nomination']['policy_digest']
            protocol=PolicyAssessmentSpec((PolicyClaim('accuracy_at_least_0_6',key,metric,'ge',.6),),sampling='independent_rows',upstream_independence='declared_independent',external_exposure='declared_unexposed',declaration_author='Fixed diagnostic',declaration_reason='IID synthetic rows; policy fixed before S and E; separate source for every trial.')
            frozen=freeze_policy_family(selected,assessment=protocol);assessed=assess_policies(frozen,config)
            claim=assessed.data['policy']['assessments'][0];rows.append({'scenario':scenario,'seed':1700+trial,'true_rate':rate,'nS':400,'nE':400,'claim':claim})
    supported={scenario:sum(r['claim']['state']=='supported' for r in rows if r['scenario']==scenario) for scenario in ('null','power')}
    passed=supported['null']<=1 and supported['power']>=5
    receipt={'scope':'Twelve fixed synthetic full-service stories; no general null/power or scientific promotion claim.','predeclared_expectations':{'null_supports_at_most':1,'power_supports_at_least':5,'trials_per_scenario':6,'seeds':list(range(1700,1706))},'supported':supported,'passed':passed,'trials':rows}
    (root/'finite-diagnostics.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n');print(json.dumps({'supported':supported,'passed':passed}))
    if not passed:raise SystemExit(1)
if __name__=='__main__':main()
