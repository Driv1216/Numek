"""Owned CG6 drafts and fixed jobs within the existing loopback API."""
import copy
import hashlib
import json
import shutil
from pathlib import Path
import threading
import uuid

from flask import abort,request
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename

from .. import compat
from ..contracts import EvaluationError,digest,strict_json,name
from .contracts import ExecutionSpec,PredictorSpec,ArtifactFile,shape,bounded,ExecutionLimits
from .services import service
from .devices import capabilities
from ..auxiliary.contracts import AuxiliaryStudySpec,AuxiliaryArtifact
from ..robustness.contracts import RobustnessSpec,FrozenRobustnessProtocol,RobustnessAssessmentSpec,PolicyStressSpec
from ..robustness.services import freeze_robustness

KINDS={'cg6_inspect','cg6_register','cg6_qualify','cg6_execute','cg6_auxiliary_fit','cg6_auxiliary_apply','cg6_auxiliary_assess','cg6_robustness','cg6_assess','cg6_policy_stress','cg6_restate'}


def register(bp,app,sessions,*,own,body,response,config_from,job_view):
    def state():
        s=sessions.current()
        for collection in ('execution_files','predictors','execution_drafts','auxiliaries','robustness_protocols'):s.setdefault(collection,{})
        return s
    def item(collection,key):state();return own(collection,key)
    def root_paths(ws=None):return sessions.roots+(str(state()['directory']),)+((str(ws.path),) if ws else ())
    def resolve_predictor(public):
        if set(public)=={'handle'}:return copy.deepcopy(item('predictors',public['handle'])['spec'])
        p=copy.deepcopy(public);files=[]
        for f in p.get('files',[]):
            if set(f)-{'name','handle','sha256'} or not {'name','handle'}<=set(f):raise EvaluationError('Model files require opaque handles.')
            info=item('execution_files',f['handle'])['identity']
            if f.get('sha256',info['sha256'])!=info['sha256']:raise EvaluationError('Model file digest differs.','model_changed')
            files.append({'name':f['name'],'path':info['path'],'sha256':info['sha256']})
        p['files']=files
        for key in ('tensor_file','keys_source'):
            if key in p.get('preprocessing',{}):p['preprocessing'][key]=item('execution_files',p['preprocessing'][key])['identity']['path']
        return PredictorSpec.from_dict(p).to_dict()
    def execution(public):
        value=copy.deepcopy(public)
        if value.get('auxiliaries') or value.get('fitted_methods'):raise EvaluationError('Use owned auxiliary and fitted-method handles in browser execution.')
        value['auxiliaries']=[item('auxiliaries',h)['artifact'] for h in value.pop('auxiliary_handles',[])]
        methods=[own('methods',h) for h in value.pop('method_handles',[])]
        value['fitted_methods']=[m['method'] for m in methods]
        value['membership_sidecars']=[v for m in methods for v in m.get('membership_sidecars',[])]
        for s in value.get('sources',[]):
            if set(s)!={'id','handle'}:raise EvaluationError('Execution sources require id and handle.')
            source=own('sources',s['handle']);sid=s['id'];s.clear();s.update(id=sid,path=source['path'],format=source['format'],encoding=source['encoding'],delimiter=source['delimiter'])
        value['predictors']=[resolve_predictor(p) for p in value.get('predictors',[])]
        return ExecutionSpec.from_dict(value)
    def resolve(kind,public):
        value=copy.deepcopy(public);opts={}
        if kind=='restatement':
            from .restatement import ExecutionRestatementSpec
            shape(value,{'result_id','spec'},{'result_id','spec'})
            parent=own('results',value['result_id'])['result']
            for source in value['spec'].get('sources',[]):
                shape(source,{'id','handle'},{'id','handle'});owned=own('sources',source['handle']);sid=source['id']
                source.clear();source.update(id=sid,**{k:owned[k] for k in ('path','format','encoding','delimiter')})
            declaration=ExecutionRestatementSpec.from_dict(value['spec'])
            return ExecutionSpec.from_dict(parent.private['execution_spec']),{'parent':parent,'restatement':declaration}
        if kind=='execution':
            if 'execution' in value:
                shape(value,{'execution','qualification'},{'execution','qualification'})
                shape(value['qualification'],{'reference','atol','rtol'})
                opts=bounded(value['qualification']);return execution(value['execution']),opts
            return execution(value),opts
        if kind=='auxiliary':
            value['execution']=execution(value['execution']).to_dict()
            artifact_handle=value.pop('artifact_handle',None)
            if artifact_handle:
                opts['artifact']=item('auxiliaries',artifact_handle)['artifact'];opts['role']=value.pop('role','E')
                return ExecutionSpec.from_dict(value['execution']),opts
            study=AuxiliaryStudySpec.from_dict(value);opts['study']=study.to_dict()
            fields={f.id:f for f in (*study.execution.context_fields,*study.inputs)}
            from dataclasses import replace
            return replace(study.execution,context_fields=tuple(fields.values())),opts
        if kind=='robustness':
            value['execution']=execution(value['execution']).to_dict();study=RobustnessSpec.from_dict(value)
            return study.execution,{'robustness':study.to_dict()}
        if kind=='assessment':
            protocol=item('robustness_protocols',value['protocol_handle'])['protocol']
            assessment=RobustnessAssessmentSpec(protocol,execution(value['execution']))
            from dataclasses import replace
            study=replace(protocol.study,execution=assessment.execution,role='E')
            return assessment.execution,{'robustness':study.to_dict(),'protocol':protocol.to_dict()}
        if kind=='policy_stress':
            robust=copy.deepcopy(value['robustness']);robust['execution']=execution(robust['execution']).to_dict()
            if 'confidenceguard_resolve_policy_input' not in app.extensions:raise EvaluationError('Policy resolver is unavailable.')
            application,_=app.extensions['confidenceguard_resolve_policy_input'](value['application'])
            stress=PolicyStressSpec(RobustnessSpec.from_dict(robust),application.to_dict(),value.get('batch_field'))
            return stress.robustness.execution,{'robustness':stress.robustness.to_dict(),'policy_stress':stress.to_dict()}
        raise EvaluationError('Unknown CG6 workflow.')

    @bp.get('/execution/capabilities',endpoint='cg6_capabilities')
    def capability():return response(capabilities())

    @bp.post('/execution/files',endpoint='cg6_files')
    def files():
        s=state();handle=uuid.uuid4().hex
        if len(s['execution_files'])>=ExecutionLimits().max_artifact_files:raise EvaluationError('Session artifact count exceeds admission.','model_limit')
        previous_bytes=sum(f['identity']['bytes'] for f in s['execution_files'].values())
        if 'file' in request.files:
            uploaded=request.files['file'];filename=secure_filename(uploaded.filename or 'artifact')
            directory=compat.protected_directory(s['directory']/'model-files'/handle);path=directory/filename
            size=0;h=hashlib.sha256()
            try:
                with path.open('xb') as out:
                    while chunk:=uploaded.stream.read(1024**2):
                        size+=len(chunk)
                        if size>(app.config.get('MAX_CONTENT_LENGTH') or 100*1024**2) or previous_bytes+size>8*1024**3:abort(413)
                        out.write(chunk);h.update(chunk)
                path.chmod(0o600)
            except BaseException:shutil.rmtree(directory,ignore_errors=True);raise
        else:
            value=body({'root_id','relative_path'},{'root_id','relative_path'})
            if value['root_id'] not in {f'root_{i}' for i in range(len(sessions.roots))}:abort(404)
            relative=Path(value['relative_path'])
            if relative.is_absolute() or '..' in relative.parts:raise EvaluationError('Root-relative model file required.')
            path=Path(sessions.roots[int(value['root_id'].split('_')[1])])/relative;filename=path.name
        identity,_,_=compat.capture(path,root_paths(),max_bytes=2*1024**3)
        if previous_bytes+identity['bytes']>8*1024**3:
            if 'file' in request.files:shutil.rmtree(directory,ignore_errors=True)
            raise EvaluationError('Session artifact bytes exceed admission.','model_limit')
        s['execution_files'][handle]={'identity':identity,'filename':filename}
        return response({'handle':handle,'name':filename,'sha256':identity['sha256'],'bytes':identity['bytes']},201)

    @bp.route('/execution/drafts',methods=['POST','GET'],endpoint='cg6_drafts')
    def drafts():
        if request.method=='GET':
            ws=app.extensions['confidenceguard_attached_workspace']()
            return response([r for r in state()['execution_drafts'].values() if r.get('workspace_instance') is None or ws and r['workspace_instance']==ws.instance_id])
        value=body({'workflow','spec','config'},{'workflow','spec'});resolve(value['workflow'],value['spec']);config_from(value.get('config',{}))
        key=uuid.uuid4().hex;record={'id':key,'workflow':value['workflow'],'spec':value['spec'],'config':value.get('config',{}),'revision':1,'fingerprint':None}
        ws=app.extensions['confidenceguard_attached_workspace']()
        if ws:record['workspace_instance']=ws.instance_id
        state()['execution_drafts'][key]=record;return response(record,201)

    @bp.route('/execution/drafts/<key>',methods=['GET','PUT','DELETE'],endpoint='cg6_draft')
    def draft(key):
        r=item('execution_drafts',key)
        if request.method=='GET':return response(r)
        if any(j.get('execution_draft_id')==key and j['state'] in {'pending','running','cancelling'} for j in state()['jobs'].values()):abort(409)
        if request.method=='DELETE':state()['execution_drafts'].pop(key);return response({'deleted':True,'immutable_results_deleted':False})
        value=body({'spec','config','expected_revision'},{'spec','expected_revision'})
        if type(value['expected_revision']) is not int or value['expected_revision']!=r['revision']:abort(409)
        resolve(r['workflow'],value['spec']);config_from(value.get('config',{}));r.update(spec=value['spec'],config=value.get('config',{}),revision=r['revision']+1,fingerprint=None)
        return response(r)

    @bp.post('/execution/protocols',endpoint='cg6_freeze')
    def freeze():
        value=body({'result_id','claims','confidence','sampling','max_cluster_size','upstream_independence','external_exposure','batch_field'},{'result_id','claims'})
        record=own('results',value.pop('result_id'))
        ws=app.extensions['confidenceguard_authorize_workspace']() if record.get('retained') else None
        protocol=ws.freeze_robustness(record['result'],**value) if ws else freeze_robustness(record['result'],**value)
        handle=uuid.uuid4().hex;state()['robustness_protocols'][handle]={'protocol':protocol,'workspace_instance':record.get('workspace_instance')}
        return response({'handle':handle,'content_digest':protocol.content_digest,'claims':len(protocol.claims)},201)

    @bp.get('/execution/protocols/<handle>/content',endpoint='cg6_protocol_content')
    def protocol_content(handle):
        r=app.response_class(json.dumps(item('robustness_protocols',handle)['protocol'].to_dict(),indent=2),mimetype='application/json')
        r.headers['Content-Disposition']='attachment; filename="protected-robustness-protocol.json"';return r

    @bp.post('/execution/protocols/import',endpoint='cg6_import_protocol')
    def import_protocol():
        value=body({'protocol'},{'protocol'});protocol=FrozenRobustnessProtocol.from_dict(value['protocol'])
        # A protocol is data-only; its original local file paths cannot grant
        # source or executable access. Assessment supplies new owned handles.
        handle=uuid.uuid4().hex;state()['robustness_protocols'][handle]={'protocol':protocol}
        return response({'handle':handle,'content_digest':protocol.content_digest},201)

    @bp.post('/workspace/execution/protocols/<content_digest>/open',endpoint='cg6_open_protocol')
    def open_protocol(content_digest):
        ws=app.extensions['confidenceguard_authorize_workspace']();protocol=ws.open_robustness_protocol(content_digest)
        handle=uuid.uuid4().hex;state()['robustness_protocols'][handle]={'protocol':protocol,'workspace_instance':ws.instance_id}
        return response({'handle':handle,'content_digest':protocol.content_digest},201)

    @bp.get('/execution/auxiliaries/<handle>/content',endpoint='cg6_auxiliary_content')
    def auxiliary_content(handle):
        artifact=copy.deepcopy(item('auxiliaries',handle)['artifact'])
        for p in artifact['predictors']:
            for f in p['files']:f['path']='REQUIRES_LOCAL_MODEL_BINDING'
        r=app.response_class(json.dumps(artifact,indent=2),mimetype='application/json')
        r.headers['Content-Disposition']='attachment; filename="protected-auxiliary-descriptor.json"';return r

    @bp.post('/execution/auxiliaries/import',endpoint='cg6_auxiliary_import')
    def auxiliary_import():
        value=body({'artifact','files'},{'artifact','files'});artifact=AuxiliaryArtifact.from_dict(value['artifact']).to_dict()
        shape(value['files'],{p['id'] for p in artifact['predictors']})
        for p in artifact['predictors']:
            shape(value['files'].get(p['id'],{}),{f['name'] for f in p['files']},{f['name'] for f in p['files']})
            for f in p['files']:
                handle=value['files'].get(p['id'],{}).get(f['name']);info=item('execution_files',handle)['identity']
                if info['sha256']!=f['sha256']:raise EvaluationError('Auxiliary model bytes differ.','model_changed')
                f['path']=info['path']
        artifact=AuxiliaryArtifact.from_dict(artifact).to_dict();handle=uuid.uuid4().hex
        state()['auxiliaries'][handle]={'artifact':artifact}
        return response({'handle':handle,'artifact_digest':artifact['artifact_digest']},201)

    @bp.post('/results/<rid>/execution/bridge',endpoint='cg6_bridge')
    def bridge(rid):
        from .bridge import as_reliability_spec
        value=body({'scope','predictors'},());record=own('results',rid);result=record['result']
        if not hasattr(result,'private') or not result.private.get('view_specs'):raise EvaluationError('Protected completed predictions required.')
        root=compat.protected_directory(state()['directory']/('bridge-'+uuid.uuid4().hex))
        spec=as_reliability_spec(result,scope=value.get('scope','original'),predictors=value.get('predictors'),directory=root).to_dict()
        public=spec['evaluation']
        for source in public['sources']:
            sid=source['id']
            handle=uuid.uuid4().hex;state()['sources'][handle]={**source,'workspace_instance':record.get('workspace_instance')}
            source.clear();source.update(id=sid,handle=handle)
        return response({'spec':spec,'completed_evidence_only':True},201)

    @bp.get('/results/<rid>/execution/<section>',endpoint='cg6_result_section')
    def section(rid,section):
        result=own('results',rid)['result'];audience=request.args.get('audience','local');data=result.to_dict(audience=audience)
        if 'cg6' not in data:abort(404)
        if section=='summary':return response({'analysis_id':rid,'name':data['name'],'task':data['task'],'coverage':data['coverage'],'cg6':data['cg6']})
        values=data['measurements'] if section=='measurements' else data['cg6'].get(section)
        try:offset=int(request.args.get('cursor','0'));limit=int(request.args.get('limit','50'))
        except ValueError:raise EvaluationError('Invalid pagination.')
        if offset<0 or not 1<=limit<=1000:raise EvaluationError('Pagination exceeds admission.')
        if section=='outputs' and audience=='local':
            from itertools import islice
            from .artifact_bytes import verify_artifact
            info=copy.deepcopy(result.private.get('output_artifact'))
            if info:
                info['path']=result.retained_path(info['path']);verify_artifact(info,root_paths(app.extensions['confidenceguard_attached_workspace']()))
                with compat.secure_open(info['path'],root_paths(app.extensions['confidenceguard_attached_workspace']())) as (stream,_):
                    page=[result.resolve_retained_assets(strict_json(line)) for line in islice(stream,offset,offset+limit)]
                total=info['records']
                return response({'result_id':rid,'items':page,'total':total,'next_cursor':str(offset+limit) if offset+limit<total else None})
            values=[]
        elif section=='outputs':values=[]
        if not isinstance(values,list):abort(404)
        return response({'result_id':rid,'items':values[offset:offset+limit],'total':len(values),'next_cursor':str(offset+limit) if offset+limit<len(values) else None})

    @bp.post('/workspace/execution/<aid>/open',endpoint='cg6_open_retained')
    def open_retained(aid):
        ws=app.extensions['confidenceguard_authorize_workspace']();result=ws.open(aid)
        if result.data.get('methodology_id')!='predictor_robustness_v1':abort(404)
        state()['results'][aid]={'result':result,'evaluation_id':None,'revision':1,'workspace_instance':ws.instance_id,'retained':True}
        return response({'result_id':aid,**handles(result,ws)})

    def handles(result,ws,session=None):
        session=session if session is not None else state()
        predictors=[];auxiliaries=[];catalog=[]
        for pid,p in result.private.get('predictors',{}).items():
            if ws:
                from .storage import retained_predictor
                p=retained_predictor(ws,result.data['analysis_id'],pid).to_dict()
            h=uuid.uuid4().hex;session['predictors'][h]={'spec':p,'workspace_instance':ws.instance_id if ws else None};predictors.append(h)
            catalog.append({'handle':h,'id':p['id'],'adapter':p['adapter'],'task':p['task']['kind']})
        for artifact in result.private.get('auxiliary_artifacts',[]):
            artifact=copy.deepcopy(artifact)
            for p in artifact['predictors']:
                for f in p['files']:f['path']=result.retained_path(f['path'])
            h=uuid.uuid4().hex;session['auxiliaries'][h]={'artifact':artifact,'workspace_instance':ws.instance_id if ws else None};auxiliaries.append(h)
        return {'predictor_handles':predictors,'predictors':catalog,'auxiliary_handles':auxiliaries}

    def submit(value):
        allowed={'kind','client_request_id','draft_id','revision','fingerprint','retain'}
        if set(value)-allowed or value.get('kind') not in KINDS:raise EvaluationError('Invalid CG6 job.')
        if 'retain' in value and type(value['retain']) is not bool:raise EvaluationError('Retention requires an explicit Boolean.')
        name(value.get('client_request_id'));s=state();request_key='cg6:'+value['client_request_id'];request_digest=digest(value)
        if request_key in s['requests']:
            prior,jid=s['requests'][request_key]
            if prior!=request_digest:abort(409)
            return response(job_view(own('jobs',jid)),202)
        record=item('execution_drafts',value.get('draft_id'))
        if type(value.get('revision')) is not int or record['revision']!=value['revision']:abort(409)
        if value['kind']!='cg6_inspect' and (not record['fingerprint'] or value.get('fingerprint')!=record['fingerprint']):abort(409)
        spec,options=resolve(record['workflow'],record['spec']);config=config_from(record['config'])
        operations={'cg6_inspect':'inspect','cg6_register':'register','cg6_execute':'execute','cg6_qualify':'qualify','cg6_auxiliary_fit':'auxiliary_fit',
                    'cg6_auxiliary_apply':'auxiliary_apply','cg6_auxiliary_assess':'auxiliary_assess','cg6_robustness':'robustness','cg6_assess':'robustness_assess','cg6_policy_stress':'policy_stress','cg6_restate':'restatement'}
        valid={'execution':{'inspect','register','execute','qualify'},'auxiliary':{'inspect','auxiliary_fit','auxiliary_apply','auxiliary_assess'},'robustness':{'inspect','robustness'},'assessment':{'inspect','robustness_assess'},'policy_stress':{'inspect','policy_stress'}}
        valid['restatement']={'inspect','restatement'}
        operation=operations[value['kind']]
        if operation not in valid[record['workflow']]:raise EvaluationError('Job kind differs from draft workflow.')
        ws=app.extensions['confidenceguard_attached_workspace']()
        if value.get('retain'):ws=app.extensions['confidenceguard_authorize_workspace']()
        authorized_roots=root_paths(ws)
        if not sessions.worker_lock.acquire(blocking=False):raise EvaluationError('Another supervised operation is active.','worker_busy')
        jid=uuid.uuid4().hex;j={'id':jid,'kind':value['kind'],'state':'pending','revision':0,'progress':{},'output':{},'error':None,
            'evaluation_id':None,'evaluation_revision':record['revision'],'execution_draft_id':record['id'],'cancel':threading.Event(),'workspace_instance':ws.instance_id if ws else None}
        s['jobs'][jid]=j;s['requests'][request_key]=(request_digest,jid);grant=s.get('workspace_grant')
        def progress(p):
            with sessions.guard:j['progress']={k:v for k,v in p.items() if k in {'stage','completed','total','workspace_bytes'}};j['revision']+=1
        def execute():
            try:
                j['state']='running'
                if ws and s.get('workspace_grant')!=grant:raise EvaluationError('Workspace detached.','workspace_access')
                if record['workflow']=='restatement':
                    from .restatement import inspect_restatement,restate_execution
                    result=inspect_restatement(options['parent'],options['restatement'],allowed_roots=authorized_roots) if operation=='inspect' else restate_execution(options['parent'],options['restatement'],config,
                        allowed_roots=authorized_roots,expected_fingerprint=value.get('fingerprint'),progress=progress,cancel=j['cancel'],workspace=ws if value.get('retain') else None,tracking_workspace=ws,request_id=request_key,_artifact_root=s['directory'])
                else:
                    result=service(spec,config,operation=operation,options=options,allowed_roots=authorized_roots,expected_fingerprint=value.get('fingerprint') if operation!='inspect' else None,
                        progress=progress,cancel=j['cancel'],workspace=ws if value.get('retain') else None,tracking_workspace=ws,request_id=request_key,_artifact_root=s['directory'])
                if ws and s.get('workspace_grant')!=grant:raise EvaluationError('Workspace detached.','workspace_access')
                if operation=='inspect':
                    record['fingerprint']=result['fingerprint'];result['effective_spec']=copy.deepcopy(record['spec']);j['output']=result
                else:
                    rid=result.data['analysis_id'];s['results'][rid]={'result':result,'evaluation_id':None,'revision':record['revision'],'workspace_instance':ws.instance_id if ws else None,'retained':bool(value.get('retain'))}
                    j['output']={'result_id':rid,**handles(result,ws if value.get('retain') else None,s)}
                # service() has crossed its atomic publication boundary. A late
                # cancellation must not relabel a committed result as cancelled.
                j['state']='succeeded'
            except Exception as exc:j['state']='cancelled' if j['cancel'].is_set() else 'failed';j['error']={'code':getattr(exc,'code','cg6_operation_failed'),'message':'Operation stopped; review the recorded inputs, runtime and limits.'}
            finally:
                j['revision']+=1;sessions.worker_lock.release()
        thread=threading.Thread(target=execute,daemon=True);j['thread']=thread;thread.start()
        return response(job_view(j),202)
    app.extensions['confidenceguard_execution_submit']=submit
