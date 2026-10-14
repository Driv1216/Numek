"""Guided M6 declarations and session-owned artifacts; one shared active worker."""
from dataclasses import asdict,replace
import hashlib
import json
import os
from pathlib import Path
import threading
from flask import Blueprint,abort,flash,jsonify,redirect,render_template,request,send_file,session,url_for
from werkzeug.utils import secure_filename
from datatrust.m4_web import Sessions
from datatrust.text_contracts import *
from datatrust.text_normalization import capture,strict_json,frames,get,MISSING,lexical
from datatrust.text import preflight,audit_text


def names(value):return tuple(x.strip() for x in value.split(',') if x.strip())


def guided(j,form,roots):
    inputs=[]
    for i,source in enumerate(j['sources']):
        p=f's{i}_';value=lambda k,default='':form.get(p+k,default).strip()
        src=TextSourceSpec(str(source['path']),source['format'],value('encoding','utf-8'),value('delimiter',','),value('quotechar','"'),names(value('json_columns')))
        fields=[]
        checksums=form.getlist(p+'field_checksum')
        field_columns=[form.getlist(p+k) for k in ['field_name','field_selector','field_kind','field_required','field_asset']]
        if len({len(x) for x in field_columns})>1:raise ValueError('Content field controls are incomplete.')
        for n,(name,sel,kind,required,asset) in enumerate(zip(*field_columns)):
            if bool(name)!=bool(sel):raise ValueError('Each content field requires both a name and selector.')
            if name and sel:fields.append(TextFieldSpec(name,sel,kind,required=='yes',AssetSpec(sel,'text',value('asset_encoding','utf-8'),checksums[n] or None if n<len(checksums) else None) if asset=='yes' else None))
        annotations=[]
        keys=['annotation_field','annotation_selector','annotation_kind','annotation_expectation','annotation_tokens','annotation_unit','annotation_scheme','annotation_overlap','annotation_status','annotation_required_statuses','annotation_answerable','annotation_content_source','annotation_content_id']
        annotation_columns=[form.getlist(p+k) for k in keys]
        if len({len(x) for x in annotation_columns})>1:raise ValueError('Annotation controls are incomplete.')
        for values in zip(*annotation_columns):
            field,sel,kind,expectation,tokens,unit,scheme,overlap,status,statuses,answerable,content_source,content_id=values
            if bool(field)!=bool(sel):raise ValueError('Each annotation requires a content field and selector.')
            if field and sel:annotations.append(TextAnnotationSpec(field,sel,kind,expectation,tokens or None,unit,scheme,overlap=='yes',status or None,names(statuses),answerable or None,content_source or None,content_id or None))
        conversation=None
        if value('conversation')=='yes':conversation=TextConversationSpec(value('messages','messages') if value('message_layout','nested')=='nested' else None,value('conversation_id') or None,value('order') or None,value('role_field','role'),value('content','content'),value('calls','tool_calls'),value('call_id','tool_call_id'),names(value('roles','system,developer,user,assistant,tool')),value('tool_closure')=='yes',value('completion')=='yes')
        retrieval=None
        if value('retrieval'):
            grades=names(value('positive_grades','1'))
            if value('grade_type','number')=='number':grades=tuple(float(x) for x in grades)
            retrieval=TextRetrievalSpec(kind=value('retrieval'),parent_source=value('parent_source') or None,parent_selector=value('parent_id') or None,field=value('chunk_field') or None,parent_field=value('parent_field') or None,extractive=value('extractive')=='yes',start_selector=value('start','start'),end_selector=value('end','end'),offset_unit=value('retrieval_unit','codepoint'),query_source=value('query_source') or None,query_selector=value('query_id','query_id'),target_source=value('target_source') or None,target_selector=value('target_id','document_id'),grade_selector=value('grade','relevance'),positive_grades=grades)
        assets=[]
        for sel,kind,encoding,checksum in zip(*(form.getlist(p+k) for k in ['asset_selector','asset_kind','asset_encoding_row','asset_checksum'])):
            if sel:assets.append(AssetSpec(sel,kind,encoding,checksum or None))
        task=TextTaskSpec(value('task',j['preset']),names(value('task_inputs')),names(value('task_outputs')),value('required_outputs')=='yes')
        inputs.append(TextInputSpec(source['id'],src,tuple(fields),value('role','corpus'),value('namespace') or None,value('identity') or None,value('split') or None,task,tuple(annotations),conversation,retrieval,tuple(assets)))
    if len(form.getlist('compare_left'))!=len(form.getlist('compare_right')) or any(bool(a)!=bool(b) for a,b in zip(form.getlist('compare_left'),form.getlist('compare_right'))):raise ValueError('Comparisons require both source selections.')
    pairs=tuple((a,b) for a,b in zip(form.getlist('compare_left'),form.getlist('compare_right')) if a and b)
    spec=TextAuditSpec(tuple(inputs),TextEvaluationSpec(pairs),tuple(map(str,roots)))
    execution=ExecutionOptions.from_dict({k:(form.get('execution_'+k) or v) if k in {'backend','scratch_directory'} else float(form.get('execution_'+k,v)) if k=='max_seconds' else int(form.get('execution_'+k,v)) for k,v in asdict(ExecutionOptions()).items() if k!='scratch_directory'})
    limits=TextWorkLimits.from_dict({k:int(form.get('limit_'+k,v)) for k,v in asdict(TextWorkLimits()).items()})
    models=TextModelOptions(form.get('language')=='yes',names(form.get('languages','ENGLISH,HINDI,SPANISH,FRENCH,GERMAN,CHINESE,ARABIC')),form.get('embedding_directory') or None,long_documents=form.get('long_documents','token_windows_v1'),tokenizer=form.get('tokenizer')=='yes',embeddings=form.get('embeddings','yes')=='yes')
    config=TextAnalysisConfig(execution,limits,models,tuple(form.getlist('representation') or ['raw','nfc']),int(form.get('seed',0)),form.get('near_duplicates')=='yes',form.get('passages')=='yes',form.get('vocabulary')=='yes',form.get('lexical_complete')=='yes',float(form.get('near_threshold',.8)),int(form.get('minimum_passage',50)))
    return spec,config


