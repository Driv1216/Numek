"""Session-local M5 declarations, confirmation, supervised work and investigation."""
from dataclasses import asdict,replace
import hashlib
import json
from pathlib import Path
import threading
import uuid
from flask import Blueprint,abort,flash,jsonify,redirect,render_template,request,send_file,session,url_for
from werkzeug.utils import secure_filename
from datatrust.m4_web import Sessions
from datatrust.ingestion import source_digest,source_signature,inspect_source_tokens
from datatrust.m4_web import source_delimiter
from datatrust.contracts import FidelityInspectionLimits
from datatrust.temporal_contracts import *
from datatrust.temporal import preflight,audit_temporal
from datatrust.temporal_presentation import report_view


def names(value):return tuple(x.strip() for x in value.split(',') if x.strip())
def document(value,default):return json.loads(value) if value.strip() else default


def guided(j,fields):
    inputs=[];availability=[]
    for source in j['sources']:
        prefix=source['id']+'_';get=lambda name,default='':fields.get(prefix+name,default).strip()
        role=get('role','dataset');semantics=None
        parsing=document(get('parsing'),{})
        if source.get('delimiter',',')!=',' and isinstance(parsing,dict) and 'delimiter' not in parsing:parsing={**parsing,'delimiter':source['delimiter']}
        source_spec=TemporalSourceSpec(str(source['path']),source['format'],source_filename=source['filename'],parsing=parsing)
        if role not in {'history','schedule','expectations'}:
            clock=ClockSpec(get('clock'),kind=get('clock_kind','instant'),encoding=get('encoding','iso'),timezone=get('timezone') or None,format=get('format') or None,epoch_unit=get('epoch_unit') or None,ambiguity=get('ambiguity','unresolved'))
            measurements=[]
            for line in get('measurements').splitlines():
                if not line.strip():continue
                vals=[x.strip() for x in line.split('|')]+['']*6
                measurements.append(MeasurementSpec(vals[0],vals[1] or None,vals[2] or 'quantitative',vals[3] or None,vals[4] or None,vals[5]=='past'))
            kind=get('schedule','none');schedule=ScheduleSpec(kind,cadence_ns=get('cadence') or None,anchor=get('anchor') or None,civil_unit=get('civil_unit') or None,timezone=get('schedule_zone') or None,month_end=get('month_end','skip'),source_id=get('schedule_source') or None,time_column=get('schedule_column') or None,entity_columns=names(get('schedule_entities')),measurement_column=get('schedule_measurement') or None,expectation=get('expectation','required_record'))
            semantics=TemporalSpec(clock,tuple(measurements),observation=get('observation','measurement'),layout=get('layout','wide'),entity_columns=names(get('entities')),observation_keys=names(get('keys')),measurement_column=get('measurement_column') or None,value_column=get('value_column') or None,schedule=schedule,active_intervals=document(get('lifecycle'),[]),unique_observations=get('unique')=='yes',source_order_is_arrival=get('arrival')=='yes',dense_long=get('dense')=='yes',assessment_time=get('assessment') or None,max_adjacency_ns=get('max_gap') or None,required_lookback_ns=get('required_lookback') or None)
            method=get('timing','unknown')
            if method!='unknown':
                cutoff=ClockSpec(get('cutoff'),timezone=get('timing_zone') or None)
                availability.append(FeatureAvailabilitySpec(source['id']+'-timing',source['id'],names(get('timing_features')),cutoff,method,availability=ClockSpec(get('available'),timezone=get('timing_zone') or None) if method=='timestamp' else None,source_clock=ClockSpec(get('available'),timezone=get('timing_zone') or None) if method=='delay' else None,delay_ns=get('delay') or None,static=get('static') or None))
        task=TaskSpec(get('task','dataset_profile'),targets=names(get('targets')))
        inputs.append(TemporalInputSpec(source['id'],source_spec,semantics,role,task,AnalysisConfig.from_dict(document(get('base_config'),{}))))
    availability+=document(fields.get('availability',''),[])
    history=document(fields.get('histories',''),[])
    if fields.get('history_source','').strip():
        features=names(fields.get('history_features',''));cols=names(fields.get('history_values',''))
        if len(features)!=len(cols):raise ValueError('History feature and value-column bindings must have the same length.')
        history.append(FeatureHistorySpec('guided-history',fields['history_source'],fields['history_aux'],features,names(fields.get('history_keys','')),names(fields.get('history_aux_keys','')),dict(zip(features,cols)),ClockSpec(fields['history_available'],timezone=fields.get('history_zone') or None),ClockSpec(fields['history_cutoff'],timezone=fields.get('history_zone') or None),state_column=fields.get('history_state') or None,null_semantics=fields.get('history_null','unknown'),latest_available_required=fields.get('history_required')=='yes'))
    maturity=document(fields.get('maturity',''),[])
    if fields.get('maturity_source','').strip():
        maturity.append(OutcomeMaturitySpec(fields['maturity_source'],fields['maturity_target'],fields['maturity_assessment'],source_clock=ClockSpec(fields['maturity_clock'],timezone=fields.get('maturity_zone') or None),delay_ns=fields['maturity_delay'],fit_cutoff=fields.get('maturity_fit') or None))
    folds=document(fields.get('folds',''),[])
    if fields.get('fold_train','').strip():
        folds.append(TemporalFoldSpec('guided-fold',fields['fold_train'],fields['fold_evaluation'],chronology=fields.get('fold_chronology','none'),entity_separation=fields.get('fold_entities','none'),origin=ClockSpec(fields['fold_origin'],timezone=fields.get('fold_zone') or None) if fields.get('fold_origin') else None,lookback_ns=fields.get('fold_lookback') or None,horizon_ns=fields.get('fold_horizon') or None,purge_ns=fields.get('fold_gap') or None,fit_cutoff=fields.get('fold_fit') or None))
    return TemporalAuditSpec(tuple(inputs),tuple(availability),tuple(history),tuple(maturity),TemporalEvaluationSpec(tuple(folds)),fields.get('dataset_name') or None,fields.get('purpose') or None)


