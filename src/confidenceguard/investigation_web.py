"""Session-owned CG4 drafts and fixed jobs on the existing local transport."""
import copy
import json
from pathlib import Path
import threading
import uuid
from flask import abort,request,send_file
from .contracts import EvaluationError,EvaluationConfig,digest,strict_json,name
from .investigation_contracts import InvestigationSpec,ConfirmationSpec,FrozenHypothesisSet
from .investigation import inspect_investigation,investigate,freeze_hypotheses,CG4_RESULT_BYTES
from .confirmation import inspect_confirmation,confirm_investigation
from . import compat

KINDS={'investigation_inspect','investigation_discover','confirmation_inspect','investigation_confirm','investigation_replay'}


def register(bp,app,sessions,*,own,body,response,resolve_evaluation,config_from,job_view,public_errors):
    base_config_from=config_from
    def config_from(value):
        if not isinstance(value,dict):raise EvaluationError('Configuration must be an object.')
        return base_config_from({'result_bytes':CG4_RESULT_BYTES,**value})
    def state():
        current=sessions.current()
        for key in ('investigations','hypothesis_sets','investigation_assets'):current.setdefault(key,{})
        return current
    def item(collection,identifier):
        value=state()[collection].get(identifier)
        if value is None:abort(404)
        if value.get('workspace_instance'):
            ws=app.extensions['confidenceguard_authorize_workspace']()
            if ws.instance_id!=value['workspace_instance']:abort(404)
        return value
    def source(value):
        if not isinstance(value,dict) or set(value)!={'id','handle'}:raise EvaluationError('Representation metadata requires an opaque source handle.')
        s=state()['sources'].get(value['handle'])
        if s is None:abort(404)
        return {'id':value['id'],**{k:s[k] for k in ('path','format','encoding','delimiter')}}
    def resolve_representations(representations,ws=None):
        representations=copy.deepcopy(representations)
        if not isinstance(representations,list):raise EvaluationError('Representations require an array.')
        for rep in representations:
            if not isinstance(rep,dict):raise EvaluationError('Representation declarations must be objects.')
            if 'matrix_path' in rep or 'model_directory' in rep:raise EvaluationError('Representation paths require owned opaque handles.')
            if rep.get('kind','supplied')=='supplied':
                handle=rep.pop('matrix_handle',None);asset=item('investigation_assets',handle)
                if asset['kind']!='vectors':raise EvaluationError('A vector asset is required.')
                rep['matrix_path']=asset['path'];rep['keys_source']=source(rep.get('keys_source'))
            elif rep['kind'] in {'e5_text','dinov2_image'}:
                asset=item('investigation_assets',rep.pop('model_handle',None))
                if asset['kind']!='model':raise EvaluationError('A pinned local model handle is required.')
                rep['model_directory']=asset['path']
            elif rep['kind']=='retained':
                if ws is None:raise EvaluationError('Retained representations require workspace authorization.')
        return representations
    app.extensions['confidenceguard_resolve_discovery_representations']=resolve_representations
    def resolve(public):
        value=copy.deepcopy(public);ws=app.extensions['confidenceguard_attached_workspace']()
        if not isinstance(value,dict):raise EvaluationError('Investigation specification required.')
        if value.get('evaluation') is not None:value['evaluation']=resolve_evaluation(state(),value['evaluation']).to_dict()
        if value.get('history') is not None:
            if not isinstance(value['history'],dict) or set(value['history'])!={'selection'}:raise EvaluationError('Historical browser inputs require an authorized workspace selection.')
            ws=app.extensions['confidenceguard_authorize_workspace']();value['history']['workspace_path']=str(ws.path)
        if 'representations' in value:value['representations']=resolve_representations(value['representations'],ws)
        return InvestigationSpec.from_dict(value),ws
    def roots(ws=None):
        return sessions.roots+(str(state()['directory']),)+((str(ws.path),) if ws else ())
    def active(iid):return any(j.get('investigation_id')==iid and j['state'] in {'pending','running','cancelling'} for j in state()['jobs'].values())
    @bp.route('/workspace/evidence-use',methods=['GET','POST'])
    def evidence_tracking():
        ws=app.extensions['confidenceguard_authorize_workspace']()
        if request.method=='GET':return response(ws.evidence_tracking())
        value=body({'enabled'},{'enabled'});return response(ws.evidence_tracking(value['enabled']))

    @bp.post('/workspace/investigations/<aid>/open')
    def open_retained(aid):
        ws=app.extensions['confidenceguard_authorize_workspace']();result=ws.open(aid)
        if result.data['methodology_id']!='failure_investigation_v1':abort(404)
        state()['results'][aid]={'result':result,'evaluation_id':None,'revision':0,'workspace_instance':ws.instance_id,'retained':True}
        return response({'result_id':aid})
    @bp.post('/investigation-assets')
    def asset():
        current=state();aid=uuid.uuid4().hex
        if request.files:
            if set(request.files)!={'file'} or set(request.form)-{'kind'} or request.form.get('kind','vectors')!='vectors':raise EvaluationError('Upload one NPY vector matrix.')
            path=current['directory']/('vectors-'+aid+'.npy');request.files['file'].save(path);kind='vectors'
        else:
            value=body({'root_id','relative_path','kind'},{'root_id','relative_path','kind'});kind=value['kind']
            index=next((i for i in range(len(sessions.roots)) if value['root_id']==f'root_{i}'),None);relative=Path(value['relative_path'])
            if index is None or relative.is_absolute() or '..' in relative.parts or kind not in {'model','vectors'}:raise EvaluationError('Choose an allowed-root-relative vector or pinned model directory.')
            path=Path(sessions.roots[index])/relative
        with compat.secure_open(path/'datatrust-model.json' if kind=='model' else path,roots()):pass
        # Full native decoding/publisher verification takes place under supervision.
        current['investigation_assets'][aid]={'path':str(path),'kind':kind}
        return response({'handle':aid,'kind':kind},201)

    @bp.route('/investigations',methods=['POST','GET'])
    def drafts():
        if request.method=='GET':return response({'items':[{'id':v['id'],'revision':v['revision'],'name':v['spec'].get('name','Failure investigation')} for v in state()['investigations'].values()]})
        value=body({'spec','config'},{'spec'});_,ws=resolve(value['spec']);config_from(value.get('config',{}));iid=uuid.uuid4().hex
        record={'id':iid,'revision':1,'spec':value['spec'],'config':value.get('config',{}),'fingerprint':None,'confirmation_inspections':{}}
        if ws:record['workspace_instance']=ws.instance_id
        state()['investigations'][iid]=record
        return response({k:v for k,v in record.items() if k!='confirmation_inspections'},201)

    @bp.route('/investigations/<iid>',methods=['GET','PUT','DELETE'])
    def draft(iid):
        record=item('investigations',iid)
        if request.method=='GET':return response({k:v for k,v in record.items() if k!='confirmation_inspections'})
        if active(iid):abort(409)
        if request.method=='DELETE':state()['investigations'].pop(iid);return response({'deleted':True,'immutable_results_deleted':False})
        value=body({'spec','config','expected_revision'},{'spec','expected_revision'})
        if value['expected_revision']!=record['revision']:abort(409)
        _,ws=resolve(value['spec']);config_from(value.get('config',{}))
        record.update(spec=value['spec'],config=value.get('config',{}),revision=record['revision']+1,fingerprint=None,confirmation_inspections={})
        record['workspace_instance']=ws.instance_id if ws else None
        return response({k:v for k,v in record.items() if k!='confirmation_inspections'})

    @bp.post('/hypothesis-sets')
    def freeze():
        value=body({'result_id','candidate_ids','confirmation','practical_thresholds'},{'result_id'})
        record=own('results',value['result_id']);result=record['result']
        protocol=ConfirmationSpec.from_dict(value.get('confirmation',{}))
        kwargs={'confirmation':protocol,'practical_thresholds':value.get('practical_thresholds')}
        ws=app.extensions['confidenceguard_authorize_workspace']() if record.get('workspace_instance') else None
        frozen=ws.freeze_hypotheses(result,value.get('candidate_ids'),**kwargs) if ws and record.get('retained') else freeze_hypotheses(result,value.get('candidate_ids'),**kwargs)
        handle=uuid.uuid4().hex;state()['hypothesis_sets'][handle]={'frozen':frozen,'workspace_instance':ws.instance_id if ws else None}
        return response({'handle':handle,'family_digest':frozen.family_digest,'content_digest':frozen.data['content_digest'],'hypotheses':len(frozen.data['hypotheses'])},201)

    @bp.post('/hypothesis-sets/import')
    def import_family():
        limit=64*1024**2
        if request.files:
            if set(request.files)!={'file'}:raise EvaluationError('Import one protected hypothesis set.')
            raw=request.files['file'].read(limit+1)
        else:raw=request.get_data()
        if len(raw)>limit:abort(413)
        frozen=FrozenHypothesisSet.from_dict(strict_json(raw));handle=uuid.uuid4().hex
        state()['hypothesis_sets'][handle]={'frozen':frozen,'imported':True}
        return response({'handle':handle,'family_digest':frozen.family_digest,'confirmation_input_required':True},201)

    @bp.get('/hypothesis-sets/<handle>')
    def family(handle):
        frozen=item('hypothesis_sets',handle)['frozen']
        return response({'handle':handle,'family_digest':frozen.family_digest,'content_digest':frozen.data['content_digest'],'confirmation':frozen.data['confirmation_spec'],
                         'hypotheses':[{'id':h['id'],'candidate_id':h['candidate_id'],'objective':h['objective'],'membership_scope':h['membership_scope']} for h in frozen.data['hypotheses']]})

    @bp.get('/hypothesis-sets/<handle>/content')
    def family_content(handle):
        frozen=item('hypothesis_sets',handle)['frozen']
        out=app.response_class(json.dumps(frozen.to_dict(),sort_keys=True,indent=2),mimetype='application/json')
        out.headers['Content-Disposition']='attachment; filename="protected-hypotheses.json"';return out

    @bp.get('/results/<rid>/investigation/<section>')
    def evidence(rid,section):
        result=own('results',rid)['result'];audience=request.args.get('audience','local')
        if audience not in {'local','shareable'}:raise EvaluationError('Unknown investigation audience.')
        data=result.data if audience=='local' else result.to_dict(audience='shareable');panel=data.get('investigation')
        if panel is not None and section=='summary':
            # A display projection, not a canonical artifact. Do not copy or
            # serialize the whole candidate pool merely to show its first page.
            return response({**{k:data[k] for k in ('analysis_id','name','coverage','task','outcomes') if k in data},
                'view':'investigation_summary/1.0','investigation':{**{k:v for k,v in panel.items() if k not in {'candidates','overlap'}},
                'candidate_count':len(panel.get('candidates',[])),
                'overlap':{k:v for k,v in panel.get('overlap',{}).items() if k!='pairs'} if isinstance(panel.get('overlap'),dict) else {},
                'overlap_pair_count':len(panel.get('overlap',{}).get('pairs',[])) if isinstance(panel.get('overlap'),dict) else len(panel.get('overlap',[]))}})
        if panel is None or section not in {'candidates','overlap','assessments','strategies','history'}:abort(404)
        values=panel.get(section,[])
        if isinstance(values,dict) and section=='overlap':values=values.get('pairs',[])
        try:limit=min(100,max(1,int(request.args.get('limit',25))));offset=int(request.args.get('cursor','0'))
        except ValueError:raise EvaluationError('Invalid pagination.')
        if offset<0:raise EvaluationError('Invalid pagination.')
        for attr in ('id','strategy','state'):
            if request.args.get(attr):values=[v for v in values if v.get(attr)==request.args[attr]]
        return response({'items':values[offset:offset+limit],'total':len(values),'next_cursor':str(offset+limit) if offset+limit<len(values) else None})

    def submit(value):
        permitted={'kind','client_request_id','investigation_id','revision','fingerprint','hypothesis_handle','confirmation_fingerprint','retain','result_id','reason'}
        if set(value)-permitted or value.get('kind') not in KINDS or not isinstance(value.get('client_request_id'),str):raise EvaluationError('Invalid investigation job.')
        name(value['client_request_id'])
        if not isinstance(value.get('revision'),int) or isinstance(value['revision'],bool) or 'retain' in value and not isinstance(value['retain'],bool):raise EvaluationError('Invalid investigation revision or retention choice.')
        current=state();iid=value.get('investigation_id');record=item('investigations',iid)
        if record['revision']!=value.get('revision'):abort(409)
        kind=value['kind'];key='cg4:'+value['client_request_id'];request_digest=digest(value)
        if key in current['requests']:
            prior,jid=current['requests'][key]
            if prior!=request_digest:abort(409)
            return response(job_view(own('jobs',jid)),202)
        spec,ws=resolve(record['spec']);config=config_from(record['config']);revision=record['revision']
        if value.get('retain'):
            ws=app.extensions['confidenceguard_authorize_workspace']()
        if kind=='investigation_discover' and (not record['fingerprint'] or value.get('fingerprint')!=record['fingerprint']):abort(409)
        family=item('hypothesis_sets',value.get('hypothesis_handle')) if kind in {'confirmation_inspect','investigation_confirm'} else None
        frozen=family['frozen'] if family else None
        if family and family.get('workspace_instance'):
            ws=app.extensions['confidenceguard_authorize_workspace']()
        origin=own('results',value.get('result_id'))['result'] if kind=='investigation_replay' else None
        if kind=='investigation_replay':
            name(value.get('reason'))
            if spec.history is None:raise EvaluationError('Historical replay requires a retained selection.')
        if kind=='investigation_confirm':
            inspected=record['confirmation_inspections'].get(value.get('hypothesis_handle'))
            if not inspected or inspected!=value.get('confirmation_fingerprint'):abort(409)
        if not sessions.worker_lock.acquire(blocking=False):raise EvaluationError('Shared worker is busy.','worker_busy')
        jid=uuid.uuid4().hex;job={'id':jid,'kind':kind,'state':'pending','revision':0,'progress':{},'output':{},'error':None,
              'evaluation_id':None,'evaluation_revision':revision,'investigation_id':iid,'cancel':threading.Event()}
        if ws:job['workspace_instance']=ws.instance_id
        current['jobs'][jid]=job;current['requests'][key]=(request_digest,jid)
        authorized_roots=roots(ws);grant=current.get('workspace_grant')
        def progress(data):
            # Worker-owned scratch paths are operational secrets, not UI fields.
            data={k:v for k,v in data.items() if k not in {'owned_workspace','scratch_directory'}}
            with sessions.guard:job['progress']=data;job['revision']+=1
        def execute():
            try:
                job['state']='running'
                if ws and current.get('workspace_grant')!=grant:raise EvaluationError('Workspace was detached.','workspace_access')
                kwargs={'allowed_roots':authorized_roots,'progress':progress,'cancel':job['cancel']}
                if kind=='investigation_inspect':
                    output=inspect_investigation(spec,config,**kwargs);record['fingerprint']=output['fingerprint']
                    record['spec']['objectives']=output['effective_spec']['objectives']
                    if output['effective_spec'].get('history'):
                        record['spec']['history']['selection']=output['effective_spec']['history']['selection']
                    output['effective_spec']=copy.deepcopy(record['spec'])
                elif kind=='confirmation_inspect':
                    output=inspect_confirmation(frozen,config,confirmation_input=spec,workspace=ws,**kwargs)
                    record['confirmation_inspections'][value['hypothesis_handle']]=output['fingerprint']
                else:
                    if kind=='investigation_discover':result=investigate(spec,config,workspace=ws,expected_fingerprint=value['fingerprint'],request_id=key,**kwargs)
                    elif kind=='investigation_replay':
                        from .investigation_replay import replay_investigation
                        result=replay_investigation(origin,spec,config,workspace=ws,reason=value['reason'],**kwargs)
                    else:result=confirm_investigation(frozen,config,confirmation_input=spec,workspace=ws,expected_fingerprint=value['confirmation_fingerprint'],request_id=key,**kwargs)
                    if value.get('retain'):ws.save_assessment(result,request_id=key)
                    rid=result.data['analysis_id'];current['results'][rid]={'result':result,'evaluation_id':None,'revision':revision,'investigation_id':iid,'workspace_instance':ws.instance_id if ws else None,'retained':bool(value.get('retain'))}
                    output={'result_id':rid,'retained':bool(value.get('retain'))}
                with sessions.guard:job.update(output=output,state='succeeded',revision=job['revision']+1)
            except Exception as exc:
                code=getattr(exc,'code','investigation_failed')
                with sessions.guard:job.update(state='cancelled' if code=='cancelled' else 'failed',error={'code':code,'message':public_errors.get(code,'Investigation stopped; review the refusal code and recorded limits.')},revision=job['revision']+1)
            finally:sessions.worker_lock.release()
        job['thread']=threading.Thread(target=execute,daemon=True);job['thread'].start()
        return response(job_view(job),202)
    app.extensions['confidenceguard_investigation_submit']=submit
