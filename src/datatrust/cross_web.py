"""Session-owned M9 guided mappings, exact evidence inspection and review snapshots."""
from dataclasses import replace
import json
from pathlib import Path
import threading
import uuid
from flask import Blueprint,abort,flash,request,redirect,url_for,session,render_template,send_file,jsonify
from werkzeug.utils import secure_filename

from datatrust.cross_contracts import *
from datatrust.cross import audit_cross_representation,_core,finalize,preflight
from datatrust.cross_sources import Store
from datatrust.cross_private_base import digest
from datatrust.cross_review import ReviewDispositionSet
from datatrust.cross_private import validate
from datatrust.m4_web import Sessions
from datatrust.scalable import Workspace
from datatrust.image_assets import capture,authorized
from datatrust.text_normalization import strict_json
from datatrust.worker import run_supervised


def preview_inputs(spec,config,*,progress=None,seal_all=False):
    work=Workspace(config.execution,[],progress,phase_plan={'estimated_peak_workspace_bytes':512*1024**2,'kind':'M9 bounded preview'})
    if progress: progress({'owned_workspace':str(work.root),'stage':'M9 mapping preview'})
    try:
        store=Store(work,spec,config)
        for item in spec.inputs: store.ingest(item)
        sealed=dict(store.files);unavailable=[]
        if seal_all:
            from datatrust.cross_diagnostics import stream
            from datatrust.contracts import AnalysisError
            for path, in stream(store.con,'SELECT DISTINCT asset FROM records WHERE asset IS NOT NULL'):
                try:
                    info,_,_=capture(path,store.roots,check=lambda:work.check('confirmation source seal'))
                    sealed[path]=info
                except AnalysisError as exc:
                    if exc.code!='source_unavailable': raise
                    unavailable.append(path)
        # Both before discovery and before reading media: sample document occurrences,
        # round-robin explicit source/layout strata with a seeded stable order.
        store.con.execute('CREATE TABLE preview_candidates AS SELECT * FROM records WHERE asset IS NOT NULL QUALIFY row_number() OVER(PARTITION BY sid,asset ORDER BY ordinal)=1')
        store.con.execute('CREATE TEMP TABLE preview_layout(rid VARCHAR,layout VARCHAR)')
        from datatrust.cross_diagnostics import stream
        from datatrust.cross_sources import decode_record,value
        batch=[]
        for rid,sid,payload in stream(store.con,'SELECT rid,sid,payload FROM preview_candidates'):
            item=store.sources[sid];record=decode_record(payload);layout=value(record,item.layout_selector) if item.layout_selector else item.layout or value(record,'layout') or 'default'
            batch.append((rid,str(layout)))
            if len(batch)>=256: store.insert('preview_layout',batch);batch=[]
        if batch: store.insert('preview_layout',batch)
        store.con.execute("CREATE TEMP TABLE selected AS SELECT rid FROM (SELECT p.rid,row_number() OVER(PARTITION BY sid,layout ORDER BY hash(p.rid,?)) n FROM preview_candidates p JOIN preview_layout q ON p.rid=q.rid) ORDER BY n,rid LIMIT 20",[config.seed])
        store.con.execute('DELETE FROM records WHERE asset IS NOT NULL AND rid NOT IN (SELECT rid FROM selected)')
        store.load_assets();suggestions=[]
        for row in store.con.execute('SELECT asset,payload FROM units ORDER BY asset,ordinal LIMIT 100').fetchall():
            u=json.loads(row[1])
            suggestions.append({'kind':u['kind'],'location':{k:u[k] for k in ('page','part','block','table') if k in u},'headers':u.get('rows',[[]])[0] if u.get('rows') else [],'text':u.get('text','')[:1000]})
        counts={}
        if spec.rules:
            from datatrust.cross_diagnostics import required
            required(store)
            for rule in spec.rules:
                counts[rule.id]=dict(store.con.execute('SELECT status,count(*) FROM outcomes WHERE rule=? GROUP BY status',[rule.id]).fetchall())
        for path,info in store.files.items():
            if path in sealed and sealed[path]['sha256']!=info['sha256']: raise ValueError('Source changed during preview.')
            sealed[path]=info
        return CrossRepresentationAuditResult({'suggestions':suggestions,'preview_counts':counts,'sample_documents':len(store.asset_cache),'sample_only':True},[],[],[],{}, {'peak_workspace_bytes':work.peak,'status':'completed','effective_limits':config.execution.to_dict() if hasattr(config.execution,'to_dict') else __import__('dataclasses').asdict(config.execution)},'',{'files':sealed,'unavailable':sorted(set(unavailable)|store.unavailable)})
    finally: work.close()


