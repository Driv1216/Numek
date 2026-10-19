import copy
import io
import json
from pathlib import Path
import time
import pytest
from click.testing import CliRunner
from confidenceguard import study,EvaluationResult
from confidenceguard.cli import main
from confidenceguard.schema import schemas,openapi,examples
from datatrust.web import create_app
from .test_methods import binary_spec

BASE='/api/confidenceguard/v1'


def test_cli_fit_apply_and_reopen(tmp_path):
    spec=binary_spec(tmp_path);manifest=tmp_path/'study.json';manifest.write_text(json.dumps(spec))
    fit=CliRunner().invoke(main,['fit','--spec',str(manifest),'--out',str(tmp_path/'fit.html'),'--json-out',str(tmp_path/'fit.json')])
    assert fit.exit_code==0,fit.output
    artifacts=json.loads(fit.output);assert Path(artifacts['fitted_methods_path']).stat().st_mode&0o077==0
    portable=json.loads((tmp_path/'fit.json').read_text());assert portable['cg2']['methods'][0]['method_evidence_state']=='fitted_only'
    assert 'coefficients' not in json.dumps(portable)
    application=copy.deepcopy(spec);application['methods']=[];application['roles']={'namespace':'new-events','proportions':{'E':1}}
    application['evaluation'].pop('outcomes');manifest.write_text(json.dumps(application))
    applied=CliRunner().invoke(main,['apply','--spec',str(manifest),'--methods',artifacts['fitted_methods_path'],'--predictions-out',str(tmp_path/'applied.jsonl'),'--out',str(tmp_path/'applied.html')])
    assert applied.exit_code==0,applied.output
    paths=json.loads(applied.output);local=json.loads(Path(paths['private_result_path']).read_text());private=json.loads(Path(paths['private_manifest_path']).read_text())
    EvaluationResult.from_dict(local,private=private)
    assert local['cg2']['assessments']==[] and paths['application']['evidence_state']=='applied_unvalidated'


def test_cg2_json_workflow_ownership_and_method_import(tmp_path):
    spec=binary_spec(tmp_path);app=create_app(tmp_path/'host',data_roots=(tmp_path,));app.testing=True
    client=app.test_client()
    try:
        headers={'X-CSRF-Token':client.get(BASE+'/session').json['data']['csrf_token']}
        upload=client.post(BASE+'/sources',data={'file':(io.BytesIO((tmp_path/'predictions.csv').read_bytes()),'predictions.csv')},headers=headers)
        spec['evaluation']['sources']=[{'id':'predictions','handle':upload.json['data']['handle']}]
        draft=client.post(BASE+'/evaluations',json={'spec':spec},headers=headers)
        assert draft.status_code==201,draft.json
        draft=draft.json['data']
        def job(kind,**kwargs):
            response=client.post(BASE+'/jobs',json={'kind':kind,'client_request_id':str(time.monotonic()),**kwargs},headers=headers)
            assert response.status_code==202,response.json
            j=response.json['data'];deadline=time.monotonic()+30
            while j['state'] in {'pending','running','cancelling'} and time.monotonic()<deadline:
                time.sleep(.02);j=client.get(BASE+'/jobs/'+j['id']).json['data']
            assert j['state']=='succeeded',j
            return j['output']
        inspected=job('inspect',evaluation_id=draft['id'],revision=1)
        assert 'path' not in inspected['effective_spec']['evaluation']['sources'][0]
        result=job('study',evaluation_id=draft['id'],revision=1,fingerprint=inspected['fingerprint'])
        assert result.get('method_handles'),client.get(BASE+'/results/'+result['result_id']+'/summary').json['data']['cg2']['fit_status']
        mid=result['method_handles'][0]
        assert app.test_client().get(BASE+'/methods/'+mid).status_code==404
        saved=client.get(BASE+'/methods/'+mid+'/content')
        assert saved.status_code==200 and saved.json['evidence_state']=='fitted_only'
        assert client.get(BASE+'/results/'+result['result_id']+'/assessments').json['data'][0]['evidence_state']=='independently_evaluated'
        exported=job('export',result_id=result['result_id'],format='html',audience='shareable')
        listed=client.get(BASE+'/results/'+result['result_id']+'/artifacts').json['data']
        methods=next(a for a in listed if a['kind']=='fitted_methods');assert methods['audience']=='local'
        portable=client.get(BASE+'/results/'+result['result_id']+'?audience=shareable').json['data']
        assert 'coefficients' not in json.dumps(portable)
        assert client.get('/confidenceguard/assets/method-client.js').status_code==200
        client2=app.test_client();headers2={'X-CSRF-Token':client2.get(BASE+'/session').json['data']['csrf_token']}
        imported=client2.post(BASE+'/methods/import',data={'file':(io.BytesIO(saved.data),'method.json')},headers=headers2)
        assert imported.status_code==201,imported.json
        assert imported.json['data']['evidence_state']=='fitted_only'
        assert client2.get(BASE+'/methods/'+mid).status_code==404
    finally:app.extensions['confidenceguard_store'].cleanup()


def test_generated_cg2_contracts_and_examples(tmp_path):
    definitions=schemas()['$defs']
    assert definitions['FittedMethod']['additionalProperties'] is False
    assert '/methods/import' in openapi()['paths']
    from confidenceguard import ReliabilitySpec
    for example in examples()['studies'].values():
        spec=copy.deepcopy(example['spec']);spec['evaluation']['sources']=[{'id':'predictions','path':str(tmp_path/'data.csv')}]
        ReliabilitySpec.from_dict(spec)
    try:import jsonschema
    except ImportError:pytest.skip('Development JSON Schema validator unavailable')
    document=schemas()
    for example in examples()['studies'].values():
        jsonschema.Draft202012Validator({'$defs':document['$defs'],'$ref':'#/$defs/TransportReliabilitySpec'}).validate(example['spec'])


def test_actual_inference_and_adjusted_tail_rejection(tmp_path):
    spec=binary_spec(tmp_path,[{'id':'platt','kind':'platt','run':'original','input':'score'}])
    spec['inference']={'mode':'independent_rows','metrics':['brier','log_loss'],'replicates':3000,'adjustment':'pointwise'}
    result=study(spec)
    contrasts=result.data['cg2']['inference']['contrasts']
    assert len(contrasts)==2
    assert all(c['status'] in {'available','unavailable'} for c in contrasts)
    assert any(c['status']=='available' for c in contrasts)
    spec['inference'].update(adjustment='bonferroni',replicates=200)
    blocked=study(spec).data['cg2']['inference']['contrasts']
    assert all(c['status']=='not_admitted' for c in blocked)
    assert all('insufficient_tail_resolution' in c['reasons'] for c in blocked)
