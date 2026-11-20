"""Ingestion: durable receipt of encrypted raw batches, then parse, minimize, check, quarantine and publish.

Commit points (plan H.4):

* **Receive.** The raw body is encrypted with the day's data key (AES-256-GCM,
  random object id, so object names reveal nothing about the plaintext) and made
  durable (W1-W3). One transaction then activates it, records the batch
  (``received``) and enqueues its processing job; only after that commit is the
  batch acknowledged (HTTP 202). A repeated (source, batch id) with the same bytes
  returns the same receipt; different bytes refuse (``batch_conflict``, 409). A
  crash before the commit leaves only a pending object, which GC reclaims.
* **Process.** Decrypt, parse, keep only declared fields (undeclared ones are
  dropped and counted), check every row, quarantine failing rows (encrypted,
  minimized, with reasons and field names), and publish the accepted rows through
  the CG3 capture path at one catalog sequence K. Facts that conflict with retained
  evidence are quarantined per fact instead of refusing the batch. The batch state,
  counts and quarantine are recorded in one final transaction; retries are
  idempotent (the publication's request id is the batch id).

Funnel invariant, per batch: ``rows_received = rows_accepted + rows_quarantined``
and ``facts_published = facts_new + facts_duplicate`` with conflicting facts
quarantined. Raw bodies and quarantined rows are never logged.
"""
import hashlib
import json
import shutil
import uuid
from pathlib import Path

from psycopg.types.json import Jsonb

from ..contracts import EvaluationError
from . import registry
from .contracts import SourceContract, check_rows, parse, to_csv

RAW_CODEC = 'encrypted_raw_batch_v1'
QUARANTINE_CODEC = 'encrypted_quarantine_rows_v1'
MAX_BATCH_BYTES = 64 * 1024**2
MAX_PENDING_BATCHES = 10_000
MAX_PENDING_RAW_BYTES = 8 * 1024**3
TERMINAL = ('published', 'quarantined', 'failed')
EVENT_KINDS = ('model_change', 'configuration_change', 'data_pipeline_change', 'rollout', 'rollback', 'other')


def fault(boundary):
    """Test-only crash injection point."""


def _translate(exc):
    from ..platform_catalog import _translate as translate
    return translate(exc)


def _aad(source_id, batch_id):
    return f'numek-batch:{source_id}:{batch_id}'.encode()


def _day_key(conn, installation, scope, purpose):
    """This UTC day's data key for ``purpose`` (one per org per day, R2.7 crypto-shredding)."""
    conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', (f'ops:day-key:{scope.org_id}:{purpose}',))
    row = conn.execute("SELECT key_id FROM ops_raw_keys WHERE org_id = %s AND day = (now() AT TIME ZONE 'utc')::date "
                       'AND purpose = %s', (scope.org_id, purpose)).fetchone()
    if row is not None:
        return row['key_id']
    key_id = installation.data_keys.create(conn, scope, purpose)
    conn.execute("INSERT INTO ops_raw_keys(org_id, day, purpose, key_id) VALUES (%s, (now() AT TIME ZONE 'utc')::date, %s, %s)",
                 (scope.org_id, purpose, key_id))
    return key_id


def _receipt(row):
    return {'batch': str(row['id']), 'source': row['source_id'], 'batch_id': row['batch_id'], 'state': row['state'],
            'contract_version': row['contract_version'], 'raw_sha256': bytes(row['raw_sha256']).hex(),
            'raw_bytes': row['raw_bytes'], 'mode': row['mode'], 'received_at': row['received_at'].isoformat(),
            'acknowledged': True}


def _authorize(installation, auth, permission, kind, ident):
    if auth is None:                                        # trusted in-process caller (directory pull, tests)
        return
    from numek_platform import identity
    from numek_platform.errors import PlatformError
    try:
        with installation.db.transaction() as conn:
            identity.authorize(conn, auth, permission, kind, ident)
    except PlatformError as exc:
        raise _translate(exc) from exc


def authenticate(installation, token):
    """Bearer token -> authenticated principal (``unauthenticated`` on failure)."""
    from numek_platform import identity
    from numek_platform.errors import PlatformError
    try:
        with installation.db.transaction() as conn:
            return identity.authenticate_token(conn, token)
    except PlatformError as exc:
        raise _translate(exc) from exc