# M5 steps shared by the classic form routes and the JSON API (datatrust.api_web). `form` is any mapping
# with the classic form's field names and string values.

def m5_check_path(store,path):
    path=Path(path).expanduser().resolve()
    if not path.is_file() or not any(path.is_relative_to(root) for root in store.roots):raise ValueError('Source is outside allowed local data roots or is not a regular file.')
    return path


def m5_fingerprint(j):
    hashes={}
    for item in j['spec'].inputs:
        path=Path(item.source.path);hashes[item.id]=source_digest(path)
    payload={'effective':preflight(j['spec'],j['config']),'source_hashes':hashes}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),hashes,payload


def start_m5(store):
    old=store.jobs.get(session.get('m5_job'))
    if old:
        if old['state']=='running':abort(400,description='Cancel the active temporal audit before starting another.')
        store.invalidate(old)
    j=store.create('temporal');session['m5_job']=j['id'];return j


def add_m5_source(store,j,upload,local,fmt,delimiter=','):
    """Admit one uploaded or data-root CSV/Parquet source. Raises ValueError/OSError; a rejected upload is removed."""
    path=None;owned=False
    try:
        store.invalidate(j)
        if fmt not in {'csv','parquet'}:raise ValueError('Choose CSV or Parquet explicitly.')
        if upload and upload.filename and local:raise ValueError('Choose upload or local path for each source.')
        if upload and upload.filename:
            filename=secure_filename(upload.filename) or 'source.'+fmt;path=j['directory']/('source-'+uuid.uuid4().hex+'.'+fmt);upload.save(path);owned=True
        elif local:path=m5_check_path(store,local);filename=path.name
        else:raise ValueError('Select a source file.')
        headers=[];preview=[];chosen=','
        if fmt=='csv':
            chosen=source_delimiter(path,delimiter)
            raw=inspect_source_tokens(path,'utf-8',FidelityInspectionLimits(max_bytes=65536,max_records=5,max_cells=1000),chosen);headers=raw['headers'];preview=raw['records']
            if not headers:raise ValueError('A readable CSV header is required.')
        j['sources'].append({'id':'source'+str(len(j['sources'])+1),'path':path,'format':fmt,'filename':filename,'owned':owned,'headers':headers,'preview':preview,'signature':source_signature(path),'sha256':source_digest(path),'delimiter':chosen,'delimiter_detected':delimiter=='auto' and chosen!=','})
        j['state']='sources'
    except (ValueError,OSError):
        if owned and path is not None and path.parent==j['directory'] and not path.is_symlink():path.unlink(missing_ok=True)
        raise


