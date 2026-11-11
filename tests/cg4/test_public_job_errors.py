"""Useful refusal guidance must never echo protected worker exception text."""
import time
import pytest

from datatrust.web import create_app
from confidenceguard.contracts import EvaluationError
from confidenceguard.transport import PUBLIC_CG4_ERRORS
from .helpers import binary

BASE='/api/confidenceguard/v1'


def test_allowed_root_choices_are_distinct_without_parent_path_disclosure(tmp_path):
    from confidenceguard.transport import _root_aliases
    assert _root_aliases(['/private/a/files','/private/b/other'])==[
        {'id':'root_0','label':'files'},{'id':'root_1','label':'other'}]
    roots=[tmp_path/'private-parent-a/models',tmp_path/'private-parent-b/models',tmp_path/'private-parent-c/models [root_0]']
    for root in roots:root.mkdir(parents=True)
    app=create_app(tmp_path/'host',data_roots=roots);app.testing=True
    try:
        value=app.test_client().get(BASE+'/session').json['data']['root_aliases']
        assert [row['id'] for row in value]==['root_0','root_1','root_2']
        assert len({row['label'] for row in value})==3
        assert value[0]['label']=='models [root_0]' and value[1]['label']=='models [root_1]'
        assert 'private-parent-' not in str(value) and str(tmp_path) not in str(value)
    finally:app.extensions['confidenceguard_store'].cleanup()


@pytest.mark.parametrize('code',['encoder_identity','encoder_runtime','vector_shape','unexpected_private_error'])
def test_CG4_failed_job_preserves_code_and_fixed_safe_guidance(tmp_path,monkeypatch,code):
    import confidenceguard.investigation_web as web
    secret='CG4_PRIVATE_WORKER_TEXT_DO_NOT_EXPORT'
    def refuse(*args,**kwargs):raise EvaluationError(secret,code)
    monkeypatch.setattr(web,'inspect_investigation',refuse)
    spec=binary(tmp_path).to_dict();app=create_app(tmp_path/'host',data_roots=(tmp_path,));app.testing=True
    client=app.test_client()
    try:
        headers={'X-CSRF-Token':client.get(BASE+'/session').json['data']['csrf_token']}
        source=client.post(BASE+'/sources',headers=headers,json={'root_id':'root_0','relative_path':'predictions.csv'}).json['data']
        spec['evaluation']['sources']=[{'id':'data','handle':source['handle']}]
        draft=client.post(BASE+'/investigations',headers=headers,json={'spec':spec}).json['data']
        posted=client.post(BASE+'/jobs',headers=headers,json={'kind':'investigation_inspect','investigation_id':draft['id'],'revision':1,'client_request_id':code})
        assert posted.status_code==202
        for _ in range(100):
            job=client.get(BASE+'/jobs/'+posted.json['data']['id']).json['data']
            if job['state'] not in {'pending','running'}:break
            time.sleep(.01)
        assert job['state']=='failed' and job['error']['code']==code
        assert secret not in str(job) and job['output']=={}
        if code in PUBLIC_CG4_ERRORS:assert job['error']['message']==PUBLIC_CG4_ERRORS[code]
        else:assert job['error']['message']=='Investigation stopped; review the refusal code and recorded limits.'
    finally:app.extensions['confidenceguard_store'].cleanup()