# Receive ---------------------------------------------------------------------------------------------------------
def receive(installation, source_id, batch_id, body, *, auth=None, mode='live', declared_identity=None, producer_dropped=0):
    """Durably acknowledge one batch. Returns its receipt (the same one for an identical retry)."""
    from numek_platform.errors import PlatformError
    from numek_platform.evidence.publish import activate_pending, stage_object
    from numek_platform.execution import jobs
    _authorize(installation, auth, 'ingest', 'source', source_id)
    if not isinstance(batch_id, str) or not 1 <= len(batch_id) <= 128 or not batch_id.isprintable():
        raise EvaluationError('A batch id is 1-128 printable characters.', 'invalid_batch')
    if mode not in ('live', 'backfill'):
        raise EvaluationError('Batch mode is live or backfill.', 'invalid_batch')
    if not isinstance(producer_dropped, int) or producer_dropped < 0:
        raise EvaluationError('Dropped-row counts are nonnegative integers.', 'invalid_batch')
    if len(body) > MAX_BATCH_BYTES:
        raise EvaluationError('Batch exceeds the size admission.', 'batch_too_large')
    src = registry.source(installation, source_id)
    dep = registry.deployment(installation, src['deployment_id'])
    catalog_id = registry.system(installation, dep['system_id'])['catalog_id']
    scope = installation.scope
    sha = hashlib.sha256(body).digest()

    def existing(conn):
        row = conn.execute('SELECT * FROM ops_batches WHERE org_id = %s AND source_id = %s AND batch_id = %s',
                           (scope.org_id, source_id, batch_id)).fetchone()
        if row is not None and bytes(row['raw_sha256']) != sha:
            raise EvaluationError('This batch id was already received with different content.', 'batch_conflict')
        return row

    with installation.db.connect() as conn:
        prior = existing(conn)
        if prior is not None:
            return _receipt(prior)
        pending = conn.execute("SELECT count(*) AS n, coalesce(sum(raw_bytes), 0) AS b FROM ops_batches WHERE org_id = %s "
                               "AND state IN ('received', 'processing')", (scope.org_id,)).fetchone()
    if pending['n'] >= MAX_PENDING_BATCHES or pending['b'] + len(body) > MAX_PENDING_RAW_BYTES:
        error = EvaluationError('Ingestion is behind; retry later.', 'backpressure')
        error.retryable = True
        raise error
    try:
        with installation.db.transaction() as conn:
            key_id = _day_key(conn, installation, scope, 'raw_batch')
            lease, _row = jobs.start_inline(conn, scope, 'ops_receive', idempotency_key=uuid.uuid4().hex, owner='ops-receive')
        envelope = installation.data_keys.encrypt(scope, key_id, body, _aad(source_id, batch_id))
        ref = stage_object(installation.db, installation.store, lease, envelope, catalog_id=catalog_id, codec=RAW_CODEC,
                           key_id=key_id, retained_for_recovery=True, object_id=uuid.uuid4())       # W1-W3: durable
        fault('raw_durable')
        with installation.db.transaction() as conn:
            jobs.assert_fence(conn, lease)
            conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))',
                         (f'ops:batch:{scope.org_id}:{source_id}:{batch_id}',))
            prior = existing(conn)
            if prior is not None:                                          # a concurrent identical retry won
                receipt = _receipt(prior)
            else:
                activate_pending(conn, scope, lease, catalog_id, [ref.id])
                watermark = conn.execute('SELECT through_tick FROM ops_watermarks WHERE org_id = %s AND source_id = %s',
                                         (scope.org_id, source_id)).fetchone()
                batch = uuid.uuid4()
                row = conn.execute(
                    '''INSERT INTO ops_batches(org_id, source_id, batch_id, id, contract_version, raw_sha256, raw_bytes,
                           raw_object, state, mode, declared_identity, producer_dropped, counts)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'received', %s, %s, %s, %s) RETURNING *''',
                    (scope.org_id, source_id, batch_id, batch, src['version'], sha, len(body), ref.id, mode,
                     Jsonb(declared_identity or {}), producer_dropped,
                     Jsonb({'watermark_at_receipt': None if watermark is None else int(watermark['through_tick'])}))).fetchone()
                # Backfill never competes with live monitoring: it runs in the maintenance lane.
                jobs.enqueue(conn, scope, 'ops_ingest_batch', idempotency_key=f'ops-batch:{batch}',
                             lane='maintenance' if mode == 'backfill' else 'essential',
                             job_class='warm', payload={'installation': str(installation.root), 'batch': str(batch)},
                             resources={'rss_bytes': 2 * 1024**3, 'threads': 1, 'seconds': 1800, 'device': 'cpu'})
                receipt = _receipt(row)
        with installation.db.connect() as conn:
            jobs.complete(conn, lease, {'batch': receipt['batch']})
    except PlatformError as exc:
        raise _translate(exc) from exc
    fault('acknowledged')
    return receipt


