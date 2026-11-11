"""Owned CG5 drafts and fixed jobs on the existing local JSON transport."""
import copy
import json
import threading
import uuid
from flask import abort,request
from werkzeug.exceptions import HTTPException

from .contracts import EvaluationError,digest,strict_json,name
from .policy_contracts import PolicyStudySpec,PolicyApplicationSpec,FrozenPolicy,FrozenPolicyFamily
from .policies import inspect_policy_study,optimize_policies,replay_policy,export_frozen_policy
from .policy_assessment import preview_policy_assessment,freeze_policy_family,inspect_policy_assessment,assess_policies
from .policy_history import analyze_policy_history

KINDS={'policy_inspect','policy_optimize','policy_replay','policy_preview','policy_assessment_inspect','policy_assess','policy_history','policy_restate','policy_inspect_look','policy_assess_look'}


def register(bp,app,sessions,*,own,body,response,resolve_evaluation,config_from,job_view):
    def state():
        current=sessions.current()
        for collection in ('policy_studies','policies','policy_families'): current.setdefault(collection,{})
        return current
    def item(collection,key):
        state(); return own(collection,key)
    def resolve(public):
        value=copy.deepcopy(public)
        if type(value) is not dict or type(value.get('input')) is not dict: raise EvaluationError('Policy input specification required.')
        inp=value['input']; ws=app.extensions['confidenceguard_attached_workspace']()
        handles=inp.pop('method_handles',[])
        if not isinstance(handles,list):raise EvaluationError('Method handles require an array.')
        if handles:
            if not isinstance(handles,list) or inp.get('fitted_methods'):raise EvaluationError('Choose owned frozen method handles or complete protected artifacts.')
            inp['fitted_methods']=[copy.deepcopy(own('methods',handle)['method']) for handle in handles]
            inp['membership_sidecars']=list({v['content_digest']:copy.deepcopy(v) for handle in handles for v in own('methods',handle).get('membership_sidecars',[])}.values())
        if inp.get('evaluation') is not None: inp['evaluation']=resolve_evaluation(state(),inp['evaluation']).to_dict()
        if inp.get('history') is not None:
            if type(inp['history']) is not dict or set(inp['history'])!={'selection'}: raise EvaluationError('History requires an authorized workspace selection.')
            ws=app.extensions['confidenceguard_authorize_workspace'](); inp['history']['workspace_path']=str(ws.path)
        if inp.get('region_representations'):
            inp['region_representations']=app.extensions['confidenceguard_resolve_discovery_representations'](inp['region_representations'],ws)
        for handle in value.pop('region_family_handles',[]):
            state().setdefault('hypothesis_sets',{})
            family=item('hypothesis_sets',handle)['frozen']; packet=family.to_dict()
            features={v['id']:v for v in inp.get('features',[])}
            for feature in packet['investigation_spec']['features']:
                if feature['id'] in features and features[feature['id']]!=feature: raise EvaluationError('Region and policy feature semantics differ.')
                features[feature['id']]=feature
            inp['features']=list(features.values())
            for artifact in packet['artifacts'].values():
                hypothesis=next(h for h in packet['hypotheses'] if h['membership_artifact']==artifact['artifact_digest'])
                inp.setdefault('regions',[]).append({'artifact':artifact,'models':packet['models'],
                    'feature_contracts':hypothesis['feature_contracts'],'representation_contract':hypothesis['representation_contract'],
                    'provenance':{'feature_time_policy':'declared_information_cutoff_v2','development_events':packet['D_S_events'],
                                  'development_units':packet['D_S_units'],'independence':'declared_independent','origin_analysis_digest':packet['origin_analysis_digest']}})
        if type(value.get('policy')) is dict and set(value['policy'])=={'handle'}:
            value['policy']=item('policies',value['policy']['handle'])['frozen'].data['policy']
        cls=PolicyApplicationSpec if value.get('schema_version')=='confidenceguard.policy_application_spec/1.0' else PolicyStudySpec
        return cls.from_dict(value),ws
    app.extensions['confidenceguard_resolve_policy_input']=resolve
    def roots(ws): return sessions.roots+(str(state()['directory']),)+((str(ws.path),) if ws else ())
    def active(key): return any(j.get('policy_study_id')==key and j['state'] in {'pending','running','cancelling'} for j in state()['jobs'].values())

    @bp.route('/policy-studies',methods=['POST','GET'],endpoint='cg5_drafts')
    def drafts():
        if request.method=='GET':
            visible=[]
            for key in state()['policy_studies']:
                try: d=item('policy_studies',key)
                except (EvaluationError,HTTPException): continue
                visible.append({k:v for k,v in d.items() if k not in {'assessment_inspections'}})
            return response(visible)
        value=body({'spec','config'},{'spec'}); _,ws=resolve(value['spec']); config_from(value.get('config',{}))
        key=uuid.uuid4().hex; record={'id':key,'revision':1,'spec':value['spec'],'config':value.get('config',{}),
                                   'fingerprint':None,'assessment_inspections':{},'workspace_instance':ws.instance_id if ws else None}
        state()['policy_studies'][key]=record
        return response({k:v for k,v in record.items() if k!='assessment_inspections'},201)

    @bp.route('/policy-studies/<key>',methods=['GET','PUT','DELETE'],endpoint='cg5_draft')
    def draft(key):
        record=item('policy_studies',key)
        if request.method=='GET': return response({k:v for k,v in record.items() if k!='assessment_inspections'})
        if active(key): abort(409)
        if request.method=='DELETE': state()['policy_studies'].pop(key); return response({'deleted':True,'immutable_results_deleted':False})
        value=body({'spec','config','expected_revision'},{'spec','expected_revision'})
        if value['expected_revision']!=record['revision']: abort(409)
        _,ws=resolve(value['spec']); config_from(value.get('config',{}))
        record.update(spec=value['spec'],config=value.get('config',{}),revision=record['revision']+1,fingerprint=None,assessment_inspections={},workspace_instance=ws.instance_id if ws else None)
        return response({k:v for k,v in record.items() if k!='assessment_inspections'})

    @bp.post('/policies/import',endpoint='cg5_import_policy')
    def import_policy():
        raw=request.files['file'].read(64*1024**2+1) if 'file' in request.files else request.get_data()
        if len(raw)>64*1024**2: abort(413)
        frozen=FrozenPolicy.from_dict(strict_json(raw)); handle=uuid.uuid4().hex
        state()['policies'][handle]={'frozen':frozen}
        return response({'handle':handle,'policy_digest':frozen.data['policy_digest'],'state':'applied_unvalidated'},201)

    @bp.post('/results/<rid>/policies/<policy_digest>/export',endpoint='cg5_export_policy')
    def export_policy(rid,policy_digest):
        record=own('results',rid); frozen=export_frozen_policy(record['result'],policy_digest); handle=uuid.uuid4().hex
        state()['policies'][handle]={'frozen':frozen,'workspace_instance':record.get('workspace_instance')}
        return response({'handle':handle,'policy_digest':policy_digest,'protected':True},201)

    @bp.get('/policies/<handle>',endpoint='cg5_policy_metadata')
    def policy_metadata(handle):
        frozen=item('policies',handle)['frozen']
        return response({'handle':handle,'policy_digest':frozen.data['policy_digest'],'task':frozen.data['policy']['task']['kind'],'protected':True})

    @bp.get('/policies/<handle>/content',endpoint='cg5_policy_content')
    def policy_content(handle):
        out=app.response_class(json.dumps(item('policies',handle)['frozen'].to_dict(),sort_keys=True,indent=2),mimetype='application/json')
        out.headers['Content-Disposition']='attachment; filename="protected-policy.json"'; return out

    @bp.post('/policy-families',endpoint='cg5_freeze')
    def freeze():
        value=body({'result_id','policy_digests','assessment','assessment_preview'},{'result_id'}); record=own('results',value['result_id'])
        result=record['result']; ws=app.extensions['confidenceguard_authorize_workspace']() if record.get('workspace_instance') else None
        options={'assessment':value.get('assessment'),'assessment_preview':value.get('assessment_preview')}
        frozen=ws.freeze_policy_family(result,value.get('policy_digests'),**options) if ws and record.get('retained') else freeze_policy_family(result,value.get('policy_digests'),**options)
        handle=uuid.uuid4().hex; state()['policy_families'][handle]={'frozen':frozen,'workspace_instance':ws.instance_id if ws else None}
        return response({'handle':handle,'assessment_family_digest':frozen.family_digest,'content_digest':frozen.data['content_digest']},201)

    @bp.post('/policy-families/import',endpoint='cg5_import_family')
    def import_family():
        raw=request.files['file'].read(64*1024**2+1) if 'file' in request.files else request.get_data()
        if len(raw)>64*1024**2: abort(413)
        frozen=FrozenPolicyFamily.from_dict(strict_json(raw)); handle=uuid.uuid4().hex; state()['policy_families'][handle]={'frozen':frozen,'imported':True}
        return response({'handle':handle,'assessment_family_digest':frozen.family_digest},201)

    @bp.get('/policy-families/<handle>',endpoint='cg5_family_metadata')
    def family_metadata(handle):
        frozen=item('policy_families',handle)['frozen']
        return response({'handle':handle,'assessment_family_digest':frozen.family_digest,'claims':frozen.data['protocol']['claims']})

    @bp.get('/policy-families/<handle>/content',endpoint='cg5_family_content')
    def family_content(handle):
        out=app.response_class(json.dumps(item('policy_families',handle)['frozen'].to_dict(),sort_keys=True,indent=2),mimetype='application/json')
        out.headers['Content-Disposition']='attachment; filename="protected-policy-family.json"'; return out

    @bp.get('/results/<rid>/policy/<section>',endpoint='cg5_evidence')
    def evidence(rid,section):
        result=own('results',rid)['result']; audience=request.args.get('audience','local')
        if audience not in {'local','shareable'}: raise EvaluationError('Unknown policy audience.')
        data=result.to_dict(audience=audience); panel=data.get('policy')
        if panel is None: abort(404)
        if section=='claim-planning':
            if audience!='local': return response({'required_constraints':[],'withheld':True})
            return response({'required_constraints':result.private['study']['constraints'],'objectives':result.private['study']['objectives'],
                             'selected_development_record':panel.get('selection_record_digest'),'assessment_values_accessed':False})
        if section=='summary':
            return response({'view':'policy_summary/1.0','analysis_id':data['analysis_id'],'task':data['task'],'name':data['name'],
                             'policy':{k:v for k,v in panel.items() if k not in {'candidates','timeline','comparisons'}},
                             'candidate_count':len(panel.get('candidates',[])),'coverage':data['coverage']})
        field={'candidates':'candidates','constraints':'candidates','assessments':'assessments','timeline':'timeline','comparisons':'comparisons',
               'constraint-ledger':'constraint_ledger','worst-windows':'worst_window_evidence'}.get(section)
        if section in {'trade-offs','tradeoffs'}: field='candidates'
        if field is None: abort(404)
        values=panel.get(field,[])
        if section in {'trade-offs','tradeoffs'}: values=[row for row in values if row['policy_digest'] in panel.get('frontier',{}).get('policies',[])]
        if section=='constraints': values=[{'policy_digest':v['policy_digest'],'constraints':v['constraints']} for v in values]
        try: offset=int(request.args.get('cursor','0')); limit=int(request.args.get('limit','50'))
        except ValueError: raise EvaluationError('Invalid pagination.')
        if offset<0 or not 1<=limit<=1000: raise EvaluationError('Pagination exceeds admission.')
        return response({'result_id':rid,'items':values[offset:offset+limit],'total':len(values),'next_cursor':str(offset+limit) if offset+limit<len(values) else None})

    @bp.post('/workspace/policies/<aid>/open',endpoint='cg5_open_retained')
    def open_retained(aid):
        ws=app.extensions['confidenceguard_authorize_workspace'](); result=ws.open(aid)
        if result.data.get('methodology_id')!='policy_selection_v1': abort(404)
        state()['results'][aid]={'result':result,'evaluation_id':None,'revision':1,'workspace_instance':ws.instance_id,'retained':True}
        return response({'result_id':aid})

    def submit(value):
        allowed={'kind','client_request_id','policy_study_id','revision','fingerprint','family_handle','assessment_fingerprint','result_id','assessment','planned_e_size','requested_half_width','retain','look_id','as_of','reason'}
        if set(value)-allowed or value.get('kind') not in KINDS: raise EvaluationError('Invalid policy job.')
        name(value.get('client_request_id'))
        current=state(); kind=value['kind']; request_key='cg5:'+value['client_request_id']; request_digest=digest(value)
        if request_key in current['requests']:
            previous,jid=current['requests'][request_key]
            if previous!=request_digest: abort(409)
            return response(job_view(own('jobs',jid)),202)
        revisits={'policy_restate','policy_inspect_look','policy_assess_look'}
        record=item('policy_studies',value.get('policy_study_id')) if kind not in revisits|{'policy_preview'} else None
        if record and (type(value.get('revision')) is not int or record['revision']!=value['revision']): abort(409)
        if 'retain' in value and type(value['retain']) is not bool: raise EvaluationError('Retention choice must be Boolean.')
        spec,ws=resolve(record['spec']) if record else (None,None)
        config=config_from(record['config'] if record else {})
        if value.get('retain'): ws=app.extensions['confidenceguard_authorize_workspace']()
        family=item('policy_families',value.get('family_handle')) if kind in {'policy_assessment_inspect','policy_assess'} else None
        if family and family.get('workspace_instance'): ws=app.extensions['confidenceguard_authorize_workspace']()
        if kind=='policy_optimize' and (not record['fingerprint'] or value.get('fingerprint')!=record['fingerprint']): abort(409)
        if kind=='policy_assess' and record['assessment_inspections'].get(value.get('family_handle'))!=value.get('assessment_fingerprint'): abort(409)
        origin=own('results',value.get('result_id')) if kind in revisits|{'policy_preview'} else None
        if origin and origin.get('workspace_instance'): ws=app.extensions['confidenceguard_authorize_workspace']()
        if kind in revisits:
            if ws is None or not origin.get('retained') or origin['result'].data.get('methodology_id')!='policy_selection_v1': raise EvaluationError('Revisits require a retained policy record and its authorized workspace.','workspace_access')
            config=config_from(origin['result'].private['config'])
            current.setdefault('policy_look_inspections',{})
            if kind=='policy_assess_look' and current['policy_look_inspections'].get((value['result_id'],value.get('look_id')))!=value.get('assessment_fingerprint'): abort(409)
        if not sessions.worker_lock.acquire(blocking=False): raise EvaluationError('Shared worker is busy.','worker_busy')
        jid=uuid.uuid4().hex; job={'id':jid,'kind':kind,'state':'pending','revision':0,'progress':{},'output':{},'error':None,
                                 'evaluation_id':None,'evaluation_revision':record['revision'] if record else None,
                                 'policy_study_id':record['id'] if record else None,'cancel':threading.Event(),'workspace_instance':ws.instance_id if ws else None}
        current['jobs'][jid]=job; current['requests'][request_key]=(request_digest,jid); grant=current.get('workspace_grant')
        authorized=roots(ws)
        def progress(update):
            safe={k:v for k,v in update.items() if k not in {'owned_workspace','scratch_directory'}}
            with sessions.guard: job.update(progress=safe,revision=job['revision']+1)
        def execute():
            try:
                job['state']='running'
                if ws and current.get('workspace_grant')!=grant: raise EvaluationError('Workspace detached.','workspace_access')
                options={'allowed_roots':authorized,'progress':progress,'cancel':job['cancel']}
                if kind=='policy_inspect':
                    output=inspect_policy_study(spec,config,**options); record['fingerprint']=output['fingerprint']; output['effective_spec']=copy.deepcopy(record['spec'])
                elif kind=='policy_preview':
                    output=preview_policy_assessment(origin['result'],value.get('assessment'),planned_e_size=value.get('planned_e_size'),requested_half_width=value.get('requested_half_width'))
                elif kind=='policy_inspect_look':
                    output=ws.inspect_policy_restatement(value['result_id'],value.get('look_id'),config,**options)
                    current['policy_look_inspections'][(value['result_id'],value.get('look_id'))]=output['fingerprint']
                elif kind=='policy_assessment_inspect':
                    output=inspect_policy_assessment(family['frozen'],config,assessment_input=spec.input,workspace=ws,**options)
                    record['assessment_inspections'][value['family_handle']]=output['fingerprint']
                else:
                    if kind=='policy_restate': result=ws.restate_policy_history(value['result_id'],as_of=value.get('as_of'),reason=value.get('reason'),config=config,request_id=request_key,**options)
                    elif kind=='policy_assess_look': result=ws.restate_policy_assessment(value['result_id'],value.get('look_id'),config,request_id=request_key,expected_fingerprint=value.get('assessment_fingerprint'),**options)
                    elif kind=='policy_optimize': result=optimize_policies(spec,config,workspace=ws,request_id=request_key,expected_fingerprint=value['fingerprint'],**options)
                    elif kind=='policy_replay': result=replay_policy(spec,config,workspace=ws,request_id=request_key,**options)
                    elif kind=='policy_history': result=analyze_policy_history(spec,config,workspace=ws,request_id=request_key,**options)
                    else: result=assess_policies(family['frozen'],config,assessment_input=spec.input,workspace=ws,request_id=request_key,expected_fingerprint=value['assessment_fingerprint'],**options)
                    if value.get('retain') and kind not in revisits: ws.save_assessment(result,request_id=request_key)
                    retained=bool(value.get('retain')) or kind in revisits
                    rid=result.data['analysis_id']; current['results'][rid]={'result':result,'evaluation_id':None,'revision':record['revision'] if record else 1,
                            'workspace_instance':ws.instance_id if ws else None,'retained':retained}
                    output={'result_id':rid,'retained':retained}
                if ws and current.get('workspace_grant')!=grant: raise EvaluationError('Workspace detached.','workspace_access')
                with sessions.guard: job.update(state='succeeded',output=output,revision=job['revision']+1)
            except Exception as exc:
                code=getattr(exc,'code','policy_failed')
                with sessions.guard: job.update(state='cancelled' if code=='cancelled' else 'failed',error={'code':code,'message':'Policy operation stopped; review the code, declared inputs and limits.'},revision=job['revision']+1)
            finally: sessions.worker_lock.release()
        job['thread']=threading.Thread(target=execute,daemon=True); job['thread'].start()
        return response(job_view(job),202)
    app.extensions['confidenceguard_policy_submit']=submit
