import csv
from dataclasses import replace
import pytest
from confidenceguard import (ReliabilityWorkspace,WorkspaceConfig,PredictionBatchSpec,InvestigationSpec,
    inspect_investigation,investigate,FeatureViewSpec,FeatureField,FeatureEnrichmentSpec,SourceSpec,freeze_hypotheses,ConfirmationSpec)
from confidenceguard.investigation import arguments,prepared
from .helpers import binary


def retained(tmp_path):
    original=binary(tmp_path);evaluation=original.evaluation.to_dict();path=tmp_path/'predictions.csv'
    with path.open() as stream:values=list(csv.DictReader(stream))
    for row in values:row.update(when='2026-01-01T00:00:00Z',available='2026-01-02T00:00:00Z')
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(values[0]));writer.writeheader();writer.writerows(values)
    evaluation['runs'][0]['prediction_at']={'column':'when'};evaluation['outcomes']['available_at']={'column':'available'}
    namespace=original.roles.namespace
    batch={'evaluation':evaluation,'namespace':namespace,'outcome_definition_version':'v1','bindings':[{'run':'model'}],
           'schema_version':'confidenceguard.prediction_batch_spec/2.0','feature_views':[v.to_dict() for v in original.features]}
    ws=ReliabilityWorkspace.initialize(tmp_path/'workspace',WorkspaceConfig(saving=True,free_disk_bytes=1));ws.ingest(batch)
    variant=ws.models()[0]['id'];spec=original.to_dict();spec.pop('evaluation');spec['roles'].pop('column');spec['objectives'][0]['run']=variant
    spec['history']={'workspace_path':str(ws.path),'selection':{'namespace':namespace,'variants':[variant],'as_of':'2026-02-01T00:00:00Z',
        'windows':[{'id':'jan','start':'2026-01-01T00:00:00Z','end':'2026-02-01T00:00:00Z'}]}}
    return ws,InvestigationSpec.from_dict(spec)


def test_typed_capture_history_and_later_enrichment_do_not_rewrite_K(tmp_path):
    ws,spec=retained(tmp_path);preview=inspect_investigation(spec)
    frozen=InvestigationSpec.from_dict(preview['effective_spec']);result=investigate(frozen,expected_fingerprint=preview['fingerprint'])
    assert result.data['investigation']['candidates']
    ws.save_assessment(result);assert ws.open(result.data['analysis_id']).to_private_dict()==result.to_private_dict()
    opportunity=next(ws.catalog.iter_facts('opportunity'))['key']
    path=tmp_path/'enrichment.csv';path.write_text('opportunity_key,value\n'+opportunity+',9007199254740993\n')
    view=FeatureViewSpec('late',(FeatureField('exact','value','integer'),),availability='at_decision')
    ws.enrich_features(FeatureEnrichmentSpec(SourceSpec('enrichment',str(path)),spec.roles.namespace,view,'2026-03-01T00:00:00Z'))
    extra=replace(frozen,features=frozen.features+(view,));s,c,roots=arguments(extra,None,None)
    with prepared(s,c,roots) as p:assert all(cell['state']=='not_retained' for cell in p.features['late.exact'])
    latest=extra.to_dict();latest['history']['selection'].update(catalog_sequence=None,as_of='2026-04-01T00:00:00Z')
    s,c,roots=arguments(latest,None,None)
    with prepared(s,c,roots) as p:
        observed=[cell for cell in p.features['late.exact'] if cell['state']=='observed']
        assert len(observed)==1 and observed[0]['canonical']=='9007199254740993'
    assert ws.open(result.data['analysis_id']).to_private_dict()==result.to_private_dict()


def test_frozen_history_replay_and_outcome_only_restatement(tmp_path):
    ws,spec=retained(tmp_path);result=ws.investigate(spec,request_id='discovery-idempotent')
    assert ws.investigate(spec,request_id='discovery-idempotent').to_private_dict()==result.to_private_dict()
    frozen=freeze_hypotheses(result,confirmation=ConfirmationSpec(upstream_independence='declared_independent',external_exposure='declared_unexposed',declaration_author='fixture',declaration_reason='Independent synthetic entities and isolated namespace.'))
    confirmation=ws.confirm_investigation(frozen,request_id='confirmation-idempotent')
    assert ws.confirm_investigation(frozen,request_id='confirmation-idempotent').to_private_dict()==confirmation.to_private_dict()
    assert any(a['state']=='confirmed' for a in confirmation.data['investigation']['assessments'])
    before=confirmation.to_private_dict()
    updates=tmp_path/'updates.csv';updates.write_text('id,y,revision,order,available,status\n'+''.join(f'{i},{1-(i//12)%2},revision-1,1,2026-03-01T00:00:00Z,final\n' for i in range(720)))
    ws.update_outcomes({'source':{'id':'outcomes','path':str(updates)},'namespace':spec.roles.namespace,'outcome_definition_version':'v1','event_columns':['id'],'column':'y','revision_column':'revision','order_column':'order','available_at':{'column':'available'},'status_column':'status'})
    restated=ws.restate_investigation(confirmation.data['analysis_id'],as_of='2026-04-01T00:00:00Z',reason='Synthetic delayed-label correction')
    assert restated.data['investigation']['stage']=='restatement'
    assert restated.data['investigation']['inference']=='descriptive_only'
    assert all(not row['statistical_confirmation'] for row in restated.data['investigation']['history'])
    assert restated.private['memberships']==confirmation.private['memberships']
    assert ws.open(confirmation.data['analysis_id']).to_private_dict()==before
    annotated=ws.annotate_investigation(restated.data['analysis_id'],'Private working explanation\nRequires a separate causal investigation.')
    assert annotated.data['investigation']['notes'] and not annotated.to_dict()['investigation']['notes']