def configure_m5(store,j,form):
    """Guided or manifest declarations to a fingerprinted specification. Raises ValueError/OSError/TypeError."""
    j['fields']=dict(form)
    store.invalidate(j);manifest=form.get('manifest','').strip()
    spec=TemporalAuditSpec.from_dict(json.loads(manifest)) if manifest else guided(j,j['fields'])
    registered={str(s['path'].resolve()) for s in j['sources']}
    for item in spec.inputs:
        if str(Path(item.source.path).resolve()) not in registered:m5_check_path(store,item.source.path)
    config=TemporalAnalysisConfig.from_dict(document(form.get('configuration',''),{}))
    j.update(spec=spec,config=config,manifest=spec.to_dict(),configuration=config.to_dict())
    digest,hashes,payload=m5_fingerprint(j);j.update(fingerprint=digest,source_hashes=hashes,effective=payload,state='confirm')


def m5_background(store,j):
    try:
        owned=tuple(str(s['path']) for s in j['sources'] if s['owned'])
        result=audit_temporal(j['spec'],j['config'],progress=lambda p:j.update(progress=p),cancel=j['cancel'],owned_snapshots=owned)
        if j['cancel'].is_set():raise ValueError('Cancelled; no completed result published.')
        if any(result.execution['provenance'][sid]['sha256']!=digest for sid,digest in j['source_hashes'].items()):raise ValueError('Source changed after confirmation; no completed result published.')
        j.update(result=result,state=result.execution['status'])
    except Exception as exc:j.update(state='cancelled' if j['cancel'].is_set() else 'failed',error=str(exc),failure_execution=getattr(exc,'execution',None))
    finally:store.lock.release()


def run_m5(store,j,fingerprint):
    """Start the confirmed audit on the single local worker. Raises ValueError."""
    if j['state']!='confirm' or fingerprint!=j.get('fingerprint') or m5_fingerprint(j)[0]!=j.get('fingerprint'):raise ValueError('Source, timezone data or declarations changed; review and confirm again.')
    if not store.lock.acquire(False):raise ValueError('One local M4/M5 worker is already active. Wait for completion or cancel it.')
    j['cancel'].clear();j.update(state='running',progress={'stage':'Starting supervised temporal worker'});j.pop('error',None)
    try:j['thread']=threading.Thread(target=m5_background,args=(store,j),daemon=True);j['thread'].start()
    except Exception:store.lock.release();raise


def m5_artifact(j,kind):
    """The owned export for kind, generated from completed evidence on first request."""
    if kind not in {'html','pdf','json'}:abort(404)
    if 'result' not in j:abort(400,description='No completed evidence is available.')
    try:
        identity=j.get('artifacts',{}).get(kind)
        if identity:
            path=identity['path']
            if path.is_symlink() or source_signature(path)!=identity['signature'] or source_digest(path)!=identity['sha256']:abort(409,description='Artifact ownership changed.')
        else:
            base=j['directory']/'temporal-review';result=j['result'];locations={}
            try:
                if kind=='json':result.write_json(base.with_suffix('.json'));locations={'json':base.with_suffix('.json')}
                else:
                    bundle=result.generate_artifacts(base.with_suffix('.'+kind),format=kind)
                    locations={k:Path(getattr(bundle,k+'_path')) for k in ('html','pdf') if getattr(bundle,k+'_path')}
            except Exception as exc:
                if getattr(exc,'artifacts',None):locations={k:Path(getattr(exc.artifacts,k+'_path')) for k in ('html','pdf','json') if getattr(exc.artifacts,k+'_path')}
                for k,path in locations.items():j.setdefault('artifacts',{})[k]={'path':path,'signature':source_signature(path),'sha256':source_digest(path)}
                raise
            for k,path in locations.items():j.setdefault('artifacts',{})[k]={'path':path,'signature':source_signature(path),'sha256':source_digest(path)}
            path=j['artifacts'][kind]['path']
        return path
    except (ValueError,OSError) as exc:abort(400,description=str(exc))


