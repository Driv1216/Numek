from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import csv,json
from tests.cg5.helpers import study
from confidenceguard.contracts import TaskDefinition,EvaluationConfig
from confidenceguard.policy_contracts import PolicySpec,PolicyMetricSpec,PolicyAssessmentSpec,PolicyClaim
from confidenceguard.policies import optimize_policies
from confidenceguard.policy_assessment import freeze_policy_family,assess_policies

if __name__=='__main__':
 with TemporaryDirectory(prefix='cg5-projection-') as td:
  s=study(Path(td));path=Path(s.input.evaluation.sources[0].path)
  with path.open() as st: rows=list(csv.DictReader(st))
  for row in rows:row.update(p='0',y='1')
  with path.open('w',newline='') as st:w=csv.DictWriter(st,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
  task=TaskDefinition('regression','Quantity',units='items',material_error=.5)
  ev=replace(s.input.evaluation,task=task,runs=(replace(s.input.evaluation.runs[0],probabilities=None,prediction='p'),))
  policy=PolicySpec(task,'model',{'root':{'kind':'action','action':{'kind':'numeric','value':0}}},'root',{'kind':'abstain'},{'kind':'unavailable'})
  s=replace(s,input=replace(s.input,evaluation=ev),families=(),baselines=(),candidates=(policy,),objectives=(PolicyMetricSpec('mae','mae',units='items'),))
  cfg=EvaluationConfig(free_disk_bytes=1);result=optimize_policies(s,cfg);key=result.data['policy']['nomination']['policy_digest']
  metrics=[PolicyMetricSpec('low','pinball',level=.1,bounds=(0,10),units='items'),PolicyMetricSpec('high','pinball',level=.9,bounds=(0,10),units='items'),PolicyMetricSpec('square','selective_risk',loss='squared',bounds=(0,10),units='squared_items'),PolicyMetricSpec('material','material_error_rate')]
  protocol=PolicyAssessmentSpec(tuple(PolicyClaim(m.id,key,m,'le',2) for m in metrics),sampling='independent_rows',upstream_independence='declared_independent',external_exposure='declared_unexposed',declaration_author='Independent review',declaration_reason='Synthetic disjoint rows')
  assessed=assess_policies(freeze_policy_family(result,assessment=protocol),cfg)
  output={'local_definitions':[r['metric_definition'] for r in assessed.data['policy']['assessments']],'public':assessed.to_dict()['policy'],'public_task':assessed.to_dict()['task']}
  Path('/private/tmp/cg5_projection_probe_results.json').write_text(json.dumps(output,indent=2));print(json.dumps(output,indent=2))