# Process ---------------------------------------------------------------------------------------------------------
def _decrypt(installation, scope, row):
    with installation.db.connect() as conn:
        obj = conn.execute('SELECT physical_key, sha256, bytes FROM objects WHERE id = %s', (row['raw_object'],)).fetchone()
    envelope = installation.store.read_verified(obj['physical_key'], bytes(obj['sha256']).hex(), obj['bytes'])
    body = installation.data_keys.decrypt(scope, envelope, _aad(row['source_id'], row['batch_id']))
    if hashlib.sha256(body).digest() != bytes(row['raw_sha256']):
        raise EvaluationError('Received batch changed.', 'evidence_changed')
    return body


def _ticks(contract, rows):
    if not contract.event_time:
        return []
    from ..compat import clock
    from ..contracts import ClockSpec
    out = []
    for row in rows:
        tick, state = clock(row.get(contract.event_time), ClockSpec('value'))
        out.append(int(tick) if state == 'valid' else None)
    return out


def _declared(contract, accepted, header):
    """The serving identity this batch declares (header and/or identity fields); None if absent or inconsistent."""
    values = dict(header or {})
    for key, field in (contract.identity or {}).items():
        seen = {row.get(field) for row in accepted if row.get(field) not in (None, '')}
        if len(seen) > 1:
            return None, 'inconsistent_within_batch'
        if seen:
            value = seen.pop()
            if values.get(key) not in (None, value):
                return None, 'header_and_rows_differ'
            values[key] = value
    return values, None


