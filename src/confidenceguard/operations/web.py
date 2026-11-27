"""The ingestion HTTP surface (S4). The full operations API, sessions and console are S9.

Every call is authenticated with a service token (``Authorization: Bearer nmk_...``) scoped to one
source (``ingest:source:<id>``) or deployment (``ingest:deployment:<id>``). Responses use the
ConfidenceGuard envelope (``{"data": ...}`` / ``{"error": {"code", "message"}}``). Request bodies are
never logged or echoed.

    POST /api/ops/v1/sources/<source>/batches            body = the batch; headers Numek-Batch-Id (required),
                                                         Numek-Mode, Numek-Dropped-Rows, Numek-Declared-Identity
    GET  /api/ops/v1/sources/<source>/batches/<batch_id>  batch status and counts
    POST /api/ops/v1/sources/<source>/watermark          {"through": instant}
    POST /api/ops/v1/deployments/<id>/events             {"kind", "at", "identity", "detail"}
    POST /api/ops/v1/deployments/<id>/statements         {"statement": {...}, "signature": base64}
    GET  /healthz
"""
import json

from ..contracts import EvaluationError
from . import identity, ingest

STATUS = {'unauthenticated': 401, 'forbidden': 403, 'unknown_source': 404, 'unknown_deployment': 404, 'unknown_batch': 404,
          'batch_conflict': 409, 'batch_too_large': 413, 'backpressure': 429, 'platform_unavailable': 503,
          'storage_full': 507}


def create_app(installation):
    from flask import Flask, jsonify, request
    app = Flask('numek-ops-ingest')
    app.config['MAX_CONTENT_LENGTH'] = ingest.MAX_BATCH_BYTES

    def fail(exc):
        code = getattr(exc, 'code', 'failed')
        response = jsonify({'error': {'code': code, 'message': str(exc)[:300]}})
        response.status_code = STATUS.get(code, 400)
        if code in ('backpressure', 'storage_full', 'platform_unavailable'):
            response.headers['Retry-After'] = '30'
        return response

    def auth():
        header = request.headers.get('Authorization', '')
        if not header.startswith('Bearer '):
            raise EvaluationError('A bearer token is required.', 'unauthenticated')
        return ingest.authenticate(installation, header[7:].strip())

    def body_json():
        value = request.get_json(silent=True)
        if not isinstance(value, dict):
            raise EvaluationError('A JSON object body is required.', 'invalid_request')
        return value

    @app.errorhandler(EvaluationError)
    def evaluation_error(exc):
        return fail(exc)

    from numek_platform.errors import PlatformError

    @app.errorhandler(PlatformError)
    def platform_error(exc):          # for example the database being unavailable before a handler translated it
        return fail(exc)

    @app.errorhandler(413)
    def too_large(_exc):
        return fail(EvaluationError('Batch exceeds the size admission.', 'batch_too_large'))

    @app.get('/healthz')
    def health():
        with installation.db.connect() as conn:
            conn.execute('SELECT 1')
        return jsonify({'data': {'status': 'ok'}})

    @app.post('/api/ops/v1/sources/<source>/batches')
    def batches(source):
        principal = auth()
        batch_id = request.headers.get('Numek-Batch-Id')
        if not batch_id:
            raise EvaluationError('Numek-Batch-Id is required.', 'invalid_batch')
        try:
            dropped = int(request.headers.get('Numek-Dropped-Rows', '0'))
            declared = json.loads(request.headers.get('Numek-Declared-Identity', '{}'))
        except ValueError as exc:
            raise EvaluationError('Invalid batch headers.', 'invalid_batch') from exc
        receipt = ingest.receive(installation, source, batch_id, request.get_data(cache=False), auth=principal,
                                 mode=request.headers.get('Numek-Mode', 'live'), declared_identity=declared,
                                 producer_dropped=dropped)
        response = jsonify({'data': receipt})
        response.status_code = 202
        return response

    @app.get('/api/ops/v1/sources/<source>/batches/<path:batch_id>')
    def batch_status(source, batch_id):
        return jsonify({'data': ingest.status(installation, source, batch_id, auth=auth())})

    @app.post('/api/ops/v1/sources/<source>/watermark')
    def watermark(source):
        return jsonify({'data': ingest.declare_watermark(installation, source, body_json().get('through'), auth=auth())})

    @app.post('/api/ops/v1/deployments/<deployment>/events')
    def events(deployment):
        principal, value = auth(), body_json()
        return jsonify({'data': ingest.record_deployment_event(installation, deployment, value.get('kind'), value.get('at'),
                                                              identity=value.get('identity'), detail=value.get('detail'),
                                                              auth=principal)})

    @app.post('/api/ops/v1/deployments/<deployment>/statements')
    def statements(deployment):
        principal, value = auth(), body_json()
        ingest._authorize(installation, principal, 'ingest', 'deployment', deployment)
        return jsonify({'data': identity.verify_signed_statement(installation, deployment, value.get('statement'),
                                                                 value.get('signature', ''))})

    return app
