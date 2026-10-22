"""Local JSON API and app client for the NUMEK DataTrust frontend.

The API is a second transport over the same session-owned jobs as the classic form UI: it reuses the
JobStore, the `job_id` session key, and the core-flow steps in datatrust.web, with the classic form's
field names as its request contract. It only tightens access: loopback host, same origin, a per-session
CSRF header on every mutation, and JSON or multipart bodies only. Artifacts are served by the existing
ownership-checked routes (/report, /download, /download/pdf, /download/json).
"""
from dataclasses import asdict, is_dataclass
from enum import Enum
import hashlib
import hmac
import math
from pathlib import Path, PurePath
import secrets
from urllib.parse import urlsplit
import uuid

import json

from flask import Blueprint, abort, jsonify, redirect, request, send_file, send_from_directory, session
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge, default_exceptions

from datatrust.history import HistoryError
from datatrust.profiler import inspect_classification_target
from datatrust.renderer import _regression_inspection_notice, presentation_identity
from datatrust.ingestion import source_digest, source_signature
from datatrust.m4_web import add_m4_source, configure_m4, discard_m4, m4_artifact, run_m4, start_m4
from datatrust.temporal_web import add_m5_source, configure_m5, m5_artifact, m5_investigation, run_m5, start_m5
from datatrust.text_web import add_m6_source, configure_m6, m6_artifact, m6_checked, m6_evidence, m6_excerpts, names as m6_names, run_m6, start_m6
from werkzeug.datastructures import MultiDict
from datatrust.cross_web import confirm_m9, m9_action, m9_action_message, m9_artifact, m9_checked, m9_disclose, m9_import_review, m9_load_result, m9_target, preview_m9, run_m9, start_m9
from datatrust.image_web import add_m7_source, configure_m7, inspect_m7, m7_artifact, m7_checked, m7_examples, m7_pairs, m7_resolve, run_m7, start_m7
from werkzeug.utils import secure_filename
from datatrust.pdf import PDFRenderError, render_pdf_report
from datatrust.web import M3_MODES, WorkflowError, artifact_owned, configure_core, configure_m3, core_parsing, core_pdf, generate_report, set_delimiter, start_job

