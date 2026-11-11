import time
from dataclasses import replace
from click.testing import CliRunner
from datatrust.web import create_app
from confidenceguard.cli import main
from confidenceguard import schema
from .helpers import binary
import pytest

BASE='/api/confidenceguard/v1'


def wait(client,jid):
    for _ in range(600):
        result=client.get(BASE+'/jobs/'+jid).json['data']
        if result['state'] not in {'pending','running','cancelling'}:return result
        time.sleep(.05)
    raise AssertionError('CG4 job did not finish')


def test_CLI_and_generated_contracts():
    result=CliRunner().invoke(main,['investigation','--help'])
    assert result.exit_code==0 and 'inspect-confirmation' in result.output and 'freeze' in result.output
    defs=schema.schemas()['$defs']
    assert defs['InvestigationSpec']['additionalProperties'] is False
    assert 'FeatureEnrichmentSpec' in defs
    assert '/hypothesis-sets/import' in schema.openapi()['paths']
    assert schema.capabilities()['investigation']['moving_blocks_in_confirmation'] is False


def test_shareable_transport_export_does_not_publish_private_model_bundle(tmp_path):
    from confidenceguard import investigate
    from confidenceguard.transport import _export
    result=investigate(binary(tmp_path))
    shared=_export(result,str(tmp_path/'shared.html'),'html','shareable',None).to_dict()['artifacts']
    assert shared['html_path'] and shared['json_path']
    assert shared['private_result_path'] is None and shared['private_manifest_path'] is None
    assert not (tmp_path/'.confidenceguard-private').exists()
    python=result.generate_artifacts(tmp_path/'python-shared.html',json_path=tmp_path/'python-shared.json')
    assert python.private_result_path is None and python.private_manifest_path is None
    assert python.fitted_methods_path is None and not (tmp_path/'.confidenceguard-private').exists()
    from confidenceguard.contracts import DisclosureSpec
    exact=result.generate_artifacts(tmp_path/'exact-aggregates.html',disclosure=DisclosureSpec(policy='exact_aggregates_v1'))
    assert exact.private_result_path is None and exact.private_manifest_path is None
    assert not (tmp_path/'.confidenceguard-private').exists()
    local=_export(result,str(tmp_path/'local.html'),'html','local',None).to_dict()['artifacts']
    assert local['private_result_path'] and local['private_manifest_path']
    assert (tmp_path/'.confidenceguard-private').is_dir()


def test_partial_export_keeps_failed_job_and_surviving_public_artifacts(tmp_path,monkeypatch):
    import io,json
    from confidenceguard import investigate
    from confidenceguard import transport
    result=investigate(binary(tmp_path));before=result.to_private_dict()
    app=create_app(tmp_path/'host',data_roots=(tmp_path,));app.testing=True;client=app.test_client()
    original_supervise=transport.compat.supervise
    def supervised(function,args,config,**options):
        if function is transport._export:
            # Exercise the real export coordinator and job serialization while
            # deterministically faulting only its native PDF converter.
            def failed_renderer(*args):raise RuntimeError('PRIVATE_RENDERER_FAILURE_SENTINEL')
            with monkeypatch.context() as patch:
                patch.setattr(transport.compat,'pdf',failed_renderer)
                return function(*args)
        return original_supervise(function,args,config,**options)
    monkeypatch.setattr(transport.compat,'supervise',supervised)
    try:
        headers={'X-CSRF-Token':client.get(BASE+'/session').json['data']['csrf_token']}
        imported=client.post(BASE+'/results/import',headers=headers,data={
            'result':(io.BytesIO(json.dumps(before).encode()),'result.json'),
            'manifest':(io.BytesIO(json.dumps(result.private).encode()),'manifest.json')})
        assert imported.status_code==201,imported.json
        rid=imported.json['data']['result_id']
        posted=client.post(BASE+'/jobs',headers=headers,json={'kind':'export','result_id':rid,
            'format':'pdf','audience':'shareable','client_request_id':'partial-pdf'})
        assert posted.status_code==202,posted.json
        done=wait(client,posted.json['data']['id'])
        assert done['state']=='failed'
        assert done['error']['code']=='pdf_or_json_export_failed_surviving_artifacts_retained'
        assert done['output']['export_error']==done['error']['code']
        assert 'PRIVATE_RENDERER_FAILURE_SENTINEL' not in json.dumps(done)
        listed=client.get(BASE+f'/results/{rid}/artifacts').json['data']
        survived=[a for a in listed if a['id'] in done['output']['artifact_ids']]
        assert {a['kind'] for a in survived}=={'html','json'}
        assert all(a['audience']=='shareable' for a in survived)
        assert all(client.get(BASE+'/artifacts/'+a['id']+'/content').status_code==200 for a in survived)
        assert before==result.to_private_dict()
    finally:app.extensions['confidenceguard_store'].cleanup()


