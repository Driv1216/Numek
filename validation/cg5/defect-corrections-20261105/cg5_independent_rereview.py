from dataclasses import replace
from itertools import product
from pathlib import Path
from tempfile import TemporaryDirectory
import copy,json,csv
from tests.cg5.test_solver_resources import problem
from tests.cg5.helpers import study,threshold
from confidenceguard.policy_contracts import *
from confidenceguard.policy_runtime import Budget
from confidenceguard.contracts import EvaluationConfig
from confidenceguard.policy_optimization import *
from confidenceguard.policies import optimize_policies

CFG=EvaluationConfig(free_disk_bytes=1)

def summarize(row):
 return {'digest':row['policy_digest'],'complexity':row['complexity'],'objectives':{k:v['value'] for k,v in row['metrics'].items() if not k.startswith('accounting:')}}

def local_nominee_loss(root):
 s,f,p=problem(root)
 abstain={'kind':'action','action':{'kind':'abstain'}}
 via={'kind':'accept','when':{'kind':'compare','value':{'kind':'constant','value':1},'op':'eq','constant':1},'accepted':'end','rejected':'end'}
 t=copy.deepcopy(f.template);t['nodes']['end']={'kind':'action','action':{'kind':'label','label':'no'}}
 f=replace(f,template=t,parameters=(replace(f.parameters[0],values=(abstain,)),replace(f.parameters[1],values=(abstain,via))))
 q=threshold(p.task,.6);nodes=q.to_dict()['nodes']
 nodes['extra']={'kind':'accept','when':{'kind':'compare','value':{'kind':'constant','value':1},'op':'eq','constant':1},'accepted':'root','rejected':'root'}
 nodes['extra2']={**nodes['extra'],'accepted':'extra','rejected':'extra'}
 q=replace(q,nodes=nodes,root='extra2')
 s=replace(s,candidates=(q,),families=(f,),baselines=(),objectives=(PolicyMetricSpec('correct','correct_issue_rate','maximize'),),search=PolicySearchSpec(absolute_tolerance=.65,relative_tolerance=0))
 oracle_rows=[evaluate_candidate(q,s,p)[0]]
 d=domains(f,p)
 for vals in product(*d.values()):oracle_rows.append(evaluate_candidate(bind(f.template,dict(zip(d,vals))),s,p)[0])
 oracle=choose(oracle_rows,s)
 actual_rows,_,runs,actual,_=search(s,replace(p,budget=Budget(p.limits,CFG)))
 # Repeat through the public supervised optimize path on supplied records.
 result=optimize_policies(s,CFG)
 return {'expected':oracle,'actual':actual,'rows':list(map(summarize,oracle_rows)),'family_standing':runs[0]['solution_standing'],'family_coverage':runs[0]['search_coverage'],'public_nominee':result.data['policy']['nomination'],'mismatch':oracle['policy_digest']!=actual['policy_digest']}

def weighted_rmse(root):
 s,f,p=problem(root,True)
 # Scale losses above one. The optimum uses extra nodes; simpler near-optima
 # must win the declared RMSE tolerance tie, even in single-objective weighted mode.
 for r in p.frames['model'][1]: r['y_num']*=3
 t=copy.deepcopy(f.template)
 t['nodes']['end1']={'kind':'action','action':{'kind':'numeric','value':3.}}
 via={'kind':'accept','when':{'kind':'compare','value':{'kind':'constant','value':1},'op':'eq','constant':1},'accepted':'end1','rejected':'end1'}
 opts=({'kind':'action','action':{'kind':'numeric','value':0.}},via,{'kind':'action','action':{'kind':'numeric','value':6.}})
 f=replace(f,template=t,parameters=tuple(replace(q,values=opts) for q in f.parameters))
 s=replace(s,objectives=(PolicyMetricSpec('loss','rmse','minimize'),),families=(f,),candidates=(),baselines=(),search=PolicySearchSpec(mode='weighted',absolute_tolerance=.9,relative_tolerance=0))
 d=domains(f,p);rows=[evaluate_candidate(bind(f.template,dict(zip(d,vs))),s,p)[0] for vs in product(*d.values())]
 expect=choose(rows,s);actual,runs=milp_family(f,d,s,replace(p,budget=Budget(p.limits,CFG)))
 return {'expected':expect,'actual':summarize(actual[1]),'rows':list(map(summarize,rows)),'standing':milp_standing(runs,actual),'mismatch':expect['policy_digest']!=actual[0].policy_digest}

def hybrid_frontier(root):
 s=study(root);task=s.input.evaluation.task
 # Fixed routing plus two variable action cells, using the established fixture.
 _,f,_=problem(root/'fixture')
 old=f.template['nodes']['root'];alt=copy.deepcopy(old);alt['rules'][0]['when']['constant']=.4
 t=copy.deepcopy(f.template);t['nodes']['root']={'parameter':'route'}
 f=replace(f,template=t,kind='composition',backend='hybrid',parameters=(PolicyParameter('route','node',(old,alt)),*f.parameters),routing_parameters=('route',))
 s=replace(s,families=(f,),candidates=(),baselines=(),objectives=(PolicyMetricSpec('correct','correct_issue_rate','maximize'),PolicyMetricSpec('abstain','abstention_rate','maximize')))
 r=optimize_policies(s,CFG)
 from confidenceguard.policy_store import prepared_policy
 from confidenceguard.policy_problem import admit
 from confidenceguard.policies import arguments
 s,cfg,roots=arguments(s,CFG)
 with prepared_policy(s.input,cfg,s.limits,roots) as store:
  dp=admit(store,s);d=domains(f,dp)
  allrows=[evaluate_candidate(bind(f.template,dict(zip(d,vs))),s,dp)[0] for vs in product(*d.values())]
  allrows+=r.data['policy']['candidates']
  nondominated=[row for row in allrows if row['observed_feasibility']=='feasible' and not any(all(a<=b for a,b in zip(objective_vector(other,s),objective_vector(row,s))) and any(a<b for a,b in zip(objective_vector(other,s),objective_vector(row,s))) for other in allrows if other['observed_feasibility']=='feasible')]
  missing=[summarize(row) for row in nondominated if row['policy_digest'] not in r.private['policies']]
 return {'missing_nondominated':missing,'search_coverage' :r.data['policy']['searches'][0]['search_coverage'],'standing':r.data['policy']['searches'][0]['solution_standing'],'frontier_standing':r.data['policy']['frontier']['standing'],'retention':r.data['policy']['retention'],'retained':len(r.data['policy']['candidates']),'space':18}

if __name__=='__main__':
 with TemporaryDirectory(prefix='cg5-independent-') as td:
  root=Path(td);results={}
  for name,fn in [('family_local_ties',local_nominee_loss),('weighted_rmse',weighted_rmse),('hybrid_frontier',hybrid_frontier)]:
   try:results[name]=fn(root/name)
   except Exception as e:results[name]={'error':repr(e)};import traceback;traceback.print_exc()
  Path('/private/tmp/cg5_independent_rereview_results.json').write_text(json.dumps(results,indent=2));print(json.dumps(results,indent=2))
