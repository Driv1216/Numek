"""Session-owned local JSON transport; independent of browser templates."""
from dataclasses import asdict,replace
import copy
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import shutil
import threading
from urllib.parse import urlsplit
import uuid
from flask import Blueprint,abort,jsonify,request,send_file,session
from werkzeug.exceptions import HTTPException
from .contracts import *
from .engine import evaluate,inspect
from .result import EvaluationResult,SharedResult,Inspection
from . import compat
from . import schema
from .method_contracts import ReliabilitySpec,parse_spec
from .methods import fit_methods,apply_methods,study

PREFIX='/api/confidenceguard/v1'


def _export(result,path,format,audience,disclosure,*,progress=None):
    try:
        artifacts=result.generate_artifacts(path,format=format,json_path=str(Path(path).with_suffix('.json')),audience=audience,disclosure=disclosure)
        output={'artifacts':asdict(artifacts)}
    except Exception as exc:
        if not getattr(exc,'artifacts',None):raise EvaluationError('Artifact export failed.','export_failed') from exc
        output={'artifacts':asdict(exc.artifacts),'export_error':'pdf_or_json_export_failed_surviving_artifacts_retained'}
    return Inspection(output,{'status':'completed','peak_workspace_bytes':0})


def _resolve(result,reference,roots,reveal,*,progress=None):
    return Inspection(result.resolve_evidence(reference,allowed_roots=roots,reveal_values=reveal),{'status':'completed','peak_workspace_bytes':0})


class Sessions:
    def __init__(self,root,roots,lock):
        self.root=compat.protected_directory(root);self.roots=tuple(str(Path(r).absolute()) for r in roots);self.worker_lock=lock;self.guard=threading.RLock();self.sessions={}
    def current(self):
        sid=session.get('confidenceguard_session')
        if sid not in self.sessions:
            sid=uuid.uuid4().hex;session['confidenceguard_session']=sid
            self.sessions[sid]={'id':sid,'csrf':secrets.token_urlsafe(32),'directory':compat.protected_directory(self.root/sid),'sources':{},'evaluations':{},'jobs':{},'results':{},'artifacts':{},'requests':{},'methods':{}}
        return self.sessions[sid]
    def cleanup(self):
        for state in list(self.sessions.values()):
            for job in state['jobs'].values():job['cancel'].set()
            for job in state['jobs'].values():
                if job.get('thread'):job['thread'].join(10)
            if not any(j.get('thread') and j['thread'].is_alive() for j in state['jobs'].values()):shutil.rmtree(state['directory'],ignore_errors=True)
        self.sessions.clear()