def fingerprint(spec,config):
    models,_=preflight(spec,config);sources={x.id:capture(x.source.path) for x in spec.inputs};assets={}
    for item in spec.inputs:
        bindings=list(item.assets)+[f.asset for f in item.fields if f.asset]
        if not bindings:continue
        for loc,record,reason in frames(item.source.path,item.source,config.execution,config.limits):
            if record is None:continue
            for asset in bindings:
                value=get(record,asset.selector)
                if not isinstance(value,str):continue
                path=(Path(item.source.path).parent/value).resolve()
                if any(path.is_relative_to(Path(root)) for root in spec.allowed_roots) and path.is_file():assets[str(path)]=capture(path)
    value={'spec':spec.to_dict(),'config':config.to_dict(),'sources':sources,'assets':assets,'models':models}
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=True).encode()).hexdigest(),value


def register(app,workspace,roots):
    root=Path(workspace)/'m6';root.mkdir(mode=0o700,exist_ok=True)
    store=Sessions(root,roots,TextAnalysisConfig());store.lock=app.extensions['datatrust_worker_lock'];app.extensions['datatrust_m6_store']=store
    bp=Blueprint('m6',__name__)
    def job():
        j=store.jobs.get(session.get('m6_job'))
        if j is None:abort(400,description='Start a text audit in this session.')
        return j
    def path_allowed(value):
        p=Path(value).expanduser().resolve()
        if not p.is_file() or not any(p.is_relative_to(r) for r in store.roots):raise ValueError('Source must be a regular file within configured roots.')
        return p
    def remember(j,kind,path):j.setdefault('artifacts',{})[kind]={'path':Path(path),'signature':capture(path)['signature'],'sha256':capture(path)['sha256']}
    def checked(j,kind):
        if j.get('result'):
            from datatrust.text_normalization import source_signature
            identities=list(j['result'].private['sources'].values())+list(j['result'].private['assets'].values())
            for model in j['result'].private['models'].values():
                identities+=list(model.get('files',{}).values())
                if model.get('manifest'):identities.append(model['manifest'])
            try:
                if any(source_signature(info['path'])!=tuple(info['signature']) for info in identities):abort(409,description='Analysis source identity changed. Reconfirm the audit.')
            except OSError:abort(409,description='Analysis source is unavailable. Reconfirm the audit.')
        a=j.get('artifacts',{}).get(kind)
        if not a:abort(404)
        current=capture(a['path'])
        if current['sha256']!=a['sha256'] or current['signature']!=a['signature']:abort(409,description='Artifact identity changed.')
        return a['path']
    def page(stage,j=None,**kwargs):return render_template('text_ui.html',stage=stage,job=j,defaults=TextAnalysisConfig(),execution_fields=asdict(ExecutionOptions()),limit_fields=asdict(TextWorkLimits()),**kwargs)
    @bp.route('/text',methods=['GET','POST'])
    def start():
        if request.method=='POST':
            old=store.jobs.get(session.get('m6_job'))
            if old:store.invalidate(old)
            j=store.create('text');os.chmod(j['directory'],0o700);j['preset']=request.form.get('preset','corpus');TextTaskSpec(j['preset']);session['m6_job']=j['id']
            return redirect(url_for('m6.sources'))
        return page('start')
    @bp.route('/text/sources',methods=['GET','POST'])
    def sources():
        j=job()
        if request.method=='POST':
            try:
                store.invalidate(j)
                if request.form.get('asset_upload')=='yes':
                    upload=request.files.get('dataset');name=secure_filename(upload.filename) if upload else ''
                    if not name:raise ValueError('Select an asset file.')
                    destination=j['directory']/name
                    # Never overwrite a source or earlier uploaded asset.
                    if destination.exists():raise ValueError('An uploaded filename is already occupied.')
                    upload.save(destination);os.chmod(destination,0o600);j.setdefault('asset_uploads',[]).append(destination)
                else:
                    upload=request.files.get('dataset');local=request.form.get('local_path','').strip();fmt=request.form.get('format','jsonl')
                    if bool(upload and upload.filename)==bool(local):raise ValueError('Choose one uploaded or local source.')
                    identity=request.form.get('source_id') or f's{len(j["sources"])+1}'
                    if identity in {s['id'] for s in j['sources']}:raise ValueError('Source ID is already used.')
                    if local:path=path_allowed(local)
                    else:
                        name=secure_filename(upload.filename)
                        if not name:raise ValueError('Select a source file.')
                        path=j['directory']/name
                        if path.exists():raise ValueError('Uploaded filename is already occupied.')
                        upload.save(path);os.chmod(path,0o600)
                    source=TextSourceSpec(str(path),fmt,request.form.get('encoding','utf-8'),request.form.get('delimiter',','),request.form.get('quotechar','"'))
                    preview=[]
                    for n,(loc,record,reason) in enumerate(frames(path,source,TextAnalysisConfig().execution,TextWorkLimits())):
                        if n>=128:break
                        if 'header' in loc:preview=loc['header'];break
                        if record is not None:preview=list(record);break
                    j['sources'].append({'id':identity,'path':path,'format':fmt,'encoding':source.encoding,'delimiter':source.delimiter,'quotechar':source.quotechar,'fields':preview})
            except Exception as exc:flash(str(exc) if isinstance(exc,ValueError) else 'Source could not be loaded.','error')
        return page('sources',j)
    @bp.route('/text/configure',methods=['GET','POST'])
    def configure():
        j=job()
        if request.method=='POST':
            j['form_values']=request.form.to_dict(flat=False)
            try:
                store.invalidate(j)
                if request.form.get('spec_json','').strip():
                    spec=TextAuditSpec.from_dict(strict_json(request.form['spec_json']));config=TextAnalysisConfig.from_dict(strict_json(request.form.get('config_json') or '{}'))
                    for item in spec.inputs:path_allowed(item.source.path)
                    spec=replace(spec,allowed_roots=tuple(map(str,store.roots))+(str(j['directory']),))
                else:spec,config=guided(j,request.form,store.roots+(j['directory'],))
                for path in [config.models.embedding_directory,config.execution.scratch_directory]:
                    if path and not any(Path(path).resolve().is_relative_to(r) for r in store.roots):raise ValueError('Model/scratch directories must stay in configured roots.')
                fp,sealed=fingerprint(spec,config);j.update(spec=spec,config=config,fingerprint=fp,sealed=sealed,state='confirm')
                return redirect(url_for('m6.confirm'))
            except Exception as exc:flash(str(exc) if isinstance(exc,ValueError) else 'Declarations could not be confirmed.','error')
        return page('configure',j)
    @bp.get('/text/confirm')
    def confirm():
        j=job()
        if j.get('state')!='confirm':return redirect(url_for('m6.configure'))
        return page('confirm',j)
    @bp.post('/text/run')
    def run():
        j=job()
        if j.get('state')!='confirm' or request.form.get('confirm')!='yes':abort(400)
        fp,sealed=fingerprint(j['spec'],j['config'])
        if fp!=j['fingerprint']:abort(409,description='Source, asset, model or declarations changed. Reconfirm the audit.')
        if not store.lock.acquire(blocking=False):abort(409,description='Another supervised audit is active.')
        j.update(state='running',progress={});j['cancel'].clear()
        def execute():
            try:
                result=audit_text(j['spec'],j['config'],progress=lambda v:j['progress'].update(v),cancel=j['cancel'])
                # Bind the result to all source/assets/models captured at confirmation.
                for sid,info in result.private['sources'].items():
                    if info['sha256']!=sealed['sources'][sid]['sha256']:raise ValueError('Source changed after confirmation.')
                for path,info in result.private['assets'].items():
                    if path not in sealed['assets'] or info['sha256']!=sealed['assets'][path]['sha256']:raise ValueError('Asset changed after confirmation.')
                if result.private['models']!=sealed['models']:raise ValueError('Model changed after confirmation.')
                j['result']=result
                artifacts=result.generate_artifacts(j['directory']/'report.html',json_path=j['directory']/'analysis.json')
                for kind,path in [('html',artifacts.html_path),('json',artifacts.json_path),('private',artifacts.private_manifest_path)]:remember(j,kind,path)
                j['state']='completed'
            except Exception as exc:j.update(state='failed',error=f'{getattr(exc,"code",type(exc).__name__)} at {getattr(exc,"stage","text execution")}',failure_execution=getattr(exc,'execution',{}))
            finally:store.lock.release()
        j['thread']=threading.Thread(target=execute,daemon=True);j['thread'].start()
        return redirect(url_for('m6.result'))
    @bp.post('/text/cancel')
    def cancel():job()['cancel'].set();return redirect(url_for('m6.result'))
    @bp.get('/text/status')
    def status():
        j=job();return jsonify(state=j['state'],progress=j.get('progress',{}),error=j.get('error'))
    @bp.get('/text/result')
    def result():return page('result',job())
    @bp.get('/text/report')
    def report():return send_file(checked(job(),'html'),mimetype='text/html')
    @bp.get('/text/download/<kind>')
    def download(kind):
        j=job()
        if kind not in {'html','json','pdf','private'}:abort(404)
        if kind=='pdf' and kind not in j.get('artifacts',{}):
            html=checked(j,'html')
            from datatrust.pdf import render_pdf_report
            path=render_pdf_report(html,j['directory']/'report.pdf',expected_html_sha256=j['artifacts']['html']['sha256']);remember(j,'pdf',path)
        return send_file(checked(j,kind),as_attachment=True)
    @bp.post('/text/evidence')
    def evidence():
        j=job()
        if j.get('state')!='completed':abort(400)
        try:value=j['result'].resolve_evidence(request.form['reference'],allowed_roots=store.roots+(j['directory'],),reveal_content=request.form.get('reveal')=='yes')
        except Exception as exc:return jsonify(status='changed_or_unavailable',reason=getattr(exc,'code',type(exc).__name__)),409
        return page('evidence',j,resolved=value)
    @bp.post('/text/export-excerpts')
    def excerpts():
        j=job()
        if j.get('state')!='completed':abort(400)
        refs=names(request.form.get('references',''));key=hashlib.sha256(json.dumps(refs).encode()).hexdigest()[:16]
        try:
            for ref in refs:j['result'].resolve_evidence(ref,allowed_roots=store.roots+(j['directory'],),reveal_content=True)
        except Exception:abort(409,description='Excerpt source changed or is unavailable. Reconfirm the audit.')
        path=j['directory']/f'excerpts-{key}.html'
        if 'excerpt-'+key not in j.get('artifacts',{}):
            artifacts=j['result'].generate_artifacts(path,excerpt_refs=refs,allowed_roots=store.roots+(j['directory'],));remember(j,'excerpt-'+key,artifacts.html_path)
        return send_file(checked(j,'excerpt-'+key),as_attachment=True)
    app.register_blueprint(bp)
