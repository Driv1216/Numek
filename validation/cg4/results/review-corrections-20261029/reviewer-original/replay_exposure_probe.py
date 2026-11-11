from pathlib import Path
from dataclasses import replace
import csv,json,tempfile,sys
sys.path.insert(0,str(Path.cwd()/'tests/cg4'))
from helpers import binary
from confidenceguard import ReliabilityWorkspace,WorkspaceConfig,InvestigationSpec,investigate,freeze_hypotheses,ConfirmationSpec,inspect_confirmation,confirm_investigation
from confidenceguard.investigation_replay import replay_investigation

def main():
 root=Path(tempfile.mkdtemp(prefix='replay-exposure-',dir='/private/tmp/numek-cg4-independent-review')).resolve();(root/'origin').mkdir();(root/'target').mkdir()
 origin_spec=binary(root/'origin');target_spec=binary(root/'target');namespace='independent-replay-exposure-fixture-'+root.name
 origin_spec=replace(origin_spec,roles=replace(origin_spec.roles,namespace=namespace));target_spec=replace(target_spec,roles=replace(target_spec.roles,namespace=namespace))
 path=root/'target/predictions.csv'
 with path.open() as f:rows=list(csv.DictReader(f))
 for row in rows:row.update(id=str(int(row['id'])+1000),entity=str(int(row['entity'])+1000),when='2026-01-01T00:00:00Z',label_at='2026-01-02T00:00:00Z')
 with path.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
 value=target_spec.to_dict();value['evaluation']['runs'][0]['prediction_at']={'column':'when'};value['evaluation']['outcomes']['available_at']={'column':'label_at'};target_spec=InvestigationSpec.from_dict(value)
 origin=investigate(origin_spec)
 ws=ReliabilityWorkspace.initialize(root/'workspace',WorkspaceConfig(saving=True,free_disk_bytes=1))
 ws.ingest({'schema_version':'confidenceguard.prediction_batch_spec/2.0','evaluation':value['evaluation'],'namespace':namespace,'outcome_definition_version':'v1','bindings':[{'run':'model'}],'feature_views':value['features']})
 variant=ws.models()[0]['id'];history=target_spec.to_dict();history.pop('evaluation');history['roles'].pop('column');history['objectives'][0]['run']=variant;history['history']={'workspace_path':str(ws.path),'selection':{'namespace':namespace,'variants':[variant],'as_of':'2026-02-01T00:00:00Z','windows':[{'id':'jan','start':'2026-01-01T00:00:00Z','end':'2026-02-01T00:00:00Z'}]}}
 replay=replay_investigation(origin,InvestigationSpec.from_dict(history),reason='Independent review reproduction: deliberately disclose target outcomes.')
 target_spec=replace(target_spec,roles=replace(target_spec.roles,namespace=namespace+'-renamed'))
 discovered=investigate(target_spec)
 policy=ConfirmationSpec(upstream_independence='declared_independent',external_exposure='declared_unexposed',declaration_author='Independent reviewer synthetic fixture',declaration_reason='Synthetic fixture. This declaration deliberately contradicts locally observable replay exposure to test enforcement.')
 frozen=freeze_hypotheses(discovered,confirmation=policy)
 preview=inspect_confirmation(frozen)
 assessed=confirm_investigation(frozen)
 result={'replay_observed_evidence':[{'period':h['period'],'planned':h['evidence']['planned'],'effect':h['evidence']['effect']} for h in replay.data['investigation']['history']],'inspection_admissibility_reasons':preview['admissibility_reasons'],'assessment_states':[{'state':a['state'],'H_outcomes_disclosed':a['H_outcomes_disclosed'],'strength':a['strength']} for a in assessed.data['investigation']['assessments']],'root':str(root)}
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
