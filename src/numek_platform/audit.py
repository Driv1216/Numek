"""Hash-chained audit log with external anchoring.

Threat model: the chain is tamper-*evident* against anyone who cannot rewrite
both the database and the anchors exported to a sink outside NUMEK. A database
superuser can rewrite the chain after its last exported anchor; anchoring
frequency bounds that window. It is not tamper-proof.

``append`` must run inside the transaction that makes the audited change.
"""
import hashlib
import json
import os

from psycopg.types.json import Jsonb

from .canonical import canonical_bytes
from .fsutil import fsync_directory

GENESIS = bytes(32)


def _entry_hash(prev_hash, seq, actor, action, target, payload):
    body = canonical_bytes({'seq': seq, 'actor': actor, 'action': action, 'target': target, 'payload': payload})
    return hashlib.sha256(prev_hash + body).digest()


def append(conn, scope, actor, action, target, payload=None):
    payload = payload or {}
    conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', (f'audit:{scope.org_id}',))
    last = conn.execute('SELECT seq, hash FROM audit_log WHERE org_id = %s ORDER BY seq DESC LIMIT 1',
                        (scope.org_id,)).fetchone()
    seq, prev = (last['seq'] + 1, bytes(last['hash'])) if last else (1, GENESIS)
    digest = _entry_hash(prev, seq, actor, action, target, payload)
    conn.execute(
        '''INSERT INTO audit_log(org_id, seq, prev_hash, hash, actor, action, target, payload)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
        (scope.org_id, seq, prev, digest, actor, action, target, Jsonb(payload)))
    return seq


def verify_chain(conn, scope):
    """Return (ok, first_bad_seq)."""
    prev = GENESIS
    expected = 1
    for row in conn.execute('SELECT * FROM audit_log WHERE org_id = %s ORDER BY seq', (scope.org_id,)):
        if row['seq'] != expected or bytes(row['prev_hash']) != prev:
            return False, row['seq']
        if bytes(row['hash']) != _entry_hash(prev, row['seq'], row['actor'], row['action'], row['target'], row['payload']):
            return False, row['seq']
        prev, expected = bytes(row['hash']), expected + 1
    return True, None


def export_anchor(conn, scope, sink_path):
    """Append the current chain head to an operator-controlled file sink."""
    head = conn.execute('SELECT seq, hash FROM audit_log WHERE org_id = %s ORDER BY seq DESC LIMIT 1',
                        (scope.org_id,)).fetchone()
    if head is None:
        return None
    line = json.dumps({'org_id': str(scope.org_id), 'seq': head['seq'], 'hash': bytes(head['hash']).hex()},
                      sort_keys=True) + '\n'
    fd = os.open(sink_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        os.write(fd, line.encode())
        os.fsync(fd)
    finally:
        os.close(fd)
    fsync_directory(os.path.dirname(os.path.abspath(sink_path)))
    conn.execute('INSERT INTO audit_anchors(org_id, seq, hash, sink) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING',
                 (scope.org_id, head['seq'], bytes(head['hash']), str(sink_path)))
    return head['seq']


def verify_against_anchors(conn, scope, sink_path):
    """Check that every anchored head still matches the stored chain."""
    ok, bad = verify_chain(conn, scope)
    if not ok:
        return False, bad
    with open(sink_path, encoding='utf-8') as stream:
        for line in stream:
            anchor = json.loads(line)
            if anchor['org_id'] != str(scope.org_id):
                continue
            row = conn.execute('SELECT hash FROM audit_log WHERE org_id = %s AND seq = %s',
                               (scope.org_id, anchor['seq'])).fetchone()
            if row is None or bytes(row['hash']).hex() != anchor['hash']:
                return False, anchor['seq']
    return True, None