# M9 steps shared by the classic form routes and the JSON API (datatrust.api_web).

def m9_allowed(store,j): return tuple(map(str,store.roots))+(str(j['directory']),)
def m9_spec(j): return CrossRepresentationAuditSpec.from_dict(j['spec'],base_directory=j['directory'])
def m9_config(j): return CrossRepresentationAnalysisConfig.from_dict(j.get('config',{}))


def m9_invalidate(store,j):
    store.invalidate(j)
    for n in ('preview','sealed','reviews','view','view_refs','view_target','view_rule','view_context','review_filter'):j.pop(n,None)


def m9_remember(store,j,kind,path):
    info,_,_=capture(path,m9_allowed(store,j));j.setdefault('artifacts',{})[kind]={'path':Path(path),'signature':tuple(info['signature']),'sha256':info['sha256']}


def m9_checked(store,j,kind):
    item=j.get('artifacts',{}).get(kind)
    if not item: abort(404)
    info,_,_=capture(item['path'],m9_allowed(store,j),expected=item)
    return item['path']


def m9_spawn(store,j,operation):
    if not store.lock.acquire(blocking=False): abort(409,description='Another supervised audit is active.')
    j['cancel'].clear();j['state']='running'
    def execute():
        try: operation()
        except Exception as exc: j.update(state='failed',error=f'{getattr(exc,"code",type(exc).__name__)} at {getattr(exc,"stage","M9 execution")}')
        finally: store.lock.release()
    j['thread']=threading.Thread(target=execute,daemon=True);j['thread'].start()


def start_m9(store):
    old=store.jobs.get(session.get('m9_job'))
    if old and old['state']=='running': abort(409)
    j=store.create('cross');session['m9_job']=j['id'];j.update(spec={'inputs':[],'relationships':[],'mappings':[],'rules':[],'separation':[],'allowed_roots':list(m9_allowed(store,j))},config={},state='configure')
    return j


