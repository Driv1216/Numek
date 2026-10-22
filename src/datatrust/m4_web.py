"""Session-local guided M4 jobs with one active supervised worker."""
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import shutil
import threading
import uuid

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, send_file, session, url_for
from werkzeug.utils import secure_filename

from datatrust import (AnalysisConfig, DatasetInput, DatasetSpec, TaskSpec, ComparisonSpec,
    ComparisonConfig, ExecutionOptions, AdvancedTabularOptions)
from datatrust.contracts import FidelityInspectionLimits, omit_default_delimiter
from datatrust.m4_contracts import spec_record
from datatrust.ingestion import resolve_delimiter, inspect_source_tokens, source_digest, source_signature
from datatrust.m4_worker import analyze_scalable, compare


class Sessions:
    def __init__(self,root,roots,config):
        self.root=Path(root);self.root.mkdir(exist_ok=True);self.roots=tuple(Path(r).resolve() for r in roots);self.config=config;self.jobs={};self.lock=threading.Lock()

    def create(self,mode):
        identity=uuid.uuid4().hex;directory=self.root/identity;directory.mkdir()
        marker=uuid.uuid4().hex;(directory/'owner').write_text(marker)
        job={'id':identity,'directory':directory,'marker':marker,'mode':mode,'sources':[],'state':'sources','cancel':threading.Event(),'progress':{}}
        self.jobs[identity]=job;return job

    def invalidate(self,job):
        if job['state']=='running':raise ValueError('Cancel the active analysis before editing its declarations.')
        for item in job.get('artifacts',{}).values():
            path=item['path']
            if path.exists() and (path.is_symlink() or source_signature(path)!=item['signature'] or source_digest(path)!=item['sha256']):raise ValueError('Artifact ownership changed; the conflicting path was left untouched.')
        for item in job.get('artifacts',{}).values():item['path'].unlink(missing_ok=True)
        for key in ('result','artifacts','fingerprint'):job.pop(key,None)
        job['state']='configure'

    def cleanup(self):
        for job in self.jobs.values():job['cancel'].set()
        for job in self.jobs.values():
            if job.get('thread'):job['thread'].join(5)
            d=job['directory']
            if not d.is_symlink() and (d/'owner').is_file() and (d/'owner').read_text()==job['marker']:shutil.rmtree(d)
        self.jobs.clear()


# M4 steps shared by the classic form routes and the JSON API (datatrust.api_web). `form` is any mapping
# with the classic form's field names and string values.

