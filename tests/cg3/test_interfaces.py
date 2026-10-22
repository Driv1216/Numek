import io
import json
import time
from pathlib import Path
import pytest
from click.testing import CliRunner
from confidenceguard.cli import main
from datatrust.web import create_app
from .test_history import workspace, batch, longitudinal

BASE = '/api/confidenceguard/v1'


def test_workspace_authorization_api_and_owned_jobs(tmp_path):
    ws = workspace(tmp_path); spec = batch(tmp_path)
    app = create_app(tmp_path/'host', data_roots=(tmp_path,), confidenceguard_workspace=ws.path, confidenceguard_launch_token='local-launch')
    app.testing = True
    client = app.test_client(); other = app.test_client()
    token = client.get(BASE+'/session').json['data']['csrf_token']; headers = {'X-CSRF-Token': token}
    assert client.get(BASE+'/workspace').status_code == 403
    assert client.get('/confidenceguard?launch=local-launch').status_code == 303
    assert other.get('/confidenceguard?launch=local-launch').status_code == 303
    assert other.get(BASE+'/workspace').status_code == 403
    assert client.get(BASE+'/workspace').status_code == 200
    uploaded = client.post(BASE+'/sources', data={'file': (io.BytesIO(Path(spec['evaluation']['sources'][0]['path']).read_bytes()), 'predictions.csv')}, headers=headers)
    spec['evaluation']['sources'] = [{'id': 'p', 'handle': uploaded.json['data']['handle']}]
    def job(kind, **fields):
        response = client.post(BASE+'/workspace/jobs', json={'kind': kind, 'client_request_id': str(time.monotonic()), **fields}, headers=headers)
        assert response.status_code == 202, response.json
        state = response.json['data']; deadline = time.monotonic()+40
        assert other.get(BASE+'/jobs/'+state['id']).status_code == 404
        while state['state'] in {'pending', 'running', 'cancelling'} and time.monotonic() < deadline:
            time.sleep(.02); state = client.get(BASE+'/jobs/'+state['id']).json['data']
        assert state['state'] == 'succeeded', state
        return state['output']
    try:
        job('ingest', spec=spec)
        analysis = longitudinal(ws)
        inspection = client.post(BASE+'/workspace/inspect', json={'spec': analysis}, headers=headers).json['data']
        output = job('analyze', spec=analysis, fingerprint=inspection['fingerprint'])
        aid = output['assessment_id']
        assert client.get(BASE+'/workspace/assessments/'+aid).status_code == 200
        assert other.get(BASE+'/workspace/assessments/'+aid).status_code == 403
        exported = job('export', assessment_id=aid, format='html', audience='shareable')
        assert exported['artifact_ids']
        for artifact in exported['artifact_ids']:
            assert client.get(BASE+'/artifacts/'+artifact+'/content').status_code == 200
            assert other.get(BASE+'/artifacts/'+artifact+'/content').status_code == 404
        assert client.post(BASE+'/workspace/detach', json={}, headers=headers).status_code == 200
        assert client.get(BASE+'/workspace').status_code == 403
        assert client.get(BASE+'/results/'+aid).status_code == 403
        assert client.get(BASE+'/artifacts/'+exported['artifact_ids'][0]+'/content').status_code == 403
    finally:
        app.extensions['confidenceguard_store'].cleanup()


def test_cli_history_contracts_and_report_reopening(tmp_path):
    ws = workspace(tmp_path); spec = batch(tmp_path); ws.ingest(spec)
    manifest = tmp_path/'analysis.json'; manifest.write_text(json.dumps(longitudinal(ws)))
    result = CliRunner().invoke(main, ['workspace', '--path', str(ws.path), 'analyze', '--spec', str(manifest), '--out', str(tmp_path/'report.html')])
    assert result.exit_code == 0, result.output
    output = json.loads(result.output)
    assert Path(output['artifacts']['html_path']).exists()
    portable = json.loads((tmp_path/'report.json').read_text())
    from confidenceguard import LongitudinalResult
    shared = LongitudinalResult.from_dict(portable)
    assert shared.to_dict() == portable
    assert 'What changed?' in (tmp_path/'report.html').read_text()
    from confidenceguard.schema import schemas, openapi, examples
    assert 'PredictionBatchSpec' in schemas()['$defs']
    assert '/workspace/jobs' in openapi()['paths']
    assert examples()['history']
