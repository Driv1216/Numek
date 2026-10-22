"""Persistent workspace authorization and thin jobs on the existing local API."""
import copy
import hmac
import logging
from pathlib import Path
import re
import threading
import time
import uuid
from flask import abort, request
from .contracts import EvaluationError, EvaluationConfig, digest
from .history_contracts import PredictionBatchSpec, OutcomeRevisionSpec, LongitudinalSpec
from .workspace import ReliabilityWorkspace
from . import compat


class LaunchLogFilter(logging.Filter):
    def filter(self, record):
        def clean(value):
            return re.sub(r'([?&]launch=)[^\s&"]+', r'\1[redacted]', value) if isinstance(value, str) else value
        record.msg = clean(record.msg)
        if isinstance(record.args, tuple): record.args = tuple(clean(v) for v in record.args)
        return True


def register(bp, app, sessions, *, workspace_path=None, launch_token=None):
    workspace = ReliabilityWorkspace(workspace_path) if workspace_path else None
    authorization = {'token': launch_token, 'expires': time.monotonic()+600, 'generation': uuid.uuid4().hex}
    logging.getLogger('werkzeug').addFilter(LaunchLogFilter())
    app.extensions['confidenceguard_workspace'] = workspace

    def redeem(token):
        if workspace and authorization['token'] and time.monotonic() < authorization['expires'] and hmac.compare_digest(token, authorization['token']):
            sessions.current()['workspace_grant'] = (workspace.instance_id, authorization['generation'])
            authorization['token'] = None
            return True
        return False
    app.extensions['confidenceguard_redeem_workspace'] = redeem

    def authorized():
        state = sessions.current()
        if workspace is None: abort(404)
        if state.get('workspace_grant') != (workspace.instance_id, authorization['generation']): abort(403)
        workspace.catalog._validate()
        if state.get('workspace_grant') != (workspace.instance_id, authorization['generation']): abort(403)
        return workspace
    app.extensions['confidenceguard_authorize_workspace'] = authorized

    def response(data, status=200): return {'api_version': 'v1', 'data': data}, status
    def body(allowed):
        from .contracts import strict_json
        if not request.is_json: abort(415)
        value = strict_json(request.get_data())
        if not isinstance(value, dict) or set(value)-set(allowed): raise EvaluationError('Unknown workspace request fields.')
        return value
    def source_spec(value):
        value = copy.deepcopy(value)
        if not isinstance(value, dict): raise EvaluationError('Source handles required.')
        state = sessions.current()
        sources = value.get('evaluation', {}).get('evaluation', value.get('evaluation', {})).get('sources') if 'evaluation' in value else [value.get('source')]
        if not isinstance(sources, list): raise EvaluationError('Source handles required.')
        for source in sources:
            if not isinstance(source, dict) or set(source) != {'id', 'handle'}: raise EvaluationError('Workspace sources require opaque handles only.')
            registered = state['sources'].get(source['handle'])
            if not registered: abort(404)
            sid = source['id']; source.clear(); source.update(id=sid, **{k: registered[k] for k in ('path', 'format', 'encoding', 'delimiter')})
        if 'evaluation' in value:
            method = value['evaluation']
            handles=method.pop('method_handles',[])
            if not isinstance(handles,list):raise EvaluationError('Method handles require an array.')
            if handles:
                if method.get('fitted_methods'):raise EvaluationError('Choose fitted payloads or owned handles.')
                owned=[]
                for handle in handles:
                    item=state['methods'].get(handle)
                    if item is None or item.get('workspace_instance',workspace.instance_id)!=workspace.instance_id:abort(404)
                    owned.append(item)
                method['fitted_methods']=[copy.deepcopy(item['method']) for item in owned]
                method['membership_sidecars']=list({v['content_digest']:copy.deepcopy(v) for item in owned for v in item.get('membership_sidecars',[])}.values())
            if method.get('output_path') is not None: raise EvaluationError('Application paths are host controlled.')
            if method.get('schema_version') == 'confidenceguard.application_spec/1.0':
                directory = compat.protected_directory(state['directory']/'applications'/uuid.uuid4().hex)
                method['output_path'] = str(directory/'predictions.jsonl')
        return value

    @bp.get('/workspace/access')
    def access():
        state = sessions.current()
        return response({'enabled': workspace is not None, 'authorized': bool(workspace and state.get('workspace_grant') == (workspace.instance_id, authorization['generation']))})

    @bp.get('/workspace')
    def status(): return response(authorized().status())

    @bp.post('/workspace/consent')
    def consent():
        ws = authorized(); value = body({'saving'})
        return response(ws.set_saving(value.get('saving')))

    @bp.post('/workspace/detach')
    def detach():
        authorized(); state = sessions.current(); state.pop('workspace_grant', None)
        for job in state['jobs'].values():
            if job.get('workspace_instance') and job['state'] in {'pending', 'running', 'cancelling'}: job['cancel'].set()
        return response({'detached': True})

    @bp.get('/workspace/models')
    def models(): return response({'items': authorized().models()})

    @bp.get('/workspace/assessments')
    def assessments(): return response({'items': authorized().assessments()})

    @bp.get('/workspace/assessments/<aid>')
    def assessment(aid):
        result = authorized().open(aid)
        audience = request.args.get('audience', 'local')
        return response(result.to_dict(audience=audience))

    @bp.post('/workspace/inspect')
    def inspect():
        ws = authorized(); value = body({'spec'})
        if not sessions.worker_lock.acquire(blocking=False):raise EvaluationError('Shared worker is busy.','worker_busy')
        try:return response(ws.inspect(value['spec']))
        finally:sessions.worker_lock.release()

    @bp.post('/workspace/deletion-preview')
    def deletion_preview():
        ws = authorized(); value = body({'object_ids', 'assessment_ids', 'batch_ids', 'purge'})
        return response(ws.deletion_preview(**value))

    @bp.post('/workspace/jobs')
    def workspace_submit():
        ws = authorized(); state = sessions.current()
        value = body({'kind', 'client_request_id', 'spec', 'config', 'fingerprint', 'assessment_id', 'as_of', 'reason', 'plan', 'format', 'audience', 'reference', 'reveal_values'})
        kind = value.get('kind'); request_id = value.get('client_request_id')
        if kind not in {'ingest', 'outcomes', 'analyze', 'restate', 'correct', 'recover', 'backup', 'delete', 'export', 'resolve_evidence'} or not isinstance(request_id, str) or not request_id or len(request_id) > 512:
            raise EvaluationError('Invalid workspace job.')
        config = EvaluationConfig.from_dict(value.get('config', {}))
        if config.scratch_directory is not None: raise EvaluationError('Scratch paths are host controlled.')
        specification = value.get('spec')
        if kind in {'ingest', 'outcomes'}:
            specification = source_spec(specification)
            specification = PredictionBatchSpec.from_dict(specification) if kind == 'ingest' else OutcomeRevisionSpec.from_dict(specification)
        if kind == 'analyze':
            specification = LongitudinalSpec.from_dict(specification)
            effective = ws.inspect(specification,populations=False)
            if value.get('fingerprint') != effective['fingerprint']: abort(409)
        key = 'workspace:' + request_id; request_digest = digest(value)
        if key in state['requests']:
            previous_digest, jid = state['requests'][key]
            if previous_digest != request_digest: abort(409)
            return response({k: v for k, v in state['jobs'][jid].items() if k not in {'cancel', 'thread'}}, 202)
        if not sessions.worker_lock.acquire(blocking=False):
            raise EvaluationError('Shared worker is busy.', 'worker_busy')
        jid = uuid.uuid4().hex
        job = {'id': jid, 'kind': 'workspace_'+kind, 'state': 'pending', 'revision': 1, 'progress': {}, 'output': {}, 'error': None,
               'evaluation_id': None, 'evaluation_revision': 0, 'cancel': threading.Event(), 'workspace_instance': ws.instance_id}
        state['jobs'][jid] = job; state['requests'][key] = (request_digest, jid)
        grant = state['workspace_grant']
        def progress(data):
            with sessions.guard: job['progress'] = data; job['revision'] += 1
        def execute():
            try:
                job['state'] = 'running'
                if state.get('workspace_grant') != grant: raise EvaluationError('Workspace was detached.', 'workspace_access')
                roots = sessions.roots + (str(state['directory']),)
                kwargs = {'progress': progress, 'cancel': job['cancel']}
                if kind == 'ingest': output = ws.ingest(specification, config, request_id=request_id, allowed_roots=roots, **kwargs)
                elif kind == 'outcomes': output = ws.update_outcomes(specification, config, request_id=request_id, allowed_roots=roots, **kwargs)
                elif kind in {'analyze', 'restate'}:
                    result = ws.analyze(specification, request_id=request_id, expected_fingerprint=value.get('fingerprint'), **kwargs) if kind == 'analyze' else ws.restate(value['assessment_id'], as_of=value.get('as_of'), reason=value['reason'], request_id=request_id, **kwargs)
                    rid = result.data['analysis_id']; state['results'][rid] = {'result': result, 'evaluation_id': None, 'revision': 0, 'workspace_instance': ws.instance_id}
                    output = {'assessment_id': rid, 'result_id': rid, 'committed': True}
                elif kind == 'correct': output = ws.correct(value['spec'], request_id=request_id)
                elif kind == 'recover': output = ws.recover()
                elif kind == 'delete':
                    output = ws.delete(value['plan'])
                    if output['workspace_retired']: authorization['generation'] = uuid.uuid4().hex
                elif kind == 'backup':
                    dest = state['directory']/('backup-'+jid)
                    manifest = ws.backup(dest)
                    import zipfile
                    archive = state['directory']/('backup-'+jid+'.zip')
                    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_STORED) as packet:
                        for relative in ('backup.json', *manifest['files']): packet.write(dest/relative, relative)
                    info, _, _ = compat.capture(archive, (str(state['directory']),))
                    aid = uuid.uuid4().hex
                    state['artifacts'][aid] = {'id': aid, 'result_id': None, 'kind': 'workspace_backup', 'audience': 'local', 'path': str(archive), 'identity': info, 'bytes': info['bytes'], 'workspace_instance': ws.instance_id}
                    output = {'artifact_ids': [aid]}
                elif kind == 'resolve_evidence':
                    result = ws.open(value['assessment_id'])
                    output = result.resolve_evidence(value['reference'], allowed_roots=(str(ws.path),), reveal_values=value.get('reveal_values', False))
                else:
                    result = ws.open(value['assessment_id'])
                    fmt = value.get('format', 'html'); audience = value.get('audience', 'shareable')
                    if fmt not in {'html', 'pdf'} or audience not in {'local', 'shareable'}: raise EvaluationError('Invalid historical export.')
                    directory = compat.protected_directory(state['directory']/('history-export-'+jid))
                    from .transport import _export
                    packet = compat.supervise(_export, (result, str(directory/('report.'+fmt)), fmt, audience, None), config, **kwargs)
                    ids = []
                    for field, path in packet.data['artifacts'].items():
                        if not field.endswith('_path') or not path: continue
                        info, _, _ = compat.capture(path, (str(state['directory']),)); aid = uuid.uuid4().hex
                        state['artifacts'][aid] = {'id': aid, 'result_id': value['assessment_id'], 'kind': field.removesuffix('_path'), 'audience': 'local' if field.startswith('private') else audience, 'path': path, 'identity': info, 'bytes': info['bytes'], 'workspace_instance': ws.instance_id}; ids.append(aid)
                    output = {'artifact_ids': ids}
                if kind=='ingest' and output.get('assessment_id'):
                    captured=ws.open(output['assessment_id']);rid=captured.data['analysis_id']
                    state['results'][rid]={'result':captured,'evaluation_id':None,'revision':0,'workspace_instance':ws.instance_id}
                    method_handles=[]
                    for method in captured.private.get('fitted_methods',[]):
                        handle=uuid.uuid4().hex
                        state['methods'][handle]={'method':method,'result_id':rid,'workspace_instance':ws.instance_id,
                            'membership_sidecars':[v for v in captured.private.get('membership_sidecars',[]) if method['artifact_digest'] in v['method_digests']]}
                        method_handles.append(handle)
                    output={**output,'result_id':rid,'method_handles':method_handles}
                with sessions.guard:
                    job['output'] = output; job['state'] = 'succeeded'
            except Exception as exc:
                with sessions.guard:
                    completed=getattr(exc,'completed_evaluation',None)
                    if completed is not None:
                        rid=completed.data['analysis_id'];state['results'][rid]={'result':completed,'evaluation_id':None,'revision':0,'workspace_instance':ws.instance_id}
                        job['output']={'result_id':rid,'evaluation_completed':True,'history_not_committed':True}
                    job['state'] = 'cancelled' if getattr(exc, 'code', '') == 'cancelled' else 'failed'
                    job['error'] = {'code': getattr(exc, 'code', 'workspace_operation_failed'), 'message': 'Workspace operation stopped; inspect declarations, ownership and resource limits.'}
            finally:
                job['revision'] += 1; sessions.worker_lock.release()
        job['thread'] = threading.Thread(target=execute, daemon=True); job['thread'].start()
        return response({k: v for k, v in job.items() if k not in {'cancel', 'thread'}}, 202)
