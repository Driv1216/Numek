"""Test helpers: CG3-shaped fact records and one-call publication."""
import uuid

from numek_platform.canonical import digest
from numek_platform.evidence import codecs
from numek_platform.evidence.publish import FactRow, publish, stage_object
from numek_platform.execution import jobs


def record(kind, identity, payload, *, revision='initial', predecessor=None, available_ns=None):
    body = {'kind': kind, 'key': digest(identity), 'identity': identity, 'revision': revision, 'payload': payload,
            'predecessor': predecessor, 'available_ns': available_ns, 'authority': None, 'reason': None}
    body['fact_digest'] = digest(body)
    return body


def lease_for(platform, kind='test', scope=None, key=None):
    scope = scope or platform.scope
    with platform.db.connect() as conn:
        lease, _row = jobs.start_inline(conn, scope, kind, idempotency_key=key or uuid.uuid4().hex, owner='tests')
    return lease


def publish_records(platform, records, *, codec=codecs.OBSERVATIONS, request_id=None, lease=None, scope=None,
                    catalog_id=None, event_ticks=None, event_hashes=None, entity_hashes=None, **kwargs):
    scope = scope or platform.scope
    catalog_id = catalog_id or platform.catalog_id
    lease = lease or lease_for(platform, scope=scope)
    if codec == codecs.OBSERVATIONS:
        data, rows = codecs.encode_observations(records)
        locations = [('row', r, 0) for r in rows]
    else:
        data, ranges = codecs.encode_jsonl(records)
        locations = [('byte_range', a, b) for a, b in ranges]
    ref = stage_object(platform.db, platform.store, lease, data, catalog_id=catalog_id, codec=codec,
                       records=len(records))
    facts = []
    for i, (rec, (kind, a, b)) in enumerate(zip(records, locations)):
        facts.append(FactRow(rec['kind'], rec['key'], rec['revision'], rec['fact_digest'], ref.id, kind, a, b,
                             predecessor=rec['predecessor'],
                             event_tick=None if event_ticks is None else event_ticks[i],
                             event_hash=None if event_hashes is None else event_hashes[i],
                             entity_hash=None if entity_hashes is None else entity_hashes[i]))
    receipt = publish(platform.db, scope, lease, catalog_id, request_id=request_id or uuid.uuid4().hex,
                      request_digest=digest([r['fact_digest'] for r in records]), kind='ingest',
                      objects=[ref], facts=facts, **kwargs)
    return receipt, ref, lease
