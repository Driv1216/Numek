from pathlib import Path
from dataclasses import replace
import csv,json,tempfile,sys
sys.path.insert(0,str(Path.cwd()/'tests/cg4'))
from helpers import binary
from confidenceguard import ReliabilityWorkspace,WorkspaceConfig,InvestigationSpec
from confidenceguard.investigation import arguments,prepared

def states(spec):
 s,c,r=arguments(spec,None,None)
 with prepared(s,c,r) as p:return {key:dict(__import__('collections').Counter(v['state'] for v in cells)) for key,cells in p.features.items()}

def main():
 root=Path(tempfile.mkdtemp(prefix='temporal-',dir='/private/tmp/numek-cg4-independent-review')).resolve()
 original=binary(root);path=root/'predictions.csv'
 with path.open() as f:rows=list(csv.DictReader(f))
 for row in rows:row.update(prediction_at='2026-01-02T00:00:00Z',cutoff='2026-01-01T00:00:00Z',content_at='2026-01-01T12:00:00Z',label_at='2026-01-03T00:00:00Z')
 with path.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
 value=original.to_dict();value['evaluation']['runs'][0]['prediction_at']={'column':'prediction_at'};value['evaluation']['outcomes']['available_at']={'column':'label_at'}
 value['features']=[{'id':'context','availability':'dated','information_cutoff':{'column':'cutoff'},'fields':[{'id':f,'column':f,'kind':'categorical','available_at':{'column':'content_at'}} for f in ('x','z')]}]
 live=InvestigationSpec.from_dict(value)
 ws=ReliabilityWorkspace.initialize(root/'workspace',WorkspaceConfig(saving=True,free_disk_bytes=1))
 ws.ingest({'schema_version':'confidenceguard.prediction_batch_spec/2.0','evaluation':value['evaluation'],'namespace':live.roles.namespace,'outcome_definition_version':'v1','bindings':[{'run':'model'}],'feature_views':value['features']})
 variant=ws.models()[0]['id'];history=live.to_dict();history.pop('evaluation');history['roles'].pop('column');history['objectives'][0]['run']=variant
 history['history']={'workspace_path':str(ws.path),'selection':{'namespace':live.roles.namespace,'variants':[variant],'as_of':'2026-02-01T00:00:00Z','windows':[{'id':'jan','start':'2026-01-01T00:00:00Z','end':'2026-02-01T00:00:00Z'}]}}
 history_spec=InvestigationSpec.from_dict(history)
 from confidenceguard import investigate,freeze_hypotheses,ConfirmationSpec,confirm_investigation
 historical_result=investigate(history_spec)
 frozen=freeze_hypotheses(historical_result,confirmation=ConfirmationSpec(upstream_independence='declared_independent',external_exposure='declared_unexposed',declaration_author='Independent reviewer synthetic fixture',declaration_reason='Independent synthetic entities and ingestion-only workspace.'))
 assessed=confirm_investigation(frozen)
 live_result=investigate(live)
 result={'live':states(live),'retained':states(history_spec),'live_candidates':len(live_result.data['investigation']['candidates']),'retained_candidates':len(historical_result.data['investigation']['candidates']),'historical_assessments':[{'state':a['state'],'H_outcomes_disclosed':a['H_outcomes_disclosed'],'strength':a['strength'],'reason':a.get('reason'),'support':a['support']} for a in assessed.data['investigation']['assessments']],'root':str(root)}
 (root/'live-spec.json').write_text(json.dumps(live.to_dict(),indent=2))
 (root/'history-spec.json').write_text(json.dumps(history_spec.to_dict(),indent=2))
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