def m5_investigation(j,family=None,measurement=None):
    if 'result' not in j:abort(400,description='Completed evidence is required.')
    return render_template('temporal_report.html',result=j['result'].to_dict(),view=report_view(j['result'],family=family,measurement=measurement))


def register(app,workspace,roots):
    store=Sessions(Path(workspace)/'m5',roots,TemporalAnalysisConfig());store.lock=app.extensions['datatrust_worker_lock'];app.extensions['datatrust_m5_store']=store
    bp=Blueprint('m5',__name__)
    def job():
        j=store.jobs.get(session.get('m5_job'))
        if j is None:abort(400,description='Start a temporal audit in this browser session.')
        return j
    @bp.route('/temporal',methods=['GET','POST'])
    def start():
        if request.method=='POST':
            start_m5(store);return redirect(url_for('m5.sources'))
        return render_template('temporal_ui.html',stage='start')
    @bp.route('/temporal/sources',methods=['GET','POST'])
    def sources():
        j=job()
        if request.method=='POST':
            try:add_m5_source(store,j,request.files.get('dataset'),request.form.get('local_path','').strip(),request.form.get('format','csv'))
            except (ValueError,OSError) as exc:flash(str(exc),'error')
            return redirect(url_for('m5.sources'))
        return render_template('temporal_ui.html',stage='sources',job=j,roots=store.roots)
    @bp.route('/temporal/configure',methods=['GET','POST'])
    def configure():
        j=job()
        if request.method=='POST':
            try:
                configure_m5(store,j,request.form)
                return redirect(url_for('m5.confirm'))
            except (ValueError,OSError,TypeError) as exc:flash(str(exc),'error')
        return render_template('temporal_ui.html',stage='configure',job=j)
    @bp.route('/temporal/confirm')
    def confirm():
        j=job()
        if not j.get('fingerprint'):return redirect(url_for('m5.configure'))
        return render_template('temporal_ui.html',stage='confirm',job=j,effective=json.dumps(j['effective'],indent=2,ensure_ascii=False))
    @bp.route('/temporal/manifest')
    def manifest():
        j=job()
        if not j.get('manifest'):abort(400)
        return app.response_class(json.dumps(j['manifest'],indent=2),mimetype='application/json',headers={'Content-Disposition':'attachment; filename=temporal-audit.json'})
    @bp.route('/temporal/run',methods=['POST'])
    def run():
        j=job()
        try:
            run_m5(store,j,request.form.get('fingerprint'))
            return redirect(url_for('m5.result'))
        except ValueError as exc:flash(str(exc),'error');return redirect(url_for('m5.confirm'))
    @bp.route('/temporal/status')
    def status():
        j=job();return jsonify(state=j['state'],progress=j['progress'],error=j.get('error'))
    @bp.route('/temporal/cancel',methods=['POST'])
    def cancel():
        j=job();j['cancel'].set();return redirect(url_for('m5.result'))
    @bp.route('/temporal/result')
    def result():return render_template('temporal_ui.html',stage='result',job=job())
    @bp.route('/temporal/investigate')
    def investigate():
        return m5_investigation(job(),request.args.get('family') or None,request.args.get('measurement') or None)
    @bp.route('/temporal/download/<kind>')
    def download(kind):
        path=m5_artifact(job(),kind)
        return send_file(path,as_attachment=True,download_name='numek-temporal-review.'+kind)
    app.register_blueprint(bp)
