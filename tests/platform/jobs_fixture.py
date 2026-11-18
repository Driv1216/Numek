"""Job functions executed in worker child processes during tests."""
import os
import time

from numek_platform.errors import PlatformError
from numek_platform.execution.probes import register_state_probe

STATE = {}
register_state_probe('jobs_fixture', lambda: tuple(sorted(STATE.items())))


def echo(ctx, payload):
    ctx.check('echo')
    assert os.path.isdir(ctx.scratch)
    return {'pid': os.getpid(), 'omp': os.environ.get('OMP_NUM_THREADS'), 'payload': payload}


def sleep(ctx, payload):
    end = time.monotonic() + payload['seconds']
    while time.monotonic() < end:
        time.sleep(0.05)
    return {'slept': payload['seconds']}


def allocate(ctx, payload):
    block = bytearray(payload['mb'] * 1024 * 1024)
    for i in range(0, len(block), 4096):
        block[i] = 1
    time.sleep(payload.get('hold', 3))
    return {'allocated': len(block)}


def leak(ctx, payload):
    STATE['leaked'] = payload.get('value', 1)
    return {'pid': os.getpid()}


def fail(ctx, payload):
    raise PlatformError('intentional failure', 'intentional', retryable=payload.get('retryable', False))


def publish(ctx, payload):
    from helpers import record
    from numek_platform.canonical import digest
    from numek_platform.evidence import codecs
    from numek_platform.evidence.publish import FactRow, publish as publish_evidence, stage_object
    import uuid
    fact = record('context', ['ns', payload['event']], {'from': 'child'})
    data, _ = codecs.encode_observations([fact])
    ref = stage_object(ctx.db, ctx.store, ctx.lease, data, catalog_id=uuid.UUID(payload['catalog_id']),
                       codec=codecs.OBSERVATIONS, records=1)
    receipt = publish_evidence(ctx.db, ctx.scope, ctx.lease, uuid.UUID(payload['catalog_id']),
                               request_id=f'job:{ctx.lease.job_id}', request_digest=digest(fact), kind='ingest',
                               objects=[ref], facts=[FactRow('context', fact['key'], 'initial', fact['fact_digest'],
                                                             ref.id, 'row', 0, 0)])
    return receipt.to_dict()