PREFIX = '/api/datatrust/v1'
CORE_MODES = ('classification', 'regression', 'unlabeled', *sorted(M3_MODES))
M4_LIMITS = {'splits': 3, 'versions': 2, 'advanced': 1, 'before_after': 2}
APP_BUNDLE = Path(__file__).resolve().parent / 'static' / 'app'
CLIENT_CSP = ("default-src 'self'; img-src 'self' data:; frame-src 'self'; object-src 'none'; "
              "frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
SAFE_METHODS = {'GET', 'HEAD'}


def plain(value):
    """JSON-safe copy of job state: never paths beyond a filename, never non-finite floats as JSON numbers."""
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted(plain(v) for v in value)
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else ('nan' if math.isnan(value) else 'inf' if value > 0 else '-inf')
    if isinstance(value, PurePath):
        return value.name
    if isinstance(value, Enum):
        return plain(value.value)
    if is_dataclass(value) and not isinstance(value, type):
        return plain(asdict(value))
    if hasattr(value, 'item'):
        return plain(value.item())
    return str(value)


def _warnings(job, warnings):
    regression = job['mode'] == 'regression'
    return [{**plain(w), 'notice': plain(_regression_inspection_notice(w)) if regression else None} for w in warnings or []]


def stage_of(job):
    if 'summary' in job and artifact_owned(job, 'html'):
        return 'report'
    return 'confirm' if 'target_info' in job else 'configure'


def job_view(job):
    """What the classic templates show for each stage, as data."""
    config, inspection = job['config'], job['inspection']
    view = {
        'mode': job['mode'], 'stage': stage_of(job),
        'source_filename': job['source_filename'], 'file_size': job.get('file_size'),
        'dataset_name': job.get('dataset_name'), 'purpose': job.get('purpose'), 'target': job.get('target'),
        'inspection': {**{k: plain(inspection.get(k)) for k in ('row_count', 'preview_row_count', 'column_count', 'columns', 'preview', 'target_options', 'limits')},
                       'parsing_warnings': _warnings(job, inspection.get('parsing_warnings'))},
        'config': {'parsing': plain(config.parsing), 'regression': plain(config.regression), 'fidelity_inspection': plain(config.fidelity_inspection),
                   'context': config.context.to_dict() if config.context else None},
        'delimiter_detected': bool(job.get('delimiter_detected')),
        'target_info': bounded_target(plain(job.get('target_info'))) if 'target_info' in job else None,
        'summary': None,
        'artifacts': sorted(k for k in ('html', 'pdf', 'json') if artifact_owned(job, k)),
        'saved_entry': (job.get('history') or {}).get('entry') if (job.get('history') or {}).get('json_sha256') == job.get('artifacts', {}).get('json', {}).get('sha256') else None,
    }
    if job['mode'] in M3_MODES:
        task, features, annotation = job.get('task_spec'), config.features, config.annotations
        view['m3'] = {
            'task': {'targets': list(task.targets), 'features': None if task.feature_columns is None else list(task.feature_columns),
                     'metadata': list(task.metadata_columns), 'groups': list(task.group_columns)} if task else None,
            'semantic_types': plain(features.semantic_types), 'scale_sensitive': features.scale_sensitive,
            'annotation': {'expectation': annotation.default.expectation, 'status_column': annotation.default.status_column} if annotation else None,
            'json': {'status_values': job.get('annotation_status_json') or 'null', 'per_target_annotations': job.get('per_target_annotation_json') or '{}',
                     'expectations_by_target': job.get('expectations_json') or '{}', 'feature_availability': job.get('availability_json') or '{}',
                     'multilabel_options': job.get('multilabel_json') or '{}'},
        }
    if view['stage'] == 'report':
        summary = plain(job['summary'])
        summary['parsing_warnings'] = _warnings(job, job['summary'].get('parsing_warnings'))
        view['summary'] = summary
    return view


# Canonical statements that are narrative, not findings (frontend/src/app/results/outcome-map.json "narrative_only").
NARRATIVE_ONLY = frozenset({'no_major_issues'})


def _app_build():
    """A digest of the packaged app's entry page (it names every hashed asset): which app build saved an entry."""
    index = Path(__file__).parent / 'static' / 'app' / 'index.html'
    try:
        return hashlib.sha256(index.read_bytes()).hexdigest()[:12]
    except OSError:
        return 'not recorded'


def _history_meta(analysis_path):
    """Index fields copied from the canonical JSON: display values only, never paths or row data."""
    a = json.loads(Path(analysis_path).read_text())
    values = (a.get('scoring') or {}).get('values') if (a.get('scoring') or {}).get('status') in {'computed', 'available'} else None
    context, profile, execution = a.get('context') or {}, a.get('profile') or {}, a.get('execution') or {}
    inputs = a.get('inputs') or (a.get('spec') or {}).get('inputs') or []
    names = [((i.get('dataset') or i.get('source') or {}).get('source_filename') or PurePath(str((i.get('dataset') or i.get('source') or {}).get('path', ''))).name) for i in inputs]
    single = (a.get('dataset') or {}).get('source_filename') or PurePath(str((a.get('dataset') or {}).get('path', ''))).name or None
    return {
        'presentation': {**presentation_identity(), 'app_build': _app_build()},
        'dataset_name': context.get('dataset_name') or (a.get('comparison') or {}).get('dataset_name') or profile.get('dataset_name'),
        'source_filename': context.get('source_filename') or (' ↔ '.join(names) if names else single),
        'roles': [{'id': i.get('id'), 'role': i.get('role'), 'file': n} for i, n in zip(inputs, names)],
        'source_sha256': (a.get('parsing') or {}).get('source_sha256'), 'methodology_id': a.get('methodology_id'),
        'schema_version': a.get('schema_version'), 'generated_at': a.get('generated_at'), 'target': profile.get('target'),
        'score': values['overall'] if values else None, 'risk_level': values['risk_level'] if values else None,
        'summary': {'findings': [{'code': f.get('code') or f.get('id'), 'title': f.get('title') or ' · '.join(str(f[k]).replace('_', ' ') for k in ('family', 'meaning') if f.get(k)),
                                  'severity': f.get('severity') or f.get('priority')} for f in a.get('findings') or [] if f.get('code') not in NARRATIVE_ONLY],
                    'scoring_status': (a.get('scoring') or {}).get('status'), 'scoring_reason': (a.get('scoring') or {}).get('reason'),
                    'execution_status': execution.get('status'), 'rows': execution.get('analyzed_rows'), 'columns': execution.get('analyzed_columns'),
                    'elapsed_seconds': execution.get('elapsed_seconds'), 'subtype': profile.get('classification_subtype'),
                    'narrative': {k: (a.get('narrative') or {}).get(k) for k in ('overall_assessment', 'principal_evidence_summary', 'recommended_action', 'summary')}},
    }


def _scrub(value, names):
    """Replace absolute source paths (keys of names) with their file names, anywhere in a structure."""
    if isinstance(value, dict):
        return {k: _scrub(v, names) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub(v, names) for v in value]
    return names.get(value, value) if isinstance(value, str) else value


def bounded_target(info, limit=50):
    """A target summary for the browser: the most frequent classes only (the list is ordered by count);
    class_count keeps the full total. Analysis and canonical reports still use every class."""
    if not isinstance(info, dict) or len(info.get('target_distribution') or []) <= limit:
        return info
    return {**info, 'target_distribution': info['target_distribution'][:limit]}


def names_only(value):
    """Resolved evidence for the browser: any path-valued field is reduced to its file name."""
    if isinstance(value, dict):
        return {k: (PurePath(v).name if isinstance(v, str) and 'path' in k.lower() and ('/' in v or '\\' in v) else names_only(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [names_only(v) for v in value]
    return value


def async_view(j, **extra):
    """A supervised job (M5 onward) as data: sources by file name, specification with paths reduced to names."""
    name = lambda src: src.get('filename') or PurePath(str(src['path'])).name
    names = {str(src['path']): name(src) for src in j.get('sources', [])}
    result = j.get('result')
    bound = j.get('history') or {}
    return {
        'state': j['state'],
        'sources': [{'id': src['id'], 'filename': name(src), 'format': src.get('format'), 'origin': 'upload' if src.get('owned', src['path'].parent == j.get('directory')) else 'local',
                     'headers': plain(src.get('headers') or src.get('fields') or []), 'preview': plain(src.get('preview') or []), 'sha256': src.get('sha256'),
                     'delimiter': src.get('delimiter', ','), 'delimiter_detected': bool(src.get('delimiter_detected'))} for src in j.get('sources', [])],
        'fields': j.get('fields', {}), 'fingerprint': j.get('fingerprint'),
        'manifest': _scrub(plain(j.get('manifest')), names), 'configuration': plain(j.get('configuration')),
        'effective': _scrub(plain(j.get('effective')), names),
        'progress': plain(j.get('progress') or {}), 'error': j.get('error'),
        'result': {'status': (result.execution or {}).get('status'), 'findings': len(result.findings)} if result is not None else None,
        'saved_entry': bound.get('entry'), **extra,
    }


def m4_view(j):
    names = {str(src['path']): src['filename'] for src in j['sources']}
    result = j.get('result')
    bound = j.get('history') or {}
    return {
        'mode': j['mode'], 'state': j['state'], 'limit': M4_LIMITS[j['mode']],
        'sources': [{'id': src['id'], 'filename': src['filename'], 'origin': 'upload' if src['owned'] else 'local',
                     'headers': plain(src['headers']), 'preview': plain(src['preview']), 'sha256': src['sha256'],
                     'delimiter': src.get('delimiter', ','), 'delimiter_detected': bool(src.get('delimiter_detected'))} for src in j['sources']],
        'fields': j.get('fields', {}), 'fingerprint': j.get('fingerprint'),
        'manifest': _scrub(plain(j.get('manifest')), names), 'configuration': plain(j.get('configuration')),
        'progress': plain(j.get('progress') or {}), 'error': j.get('error'),
        'result': {'status': result.execution['status'], 'findings': len(result.findings)} if result else None,
        'saved_entry': bound.get('entry'),
    }


def register(app, analysis_config, max_upload_mib, history=None, launch_token=None):
    store = app.extensions['datatrust_job_store']
    m4 = app.extensions['datatrust_m4_store']
    m5 = app.extensions['datatrust_m5_store']
    m6 = app.extensions['datatrust_m6_store']
    m7 = app.extensions['datatrust_m7_store']
    m9 = app.extensions['datatrust_m9_store']
    app.extensions['datatrust_history'] = history
    launch = {'token': launch_token}
    bp = Blueprint('datatrust_api', __name__, url_prefix=PREFIX)

    def failure(status, code, message, back=None):
        body = {'api_version': 'v1', 'error': {'code': code, 'message': message, 'request_id': uuid.uuid4().hex}}
        if back:
            body['error']['back'] = back
        return jsonify(body), status

    def ok(data, status=200):
        return jsonify({'api_version': 'v1', 'data': data}), status

    def current_job():
        job = store.get(session.get('job_id'))
        if not job:
            abort(404, description='That analysis session is no longer available. Upload the CSV again.')
        return job

    def fields():
        """The classic form's fields, as a JSON object of strings."""
        value = request.get_json(silent=True)
        if not isinstance(value, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in value.items()):
            abort(422, description='Send the analysis fields as a JSON object of text values.')
        return value

    def can_save():
        return bool(history and session.get('history_access') and history.saving)

    def record(job, pending_id=None):
        """Copy this job's ownership-verified canonical artifacts into history. Never fails the analysis."""
        kinds = {k: (job['artifacts'][k]['path'], job['artifacts'][k]['sha256']) for k in ('json', 'html') if artifact_owned(job, k)}
        if job.get('pdf_html_digest') == job.get('artifacts', {}).get('html', {}).get('sha256') and artifact_owned(job, 'pdf'):
            kinds['pdf'] = (job['artifacts']['pdf']['path'], job['artifacts']['pdf']['sha256'])
        try:
            if 'json' not in kinds or 'html' not in kinds:
                raise HistoryError('The report files were not available to save.')
            eid = history.record(workflow='core', mode=job['mode'], artifacts=kinds, meta=_history_meta(kinds['json'][0]), pending_id=pending_id)
            job['history'] = {'entry': eid, 'json_sha256': kinds['json'][1], 'pdf': 'pdf' in kinds}
            return {'saved': True, 'entry': eid}
        except (HistoryError, OSError) as exc:
            if pending_id:
                history.end(pending_id)
            return {'saved': False, 'message': str(exc) if isinstance(exc, HistoryError) else 'The analysis could not be saved to history.'}

    def sweep():
        """Attach PDFs rendered later in a live session to the saved entry of that same analysis."""
        if not history:
            return
        for job in list(store.jobs.values()):
            bound = job.get('history')
            if not bound or bound.get('pdf') or job.get('artifacts', {}).get('json', {}).get('sha256') != bound['json_sha256']:
                continue
            if job.get('pdf_html_digest') == job['artifacts'].get('html', {}).get('sha256') and artifact_owned(job, 'pdf'):
                try:
                    history.attach(bound['entry'], 'pdf', job['artifacts']['pdf']['path'], job['artifacts']['pdf']['sha256'], html_sha256=job.get('pdf_html_digest'))
                    bound['pdf'] = True
                except (HistoryError, OSError, KeyError):
                    app.logger.warning('A generated PDF could not be attached to its saved analysis.')

        # Supervised workflows: record a completed result whose run was confirmed with saving on.
        for jobs, workflow, artifact in ((m4.jobs, 'm4', m4_artifact), (m5.jobs, 'm5', m5_artifact), (m6.jobs, 'm6', m6_artifact), (m7.jobs, 'm7', m7_artifact), (m9.jobs, 'm9', lambda j, k: m9_artifact(m9, j, k))):
            for j in list(jobs.values()):
                intent = j.get('history_intent')
                if intent and j['state'] in {'failed', 'cancelled'}:
                    history.end(j.pop('history_intent'))
                elif intent and j['state'] in {'completed', 'partial'} and 'result' in j and not j.get('history'):
                    try:
                        kinds = {k: (artifact(j, k), j['artifacts'][k]['sha256']) for k in ('json', 'html')}
                        if 'pdf' in j.get('artifacts', {}):
                            kinds['pdf'] = (artifact(j, 'pdf'), j['artifacts']['pdf']['sha256'])
                        mode = j['mode'] if workflow == 'm4' else j.get('preset') or ('records_documents' if workflow == 'm9' else workflow)
                        meta = _history_meta(kinds['json'][0])
                        meta['source_filename'] = meta['source_filename'] or ' · '.join(PurePath(str(src.get('path') or (src.get('source') or {}).get('path', ''))).name for src in j.get('sources') or (j.get('spec') or {}).get('inputs', []))
                        meta['dataset_name'] = meta['dataset_name'] or j.get('dataset_name')
                        eid = history.record(workflow=workflow, mode=mode, artifacts=kinds, meta=meta, pending_id=intent)
                        j['history'] = {'entry': eid, 'json_sha256': kinds['json'][1], 'pdf': 'pdf' in kinds}
                    except (HTTPException, HistoryError, OSError):
                        history.end(intent)
                        app.logger.warning('A completed analysis could not be saved to history.')
                    j.pop('history_intent', None)
                bound = j.get('history')
                if bound and not bound['pdf'] and 'pdf' in j.get('artifacts', {}):
                    try:
                        history.attach(bound['entry'], 'pdf', artifact(j, 'pdf'), j['artifacts']['pdf']['sha256'])
                        bound['pdf'] = True
                    except (HTTPException, HistoryError, OSError, KeyError):
                        app.logger.warning('A generated PDF could not be attached to its saved analysis.')

    app.extensions['datatrust_history_sweep'] = sweep

    def saved():
        if not history:
            abort(404, description='Local history is turned off for this DataTrust session.')
        if not session.get('history_access'):
            abort(403, description='Open DataTrust from your terminal to see saved analyses.')
        return history

    @bp.before_request
    def guard():
        host = urlsplit('http://' + request.host).hostname
        if host not in {'localhost', '127.0.0.1', '::1'}:
            abort(403, description='Loopback host required.')
        origin = request.headers.get('Origin')
        if origin and origin != request.host_url.rstrip('/'):
            abort(403, description='Same origin required.')
        if request.headers.get('Sec-Fetch-Site') == 'cross-site':
            abort(403, description='Same origin required.')
        token = session.setdefault('datatrust_api_csrf', secrets.token_urlsafe(32))
        if request.method not in SAFE_METHODS:
            if not hmac.compare_digest(request.headers.get('X-CSRF-Token', ''), token):
                abort(403, description='A current CSRF token is required. Reload the page and try again.')
            if not (request.is_json or request.mimetype == 'multipart/form-data'):
                abort(415, description='Send JSON, or multipart form data for uploads.')
        try:
            sweep()
        except Exception:  # recording must never break a request; the next request or shutdown retries
            app.logger.exception('Saved-analysis sweep failed')

    @bp.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers.setdefault('X-Frame-Options', 'DENY')  # a saved report sets SAMEORIGIN for the app's viewer
        return response

    @bp.errorhandler(Exception)
    def error(exc):
        if isinstance(exc, HistoryError):
            return failure(409, 'history', str(exc))
        if isinstance(exc, WorkflowError):
            return failure(422, 'workflow', str(exc), exc.back)
        if isinstance(exc, RequestEntityTooLarge):
            return failure(413, 'too_large', f'CSV exceeds the {max_upload_mib:g} MiB local UI limit.', 'index')
        if isinstance(exc, MemoryError):
            return failure(422, 'memory', 'The dataset could not be analyzed with available memory. Try a smaller input or tighter limits.', 'confirm')
        if isinstance(exc, HTTPException):
            return failure(exc.code, f'http_{exc.code}', exc.description or exc.name)
        app.logger.exception('DataTrust API request failed')
        return failure(500, 'operation_failed', 'The request could not be completed.')

    # Flask prefers the app's code-specific handlers (the classic 400 and 413 pages) over a blueprint's
    # generic one, so the API's JSON handler is registered for every status code too.
    for status in default_exceptions:
        bp.register_error_handler(status, error)

    @bp.get('/session')
    def bootstrap():
        return ok({'csrf_token': session['datatrust_api_csrf'], 'upload_limit_bytes': app.config.get('MAX_CONTENT_LENGTH'),
                   'upload_limit_mib': max_upload_mib, 'modes': list(CORE_MODES),
                   'roots': [{'id': f'root_{i}', 'label': r.name or 'root'} for i, r in enumerate(m4.roots)]})

    @bp.get('/core/job')
    def read_job():
        job = store.get(session.get('job_id'))
        return ok({'job': job_view(job) if job else None})

    @bp.post('/core/jobs')
    def create_job():
        mode = request.form.get('mode', 'classification')
        job = start_job(store, analysis_config, mode, request.files.get('dataset'), request.form.get('delimiter', 'auto'))
        return ok({'job': job_view(job)}, 201)

    @bp.get('/core/job/context')
    def context_candidates():
        """Suggested placeholder and sentinel codes for the uploaded file (candidate_rules_v1), read in full with the
        job's parsing. Suggestions only: nothing is interpreted until it is declared."""
        from datatrust.contextual import candidates, RULES
        from datatrust.contracts import AVAILABILITY_VALUES, CONTEXT_MEANINGS, CONDITION_OPERATORS
        from datatrust.ingestion import read_csv
        job = current_job()
        try:
            data = read_csv(job['dataset_path'], options=core_parsing(job))
        except (OSError, ValueError) as exc:
            raise WorkflowError(f'The file could not be read for suggestions: {exc}', 'configure') from exc
        context = job['config'].context
        return ok({'candidates': candidates(data, [str(c) for c in data.columns]), 'rules': RULES, 'columns': [str(c) for c in data.columns],
                   'context': context.to_dict() if context else None, 'meanings': list(CONTEXT_MEANINGS),
                   'availability': list(AVAILABILITY_VALUES), 'operators': list(CONDITION_OPERATORS)})

    @bp.post('/core/job/delimiter')
    def change_delimiter():
        """Read the uploaded file again with another separator; declarations for the old columns are cleared."""
        return ok({'job': job_view(set_delimiter(current_job(), fields().get('delimiter', '')))})

    @bp.post('/core/job/configure')
    def configure():
        job = current_job()
        next_stage = (configure_m3 if job['mode'] in M3_MODES else configure_core)(job, fields())
        return ok({'next': next_stage, 'job': job_view(job)})

    @bp.post('/core/job/generate')
    def generate():
        job = current_job()
        body = fields()
        save = can_save() and body.get('save_to_history', 'yes') != 'no'
        pending = history.begin('core', job.get('dataset_name') or job['source_filename']) if save else None
        try:
            generate_report(job, body, analysis_config)
        except BaseException:
            if pending:
                history.end(pending)
            raise
        return ok({'job': job_view(job), 'history': record(job, pending) if save else {'saved': False}})

    @bp.get('/core/job/target-preview')
    def target_preview():
        # Read-only: the same inspection Configure runs on submit, so the selection panel can show it first.
        job = current_job()
        target = request.args.get('target', '')
        if job['mode'] != 'classification' or target not in job['inspection']['columns']:
            abort(422, description='Choose a target column from the uploaded dataset.')
        return ok({'target_info': bounded_target(plain(inspect_classification_target(job['dataset_path'], target, options=core_parsing(job))))})

    @bp.get('/core/job/report')
    def core_report():
        job = current_job()
        if not artifact_owned(job, 'html'):
            abort(404, description='No canonical report is available for this session.')
        return framed(send_file(job['report_path'], mimetype='text/html'))

    @bp.get('/core/job/download/<kind>')
    def core_download(kind):
        """The canonical HTML, JSON or PDF of this session's analysis, as the classic downloads name them."""
        job = current_job()
        if kind not in {'html', 'json', 'pdf'} or not artifact_owned(job, 'json' if kind == 'json' else 'html'):
            abort(404, description='No canonical report is available for this session.')
        stem = secure_filename(job.get('dataset_name') or Path(job['source_filename']).stem) or 'datatrust'
        if kind == 'json':
            return send_file(job['json_path'], mimetype='application/json', as_attachment=True, download_name='datatrust-analysis.json')
        if kind == 'html':
            return send_file(job['report_path'], mimetype='text/html', as_attachment=True, download_name=f'{stem}-reliability-report.html')
        try:
            path = core_pdf(job)
        except (PDFRenderError, ValueError) as exc:
            abort(409, description=str(exc))
        return send_file(path, mimetype='application/pdf', as_attachment=True, download_name=f'{stem}-reliability-report.pdf')

    @bp.get('/core/job/analysis')
    def analysis():
        job = current_job()
        if not artifact_owned(job, 'json'):
            abort(404, description='No canonical analysis is available for this session.')
        return send_file(job['json_path'], mimetype='application/json')

    @bp.post('/core/job/new')
    def new():
        store.remove(session.pop('job_id', None))
        return ok({'job': None})

    # ——— M4: split audit, version comparison, advanced analysis ———
    def m4_job():
        j = m4.jobs.get(session.get('m4_job'))
        if j is None:
            abort(404, description='This M4 session is unavailable; start a new local analysis.')
        return j

    @bp.get('/m4/job')
    def m4_read():
        j = m4.jobs.get(session.get('m4_job'))
        return ok({'job': m4_view(j) if j else None})

    @bp.post('/m4/start')
    def m4_start():
        return ok({'job': m4_view(start_m4(m4, fields().get('mode')))}, 201)

    @bp.post('/m4/sources')
    def m4_sources():
        j = m4_job()
        upload, local = None, ''
        if request.mimetype == 'multipart/form-data':
            upload, delimiter = request.files.get('dataset'), request.form.get('delimiter', 'auto')
        else:
            body = fields()
            delimiter = body.get('delimiter', 'auto')
            index = next((i for i in range(len(m4.roots)) if body.get('root_id') == f'root_{i}'), None)
            relative = body.get('relative_path', '').strip()
            if index is None or not relative:
                abort(422, description='Choose a data root and a CSV path inside it.')
            local = str(m4.roots[index] / relative)
        try:
            add_m4_source(m4, j, upload, local, delimiter)
        except (ValueError, OSError) as exc:
            raise WorkflowError(str(exc), 'sources') from exc
        return ok({'job': m4_view(j)})

    @bp.post('/m4/configure')
    def m4_configure():
        j = m4_job()
        if not j['sources']:
            abort(409, description='Add a source first.')
        try:
            configure_m4(m4, j, fields())
        except (ValueError, OSError) as exc:
            raise WorkflowError(str(exc), 'configure') from exc
        return ok({'job': m4_view(j)})

    @bp.post('/m4/run')
    def m4_run():
        j = m4_job()
        body = fields()
        try:
            run_m4(m4, j, body.get('fingerprint'))
        except ValueError as exc:
            raise WorkflowError(str(exc), 'confirm') from exc
        if can_save() and body.get('save_to_history', 'yes') != 'no':
            names = ' ↔ '.join(src['filename'] for src in j['sources'])
            j['history_intent'] = history.begin('m4', (j.get('fields') or {}).get('dataset_name') or names)
        return ok({'job': m4_view(j)})

    @bp.post('/m4/cancel')
    def m4_cancel():
        j = m4_job()
        j['cancel'].set()
        return ok({'job': m4_view(j)})

    @bp.get('/m4/analysis')
    def m4_analysis():
        return send_file(m4_artifact(m4_job(), 'json'), mimetype='application/json')

    @bp.get('/m4/download/<kind>')
    def m4_download(kind):
        return send_file(m4_artifact(m4_job(), kind), as_attachment=True, download_name='numek-m4-review.' + kind)

    @bp.get('/m4/report')
    def m4_report():
        response = send_file(m4_artifact(m4_job(), 'html'), mimetype='text/html')
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Content-Security-Policy'] = "frame-ancestors 'self'"
        return response

    @bp.post('/m4/new')
    def m4_new():
        discard_m4(m4)
        session.pop('m4_job', None)
        return ok({'job': None})

    # ——— M5: temporal reliability ———
    def m5_job():
        j = m5.jobs.get(session.get('m5_job'))
        if j is None:
            abort(404, description='Start a temporal audit in this browser session.')
        return j

    def local_path(roots, body):
        index = next((i for i in range(len(roots)) if body.get('root_id') == f'root_{i}'), None)
        relative = body.get('relative_path', '').strip()
        if index is None or not relative:
            abort(422, description='Choose a data root and a file path inside it.')
        return str(roots[index] / relative)

    @bp.get('/temporal/job')
    def m5_read():
        j = m5.jobs.get(session.get('m5_job'))
        return ok({'job': async_view(j) if j else None})

    @bp.post('/temporal/start')
    def m5_start():
        fields()
        return ok({'job': async_view(start_m5(m5))}, 201)

    @bp.post('/temporal/sources')
    def m5_sources():
        j = m5_job()
        if request.mimetype == 'multipart/form-data':
            upload, local, fmt, delimiter = request.files.get('dataset'), '', request.form.get('format', 'csv'), request.form.get('delimiter', 'auto')
        else:
            body = fields()
            upload, local, fmt, delimiter = None, local_path(m5.roots, body), body.get('format', 'csv'), body.get('delimiter', 'auto')
        try:
            add_m5_source(m5, j, upload, local, fmt, delimiter)
        except (ValueError, OSError) as exc:
            raise WorkflowError(str(exc), 'sources') from exc
        return ok({'job': async_view(j)})

    @bp.post('/temporal/configure')
    def m5_configure():
        j = m5_job()
        try:
            configure_m5(m5, j, fields())
        except (ValueError, OSError, TypeError) as exc:
            raise WorkflowError(str(exc), 'configure') from exc
        return ok({'job': async_view(j)})

    @bp.post('/temporal/run')
    def m5_run():
        j = m5_job()
        body = fields()
        try:
            run_m5(m5, j, body.get('fingerprint'))
        except ValueError as exc:
            raise WorkflowError(str(exc), 'confirm') from exc
        if can_save() and body.get('save_to_history', 'yes') != 'no':
            j['history_intent'] = history.begin('m5', (j.get('fields') or {}).get('dataset_name') or ' · '.join(src['filename'] for src in j['sources']))
        return ok({'job': async_view(j)})

    @bp.post('/temporal/cancel')
    def m5_cancel():
        j = m5_job()
        j['cancel'].set()
        return ok({'job': async_view(j)})

    @bp.get('/temporal/analysis')
    def m5_analysis():
        return send_file(m5_artifact(m5_job(), 'json'), mimetype='application/json')

    def framed(response):
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Content-Security-Policy'] = "frame-ancestors 'self'"
        return response

    @bp.get('/temporal/download/<kind>')
    def m5_download(kind):
        return send_file(m5_artifact(m5_job(), kind), as_attachment=True, download_name='numek-temporal-review.' + kind)

    @bp.get('/temporal/report')
    def m5_report():
        return framed(send_file(m5_artifact(m5_job(), 'html'), mimetype='text/html'))

    @bp.get('/temporal/investigate')
    def m5_investigate():
        html = m5_investigation(m5_job(), request.args.get('family') or None, request.args.get('measurement') or None)
        return framed(app.response_class(html, mimetype='text/html'))

    @bp.post('/temporal/new')
    def m5_new():
        j = m5.jobs.get(session.get('m5_job'))
        if j:
            if j['state'] == 'running':
                abort(409, description='Cancel the active temporal audit before starting another.')
            m5.invalidate(j)
            m5.jobs.pop(j['id'], None)
        session.pop('m5_job', None)
        return ok({'job': None})

    # ——— M6: text reliability ———
    def m6_job():
        j = m6.jobs.get(session.get('m6_job'))
        if j is None:
            abort(404, description='Start a text audit in this session.')
        return j

    def multi_fields():
        """The classic form's fields as JSON: text values, or lists of text for repeated rows."""
        value = request.get_json(silent=True)
        ok_value = lambda v: isinstance(v, str) or (isinstance(v, list) and all(isinstance(x, str) for x in v))
        if not isinstance(value, dict) or not all(isinstance(k, str) and ok_value(v) for k, v in value.items()):
            abort(422, description='Send the declarations as a JSON object of text values or lists of text.')
        return MultiDict([(k, x) for k, v in value.items() for x in (v if isinstance(v, list) else [v])])

    def m6_view(j):
        from datatrust.text_contracts import ExecutionOptions, TextWorkLimits
        return async_view(j, preset=j.get('preset'), form_values=j.get('form_values') or {}, assets=[PurePath(str(a)).name for a in j.get('asset_uploads', [])],
                          execution_defaults={k: v for k, v in asdict(ExecutionOptions()).items() if k not in {'scratch_directory', 'backend'}},
                          limit_defaults=asdict(TextWorkLimits()))

    @bp.get('/text/job')
    def m6_read():
        j = m6.jobs.get(session.get('m6_job'))
        return ok({'job': m6_view(j) if j else None})

    @bp.post('/text/start')
    def m6_start():
        return ok({'job': m6_view(start_m6(m6, fields().get('preset', 'corpus')))}, 201)

    @bp.post('/text/sources')
    def m6_sources():
        j = m6_job()
        if request.mimetype == 'multipart/form-data':
            form, upload = request.form, request.files.get('dataset')
        else:
            body = fields()
            form, upload = MultiDict({**body, 'local_path': local_path(m6.roots, body)}), None
        try:
            add_m6_source(m6, j, form, upload)
        except Exception as exc:
            raise WorkflowError(str(exc) if isinstance(exc, ValueError) else 'Source could not be loaded.', 'sources') from exc
        return ok({'job': m6_view(j)})

    @bp.post('/text/configure')
    def m6_configure():
        j = m6_job()
        try:
            configure_m6(m6, j, multi_fields())
        except HTTPException:
            raise
        except Exception as exc:
            raise WorkflowError(str(exc) if isinstance(exc, ValueError) else 'Declarations could not be confirmed.', 'configure') from exc
        return ok({'job': m6_view(j)})

    @bp.post('/text/run')
    def m6_run():
        j = m6_job()
        body = fields()
        if body.get('fingerprint') != j.get('fingerprint'):
            raise WorkflowError('The confirmation is stale.', 'confirm')
        run_m6(m6, j, 'yes')
        if can_save() and body.get('save_to_history', 'yes') != 'no':
            j['history_intent'] = history.begin('m6', ' · '.join(PurePath(str(src['path'])).name for src in j['sources']))
        return ok({'job': m6_view(j)})

    @bp.post('/text/cancel')
    def m6_cancel():
        j = m6_job()
        j['cancel'].set()
        return ok({'job': m6_view(j)})

    @bp.get('/text/analysis')
    def m6_analysis():
        return send_file(m6_artifact(m6_job(), 'json'), mimetype='application/json')

    @bp.get('/text/download/<kind>')
    def m6_download(kind):
        return send_file(m6_artifact(m6_job(), kind), as_attachment=True)

    @bp.get('/text/report')
    def m6_report():
        return framed(send_file(m6_checked(m6_job(), 'html'), mimetype='text/html'))

    @bp.post('/text/evidence')
    def m6_reveal():
        """Exact local evidence for one reference; content only when reveal is asked for explicitly."""
        j, body = m6_job(), fields()
        if j.get('state') != 'completed':
            abort(400, description='Completed evidence is required.')
        try:
            value = m6_evidence(m6, j, body.get('reference', ''), body.get('reveal') == 'yes')
        except HTTPException:
            raise
        except Exception as exc:
            return failure(409, 'changed_or_unavailable', f'The evidence changed or is unavailable ({getattr(exc, "code", type(exc).__name__)}). Reconfirm the audit.')
        return ok({'resolved': names_only(plain(value))})

    @bp.post('/text/export-excerpts')
    def m6_export():
        return send_file(m6_excerpts(m6, m6_job(), m6_names(fields().get('references', ''))), as_attachment=True)

    @bp.post('/text/new')
    def m6_new():
        j = m6.jobs.get(session.get('m6_job'))
        if j:
            if j['state'] == 'running':
                abort(409, description='Cancel the active text audit before starting another.')
            m6.invalidate(j)
            m6.jobs.pop(j['id'], None)
        session.pop('m6_job', None)
        return ok({'job': None})

    # ——— M7: image reliability ———
    def m7_job():
        j = m7.jobs.get(session.get('m7_job'))
        if j is None:
            abort(404, description='Start an image audit in this session.')
        return j

    def m7_view(j):
        paths = {}
        for item in j['sources']:
            src = item.get('source') or {}
            for key in ('path', 'asset_root'):
                if src.get(key):
                    paths[str(src[key])] = PurePath(str(src[key])).name
        result = j.get('result')
        config = j.get('config')
        return {
            'state': j['state'], 'phase': j.get('phase'), 'preset': j.get('preset'), 'inspected': bool(j.get('inspected')), 'preview': plain(j.get('preview')),
            'sources': [{**_scrub(plain(item), paths), 'filename': PurePath(str((item.get('source') or {}).get('path', ''))).name, 'format': (item.get('source') or {}).get('format'),
                         'origin': 'upload' if str((item.get('source') or {}).get('path', '')).startswith(str(j['directory'])) else 'local', 'headers': [], 'preview': [], 'sha256': None} for item in j['sources']],
            'fields': j.get('form_values') or {}, 'fingerprint': j.get('fingerprint') if j['state'] in {'confirm', 'running', 'completed', 'failed', 'cancelled'} else None,
            'manifest': {k: v for k, v in _scrub(plain(j['spec'].to_dict()), paths).items() if k != 'allowed_roots'} if j.get('spec') is not None else None, 'configuration': plain(config.to_dict()) if config is not None else None, 'effective': None,
            'max_seconds': config.execution.max_seconds if config is not None else None,
            'progress': plain(j.get('progress') or {}), 'error': j.get('error'),
            'result': {'status': 'completed', 'findings': len(result.findings)} if result is not None and j['state'] == 'completed' else None,
            'saved_entry': (j.get('history') or {}).get('entry'),
        }

    def root_path(roots, body, key):
        if not body.get(key, '').strip():
            return ''
        return local_path(roots, {'root_id': body.get('root_id', ''), 'relative_path': body[key]})

    @bp.get('/images/job')
    def m7_read():
        j = m7.jobs.get(session.get('m7_job'))
        return ok({'job': m7_view(j) if j else None})

    @bp.post('/images/start')
    def m7_start():
        return ok({'job': m7_view(start_m7(m7, fields().get('preset', 'directory')))}, 201)

    @bp.post('/images/sources')
    def m7_sources():
        j = m7_job()
        if request.mimetype == 'multipart/form-data':
            form, upload = request.form, request.files.get('manifest')
        else:
            body = fields()
            form = MultiDict({k: v for k, v in body.items() if k not in {'root_id', 'relative_path', 'asset_relative'}})
            form['local_path'] = local_path(m7.roots, body)
            if body.get('asset_relative', '').strip():
                form['asset_root'] = root_path(m7.roots, body, 'asset_relative')
            upload = None
        try:
            add_m7_source(m7, j, form, upload)
        except Exception as exc:
            raise WorkflowError(str(exc) if isinstance(exc, ValueError) else 'Source is outside permitted roots or unavailable.', 'sources') from exc
        return ok({'job': m7_view(j)})

    @bp.post('/images/inspect')
    def m7_inspect():
        j = m7_job()
        fields()
        inspect_m7(m7, j)
        j['phase'] = 'inspect'
        return ok({'job': m7_view(j)})

    @bp.post('/images/configure')
    def m7_configure():
        j = m7_job()
        try:
            configure_m7(m7, j, fields())
        except HTTPException:
            raise
        except Exception as exc:
            raise WorkflowError(str(exc) if isinstance(exc, ValueError) else 'Declarations could not be confirmed.', 'configure') from exc
        j['phase'] = 'prepare'
        return ok({'job': m7_view(j)})

    @bp.post('/images/run')
    def m7_run():
        j = m7_job()
        body = fields()
        if body.get('fingerprint') != j.get('fingerprint'):
            raise WorkflowError('The confirmation is stale.', 'confirm')
        run_m7(m7, j, 'yes')
        j['phase'] = 'run'
        if can_save() and body.get('save_to_history', 'yes') != 'no':
            j['history_intent'] = history.begin('m7', j.get('dataset_name') or ' · '.join(PurePath(str((i.get('source') or {}).get('path', ''))).name for i in j['sources']))
        return ok({'job': m7_view(j)})

    @bp.post('/images/cancel')
    def m7_cancel():
        j = m7_job()
        j['cancel'].set()
        return ok({'job': m7_view(j)})

    @bp.get('/images/analysis')
    def m7_analysis():
        return send_file(m7_artifact(m7_job(), 'json'), mimetype='application/json')

    @bp.get('/images/download/<kind>')
    def m7_download(kind):
        return send_file(m7_artifact(m7_job(), kind), as_attachment=True)

    @bp.get('/images/report')
    def m7_report():
        return framed(send_file(m7_checked(m7_job(), 'html'), mimetype='text/html'))

    @bp.get('/images/pairs')
    def m7_pair_list():
        references, pairs = m7_pairs(m7_job())
        return ok({'references': references, 'pairs': plain(pairs)})

    @bp.post('/images/resolve')
    def m7_reveal():
        """Verified local images for up to two references; labels and overlays only when asked for."""
        j, body = m7_job(), fields()
        references = [r for r in body.get('references', '').split(',') if r][:2]
        options = {'overlays': body.get('overlays') == 'yes', 'labels': body.get('labels') == 'yes'}
        if j.get('state') != 'completed':
            abort(400, description='Completed evidence is required.')
        try:
            resolved = [m7_resolve(m7, j, ref, options) for ref in references]
        except HTTPException:
            raise
        except Exception:
            return failure(409, 'changed_or_unavailable', 'Evidence changed, is unavailable, or has an unresolved overlay frame.')
        return ok({'resolved': names_only(plain(resolved))})

    @bp.post('/images/export-examples')
    def m7_export():
        body = fields()
        return send_file(m7_examples(m7, m7_job(), [r for r in body.get('references', '').split(',') if r], body.get('overlays') == 'yes', body.get('labels') == 'yes'), as_attachment=True)

    @bp.post('/images/new')
    def m7_new():
        j = m7.jobs.get(session.get('m7_job'))
        if j:
            if j['state'] == 'running':
                abort(409, description='Cancel the active image audit before starting another.')
            m7.invalidate(j)
            m7.jobs.pop(j['id'], None)
        session.pop('m7_job', None)
        return ok({'job': None})

    # ——— M9: records ↔ documents ———
    def m9_job():
        j = m9.jobs.get(session.get('m9_job'))
        if j is None:
            abort(404, description='Start an M9 audit.')
        return j

    def m9_view(j):
        paths = {}
        for item in j['spec'].get('inputs', []):
            for key in ('path', 'asset_root'):
                if item.get(key):
                    paths[str(item[key])] = PurePath(str(item[key])).name
        result = j.get('result')
        reviews = j.get('reviews')
        entries = getattr(reviews, 'entries', None) or {}
        return {
            'state': j['state'], 'phase': j.get('phase'),
            'spec': {k: v for k, v in _scrub(plain(j['spec']), paths).items() if k != 'allowed_roots'}, 'config': plain(j.get('config') or {}),
            'sources': [{'id': i['id'], 'filename': PurePath(str(i['path'])).name, 'format': i.get('format'), 'kind': i.get('kind'), 'role': i.get('role'),
                         'origin': 'upload' if str(i['path']).startswith(str(j['directory'])) else 'local', 'headers': [], 'preview': [], 'sha256': None} for i in j['spec'].get('inputs', [])],
            'preview': names_only(plain(j.get('preview'))), 'fields': {k: v for k, v in (j.get('form_values') or {}).items() if not k.endswith('_json')},
            'fingerprint': (j.get('sealed') or {}).get('spec') if j['state'] in {'confirm', 'running', 'completed', 'failed', 'cancelled'} else None,
            'sealed_models': plain((j.get('sealed') or {}).get('models')), 'manifest': None, 'configuration': None, 'effective': None,
            'progress': names_only(plain(j.get('progress') or {})), 'error': j.get('error'),
            'result': {'status': 'completed', 'findings': len(result.findings)} if result is not None and j['state'] == 'completed' else None,
            'reviews': {k: {kk: vv for kk, vv in plain(v).items() if kk in {'disposition', 'note'}} for k, v in entries.items()} if isinstance(entries, dict) else {},
            'saved_entry': (j.get('history') or {}).get('entry'),
        }

    @bp.get('/cross/job')
    def m9_read():
        j = m9.jobs.get(session.get('m9_job'))
        return ok({'job': m9_view(j) if j else None})

    @bp.post('/cross/start')
    def m9_start():
        fields()
        return ok({'job': m9_view(start_m9(m9))}, 201)

    @bp.post('/cross/action')
    def m9_do():
        """One guided configure action, with the classic action field names."""
        j = m9_job()
        if request.mimetype == 'multipart/form-data':
            values, upload = request.form, request.files.get('source')
        else:
            body = fields()
            values, upload = MultiDict(body), None
            if body.get('action') == 'source' and body.get('relative_path', '').strip():
                values['path'] = local_path(m9.roots, body)
                if body.get('asset_relative', '').strip():
                    values['asset_root'] = local_path(m9.roots, {'root_id': body.get('root_id', ''), 'relative_path': body['asset_relative']})
        if j['state'] in {'confirm', 'completed'}:
            j['state'] = 'configure'
        try:
            m9_action(m9, j, values, upload)
        except Exception as exc:
            raise WorkflowError(m9_action_message(exc), 'configure') from exc
        return ok({'job': m9_view(j)})

    @bp.post('/cross/preview')
    def m9_preview():
        j = m9_job()
        fields()
        preview_m9(m9, j)
        j['phase'] = 'preview'
        return ok({'job': m9_view(j)})

    @bp.post('/cross/seal')
    def m9_seal():
        j = m9_job()
        fields()
        confirm_m9(m9, j)
        j['phase'] = 'seal'
        return ok({'job': m9_view(j)})

    @bp.post('/cross/run')
    def m9_run():
        j = m9_job()
        body = fields()
        if body.get('fingerprint') != (j.get('sealed') or {}).get('spec'):
            raise WorkflowError('The confirmation is stale.', 'confirm')
        run_m9(m9, j)
        j['phase'] = 'run'
        if can_save() and body.get('save_to_history', 'yes') != 'no':
            j['history_intent'] = history.begin('m9', ' · '.join(PurePath(str(i['path'])).name for i in j['spec'].get('inputs', [])))
        return ok({'job': m9_view(j)})

    @bp.post('/cross/cancel')
    def m9_cancel():
        j = m9_job()
        j['cancel'].set()
        return ok({'job': m9_view(j)})

    @bp.get('/cross/analysis')
    def m9_analysis():
        return send_file(m9_artifact(m9, m9_job(), 'json'), mimetype='application/json')

    @bp.get('/cross/download/<kind>')
    def m9_download(kind):
        response = send_file(m9_artifact(m9, m9_job(), kind), as_attachment=True)
        if kind == 'review':
            response.headers['Cache-Control'] = 'no-store'
        return response

    @bp.get('/cross/spec')
    def m9_specification():
        """The current declarations for re-import, as a local download (it names the local source paths)."""
        response = jsonify(m9_job()['spec'])
        response.headers['Content-Disposition'] = 'attachment; filename=cross-specification.json'
        return response

    @bp.get('/cross/report')
    def m9_report():
        return framed(send_file(m9_checked(m9, m9_job(), 'html'), mimetype='text/html'))

    @bp.post('/cross/investigate')
    def m9_investigate():
        """Exact local evidence for one review target: excerpts, locators, context and the frozen rule."""
        j, body = m9_job(), fields()
        if j['state'] != 'completed':
            abort(409, description='Completed evidence is required.')
        m9_target(m9, j, body.get('target', ''))
        return ok({'target': j['view_target'], 'evidence': names_only(plain(j['view'])), 'context': names_only(plain(j.get('view_context'))), 'rule': plain(j.get('view_rule'))})

    @bp.post('/cross/review')
    def m9_review():
        j, body = m9_job(), fields()
        if j['state'] != 'completed':
            abort(409, description='Completed evidence is required.')
        j['reviews'].set(body.get('target', '').strip(), body.get('disposition', '').strip(), body.get('note', ''))
        return ok({'job': m9_view(j)})

    @bp.post('/cross/import-review')
    def m9_import():
        j = m9_job()
        if request.mimetype == 'multipart/form-data' and request.files.get('review'):
            raw = request.files['review'].read(32 * 1024 ** 2 + 1)
        else:
            raw = fields().get('review_json', '').strip().encode()
        m9_import_review(j, raw)
        return ok({'job': m9_view(j)})

    @bp.post('/cross/load-result')
    def m9_reopen():
        """Reopen a completed result with its private manifest, supplied by the user (multipart: report, private)."""
        j = m9.jobs.get(session.get('m9_job')) or start_m9(m9)
        if request.mimetype != 'multipart/form-data' or 'report' not in request.files or 'private' not in request.files:
            abort(400, description='Completed report/manifest binding differs.')
        m9_load_result(m9, j, request.files['report'].read(32 * 1024 ** 2 + 1), request.files['private'].read(64 * 1024 ** 2 + 1))
        j['phase'] = 'run'
        return ok({'job': m9_view(j)})

    @bp.post('/cross/disclose')
    def m9_disclosure():
        body = fields()
        split = lambda k: [r for r in body.get(k, '').split(',') if r]
        return send_file(m9_disclose(m9, m9_job(), split('excerpt_refs'), split('image_refs')), as_attachment=True)

    @bp.post('/cross/new')
    def m9_new():
        j = m9.jobs.get(session.get('m9_job'))
        if j:
            if j['state'] == 'running':
                abort(409, description='Cancel the active audit before starting another.')
            m9.invalidate(j)
            m9.jobs.pop(j['id'], None)
        session.pop('m9_job', None)
        return ok({'job': None})

    @bp.get('/history/state')
    def history_state():
        if not history:
            return ok({'enabled': False})
        if not session.get('history_access'):
            return ok({'enabled': True, 'access': False})
        home = str(Path.home())
        where = str(history.root)
        return ok({'enabled': True, 'access': True, **history.settings(), **history.usage(), 'interrupted': history.interrupted(),
                   'location': '~' + where[len(home):] if where.startswith(home) else where})

    @bp.post('/history/choice')
    def history_choice():
        value = fields().get('saving')
        return ok(saved().set_settings(saving=value))

    @bp.post('/history/settings')
    def history_settings():
        body = fields()
        def limit(name, scale=1):
            if name not in body:
                return ...
            text = body[name].strip()
            if not text:
                return None
            if not text.isdigit() or int(text) < 1:
                abort(422, description='Retention limits must be positive whole numbers, or left empty to keep everything.')
            return int(text) * scale
        return ok(saved().set_settings(max_age_days=limit('max_age_days'), max_total_bytes=limit('max_total_mib', 1024 * 1024)))

    @bp.get('/history')
    def history_list():
        h = saved()
        try:
            cursor = max(0, int(request.args.get('cursor', '0')))
        except ValueError:
            abort(422, description='Invalid cursor.')
        return ok(h.search(q=request.args.get('q', '')[:200], workflow=request.args.get('workflow') or None, risk=request.args.get('risk') or None,
                           date_from=request.args.get('from') or None, date_to=request.args.get('to') or None, cursor=cursor, limit=50))

    def entry_or_404(eid):
        try:
            return saved().verify(eid)
        except KeyError:
            abort(404, description='That saved analysis no longer exists.')

    @bp.get('/history/<eid>')
    def history_entry(eid):
        view = entry_or_404(eid)
        job = store.get(session.get('job_id'))
        live = bool(job and (job.get('history') or {}).get('entry') == eid and artifact_owned(job, 'html')
                    and job['artifacts']['json']['sha256'] == job['history']['json_sha256'])
        return ok({**view, 'live': live})

    def saved_file(eid, kind):
        entry_or_404(eid)
        try:
            return saved().file(eid, kind)
        except KeyError:
            abort(404, description='That file was not saved with this analysis.')

    @bp.get('/history/<eid>/analysis')
    def history_analysis(eid):
        return send_file(saved_file(eid, 'json'), mimetype='application/json')

    @bp.get('/history/<eid>/report')
    def history_report(eid):
        response = send_file(saved_file(eid, 'html'), mimetype='text/html')
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Content-Security-Policy'] = "frame-ancestors 'self'"
        return response

    @bp.get('/history/<eid>/download/<kind>')
    def history_download(eid, kind):
        if kind not in {'html', 'pdf', 'json'}:
            abort(404)
        view = entry_or_404(eid)
        stem = ''.join(c if c.isalnum() or c in '-_' else '-' for c in (view['dataset_name'] or 'datatrust')).strip('-') or 'datatrust'
        name = {'html': f'{stem}-reliability-report.html', 'pdf': f'{stem}-reliability-report.pdf', 'json': 'datatrust-analysis.json'}[kind]
        return send_file(saved_file(eid, kind), as_attachment=True, download_name=name)

    @bp.post('/history/<eid>/pdf')
    def history_pdf(eid):
        """A PDF of a saved analysis, rendered from its verified saved HTML; no dataset is needed."""
        entry_or_404(eid)
        try:
            view = saved().generate_pdf(eid, render_pdf_report)
        except KeyError:
            abort(404, description='That saved analysis no longer exists.')
        except PDFRenderError as exc:
            return failure(409, 'pdf', f'{exc} The saved HTML report is unchanged.')
        return ok(view)

    @bp.post('/history/<eid>/delete')
    def history_delete(eid):
        try:
            saved().delete(eid)
        except KeyError:
            abort(404, description='That saved analysis no longer exists.')
        return ok({'deleted': eid})

    @bp.post('/history/clear')
    def history_clear():
        if fields().get('confirm') != 'delete-all':
            abort(422, description='Confirm that every saved analysis should be deleted.')
        return ok({'deleted': saved().clear()})

    @bp.post('/history/pending/<pid>/dismiss')
    def history_dismiss(pid):
        saved().dismiss(pid)
        return ok({'dismissed': pid})

    app.register_blueprint(bp)

    client = Blueprint('datatrust_client', __name__)

    @client.after_request
    def client_headers(response):
        response.headers['Content-Security-Policy'] = CLIENT_CSP
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        return response

    @client.get('/app/')
    @client.get('/app/<path:subpath>')
    def shell(subpath=''):
        # The launch link printed or opened by `datatrust ui` unlocks history for this browser, once.
        offered = request.args.get('launch')
        if offered is not None:
            if launch['token'] and hmac.compare_digest(offered, launch['token']):
                session['history_access'] = True
                launch['token'] = None
            return redirect(request.path, code=303)
        if not (APP_BUNDLE / 'index.html').is_file():
            return 'The DataTrust app bundle is not built. Run "npm run build:app" in frontend/.', 503, {'Content-Type': 'text/plain; charset=utf-8'}
        if subpath.startswith('assets/'):
            return send_from_directory(APP_BUNDLE / 'assets', subpath.removeprefix('assets/'), max_age=31536000)
        response = send_from_directory(APP_BUNDLE, 'index.html', max_age=0)
        response.headers['Cache-Control'] = 'no-store'
        return response

    app.register_blueprint(client)