def m4_fingerprint(j):
    sources=[]
    for s in j['sources']:
        if source_signature(s['path'])!=s['signature'] or source_digest(s['path'])!=s['sha256']:raise ValueError('A source changed; add it again and confirm the new interpretation.')
        sources.append({'id':s['id'],'sha256':s['sha256']})
    return hashlib.sha256(json.dumps({'spec':omit_default_delimiter(j['manifest']),'config':omit_default_delimiter(j['configuration']),'sources':sources},sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def source_delimiter(path, delimiter):
    """A source's declared separator: one of the four, or "auto" to detect it. Ambiguous files raise ValueError."""
    if delimiter not in {"auto", ",", ";", "\t", "|"}:
        raise ValueError("Choose a comma, semicolon, tab or vertical bar separator.")
    return resolve_delimiter(path, delimiter)



def discard_m4(store):
    """Remove this session's M4 job and its owned workspace; refused while its worker runs."""
    previous=store.jobs.get(session.get('m4_job'))
    if previous and previous['state']=='running':abort(400,description='Cancel the active worker before starting another job.')
    if previous:
        store.invalidate(previous)
        directory=previous['directory']
        if not directory.is_symlink() and (directory/'owner').read_text()==previous['marker']:shutil.rmtree(directory)
        store.jobs.pop(previous['id'],None)


def start_m4(store,mode):
    if mode not in {'splits','versions','advanced','before_after'}:abort(400)
    discard_m4(store)
    j=store.create(mode);session['m4_job']=j['id'];return j


def add_m4_source(store,j,upload,local,delimiter=','):
    """Admit one uploaded or data-root CSV. Raises ValueError/OSError; a rejected upload is removed."""
    path=None;owned=False
    try:
        if len(j['sources'])>= (3 if j['mode']=='splits' else 2 if j['mode'] in {'versions','before_after'} else 1):raise ValueError('This workflow already has its maximum number of input roles.')
        store.invalidate(j);owned=False
        if upload and upload.filename and local:raise ValueError('Choose an upload or a local file for this source.')
        if upload and upload.filename:
            filename=secure_filename(upload.filename) or 'source.csv';path=j['directory']/('source-'+uuid.uuid4().hex+'.csv');upload.save(path);owned=True
        elif local:
            path=Path(local).expanduser().resolve()
            if not any(path.is_relative_to(root) for root in store.roots) or not path.is_file():raise ValueError('Local file is outside the configured data roots or is not a regular CSV file; symlink escapes are rejected.')
            filename=path.name
        else:raise ValueError('Select a CSV upload or enter a local CSV path.')
        chosen=source_delimiter(path,delimiter)
        raw=inspect_source_tokens(path,'utf-8',FidelityInspectionLimits(max_bytes=65536,max_records=5,max_cells=1000),chosen)
        if not raw['headers']:raise ValueError('A readable CSV header is required.')
        j['sources'].append({'id':'source'+str(len(j['sources'])+1),'path':path,'filename':filename,'owned':owned,'signature':source_signature(path),'sha256':source_digest(path),'headers':raw['headers'],'preview':raw['records'],'delimiter':chosen,'delimiter_detected':delimiter=='auto' and chosen!=','})
        j['state']='sources'
    except (ValueError,OSError):
        if owned and path is not None and path.parent==j['directory'] and not path.is_symlink():path.unlink(missing_ok=True)
        raise


def configure_m4(store,j,form):
    """Declarations to an effective specification bound by fingerprint. Raises ValueError/OSError."""
    store.invalidate(j)
    inputs=[];mappings={}
    for i,s in enumerate(j['sources']):
        target=tuple(x.strip() for x in form.get(s['id']+'_targets','').split(',') if x.strip())
        features=tuple(x.strip() for x in form.get(s['id']+'_features','').split(',') if x.strip())
        groups=tuple(x.strip() for x in form.get(s['id']+'_groups','').split(',') if x.strip())
        kind=form.get(s['id']+'_task','dataset_profile')
        task=TaskSpec(kind,targets=target,feature_columns=features or None,group_columns=groups)
        declared=json.loads(form.get(s['id']+'_parsing','{}') or '{}')
        config=AnalysisConfig.from_dict(declared)
        if s.get('delimiter',',')!=',' and 'delimiter' not in (declared.get('parsing') or {}):
            config=replace(config,parsing=replace(config.parsing,delimiter=s['delimiter']))
        item=DatasetInput(s['id'],form.get(s['id']+'_role','dataset'),DatasetSpec(str(s['path']),source_filename=s['filename']),task,config)
        inputs.append(item);mappings[s['id']]=json.loads(form.get(s['id']+'_mapping','{}') or '{}')
    configdata=json.loads(form.get('configuration','{}') or '{}')
    if j['mode']=='advanced':
        if len(inputs)!=1:raise ValueError('Advanced standalone analysis takes one source.')
        options=AnalysisConfig.from_dict({**asdict(inputs[0].config),'execution':configdata.get('execution',{}),'advanced':configdata.get('advanced',{})})
        j['configuration']=asdict(options);j['manifest']=asdict(inputs[0]);j['spec']=inputs[0];j['config']=options
    else:
        keys=lambda field:tuple(tuple(c.strip() for c in line.split(',') if c.strip()) for line in form.get(field,'').splitlines() if line.strip())
        before_after=j['mode']=='before_after'
        transformations=json.loads(form.get('transformations','[]') or '[]') if before_after else ()
        if before_after:
            # Before is the reference and After the current version: the versions engine and its tests stay unchanged.
            inputs=[replace(item,role='reference' if i==0 else 'current') for i,item in enumerate(inputs)]
        spec=ComparisonSpec('versions' if before_after else j['mode'],tuple(inputs),column_mappings=mappings,identity_keys=keys('identity_keys'),group_keys=keys('group_keys'),evaluation_intent=form.get('evaluation_intent','unknown'),
                            preset='before_after' if before_after else None,transformations=tuple(transformations))
        config=ComparisonConfig.from_dict(configdata)
        j.update(manifest=spec_record(asdict(spec)),configuration=asdict(config),spec=spec,config=config)
    j['fields'] = dict(form)
    j['fingerprint']=m4_fingerprint(j);j['state']='confirm'


def m4_background(store,j):
    try:
        progress=lambda value:j.update(progress=value)
        owned=tuple(str(s['path']) for s in j['sources'] if s['owned'])
        if j['mode']=='advanced':
            item=j['spec'];result=analyze_scalable(item.dataset,item.task,j['config'],progress=progress,cancel=j['cancel'],owned_snapshots=owned)
        else:result=compare(j['spec'],j['config'],progress=progress,cancel=j['cancel'],owned_snapshots=owned)
        if j['cancel'].is_set():raise ValueError('Cancelled; no completed result published.')
        j.update(result=result,state='completed' if result.execution['status']=='completed' else 'partial')
    except Exception as exc:j.update(state='cancelled' if j['cancel'].is_set() else 'failed',error=str(exc))
    finally:store.lock.release()


def run_m4(store,j,fingerprint):
    """Start the confirmed job on the single local worker. Raises ValueError."""
    if j['state']!='confirm' or not j.get('fingerprint') or m4_fingerprint(j)!=j['fingerprint']:raise ValueError('Declarations or sources changed; review and confirm again.')
    if fingerprint!=j['fingerprint']:raise ValueError('The confirmation is stale.')
    if not store.lock.acquire(blocking=False):raise ValueError('One local worker is already active; cancel it or wait for completion.')
    j['cancel'].clear();j['state']='running';j['progress']={'stage':'Waiting for worker'};j.pop('error',None)
    j['thread']=threading.Thread(target=m4_background,args=(store,j),daemon=True);j['thread'].start()


def m4_artifact(j,kind):
    """The owned export for kind, generated from completed evidence on first request."""
    if kind not in {'html','pdf','json'}:abort(404)
    if 'result' not in j:abort(400,description='No completed evidence is available for export.')
    identity=j.get('artifacts',{}).get(kind)
    if identity:
        path=identity['path']
        if path.is_symlink() or source_signature(path)!=identity['signature'] or source_digest(path)!=identity['sha256']:abort(409,description='Artifact ownership changed; cached artifact was not served.')
    else:
        try:
            result=j['result'];base=j['directory']/'review'
            if kind=='json':result.write_json(base.with_suffix('.json'));locations={'json':base.with_suffix('.json')}
            else:
                bundle=result.generate_artifacts(base.with_suffix('.'+kind),format=kind);locations={k:Path(getattr(bundle,k+'_path')) for k in ('html','pdf') if getattr(bundle,k+'_path')}
            for k,path in locations.items():j.setdefault('artifacts',{})[k]={'path':path,'signature':source_signature(path),'sha256':source_digest(path)}
            identity=j['artifacts'][kind];path=identity['path']
        except Exception as exc:abort(400,description=str(exc))
    return path


def register(app,workspace,roots,default_config):
    store=Sessions(Path(workspace)/'m4',roots,default_config);store.lock=app.extensions['datatrust_worker_lock'];app.extensions['datatrust_m4_store']=store
    bp=Blueprint('m4',__name__)

    def job():
        value=store.jobs.get(session.get('m4_job'))
        if value is None:abort(400,description='This M4 session is unavailable; start a new local analysis.')
        return value

    @bp.route('/m4',methods=['GET','POST'])
    def start():
        if request.method=='POST':
            start_m4(store,request.form.get('mode'));return redirect(url_for('m4.sources'))
        return render_template('m4_ui.html',stage='start')

    @bp.route('/m4/sources',methods=['GET','POST'])
    def sources():
        j=job()
        if request.method=='POST':
            try:add_m4_source(store,j,request.files.get('dataset'),request.form.get('local_path','').strip())
            except (ValueError,OSError) as exc:flash(str(exc),'error')
            return redirect(url_for('m4.sources'))
        return render_template('m4_ui.html',stage='sources',job=j,roots=store.roots)

    @bp.route('/m4/configure',methods=['GET','POST'])
    def configure():
        j=job()
        if not j['sources']:return redirect(url_for('m4.sources'))
        if request.method=='POST':
            try:
                configure_m4(store,j,request.form);return redirect(url_for('m4.confirm'))
            except (ValueError,OSError) as exc:flash(str(exc),'error')
        return render_template('m4_ui.html',stage='configure',job=j)

    @bp.route('/m4/confirm')
    def confirm():
        j=job()
        if 'fingerprint' not in j:return redirect(url_for('m4.configure'))
        return render_template('m4_ui.html',stage='confirm',job=j,manifest=json.dumps(j['manifest'],indent=2,ensure_ascii=False),configuration=json.dumps(j['configuration'],indent=2,ensure_ascii=False))

    @bp.route('/m4/run',methods=['POST'])
    def run():
        j=job()
        try:
            run_m4(store,j,request.form.get('fingerprint'))
            return redirect(url_for('m4.result'))
        except ValueError as exc:flash(str(exc),'error');return redirect(url_for('m4.confirm'))

    @bp.route('/m4/status')
    def status():
        j=job();return jsonify(state=j['state'],progress=j['progress'],error=j.get('error'))

    @bp.route('/m4/cancel',methods=['POST'])
    def cancel():
        j=job();j['cancel'].set();return redirect(url_for('m4.result'))

    @bp.route('/m4/result')
    def result():
        j=job();return render_template('m4_ui.html',stage='result',job=j)

    @bp.route('/m4/download/<kind>')
    def download(kind):
        j=job()
        path=m4_artifact(j,kind)
        return send_file(path,as_attachment=True,download_name='numek-m4-review.'+kind)

    app.register_blueprint(bp)