def test_api_discovery_freeze_confirmation_and_session_isolation(tmp_path):
    spec=binary(tmp_path).to_dict();spec['roles']['namespace']='api-'+tmp_path.name
    app=create_app(tmp_path/'host',data_roots=(tmp_path,));app.testing=True;client=app.test_client()
    try:
        headers={'X-CSRF-Token':client.get(BASE+'/session').json['data']['csrf_token']}
        registered=client.post(BASE+'/sources',headers=headers,json={'root_id':'root_0','relative_path':'predictions.csv'})
        assert registered.status_code==201
        spec['evaluation']['sources']=[{'id':'data','handle':registered.json['data']['handle']}]
        draft=client.post(BASE+'/investigations',headers=headers,json={'spec':spec}).json['data']
        assert app.test_client().get(BASE+'/investigations/'+draft['id']).status_code==404
        def job(kind,**values):
            posted=client.post(BASE+'/jobs',headers=headers,json={'kind':kind,'investigation_id':draft['id'],'revision':1,'client_request_id':kind,**values})
            assert posted.status_code==202,posted.json
            done=wait(client,posted.json['data']['id']);assert done['state']=='succeeded',done
            return done['output']
        inspected=job('investigation_inspect');assert not inspected['H_outcomes_disclosed']
        assert inspected['effective_spec']['objectives'][0]['units']=='fraction'
        discovered=job('investigation_discover',fingerprint=inspected['fingerprint']);rid=discovered['result_id']
        page=client.get(BASE+f'/results/{rid}/investigation/candidates?limit=1').json['data']
        assert len(page['items'])==1 and page['total']>1
        summary=client.get(BASE+f'/results/{rid}/investigation/summary').json['data']
        assert summary['view']=='investigation_summary/1.0'
        assert summary['investigation']['candidate_count']==page['total'] and 'candidates' not in summary['investigation']
        assert 'pairs' not in summary['investigation']['overlap']
        assert app.test_client().get(BASE+f'/results/{rid}/investigation/summary').status_code==404
        frozen=client.post(BASE+'/hypothesis-sets',headers=headers,json={'result_id':rid}).json['data']
        inspected=job('confirmation_inspect',hypothesis_handle=frozen['handle'])
        assessed=job('investigation_confirm',hypothesis_handle=frozen['handle'],confirmation_fingerprint=inspected['fingerprint'])
        rows=client.get(BASE+f"/results/{assessed['result_id']}/investigation/assessments").json['data']['items']
        assert all(row['state']=='statistically_inadmissible' for row in rows)
        for audience in ('local','shareable'):
            summary=client.get(BASE+f"/results/{assessed['result_id']}/investigation/summary?audience={audience}").json['data']
            assert summary['outcomes']['scope']=='observed_labels'
        assert client.post(BASE+'/investigations',json={'spec':spec}).status_code==403
    finally:app.extensions['confidenceguard_store'].cleanup()