def m9_action(store,j,values,upload):
    """One guided configure action (source, relationship, mapping, rule, import, models, remove). Raises on refusal."""
    form=lambda name,default='':values.get(name,default).strip()
    columns=lambda name:tuple(x.strip() for x in form(name).split(',') if x.strip())
    j['form_values']=values.to_dict() if hasattr(values,'to_dict') else dict(values)
    m9_invalidate(store,j);action=form('action')
    if action=='source':
        local=form('path')
        if bool(local)==bool(upload and upload.filename): raise ValueError('Choose one local path or upload.')
        if upload and upload.filename:
            path=j['directory']/(uuid.uuid4().hex+'-'+secure_filename(upload.filename));upload.save(path);path.chmod(0o600)
        else: path=Path(local).absolute();authorized(path,m9_allowed(store,j))
        metadata=strict_json(form('metadata','{}'))
        source=CrossRepresentationInputSpec(form('source_id'),str(path),form('kind','structured'),form('format','csv'),id_selector=form('id_selector','id'),text_selector=form('text_selector','text'),path_selector=form('path_selector','path'),split_selector=form('split_selector') or None,role=form('role','dataset'),language=form('language') or None,layout=form('layout') or None,layout_selector=form('layout_selector') or None,asset_root=form('asset_root') or None,metadata=metadata,json_columns=columns('json_columns'),delimiter=values.get('delimiter',',') or ',')
        j['spec']['inputs']=[x for x in j['spec']['inputs'] if x['id']!=source.id]+[source.to_dict()]
    elif action=='relationship':
        context_map={name:[form('left_'+name),form('right_'+name)] for name in ('entity','period','version','currency','unit') if form('left_'+name) or form('right_'+name)}
        cutoff=ClockSpec(form('cutoff'),timezone=form('timezone') or None) if form('cutoff') else None
        available=ClockSpec(form('availability'),timezone=form('timezone') or None) if form('availability') else None
        r=RelationshipSpec(form('relationship_id'),form('left_source'),form('right_source'),columns('left_keys') or ('id',),columns('right_keys') or ('id',),namespace=form('namespace','declared'),meaning=form('meaning','supporting_evidence'),cardinality=form('cardinality','one_to_many'),required=form('required','required'),key_representation=form('key_representation','typed'),association_source=form('association_source') or None,association_left=form('association_left','left_id'),association_right=form('association_right','right_id'),context=context_map,cutoff=cutoff,availability=available,version_mode=form('version_mode','all'))
        j['spec']['relationships']=[x for x in j['spec']['relationships'] if x['id']!=r.id]+[r.to_dict()]
    elif action=='mapping':
        headers={};context_columns={}
        if form('mapping_kind')=='table_field':
            headers={'label':columns('row_headers'),'value':columns('value_headers')}
            if form('period_headers'): headers['period']=columns('period_headers');context_columns['period']=form('period_selector','period')
        m=DocumentMappingSpec(form('mapping_id'),layout=form('mapping_layout','default'),kind=form('mapping_kind','label_value'),labels=columns('labels'),pattern=form('pattern',r'\s*:\s*(?P<value>[^\n]+)'),section=form('section') or None,pages=tuple(int(x) for x in columns('pages')),headers=headers,row_column='label' if headers else None,row_label=form('row_label') or None,row_selector=form('row_selector') or None,context_columns=context_columns,strategy=form('strategy','lines'),unit=form('mapping_unit') or None,currency=form('mapping_currency') or None)
        j['spec']['mappings']=[x for x in j['spec']['mappings'] if x['id']!=m.id]+[m.to_dict()]
    elif action=='rule':
        r=ReconciliationRule(form('rule_id'),form('rule_relationship'),form('field'),mapping=form('mapping') or None,right_field=form('right_field') or None,method=form('method','decimal'),representation=form('representation','raw'),tolerance=form('tolerance','0'),factor=form('factor','1'),unit=form('unit') or None,currency=form('currency') or None,authority_role=form('authority_role') or None,claim_template=form('claim_template') or None,claim_language=form('claim_language') or None)
        j['spec']['rules']=[x for x in j['spec']['rules'] if x['id']!=r.id]+[r.to_dict()]
    elif action=='import':
        imported=CrossRepresentationAuditSpec.from_dict(strict_json(form('spec_json')),base_directory=j['directory'])
        j['spec']=replace(imported,allowed_roots=m9_allowed(store,j)).to_dict();j['config']=CrossRepresentationAnalysisConfig.from_dict(strict_json(form('config_json','{}'))).to_dict()
    elif action=='models':
        cfg=CrossRepresentationAnalysisConfig(models=CrossModelOptions(form('nli_directory') or None,form('retrieval_directory') or None,form('image_text_directory') or None))
        j['config']=cfg.to_dict()
    elif action=='remove':
        name=form('collection');identity=form('identity')
        if name not in {'inputs','relationships','mappings','rules','separation'}: raise ValueError('Invalid collection.')
        j['spec'][name]=[x for x in j['spec'][name] if x['id']!=identity]
    else: raise ValueError('Unknown mapping action.')
    # Validate a complete configuration when possible; partial wizard state remains editable.
    if j['spec']['inputs']: m9_spec(j)


def m9_action_message(exc):
    return str(exc) if isinstance(exc,ValueError) and not hasattr(exc,'code') else 'Source/configuration is unavailable or outside permitted roots.'


def preview_m9(store,j):
    s=m9_spec(j);c=m9_config(j)
    def operation():
        r=run_supervised(preview_inputs,(s,c),c.execution,progress=lambda p:j.setdefault('progress',{}).update(p),cancel=j['cancel'])
        j.update(preview=r.profile,preview_binding=digest([s.to_dict(),c.to_dict()]),state='configure')
    m9_spawn(store,j,operation)


def confirm_m9(store,j):
    s=m9_spec(j);c=m9_config(j);p=preflight(s,c)
    def operation():
        r=run_supervised(seal_preview,(s,c),c.execution,progress=lambda v:j.setdefault('progress',{}).update(v),cancel=j['cancel'])
        j.update(config=c.to_dict(),preview=r.profile,sealed={'spec':digest(s.to_dict()),'config':digest(c.to_dict()),'files':r.private['files'],'unavailable':r.private['unavailable'],'models':p},state='confirm')
    m9_spawn(store,j,operation)