def register(app,workspace,roots,*,persistent_workspace=None,launch_token=None):
    app.config['SESSION_COOKIE_HTTPONLY']=True
    app.config['SESSION_COOKIE_SAMESITE']='Strict'
    store=Sessions(Path(workspace)/'confidenceguard',roots,app.extensions['datatrust_worker_lock']);app.extensions['confidenceguard_store']=store
    bp=Blueprint('confidenceguard_api',__name__,url_prefix=PREFIX)
    def response(data,status=200):return jsonify({'api_version':'v1','data':exact(data)}),status
    def own(collection,identifier):
        value=store.current()[collection].get(identifier)
        if value is None:abort(404)
        if value.get('workspace_instance') is not None:
            authorized=app.extensions['confidenceguard_authorize_workspace']()
            if authorized.instance_id!=value['workspace_instance']:abort(404)
        return value
    def body(allowed,required=()):
        if not request.is_json:abort(415)
        try:value=strict_json(request.get_data(as_text=True))
        except (ValueError,UnicodeError):raise EvaluationError('Invalid JSON request.')
        if not isinstance(value,dict) or set(value)-set(allowed) or set(required)-set(value):raise EvaluationError('Unknown or missing request fields.')
        return value
    def job_view(j):
        return {k:j[k] for k in ('id','kind','state','revision','progress','output','error','evaluation_id','evaluation_revision')}
    def resolve_spec(state,public):
        value=copy.deepcopy(public)
        if not isinstance(value,dict):raise EvaluationError('A transport specification requires source handles.')
        cg2=value.get('schema_version') in {'confidenceguard.evaluation_spec/1.1','confidenceguard.study_spec/1.0','confidenceguard.application_spec/1.0'}
        target=value.get('evaluation') if cg2 else value
        if not isinstance(target,dict) or not isinstance(target.get('sources'),list):raise EvaluationError('A transport specification requires source handles.')
        if cg2:
            if value.get('output_path') is not None:raise EvaluationError('Application destinations are controlled by the host.')
            handles=value.pop('method_handles',[])
            if not isinstance(handles,list):raise EvaluationError('Method handles require an array.')
            if handles:
                if value.get('fitted_methods'):raise EvaluationError('Choose fitted payloads or owned method handles.')
                value['fitted_methods']=[copy.deepcopy(own('methods',handle)['method']) for handle in handles]
                sidecars={v['content_digest']:copy.deepcopy(v) for handle in handles for v in own('methods',handle).get('membership_sidecars',[])}
                value['membership_sidecars']=list(sidecars.values())
            # Stable per-configuration destination is included in inspection binding.
            value['output_path']=str(state['directory']/'applications'/digest(public)/'predictions.jsonl')
        for s in target['sources']:
            if not isinstance(s,dict) or set(s)!={'id','handle'}:raise EvaluationError('Transport sources require only id and handle; paths are not accepted.')
            source=state['sources'].get(s['handle'])
            if source is None:abort(404)
            sid=s['id'];s.clear();s.update(id=sid,path=source['path'],format=source['format'],encoding=source['encoding'],delimiter=source['delimiter'])
        return parse_spec(value)
    def config_from(value):
        if not isinstance(value,dict) or value.get('scratch_directory') is not None:raise EvaluationError('Scratch roots are controlled by the local host.')
        return EvaluationConfig.from_dict(value)
    def active(state,eid):return any(j['evaluation_id']==eid and j['state'] in {'pending','running','cancelling'} for j in state['jobs'].values())
    def remember(state,rid,artifacts,audience):
        ids=[]
        for kind,path in artifacts.items():
            if not kind.endswith('_path') or path is None:continue
            info,_,_=compat.capture(path,(str(state['directory']),))
            aid=uuid.uuid4().hex;state['artifacts'][aid]={'id':aid,'result_id':rid,'kind':kind.removesuffix('_path'),'audience':'local' if kind.startswith('private') or kind in {'fitted_methods_path','application_path'} else audience,'path':path,'identity':info,'bytes':info['bytes']};ids.append(aid)
        return ids

    @bp.before_request
    def guard():
        host=urlsplit('http://'+request.host).hostname
        if host not in {'localhost','127.0.0.1','::1'}:abort(403,description='Loopback host required.')
        origin=request.headers.get('Origin')
        if origin and origin!=request.host_url.rstrip('/'):abort(403,description='Same origin required.')
        if request.headers.get('Sec-Fetch-Site')=='cross-site':abort(403,description='Same origin required.')
        state=store.current()
        if request.method in {'POST','PUT','DELETE','PATCH'} and not hmac.compare_digest(request.headers.get('X-CSRF-Token',''),state['csrf']):abort(403,description='A current JSON CSRF token is required.')

    @bp.after_request
    def headers(r):
        r.headers['Cache-Control']='no-store';r.headers['X-Content-Type-Options']='nosniff';r.headers['X-Frame-Options']='DENY'
        return r

    @bp.errorhandler(Exception)
    def failure(exc):
        status=exc.code if isinstance(exc,HTTPException) else 422 if isinstance(exc,(ValueError,TypeError)) else 500
        code=exc.code if isinstance(exc,EvaluationError) else f'http_{status}' if isinstance(exc,HTTPException) else 'invalid_request' if status==422 else 'operation_failed'
        if code in {'workspace_busy','worker_busy','stale_confirmation','idempotency_conflict','stale_deletion','operation_incomplete'}:status=409
        if code in {'history_quota','history_record_limit','manifest_limit','history_scan_limit'}:status=413
        return jsonify({'api_version':'v1','error':{'code':code,'message':'Request could not be completed; review the declared fields or resource state.','field_errors':[{'pointer':'/','code':code}] if status==422 else [],'request_id':uuid.uuid4().hex,'retryable':status==409}}),status

    @bp.get('/session')
    def bootstrap():
        s=store.current();return response({'csrf_token':s['csrf'],'root_aliases':[{'id':f'root_{i}','label':Path(p).name} for i,p in enumerate(store.roots)],'session_lifetime':'local_process'})
    @bp.get('/capabilities')
    def capabilities():return response({**schema.capabilities(),'upload_limit_bytes':app.config.get('MAX_CONTENT_LENGTH')})
    @bp.get('/schemas')
    def schemas():return jsonify(schema.schemas())
    @bp.get('/openapi.json')
    def openapi():return jsonify(schema.openapi())
    @bp.get('/examples')
    def examples():return response(schema.examples())

    @bp.post('/sources')
    def sources():
        state=store.current();sid=uuid.uuid4().hex
        if request.files:
            if set(request.files)!={'file'} or set(request.form)-{'format','encoding','delimiter'}:raise EvaluationError('Upload requires one file and supported parsing fields.')
            upload=request.files['file'];fmt=request.form.get('format') or ('parquet' if (upload.filename or '').lower().endswith('.parquet') else 'csv')
            choice(fmt,{'csv','parquet'},'source format')
            path=state['directory']/f'upload-{sid}.{fmt}';upload.save(path)
            value={'format':fmt,'encoding':request.form.get('encoding','utf-8-sig'),'delimiter':request.form.get('delimiter',',')}
        else:
            value=body({'root_id','relative_path','format','encoding','delimiter'},{'root_id','relative_path'})
            index=next((i for i in range(len(store.roots)) if value['root_id']==f'root_{i}'),None)
            relative=Path(value['relative_path'])
            if index is None or relative.is_absolute() or '..' in relative.parts:raise EvaluationError('Choose an allowed-root-relative file.')
            path=Path(store.roots[index])/relative;fmt=value.get('format') or ('parquet' if path.suffix.lower()=='.parquet' else 'csv')
            # Secure regular-file/root validation; content hashing happens under the supervised job.
            with compat.secure_open(path,store.roots):pass
        source=SourceSpec(sid,str(path),fmt,value.get('encoding','utf-8-sig'),value.get('delimiter',','))
        config=EvaluationConfig();columns=[]
        from .sources import records
        for coordinate,_ in records(path,source,config):
            if 'header' in coordinate:columns=coordinate['header'];break
        state['sources'][sid]={'path':str(path),'format':fmt,'encoding':source.encoding,'delimiter':source.delimiter,'columns':columns}
        return response({'handle':sid,'format':fmt,'columns':columns},201)

    @bp.route('/evaluations',methods=['POST'])
    def create_evaluation():
        value=body({'spec','config'},{'spec'});state=store.current();resolve_spec(state,value['spec']);config_from(value.get('config',{}))
        eid=uuid.uuid4().hex;state['evaluations'][eid]={'id':eid,'revision':1,'spec':value['spec'],'config':value.get('config',{}),'confirmation':None}
        return response(state['evaluations'][eid],201)

    @bp.route('/evaluations/<eid>',methods=['GET','PUT','DELETE'])
    def evaluation(eid):
        state=store.current();ev=own('evaluations',eid)
        if request.method=='GET':return response(ev)
        if active(state,eid):abort(409)
        if request.method=='DELETE':
            remove=[rid for rid,v in state['results'].items() if v['evaluation_id']==eid]
            for aid,a in list(state['artifacts'].items()):
                if a['result_id'] in remove:
                    if a['kind']=='application':
                        try:
                            compat.capture(a['path'],(str(state['directory']),),expected=a['identity']);Path(a['path']).unlink()
                        except (OSError,EvaluationError):pass
                    state['artifacts'].pop(aid)
            for mid,m in list(state['methods'].items()):
                if m['result_id'] in remove:state['methods'].pop(mid)
            for rid in remove:
                state['results'].pop(rid);shutil.rmtree(state['directory']/rid,ignore_errors=True)
            for jid,j in list(state['jobs'].items()):
                if j['evaluation_id']==eid:state['jobs'].pop(jid)
            state['evaluations'].pop(eid);return response({'deleted':True})
        value=body({'spec','config','expected_revision'},{'spec','expected_revision'})
        if value['expected_revision']!=ev['revision']:abort(409)
        resolve_spec(state,value['spec']);config_from(value.get('config',{}))
        ev.update(spec=value['spec'],config=value.get('config',{}),revision=ev['revision']+1,confirmation=None)
        return response(ev)

    @bp.post('/jobs')
    def submit():
        value=body({'kind','client_request_id','evaluation_id','revision','fingerprint','result_id','format','audience','disclosure','reference','reveal_values'},{'kind','client_request_id'})
        state=store.current();choice(value['kind'],{'inspect','evaluate','fit','apply','study','export','resolve_evidence'},'job kind');name(value['client_request_id'])
        request_key=value['client_request_id'];request_digest=digest(value)
        if request_key in state['requests']:
            old_digest,jid=state['requests'][request_key]
            if old_digest!=request_digest:abort(409)
            return response(job_view(state['jobs'][jid]),202)
        kind=value['kind'];eid=None;ev=None;item=None
        permitted={'kind','client_request_id'}|({'evaluation_id','revision'} if kind=='inspect' else {'evaluation_id','revision','fingerprint'} if kind in {'evaluate','fit','apply','study'} else {'result_id','format','audience','disclosure'} if kind=='export' else {'result_id','reference','reveal_values'})
        if set(value)-permitted:raise EvaluationError('Fields do not apply to this job kind.')
        if 'reveal_values' in value and not isinstance(value['reveal_values'],bool):raise EvaluationError('reveal_values must be boolean.')
        if 'revision' in value and (isinstance(value['revision'],bool) or not isinstance(value['revision'],int)):raise EvaluationError('revision must be an integer.')
        if kind in {'inspect','evaluate','fit','apply','study'}:
            eid=value.get('evaluation_id');ev=own('evaluations',eid)
            if value.get('revision')!=ev['revision']:abort(409)
            if kind!='inspect' and (not ev['confirmation'] or value.get('fingerprint')!=ev['confirmation']):abort(409)
            spec=resolve_spec(state,ev['spec']);config=config_from(ev['config']);revision=ev['revision'];fingerprint=ev['confirmation']
            if kind in {'fit','apply','study'} and not isinstance(spec,ReliabilitySpec):raise EvaluationError('CG2 jobs require a CG2 specification.')
        else:
            item=own('results',value.get('result_id'));eid=item['evaluation_id'];revision=item['revision'];config=EvaluationConfig()
            if isinstance(item['result'],EvaluationResult):config=EvaluationConfig.from_dict(item['result'].private['config'])
            if kind=='export':
                choice(value.get('format','html'),{'html','pdf'},'export format');choice(value.get('audience','shareable'),{'local','shareable'},'audience')
                if 'disclosure' in value:DisclosureSpec.from_dict(value['disclosure'])
            elif not isinstance(item['result'],EvaluationResult):raise EvaluationError('Exact evidence is unavailable in a shareable import.')
            elif value.get('reference') not in item['result'].private['locators']:raise EvaluationError('Unknown evidence reference.')
        if not store.worker_lock.acquire(blocking=False):
            return jsonify({'api_version':'v1','error':{'code':'worker_busy','message':'Another supervised operation is active.','request_id':uuid.uuid4().hex,'retryable':True}}),409
        jid=uuid.uuid4().hex
        j={'id':jid,'kind':kind,'state':'pending','revision':0,'progress':{},'output':{},'error':None,'evaluation_id':eid,'evaluation_revision':revision,'cancel':threading.Event()}
        state['jobs'][jid]=j;state['requests'][request_key]=(request_digest,jid)
        def progress(p):
            with store.guard:
                j['progress']={k:p[k] for k in ('stage','workspace_bytes','completed','total') if k in p};j['revision']+=1
        def execute():
            try:
                with store.guard:j['state']='running';j['revision']+=1
                authorized=store.roots+(str(state['directory']),)
                if kind=='inspect':
                    output=inspect(spec,config,progress=progress,cancel=j['cancel'],allowed_roots=authorized)
                    output['effective_spec']=copy.deepcopy(ev['spec']);output['effective_config'].pop('scratch_directory',None)
                    with store.guard:
                        if j['cancel'].is_set():j['state']='cancelled'
                        else:ev['confirmation']=output['fingerprint'];j['output']=output;j['state']='succeeded'
                elif kind in {'evaluate','fit','apply','study'}:
                    operation={'evaluate':evaluate,'fit':fit_methods,'apply':apply_methods,'study':study}[kind]
                    result=operation(spec,config,progress=progress,cancel=j['cancel'],allowed_roots=authorized,expected_fingerprint=fingerprint)
                    with store.guard:
                        if j['cancel'].is_set() and not result.execution.get('application_committed'):j['state']='cancelled'
                        else:
                            rid=result.data['analysis_id'];state['results'][rid]={'result':result,'evaluation_id':eid,'revision':revision};j['output']={'result_id':rid}
                            method_handles=[]
                            for method in result.private.get('fitted_methods',[]):
                                handle=uuid.uuid4().hex;state['methods'][handle]={'method':method,'result_id':rid,'membership_sidecars':[v for v in result.private.get('membership_sidecars',[]) if method['artifact_digest'] in v['method_digests']]};method_handles.append(handle)
                            if method_handles:j['output']['method_handles']=method_handles
                            if result.private.get('application_export'):
                                j['output']['artifact_ids']=remember(state,rid,{'application_path':result.private['application_export']['path']},'local')
                            j['state']='succeeded'
                elif kind=='resolve_evidence':
                    packet=compat.supervise(_resolve,(item['result'],value['reference'],authorized,bool(value.get('reveal_values',False))),config,progress=progress,cancel=j['cancel'])
                    with store.guard:
                        j['output']=packet.data;j['state']='cancelled' if j['cancel'].is_set() else 'succeeded'
                        if j['state']=='cancelled':j['output']={}
                else:
                    rid=value['result_id'];directory=compat.protected_directory(state['directory']/rid/'exports'/jid)
                    path=directory/('report.pdf' if value.get('format')=='pdf' else 'report.html')
                    packet=compat.supervise(_export,(item['result'],str(path),value.get('format','html'),value.get('audience','shareable'),value.get('disclosure')),config,progress=progress,cancel=j['cancel'])
                    with store.guard:
                        ids=remember(state,rid,packet.data['artifacts'],value.get('audience','shareable'));j['output']={'artifact_ids':ids}
                        j['state']='failed' if packet.data.get('export_error') else 'succeeded';j['error']={'code':packet.data['export_error']} if packet.data.get('export_error') else None
                        if j['cancel'].is_set():j['state']='cancelled'
            except Exception as exc:
                with store.guard:
                    j['state']='cancelled' if j['cancel'].is_set() or getattr(exc,'code',None)=='cancelled' else 'failed'
                    j['error']={'code':getattr(exc,'code','operation_failed'),'stage':getattr(exc,'stage','job'),'message':'Operation stopped; inspect the declared input, ownership and resource settings.'}
            finally:
                with store.guard:j['revision']+=1
                store.worker_lock.release()
        j['thread']=threading.Thread(target=execute,daemon=True);j['thread'].start()
        return response(job_view(j),202)

    @bp.get('/jobs/<jid>')
    def job(jid):return response(job_view(own('jobs',jid)))
    @bp.post('/jobs/<jid>/cancel')
    def cancel(jid):
        j=own('jobs',jid)
        with store.guard:
            if j['state'] in {'pending','running','cancelling'}:j['cancel'].set();j['state']='cancelling';j['revision']+=1
        return response(job_view(j))

    def result_view(rid):
        item=own('results',rid);audience=request.args.get('audience','local')
        if isinstance(item['result'],SharedResult) and audience=='local':audience='shareable'
        return item['result'].to_dict(audience=audience)
    @bp.get('/results/<rid>')
    def result(rid):return response(result_view(rid))
    @bp.get('/results/<rid>/<section>')
    def section(rid,section):
        data=result_view(rid)
        if section in {'methods','assessments'}:
            if 'cg2' not in data:abort(404)
            return response(data['cg2'].get(section,[]))
        if section=='summary':
            headline=[m for m in data['measurements'] if m['scope']=='overall' and m['metric'] in {'accuracy','mae','rmse','brier','log_loss','interval_coverage'}]
            summary={'analysis_id':data['analysis_id'],'name':data['name'],'task':data['task'],'runs':data['runs'],'headlines':headline,'findings':data['findings'],'comparison':data['comparison']}
            if 'cg2' in data:summary['cg2']=data['cg2']
            return response(summary)
        if section not in {'measurements','findings','coverage'}:abort(404)
        values=data[section]
        if isinstance(values,dict):return response(values)
        for attr in ('run','metric','scope','family','id'):
            if request.args.get(attr):values=[v for v in values if v.get(attr)==request.args[attr]]
        try:limit=min(1000,max(1,int(request.args.get('limit',100))));offset=int(request.args.get('cursor','0'))
        except ValueError:raise EvaluationError('Invalid pagination.')
        if offset<0:raise EvaluationError('Invalid pagination.')
        return response({'items':values[offset:offset+limit],'total':len(values),'next_cursor':str(offset+limit) if offset+limit<len(values) else None,'result_id':rid})

    @bp.get('/results/<rid>/artifacts')
    def artifacts(rid):
        own('results',rid)
        return response([{k:a[k] for k in ('id','kind','audience','bytes')} for a in store.current()['artifacts'].values() if a['result_id']==rid])
    @bp.get('/artifacts/<aid>/content')
    def content(aid):
        a=own('artifacts',aid);compat.capture(a['path'],(str(store.current()['directory']),),expected=a['identity'])
        return send_file(a['path'],as_attachment=True,download_name=Path(a['path']).name)

    @bp.post('/results/import')
    def import_result():
        if not request.files or set(request.files)-{'result','manifest'} or 'result' not in request.files:raise EvaluationError('Import a result and optional protected manifest.')
        raw=request.files['result'].read(EvaluationConfig().private_bytes+1)
        if len(raw)>EvaluationConfig().private_bytes:abort(413)
        private=None
        if 'manifest' in request.files:
            mraw=request.files['manifest'].read(EvaluationConfig().private_bytes+1)
            if len(mraw)>EvaluationConfig().private_bytes:abort(413)
            private=strict_json(mraw)
        loaded=EvaluationResult.from_dict(strict_json(raw),private=private);rid=loaded.data['analysis_id'];state=store.current()
        if rid in state['results']:abort(409)
        state['results'][rid]={'result':loaded,'evaluation_id':None,'revision':0}
        output={'result_id':rid,'audience':'shareable' if isinstance(loaded,SharedResult) else 'local'}
        if isinstance(loaded,EvaluationResult) and loaded.private.get('fitted_methods'):
            handles=[]
            for method in loaded.private['fitted_methods']:
                mid=uuid.uuid4().hex;state['methods'][mid]={'method':method,'result_id':rid,'membership_sidecars':[v for v in loaded.private.get('membership_sidecars',[]) if method['artifact_digest'] in v['method_digests']]};handles.append(mid)
            output['method_handles']=handles
        return response(output,201)

    @bp.post('/methods/import')
    def import_methods():
        from .method_cli import collection
        from .method_contracts import MethodLimits
        limit=MethodLimits().method_bytes
        if request.files:
            if set(request.files)!={'file'}:raise EvaluationError('Import one fitted method/collection file.')
            raw=request.files['file'].read(limit+1)
        else:
            if request.content_length and request.content_length>limit:abort(413)
            raw=request.get_data()
        if len(raw)>limit:abort(413)
        methods,sidecars=collection(raw,with_membership=True);state=store.current();handles=[]
        for method in methods:
            mid=uuid.uuid4().hex;state['methods'][mid]={'method':method,'result_id':None,'membership_sidecars':[v for v in sidecars if method['artifact_digest'] in v['method_digests']]};handles.append(mid)
        return response({'method_handles':handles,'evidence_state':'fitted_only','historical_validation_not_inferred':True},201)

    @bp.get('/methods/<mid>')
    def method_metadata(mid):
        method=own('methods',mid)['method']
        return response({'handle':mid,'id':method['id'],'kind':method['definition']['kind'],'algorithm_version':method['algorithm_version'],
                         'run':method['definition']['run'],'model':method['model'],'task':method['task'],
                         'definition':method['definition'],'input_signature':method['input_signature'],
                         'artifact_digest':method['artifact_digest'],'evidence_state':'fitted_only',
                         'application_policy':'New applications are unvalidated; historical evidence never implies future improvement or coverage.'})

    @bp.get('/methods/<mid>/content')
    def method_content(mid):
        method=own('methods',mid)['method']
        r=app.response_class(json.dumps(method,sort_keys=True,indent=2,allow_nan=False),mimetype='application/json')
        r.headers['Content-Disposition']='attachment; filename="fitted-method.json"'
        return r

    from .history_web import register as register_history
    register_history(bp,app,store,workspace_path=persistent_workspace,launch_token=launch_token)
    app.register_blueprint(bp)
    static=Blueprint('confidenceguard_client',__name__,static_folder='static',static_url_path='/confidenceguard/assets')
    @static.after_request
    def client_headers(r):
        r.headers['X-Frame-Options']='DENY'
        r.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return r
    @static.get('/confidenceguard')
    def client():
        if 'launch' in request.args:
            app.extensions['confidenceguard_redeem_workspace'](request.args['launch'])
            from flask import redirect
            return redirect('/confidenceguard',code=303)
        return static.send_static_file('index.html')
    app.register_blueprint(static)