def process_batch(installation, batch, *, lease=None, cancel=None, deadline=None):
    """Process one received batch (idempotent). Returns the batch status."""
    from numek_platform.errors import PlatformError
    from numek_platform.evidence.publish import activate_pending, stage_object
    from numek_platform.execution import jobs
    from ..execution_context import InProcessContext, using
    scope = installation.scope
    batch = uuid.UUID(str(batch))
    with installation.db.connect() as conn:
        row = conn.execute('SELECT * FROM ops_batches WHERE org_id = %s AND id = %s', (scope.org_id, batch)).fetchone()
    if row is None:
        raise EvaluationError('Unknown batch.', 'unknown_batch')
    if row['state'] in TERMINAL:
        return status(installation, row['source_id'], row['batch_id'])
    src = registry.source(installation, row['source_id'], row['contract_version'])
    contract = SourceContract.from_dict(src['contract'])
    dep = registry.deployment(installation, src['deployment_id'])
    system = registry.system(installation, dep['system_id'])
    own_lease = lease is None
    try:
        with installation.db.transaction() as conn:
            conn.execute("UPDATE ops_batches SET state = 'processing' WHERE id = %s AND state IN ('received', 'processing')", (batch,))
            if own_lease:
                lease, _ = jobs.start_inline(conn, scope, 'ops_process', idempotency_key=uuid.uuid4().hex, owner='ops-process')
        counts = dict(row['counts'] or {})
        try:
            body = _decrypt(installation, scope, row)
            rows = parse(contract, body)
            del body
            accepted, quarantined, dropped = check_rows(contract, rows)
        except EvaluationError as exc:
            return _finish_failed(installation, scope, row, exc, lease, own_lease)
        ticks = _ticks(contract, accepted)
        watermark = counts.get('watermark_at_receipt')
        declared, declared_problem = _declared(contract, accepted, row['declared_identity'])
        counts.update(rows_received=len(rows), rows_accepted=len(accepted), rows_quarantined=len(quarantined),
                      fields_dropped=dropped, values_dropped=sum(dropped.values()), producer_dropped=row['producer_dropped'],
                      late_rows=sum(1 for t in ticks if watermark is not None and t is not None and t <= watermark),
                      event_tick_range=[min((t for t in ticks if t is not None), default=None),
                                        max((t for t in ticks if t is not None), default=None)])
        fault('checked')

        # Publication of accepted rows through the CG3 capture path (K assigned there).
        receipt, directory = None, installation.catalog_root(system['catalog_id']) / 'ingest' / batch.hex
        if accepted:
            from numek_platform.fsutil import private_directory, write_atomic
            private_directory(directory)
            path = directory / 'rows.csv'
            write_atomic(path, to_csv(contract, accepted))          # deterministic: a retry has the same identity
            ws = registry.workspace(installation, dep['system_id'])
            with using(InProcessContext(deadline=deadline, cancel=cancel)):
                receipt = ws.ingest(contract.batch_spec(path), request_id=f'ops-batch:{batch}', allowed_roots=(str(directory),),
                                    conflicts='quarantine', cancel=cancel)
            fault('published')
        conflicts = (receipt or {}).get('quarantined_facts', [])
        counts.update(facts_new=(receipt or {}).get('new_facts', 0), facts_duplicate=(receipt or {}).get('duplicate_occurrences', 0),
                      facts_quarantined=len(conflicts))

        # Quarantined rows: minimized, encrypted, with their own retention.
        rows_ref = None
        if quarantined:
            with installation.db.transaction() as conn:
                key_id = _day_key(conn, installation, scope, 'quarantine_rows')
            payload = '\n'.join(json.dumps({'ordinal': o, 'row': r}, sort_keys=True) for o, _reasons, _fields, r in quarantined)
            envelope = installation.data_keys.encrypt(scope, key_id, payload.encode(), _aad(row['source_id'], row['batch_id']))
            rows_ref = stage_object(installation.db, installation.store, lease, envelope, catalog_id=system['catalog_id'],
                                    codec=QUARANTINE_CODEC, records=len(quarantined), key_id=key_id, object_id=uuid.uuid4())

        state = 'published' if receipt is not None else 'quarantined'
        with installation.db.transaction() as conn:
            jobs.assert_fence(conn, lease)
            current = conn.execute('SELECT state FROM ops_batches WHERE id = %s FOR UPDATE', (batch,)).fetchone()
            if current['state'] in TERMINAL:                        # another attempt finished first
                return status(installation, row['source_id'], row['batch_id'])
            if rows_ref is not None:
                activate_pending(conn, scope, lease, system['catalog_id'], [rows_ref.id])
            for ordinal, reasons, fields, _row in quarantined:
                conn.execute('INSERT INTO ops_quarantine(org_id, batch, ordinal, reasons, fields, rows_object) VALUES (%s, %s, %s, %s, %s, %s)',
                             (scope.org_id, batch, ordinal, reasons, fields, rows_ref.id))
            for fact in conflicts:
                conn.execute('INSERT INTO ops_quarantine(org_id, batch, ordinal, reasons, fact) VALUES (%s, %s, -1, %s, %s)',
                             (scope.org_id, batch, [fact['reason']], Jsonb({k: fact[k] for k in ('kind', 'key', 'revision')})))
            from .identity import record_batch_identity
            record_batch_identity(conn, scope, dep, declared, declared_problem, row)
            conn.execute('''UPDATE ops_batches SET state = %s, counts = %s, catalog_sequence = %s, finished_at = clock_timestamp()
                            WHERE id = %s''', (state, Jsonb(counts), (receipt or {}).get('catalog_sequence'), batch))
            # Processed: the raw body is no longer needed for recovery (retention still applies).
            conn.execute('UPDATE objects SET retained_for_recovery = false WHERE id = %s', (row['raw_object'],))
        if own_lease:
            with installation.db.connect() as conn:
                jobs.complete(conn, lease, {'state': state})
        shutil.rmtree(directory, ignore_errors=True)               # minimized plaintext never outlives publication
    except PlatformError as exc:
        raise _translate(exc) from exc
    return status(installation, row['source_id'], row['batch_id'])