def run_m9(store,j):
    if j['state']!='confirm': abort(409)
    s=m9_spec(j);c=m9_config(j);sealed=j['sealed']
    if sealed['spec']!=digest(s.to_dict()) or sealed['config']!=digest(c.to_dict()): abort(409)
    def operation():
        for info in sealed['files'].values(): capture(info['path'],m9_allowed(store,j),expected=info)
        from datatrust.image_assets import secure_open
        from datatrust.contracts import AnalysisError
        for path in sealed['unavailable']:
            try:
                with secure_open(path,m9_allowed(store,j)): raise ValueError('Source availability changed after confirmation.')
            except AnalysisError as exc:
                if exc.code!='source_unavailable': raise
        if preflight(s,c)!=sealed['models']: raise ValueError('Model confirmation changed.')
        owned=tuple(p for p in j['directory'].iterdir() if p.is_file() and p.name.startswith(tuple('0123456789abcdef')) and not p.is_symlink())
        r=audit_cross_representation(s,c,progress=lambda v:j.setdefault('progress',{}).update(v),cancel=j['cancel'],owned_snapshots=owned)
        for path,info in sealed['files'].items():
            if path not in r.private['files'] or r.private['files'][path]['sha256']!=info['sha256']: raise ValueError('Source changed after preview.')
        j.update(result=r,reviews=r.review_dispositions())
        a=r.generate_artifacts(j['directory']/'report.html',json_path=j['directory']/'analysis.json')
        for kind,path in [('html',a.html_path),('json',a.json_path),('private',a.private_manifest_path)]: m9_remember(store,j,kind,path)
        j['state']='completed'
    m9_spawn(store,j,operation)


def m9_target(store,j,target):
    """Exact local evidence, context and frozen rule for one review target (kept on the job as the classic page shows it)."""
    t=j['result'].profile['review_targets'].get(target)
    if not t: abort(400)
    resolved=[]
    for ref in t['evidence_refs']:
        if ref not in j['result'].private['locators']: continue
        try: resolved.append(j['result'].resolve_evidence(ref,allowed_roots=m9_allowed(store,j),reveal_content=True))
        except Exception: resolved.append({'reference':ref,'status':'unavailable','excerpt':'Exact source evidence is unavailable or changed.'})
    j.update(view=resolved,view_target=target)
    private=j['result'].private['targets'].get(target,{})
    j['view_context']=private.get('contexts',[])
    j['view_rule']=next((r for r in j['result'].private['spec']['rules'] if r['id']==private.get('rule')),None)
    if j['view_rule'] is None and t.get('semantic',{}).get('rule','').startswith('rule_'):
        index=int(t['semantic']['rule'].split('_')[1])-1
        if 0<=index<len(j['result'].private['spec']['rules']): j['view_rule']=j['result'].private['spec']['rules'][index]


def m9_import_review(j,raw):
    if j['state']!='completed': abort(409)
    try:
        if len(raw)>32*1024**2: raise ValueError('Review import exceeds result budget.')
        j['reviews']=ReviewDispositionSet.from_dict(strict_json(raw.decode()),result=j['result'])
    except Exception: abort(400,description='Review binding or entries differ from this original result.')


def m9_load_result(store,j,report_raw,manifest_raw):
    if j['state']=='running': abort(409)
    try:
        report=strict_json(report_raw.decode());manifest=strict_json(manifest_raw.decode())
        r=CrossRepresentationAuditResult.from_dict(report,private=manifest)
        m9_invalidate(store,j)
        prefix='reopened-'+r.profile['audit_id']
        artifacts=r.generate_artifacts(j['directory']/(prefix+'.html'),json_path=j['directory']/(prefix+'.json'),private_out=j['directory']/'.datatrust-private'/prefix/'manifest.json')
        for kind,path in [('html',artifacts.html_path),('json',artifacts.json_path),('private',artifacts.private_manifest_path)]: m9_remember(store,j,kind,path)
        j.update(result=r,reviews=r.review_dispositions(),state='completed')
    except Exception: abort(400,description='Completed report/manifest binding differs.')


def m9_artifact(store,j,kind):
    """The owned artifact for kind; review snapshots and the PDF are written on first request."""
    if j['state']!='completed': abort(409)
    if kind=='review':
        raw=j['reviews'].json_text();path=j['directory']/('review-'+digest(raw)[:20]+'.json')
        if not path.exists(): j['reviews'].export(path,result=j['result'])
        return path
    if kind=='pdf' and kind not in j.get('artifacts',{}):
        from datatrust.pdf import render_pdf_report
        path=render_pdf_report(m9_checked(store,j,'html'),j['directory']/'report.pdf',expected_html_sha256=j['artifacts']['html']['sha256']);m9_remember(store,j,'pdf',path)
    if kind not in {'html','pdf','json','private'}: abort(404)
    return m9_checked(store,j,kind)


def m9_disclose(store,j,excerpt_refs,image_refs):
    if j['state']!='completed': abort(409)
    options=CrossDisclosureOptions(tuple(excerpt_refs),tuple(image_refs))
    key=digest(options.to_dict())[:24];path=j['directory']/('disclosed-'+key+'.html')
    a=j['result'].generate_artifacts(path,disclosure=options,allowed_roots=m9_allowed(store,j));m9_remember(store,j,'disclosed-'+key,a.html_path)
    return m9_checked(store,j,'disclosed-'+key)


