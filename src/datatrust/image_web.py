"""Standard-format presets and session-local visual investigation; one shared worker."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import threading
from flask import Blueprint,abort,flash,jsonify,render_template,request,redirect,send_file,session,url_for
from werkzeug.utils import secure_filename

from datatrust.image_contracts import *
from datatrust.image_assets import capture,authorized
from datatrust.image_sources import roots_for,source_plan,Store,ingest
from datatrust.image_private import digest
from datatrust.images import audit_images
from datatrust.m4_web import Sessions
from datatrust.scalable import Workspace
from datatrust.worker import run_supervised
from datatrust.text_normalization import strict_json

PRESETS={'directory':('directory','unlabeled','unlabeled'),'classes':('directory','classification','class_subdirectories'),'manifest':('jsonl','unlabeled','unlabeled'),'coco_detection':('coco','detection','unlabeled'),'coco_segmentation':('coco','segmentation','unlabeled'),'yolo':('yolo','detection','unlabeled'),'masks':('jsonl','segmentation','unlabeled')}


def inspection_binding(spec):
    # Only changes that alter admitted source/media membership need a fresh seal.
    return digest([{'source':item.source.to_dict(),'path':item.mapping.path,'mask':item.mapping.mask,'objects':item.mapping.objects,'segmentation':item.task.kind=='segmentation','associated':item.annotations.associated_source.to_dict() if item.annotations.associated_source else None,'associated_key':item.annotations.associated_key,'associated_primary_key':item.mapping.logical_id if item.annotations.associated_source else None} for item in spec.inputs])


def inspect_inputs(spec,config,*,progress=None):
    plan=source_plan(spec,config); work=None
    try:
        work=Workspace(config.execution,[],progress,phase_plan={'estimated_peak_workspace_bytes':plan.estimated_peak_workspace_bytes,'kind':'image_inspection'},image_source_plan=plan)
        if progress: progress({'owned_workspace':str(work.root),'stage':'source inspection'})
        store=Store(work,spec,config,'inspection')
        for item in spec.inputs:
            ingest(store,item)
            for payload, in store.con.execute('SELECT payload FROM occurrences WHERE sid=?',[item.id]).fetchall():
                value=json.loads(payload).get('mask')
                if isinstance(value,str):
                    asset_root=Path(item.source.asset_root or Path(item.source.path).parent)
                    store.media_file(asset_root/value,item.id,kind='mask')
        files={p:{k:v for k,v in info.items() if k!='snapshot'} for p,info in store.files.items()}
        return ImageAuditResult({'occurrences':store.count,'metadata_fields':sorted({k for item in spec.inputs for k in item.mapping.to_dict()})},[],[],[],{}, {'status':'completed','peak_workspace_bytes':work.peak},'',{'files':files,'memberships':store.memberships})
    finally:
        if work: work.close()


# M7 steps shared by the classic form routes and the JSON API (datatrust.api_web).

def m7_allowed(store,j): return tuple(map(str,store.roots))+(str(j['directory']),)


def m7_remember(j,kind,path):
    info,_,_=capture(path,(j['directory'],)); j.setdefault('artifacts',{})[kind]={'path':Path(path),'signature':tuple(info['signature']),'sha256':info['sha256']}


def m7_checked(j,kind):
    a=j.get('artifacts',{}).get(kind)
    if not a: abort(404)
    info,_,_=capture(a['path'],(j['directory'],))
    if tuple(info['signature'])!=a['signature'] or info['sha256']!=a['sha256']: abort(409,description='Artifact identity changed.')
    return a['path']


def m7_artifact(j,kind):
    if kind not in {'html','json','pdf','private'}: abort(404)
    if kind=='pdf' and kind not in j.get('artifacts',{}):
        from datatrust.pdf import render_pdf_report
        path=render_pdf_report(m7_checked(j,'html'),j['directory']/'report.pdf',expected_html_sha256=j['artifacts']['html']['sha256']); m7_remember(j,'pdf',path)
    return m7_checked(j,kind)


def m7_spawn(store,j,operation):
    if not store.lock.acquire(blocking=False): abort(409,description='Another supervised audit is active.')
    j['cancel'].clear(); j['state']='running'
    def execute():
        try: operation()
        except Exception as exc: j.update(state='failed',error=f'{getattr(exc,"code",type(exc).__name__)} at {getattr(exc,"stage","image execution")}')
        finally: store.lock.release()
    j['thread']=threading.Thread(target=execute,daemon=True); j['thread'].start()


def start_m7(store,preset):
    old=store.jobs.get(session.get('m7_job'))
    if old and old['state']=='running': abort(409)
    j=store.create('images'); os.chmod(j['directory'],0o700); session['m7_job']=j['id']; j['preset']=preset
    if j['preset'] not in PRESETS: abort(400)
    return j


def add_m7_source(store,j,form,upload):
    """A local source within the roots, or one uploaded manifest. Raises on refusal."""
    store.invalidate(j)
    local=form.get('local_path','').strip()
    if bool(local)==bool(upload and upload.filename): raise ValueError('Choose a local source or one manifest upload.')
    fmt,task,layout=PRESETS[j['preset']]
    if upload and upload.filename:
        if fmt=='directory': raise ValueError('Directory audits use a configured local root.')
        path=j['directory']/('source-'+secure_filename(upload.filename)); upload.save(path); path.chmod(0o600)
    else: path=Path(local).absolute(); authorized(path,m7_allowed(store,j))
    if j['preset'] in {'manifest','masks'}: fmt=form.get('format','jsonl')
    asset_root=form.get('asset_root','').strip() or None
    if asset_root: authorized(asset_root,m7_allowed(store,j))
    identity=form.get('source_id','dataset').strip()
    source=ImageSourceSpec(str(path),fmt,asset_root,layout)
    item=ImageInputSpec(identity,source,ImageTaskSpec(task),role=form.get('role','dataset'),annotations=ImageAnnotationSpec(box_format='xywh' if fmt=='coco' else 'normalized_cxcywh' if fmt=='yolo' else 'xyxy',mask_encoding='coco' if fmt=='coco' else 'semantic_png'))
    if identity in {x['id'] for x in j['sources']}: raise ValueError('Source ID is already present.')
    j['sources'].append(item.to_dict()); j['state']='sources'


def inspect_m7(store,j):
    if not j['sources']: abort(400)
    spec=ImageAuditSpec.from_dict({'inputs':j['sources'],'allowed_roots':list(m7_allowed(store,j))}); config=ImageAnalysisConfig()
    def operation():
        r=run_supervised(inspect_inputs,(spec,config),config.execution,progress=lambda p:j.setdefault('progress',{}).update(p),cancel=j['cancel'])
        j.update(inspected=r.private,inspection_binding=inspection_binding(spec),preview=r.profile,state='configure',spec_json=json.dumps(spec.to_dict(),indent=2))
    m7_spawn(store,j,operation)


def configure_m7(store,j,form):
    """Declarations, then a supervised seal (model preflight and inventory) that ends in confirm. Raises on refusal."""
    j['form_values']=form.to_dict() if hasattr(form,'to_dict') else dict(form)
    if j['state']=='running': abort(409)
    store.invalidate(j)
    if form.get('advanced')=='yes':
        spec=ImageAuditSpec.from_dict(strict_json(form['spec_json'])); config=ImageAnalysisConfig.from_dict(strict_json(form.get('config_json') or '{}'))
    else:
        inputs=[]
        for n,value in enumerate(j['sources']):
            item=ImageInputSpec.from_dict(value); prefix=f's{n}_'
            mapping=ImageMappingSpec(**{k:(tuple(x.strip() for x in form.get(prefix+k,'').split(',') if x.strip()) if k=='groups' else form.get(prefix+k,getattr(item.mapping,k)) or None) for k in item.mapping.to_dict()})
            columns=tuple(x.strip() for x in form.get(prefix+'json_columns','').split(',') if x.strip())
            task=form.get(prefix+'task',item.task.kind)
            cats=tuple(int(x.strip()) if task in {'detection','segmentation'} and x.strip().isdigit() else x.strip() for x in form.get(prefix+'categories','').split(',') if x.strip())
            ann=replace(item.annotations,box_format=form.get(prefix+'box_format',item.annotations.box_format),color_mapping=strict_json(form.get(prefix+'color_mapping') or '{}'),expectation=form.get(prefix+'expectation','unknown'),coordinate_frame=form.get(prefix+'frame','encoded'),categories=cats,mask_encoding=form.get(prefix+'mask_encoding',item.annotations.mask_encoding),missing_yolo_labels_are_negative=form.get(prefix+'missing_negative')=='yes')
            inputs.append(replace(item,source=replace(item.source,json_columns=columns),task=ImageTaskSpec(task),mapping=mapping,annotations=ann))
        spec=ImageAuditSpec(tuple(inputs),allowed_roots=m7_allowed(store,j),dataset_name=form.get('dataset_name') or None)
        config=ImageAnalysisConfig(models=ImageModelOptions(form.get('model_directory') or None))
    spec=replace(spec,allowed_roots=m7_allowed(store,j))
    for item in spec.inputs: authorized(item.source.path,m7_allowed(store,j))
    if config.models.directory: authorized(config.models.directory,m7_allowed(store,j))
    if config.execution.scratch_directory: authorized(config.execution.scratch_directory,m7_allowed(store,j))
    j.update(sources=[x.to_dict() for x in spec.inputs],spec_json=json.dumps(spec.to_dict(),indent=2),dataset_name=spec.dataset_name,spec=spec,config=config,fingerprint=digest({'spec':spec.to_dict(),'config':config.to_dict()}))
    def prepare():
        from datatrust.images import preflight
        j['sealed_model']=preflight(spec,config)
        binding=inspection_binding(spec)
        if not j.get('inspected') or j.get('inspection_binding')!=binding:
            r=run_supervised(inspect_inputs,(spec,config),config.execution,progress=lambda p:j.setdefault('progress',{}).update(p),cancel=j['cancel'])
            j.update(inspected=r.private,inspection_binding=binding)
        j['state']='confirm'
    m7_spawn(store,j,prepare)


def run_m7(store,j,confirmed):
    if j['state']!='confirm' or confirmed!='yes': abort(400)
    def operation():
        r=audit_images(j['spec'],j['config'],progress=lambda p:j.setdefault('progress',{}).update(p),cancel=j['cancel'])
        seal=j.get('inspected')
        if seal:
            for path,info in seal['files'].items():
                if path not in r.private['files'] or info['sha256']!=r.private['files'][path]['sha256'] or info['signature'][:4]!=r.private['files'][path]['signature'][:4]: raise ValueError('Source changed after inspection; inspect and confirm again.')
            if seal['memberships']!=r.private['memberships']: raise ValueError('Directory membership changed after inspection.')
        if j.get('sealed_model')!=r.private['model']: raise ValueError('Model changed after confirmation.')
        j['result']=r
        a=r.generate_artifacts(j['directory']/'report.html',json_path=j['directory']/'analysis.json')
        for kind,path in [('html',a.html_path),('json',a.json_path),('private',a.private_manifest_path)]: m7_remember(j,kind,path)
        j['state']='completed'
    m7_spawn(store,j,operation)


def m7_pairs(j):
    """Retained references and candidate pairs of a completed audit."""
    if j['state']!='completed': abort(400)
    references=list(j['result'].private['locators'])
    pairs=[]
    for record in j['result'].evidence:
        for value in record['data'].get('examples',record['data'].get('candidates',[])):
            if value.get('left') and value.get('right'):
                pairs.append(dict(value,family=record['family']))
    return references,pairs


def m7_resolve(store,j,ref,options):
    return j['result'].resolve_evidence(ref,allowed_roots=m7_allowed(store,j),reveal_image=True,overlays=options.get('overlays',False),labels=options.get('labels',False))


def m7_examples(store,j,refs,overlays,labels):
    if j['state']!='completed': abort(400)
    opts=ImageDisclosureOptions(tuple(refs),overlays,labels)
    key=digest(opts.to_dict())[:24]; path=j['directory']/f'examples-{key}.html'
    if 'example-'+key not in j.get('artifacts',{}):
        a=j['result'].generate_artifacts(path,disclosure=opts,allowed_roots=m7_allowed(store,j)); m7_remember(j,'example-'+key,a.html_path)
    return m7_checked(j,'example-'+key)


def register(app,workspace,roots):
    root=Path(workspace)/'m7'; root.mkdir(mode=0o700,exist_ok=True)
    store=Sessions(root,roots,ImageAnalysisConfig()); store.lock=app.extensions['datatrust_worker_lock']; app.extensions['datatrust_m7_store']=store
    bp=Blueprint('m7',__name__)
    def job():
        j=store.jobs.get(session.get('m7_job'))
        if j is None: abort(400,description='Start an image audit in this session.')
        return j
    def page(stage,j=None,**kwargs): return render_template('image_ui.html',stage=stage,job=j,presets=PRESETS,**kwargs)
    @bp.route('/images',methods=['GET','POST'])
    def start():
        if request.method=='POST':
            start_m7(store,request.form.get('preset','directory'))
            return redirect(url_for('m7.sources'))
        return page('start')
    @bp.route('/images/sources',methods=['GET','POST'])
    def sources():
        j=job()
        if request.method=='POST':
            try: add_m7_source(store,j,request.form,request.files.get('manifest'))
            except Exception as exc: flash(str(exc) if isinstance(exc,ValueError) else 'Source is outside permitted roots or unavailable.','error')
        return page('sources',j)
    @bp.post('/images/inspect')
    def inspect():
        inspect_m7(store,job()); return redirect(url_for('m7.result'))
    @bp.route('/images/configure',methods=['GET','POST'])
    def configure():
        j=job()
        if request.method=='POST':
            try:
                configure_m7(store,j,request.form)
                return redirect(url_for('m7.result'))
            except Exception as exc: flash(str(exc) if isinstance(exc,ValueError) else 'Declarations could not be confirmed.','error')
        return page('configure',j)
    @bp.get('/images/confirm')
    def confirm():
        j=job()
        if j['state']!='confirm': return redirect(url_for('m7.configure'))
        return page('confirm',j)
    @bp.post('/images/run')
    def run():
        run_m7(store,job(),request.form.get('confirm')); return redirect(url_for('m7.result'))
    @bp.post('/images/cancel')
    def cancel(): job()['cancel'].set(); return redirect(url_for('m7.result'))
    @bp.get('/images/status')
    def status():
        j=job(); return jsonify(state=j['state'],progress=j.get('progress',{}),error=j.get('error'))
    @bp.get('/images/result')
    def result(): return page('result',job())
    @bp.get('/images/report')
    def report(): return send_file(m7_checked(job(),'html'),mimetype='text/html')
    @bp.get('/images/download/<kind>')
    def download(kind):
        return send_file(m7_artifact(job(),kind),as_attachment=True)
    @bp.route('/images/investigate',methods=['GET','POST'])
    def investigate():
        j=job()
        references,pairs=m7_pairs(j)
        selected=j.get('view_refs',references[:2])
        resolved=[]
        if request.method=='POST':
            try:
                selected=request.form.getlist('reference')[:2] or selected
                pair=request.form.get('pair')
                if pair is not None:
                    index=int(pair)
                    if not 0<=index<len(pairs): abort(400)
                    selected=[pairs[index]['left'],pairs[index]['right']]
                move=request.form.get('move')
                if move and references:
                    index=references.index(selected[0]) if selected and selected[0] in references else 0
                    index=(index+(1 if move=='next' else -1))%len(references)
                    selected=[references[index],references[(index+1)%len(references)]]
                j['view_refs']=selected
                if pair is None:
                    j['view_options']={'overlays':request.form.get('overlays')=='yes','labels':request.form.get('labels')=='yes'}
                options=j.get('view_options',{})
                for ref in selected:
                    resolved.append(m7_resolve(store,j,ref,options))
            except Exception: flash('Evidence changed, is unavailable, or has an unresolved overlay frame.','error')
        response=app.make_response(page('investigate',j,references=references,resolved=resolved,selected=selected,pairs=pairs)); response.headers['Cache-Control']='no-store'; return response
    @bp.post('/images/export-examples')
    def examples():
        return send_file(m7_examples(store,job(),request.form.getlist('reference'),request.form.get('overlays')=='yes',request.form.get('labels')=='yes'),as_attachment=True)
    app.register_blueprint(bp)