def _finish_failed(installation, scope, row, exc, lease, own_lease):
    from numek_platform.execution import jobs
    with installation.db.transaction() as conn:
        conn.execute('''UPDATE ops_batches SET state = 'failed', error = %s, finished_at = clock_timestamp()
                        WHERE id = %s AND state NOT IN ('published', 'quarantined', 'failed')''',
                     (Jsonb({'code': getattr(exc, 'code', 'failed'), 'message': str(exc)[:300]}), row['id']))
    if own_lease:
        with installation.db.connect() as conn:
            jobs.complete(conn, lease, {'state': 'failed'})
    return status(installation, row['source_id'], row['batch_id'])


def process_job(ctx, payload):
    """Worker-host entry point (``ops_ingest_batch``): the job process is the isolation boundary."""
    from numek_platform.installation import Installation
    import time
    remaining = max(1.0, ctx.deadline - time.monotonic())
    return process_batch(Installation(payload['installation']), payload['batch'], lease=ctx.lease,
                         deadline=time.monotonic() + remaining)


def process_pending(installation, *, limit=None):
    """Process every received batch in this process (single-host operation and tests)."""
    with installation.db.connect() as conn:
        rows = conn.execute("SELECT id FROM ops_batches WHERE org_id = %s AND state IN ('received', 'processing') "
                            'ORDER BY received_at LIMIT %s', (installation.scope.org_id, limit)).fetchall()
    return [process_batch(installation, r['id']) for r in rows]


# Status and funnel -------------------------------------------------------------------------------------------
def status(installation, source_id, batch_id, *, auth=None):
    _authorize(installation, auth, 'ingest', 'source', source_id)
    with installation.db.connect() as conn:
        row = conn.execute('SELECT * FROM ops_batches WHERE org_id = %s AND source_id = %s AND batch_id = %s',
                           (installation.scope.org_id, source_id, batch_id)).fetchone()
        if row is None:
            raise EvaluationError('Unknown batch.', 'unknown_batch')
        reasons = {}
        for q in conn.execute('SELECT unnest(reasons) AS r, count(*) AS n FROM ops_quarantine WHERE batch = %s GROUP BY 1', (row['id'],)):
            reasons[q['r']] = q['n']
    return {**_receipt(row), 'counts': row['counts'], 'catalog_sequence': row['catalog_sequence'], 'error': row['error'],
            'quarantine_reasons': reasons}


def funnel(installation, source_id):
    """Source totals with the reconciliation the funnel must satisfy."""
    with installation.db.connect() as conn:
        rows = conn.execute('SELECT state, counts, producer_dropped FROM ops_batches WHERE org_id = %s AND source_id = %s',
                            (installation.scope.org_id, source_id)).fetchall()
    total = {'batches': len(rows), 'by_state': {}, 'rows_received': 0, 'rows_accepted': 0, 'rows_quarantined': 0,
             'facts_new': 0, 'facts_duplicate': 0, 'facts_quarantined': 0, 'values_dropped': 0, 'producer_dropped': 0,
             'late_rows': 0}
    for r in rows:
        total['by_state'][r['state']] = total['by_state'].get(r['state'], 0) + 1
        total['producer_dropped'] += r['producer_dropped']
        for key in ('rows_received', 'rows_accepted', 'rows_quarantined', 'facts_new', 'facts_duplicate', 'facts_quarantined',
                    'values_dropped', 'late_rows'):
            total[key] += (r['counts'] or {}).get(key, 0)
    total['reconciled'] = total['rows_received'] == total['rows_accepted'] + total['rows_quarantined']
    return total


# Watermarks and window closure -------------------------------------------------------------------------------
def _tick(value):
    from .. import compat
    from ..contracts import ClockSpec
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    tick, state = compat.clock(value, ClockSpec('value'))
    if state != 'valid':
        raise EvaluationError('An unambiguous instant is required.', 'invalid_clock')
    return int(tick)