def register(app,workspace,roots):
    root=Path(workspace)/'m9';root.mkdir(mode=0o700,exist_ok=True)
    store=Sessions(root,roots,CrossRepresentationAnalysisConfig());store.lock=app.extensions['datatrust_worker_lock'];app.extensions['datatrust_m9_store']=store
    bp=Blueprint('m9',__name__)
    def job():
        j=store.jobs.get(session.get('m9_job'))
        if j is None: abort(400,description='Start an M9 audit.')
        return j
    def page(j):
        from datatrust.cross_presentation import report_view
        return render_template('cross_ui.html',job=j,spec=j['spec'],sources=j['spec']['inputs'],view=report_view(j['result']) if j.get('result') else None)
    def form(name,default=''): return request.form.get(name,default).strip()

    @bp.route('/cross-representation',methods=['GET','POST'])
    def start():
        if request.method=='POST':
            start_m9(store);return redirect(url_for('m9.configure'))
        return render_template('cross_ui.html',job=None,spec={},sources=[])

    @bp.route('/cross-representation/configure',methods=['GET','POST'])
    def configure():
        j=job()
        if request.method=='GET' and (j['state']=='confirm' or request.args.get('edit')=='1' and j['state']=='completed'): j['state']='configure'
        if request.method=='POST':
            try: m9_action(store,j,request.form,request.files.get('source'))
            except Exception as exc: flash(m9_action_message(exc),'error')
        return page(j)

    @bp.get('/cross-representation/spec')
    def specification(): return jsonify(job()['spec'])

    @bp.post('/cross-representation/preview')
    def preview():
        preview_m9(store,job());return redirect(url_for('m9.result'))

    @bp.post('/cross-representation/confirm')
    def confirm():
        confirm_m9(store,job());return redirect(url_for('m9.result'))

    @bp.post('/cross-representation/run')
    def run():
        run_m9(store,job());return redirect(url_for('m9.result'))

    @bp.post('/cross-representation/cancel')
    def cancel(): job()['cancel'].set();return redirect(url_for('m9.result'))

    @bp.get('/cross-representation/status')
    def status():
        j=job();return jsonify(state=j['state'],progress=j.get('progress',{}),error=j.get('error'))

    @bp.get('/cross-representation/result')
    def result(): return page(job())

    @bp.route('/cross-representation/investigate',methods=['GET','POST'])
    def investigate():
        j=job()
        if j['state']!='completed': abort(409)
        if request.method=='POST': m9_target(store,j,form('target'))
        j['review_filter']=request.args.get('disposition','all')
        if j['review_filter'] not in {'all','unreviewed','confirm','dismiss','unresolved'}: abort(400)
        response=app.make_response(page(j));response.headers['Cache-Control']='no-store';return response

    @bp.post('/cross-representation/review')
    def review():
        j=job()
        if j['state']!='completed': abort(409)
        j['reviews'].set(form('target'),form('disposition'),request.form.get('note',''))
        return redirect(url_for('m9.investigate'))

    @bp.post('/cross-representation/import-review')
    def import_review():
        j=job()
        if j['state']!='completed': abort(409)
        upload=request.files.get('review')
        m9_import_review(j,upload.read(32*1024**2+1) if upload else form('review_json').encode())
        return redirect(url_for('m9.investigate'))

    @bp.post('/cross-representation/load-result')
    def load_result():
        j=job()
        if j['state']=='running': abort(409)
        try: report_raw=request.files['report'].read(32*1024**2+1);manifest_raw=request.files['private'].read(64*1024**2+1)
        except Exception: abort(400,description='Completed report/manifest binding differs.')
        m9_load_result(store,j,report_raw,manifest_raw)
        return redirect(url_for('m9.investigate'))

    @bp.get('/cross-representation/download/<kind>')
    def download(kind):
        j=job()
        path=m9_artifact(store,j,kind)
        response=send_file(path,as_attachment=True)
        if kind=='review': response.headers['Cache-Control']='no-store'
        return response

    @bp.post('/cross-representation/disclose')
    def disclose():
        return send_file(m9_disclose(store,job(),request.form.getlist('excerpt_ref'),request.form.getlist('image_ref')),as_attachment=True)
    app.register_blueprint(bp)


def seal_preview(spec,config,*,progress=None): return preview_inputs(spec,config,progress=progress,seal_all=True)