def declare_watermark(installation, source_id, through, *, auth=None):
    """The producer declares it has sent every row with event time <= ``through``. Monotonic (never regresses)."""
    _authorize(installation, auth, 'ingest', 'source', source_id)
    registry.source(installation, source_id)
    tick = _tick(through)
    with installation.db.transaction() as conn:
        row = conn.execute(
            '''INSERT INTO ops_watermarks(org_id, source_id, through_tick) VALUES (%s, %s, %s)
               ON CONFLICT (org_id, source_id) DO UPDATE SET
                   through_tick = greatest(ops_watermarks.through_tick, EXCLUDED.through_tick), updated_at = clock_timestamp()
               RETURNING through_tick''', (installation.scope.org_id, source_id, tick)).fetchone()
    return {'source': source_id, 'through_tick': int(row['through_tick']), 'regression_ignored': int(row['through_tick']) > tick}


def window_closure(installation, source_id, start, end, *, allowed_lateness_ns, now_tick=None):
    """Closure standing of the half-open window [start, end) for one source (plan G.1)."""
    import time
    start, end = _tick(start), _tick(end)
    now_tick = time.time_ns() if now_tick is None else _tick(now_tick)
    with installation.db.connect() as conn:
        row = conn.execute('SELECT through_tick FROM ops_watermarks WHERE org_id = %s AND source_id = %s',
                           (installation.scope.org_id, source_id)).fetchone()
    if row is not None and int(row['through_tick']) >= end:
        return {'closed': True, 'standing': 'producer_declared_complete', 'window': [start, end]}
    if now_tick - end >= allowed_lateness_ns:
        return {'closed': True, 'standing': 'assumed_complete_after_lateness', 'window': [start, end]}
    return {'closed': False, 'standing': 'open', 'window': [start, end]}


# Deployment events ---------------------------------------------------------------------------------------------
def record_deployment_event(installation, deployment_id, kind, at, *, identity=None, detail=None, auth=None, actor='system'):
    _authorize(installation, auth, 'ingest', 'deployment', deployment_id)
    if kind not in EVENT_KINDS:
        raise EvaluationError('Unknown deployment event kind.', 'invalid_event')
    registry.deployment(installation, deployment_id)
    from datetime import datetime, timezone
    when = datetime.fromtimestamp(_tick(at) / 1e9, tz=timezone.utc)
    event_id = uuid.uuid4()
    with installation.db.transaction() as conn:
        conn.execute('''INSERT INTO ops_deployment_events(org_id, id, deployment_id, kind, at, identity, detail, recorded_by)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                     (installation.scope.org_id, event_id, deployment_id, kind, when, Jsonb(identity or {}), Jsonb(detail or {}),
                      actor if auth is None else f'principal:{auth.principal.id}'))
    return {'event': str(event_id), 'deployment': deployment_id, 'kind': kind, 'at': when.isoformat()}


# Directory pull ------------------------------------------------------------------------------------------------
def pull_directory(installation, source_id, directory, *, processed=None):
    """Receive every new or changed file in ``directory`` as a batch. Never deletes customer files; with
    ``processed`` (a directory) received files are moved there instead."""
    import os
    src = registry.source(installation, source_id)
    suffix = '.' + SourceContract.from_dict(src['contract']).format
    directory = Path(directory).absolute()
    receipts = []
    for path in sorted(p for p in directory.iterdir() if p.is_file() and not p.is_symlink() and p.suffix == suffix):
        info = path.stat()
        body = path.read_bytes()
        sha = hashlib.sha256(body).hexdigest()
        with installation.db.connect() as conn:
            seen = conn.execute('SELECT batch_id FROM ops_directory_files WHERE org_id = %s AND source_id = %s AND path = %s '
                                'AND sha256 = %s', (installation.scope.org_id, source_id, str(path), bytes.fromhex(sha))).fetchone()
        if seen is not None:
            continue
        receipt = receive(installation, source_id, f'file:{sha}', body)
        with installation.db.transaction() as conn:
            conn.execute('''INSERT INTO ops_directory_files(org_id, source_id, path, size, mtime_ns, sha256, batch_id)
                            VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING''',
                         (installation.scope.org_id, source_id, str(path), info.st_size, info.st_mtime_ns, bytes.fromhex(sha),
                          receipt['batch_id']))
        if processed is not None:
            target = Path(processed).absolute()
            target.mkdir(mode=0o700, exist_ok=True)
            os.replace(path, target / path.name)
        receipts.append({**receipt, 'path': str(path)})
    return receipts
