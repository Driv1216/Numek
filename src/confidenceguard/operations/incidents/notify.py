"""Notifications: outbox, allowlisted egress, signed webhooks and SMTP, retries and dead letters (plan H.7, C.6).

**When a row is enqueued.** Outbox rows are written in the transaction that records the incident event, and
only for state or priority changes: opened, state_changed, priority_changed, escalated, reopened, resolved.

**Delivery.**
- Delivery is at least once, and every attempt carries an idempotency key.
- Payloads hold ids, priority, state and a link only, never evidence values.
- Webhooks are HMAC-SHA256 signed: ``Numek-Signature: sha256=<hex>`` over ``timestamp.body``, with the channel's
  secret. SMTP uses implicit TLS (``smtps``) or STARTTLS. Plaintext SMTP needs an explicit
  ``allow_plaintext`` on the channel.
- Every destination goes through ``numek_platform.egress``: the allowlist, checked-address pinning, no redirects,
  and bounded timeouts.

**Retries.** A failure retries with exponential backoff (30 s, doubling, capped at 1 h). After ``MAX_ATTEMPTS``
the row is a dead letter, which raises a deterministic health condition (``notification_dead_letter``).

**Rules.**
- A rule sets the minimum priority, optional digest batching and quiet windows. P1 is never held.
- Escalation levels route escalations to further rules.
"""
import hashlib
import hmac
import json
import secrets as _secrets
import smtplib
import socket
import ssl
import uuid
from datetime import datetime, timedelta
from email.message import EmailMessage

from psycopg.types.json import Jsonb

from ...contracts import EvaluationError
from . import priority as priority_table

KINDS = ('opened', 'state_changed', 'priority_changed', 'escalated', 'reopened', 'resolved')
MAX_ATTEMPTS = 8
CLAIM_SECONDS = 300


def _secret_name(scope, channel_id):
    return f'notify/{scope.org_id}/{channel_id}'


def configure_channel(installation, channel_id, kind, destination, *, config=None, credentials=None, actor='system'):
    """Register a channel. A webhook's HMAC key is generated and returned once; SMTP credentials stay in secrets."""
    from .. import audit_action
    if kind not in ('webhook', 'smtp'):
        raise EvaluationError('Channels are webhook or smtp.', 'invalid_channel')
    scheme = destination.split(':', 1)[0].lower()
    if (kind == 'webhook') != (scheme in ('https', 'http')) or (kind == 'smtp' and scheme not in ('smtp', 'smtps')):
        raise EvaluationError('Webhooks use http(s) destinations; SMTP channels use smtp(s)://host:port.', 'invalid_channel')
    config = dict(config or {})
    if kind == 'smtp' and not (config.get('from') and config.get('to')):
        raise EvaluationError('SMTP channels declare from and to.', 'invalid_channel')
    scope = installation.scope
    name = _secret_name(scope, channel_id)
    shown = None
    if kind == 'webhook':
        key = _secrets.token_bytes(32)
        installation.secrets.put(name, key)
        shown = key.hex()
    else:
        installation.secrets.put(name, json.dumps(credentials or {}).encode())
    with installation.db.transaction() as conn:
        conn.execute('''INSERT INTO ops_notification_channels(org_id, id, kind, destination, secret_name, config)
                        VALUES (%s, %s, %s, %s, %s, %s)''', (scope.org_id, channel_id, kind, destination, name, Jsonb(config)))
        audit_action(conn, scope, actor, 'notification.channel', channel_id, {'kind': kind, 'destination': destination})
    return {'channel': channel_id, 'kind': kind, 'signing_key': shown,
            'note': 'The signing key is shown once and never stored in the database.' if shown else None}


def add_rule(installation, rule_id, channel_id, *, deployment_id=None, min_priority='P2', digest_seconds=None, quiet=(),
             escalation_level=0, actor='system'):
    from .. import audit_action
    if min_priority not in priority_table.RANK:
        raise EvaluationError('min_priority is P1-P4.', 'invalid_rule')
    scope = installation.scope
    with installation.db.transaction() as conn:
        conn.execute('''INSERT INTO ops_notification_rules(org_id, id, channel_id, deployment_id, min_priority, digest_seconds, quiet,
                            escalation_level) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                     (scope.org_id, rule_id, channel_id, deployment_id, min_priority, digest_seconds, Jsonb([list(q) for q in quiet]),
                      escalation_level))
        audit_action(conn, scope, actor, 'notification.rule', rule_id, {'channel': channel_id, 'min_priority': min_priority})


def _quiet_until(quiet, now):
    for start, end in quiet or ():
        a, b = datetime.fromisoformat(start.replace('Z', '+00:00')), datetime.fromisoformat(end.replace('Z', '+00:00'))
        if a <= now < b:
            return b
    return None


def enqueue(conn, scope, incident, event_seq, kind, *, now):
    """Outbox rows for one incident event (inside the event's transaction)."""
    if kind not in KINDS:
        return 0
    rules = conn.execute('''SELECT r.* FROM ops_notification_rules r JOIN ops_notification_channels c ON c.org_id = r.org_id AND c.id = r.channel_id
                            WHERE r.org_id = %s AND c.enabled AND (r.deployment_id IS NULL OR r.deployment_id = %s) ORDER BY r.id''',
                         (scope.org_id, incident['deployment_id'])).fetchall()
    payload = {'incident': str(incident['id']), 'number': incident['number'], 'deployment': incident['deployment_id'],
               'priority': incident['priority'], 'state': incident['state'], 'event': kind, 'event_seq': event_seq,
               'escalation_level': incident['escalation_level'], 'link': f"/ops/incidents/{incident['id']}", 'at': now.isoformat()}
    count = 0
    for rule in rules:
        if not priority_table.at_least(incident['priority'], rule['min_priority']):
            continue
        wanted_level = incident['escalation_level'] if kind == 'escalated' else 0
        if rule['escalation_level'] != wanted_level:
            continue
        state, due = 'queued', now
        if incident['priority'] != 'P1':
            if rule['digest_seconds']:
                state, due = 'held', now + timedelta(seconds=rule['digest_seconds'])
            quiet = _quiet_until(rule['quiet'], now)
            if quiet is not None:
                due = max(due, quiet)
        inserted = conn.execute('''INSERT INTO ops_notification_outbox(org_id, id, channel_id, rule_id, incident_id, event_seq, idempotency_key,
                                       payload, state, next_attempt_at)
                                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (org_id, idempotency_key) DO NOTHING''',
                                (scope.org_id, uuid.uuid4(), rule['channel_id'], rule['id'], incident['id'], event_seq,
                                 f"{rule['id']}:{incident['id']}:{event_seq}", Jsonb(payload), state, due)).rowcount
        count += inserted
    return count


# Sending ---------------------------------------------------------------------------------------------------------
class _PinnedSMTP(smtplib.SMTP):
    def __init__(self, address, timeout, **kwargs):
        self._address = str(address)
        super().__init__(timeout=timeout, **kwargs)

    def _get_socket(self, host, port, timeout):
        return socket.create_connection((self._address, port), timeout)


class _PinnedSMTPSSL(smtplib.SMTP_SSL):
    def __init__(self, address, timeout, context):
        self._address = str(address)
        super().__init__(timeout=timeout, context=context)

    def _get_socket(self, host, port, timeout):
        raw = socket.create_connection((self._address, port), timeout)
        return self.context.wrap_socket(raw, server_hostname=host)


def _webhook(channel, key, body, idempotency_key, allowlist, now, resolver):
    from numek_platform import egress
    stamp = now.isoformat()
    signature = hmac.new(key, stamp.encode() + b'.' + body, hashlib.sha256).hexdigest()
    headers = {'Content-Type': 'application/json', 'Numek-Idempotency-Key': idempotency_key, 'Numek-Timestamp': stamp,
               'Numek-Signature': f'sha256={signature}'}
    kwargs = {'resolver': resolver} if resolver else {}
    status, _data = egress.post(channel['destination'], body, headers, allowlist, **kwargs)
    if 200 <= status < 300:
        return None
    return {'code': 'redirect_refused' if 300 <= status < 400 else 'http_status', 'status': status}


def _smtp(channel, credentials, body, idempotency_key, allowlist, resolver):
    from numek_platform import egress
    kwargs = {'resolver': resolver} if resolver else {}
    entry, host, port, address = egress.check_destination(channel['destination'], allowlist, **kwargs)
    config = channel['config']
    message = EmailMessage()
    message['From'], message['To'] = config['from'], config['to']
    data = json.loads(body)
    items = data.get('digest') or [data]
    message['Subject'] = (f"[NUMEK {items[0]['priority']}] incident #{items[0]['number']} {items[0]['event']}" if len(items) == 1
                          else f'[NUMEK] {len(items)} incident updates')
    message['Message-ID'] = f'<{idempotency_key}@numek>'
    message.set_content('\n'.join(f"#{i['number']} {i['deployment']} {i['priority']} {i['state']} ({i['event']}) {i['link']}"
                                  for i in items))
    context = ssl.create_default_context()
    if entry.scheme == 'smtps':
        client = _PinnedSMTPSSL(address, 10, context)
        client.connect(host, port)
    else:
        client = _PinnedSMTP(address, 10)
        client.connect(host, port)
        if not config.get('allow_plaintext'):
            client.starttls(context=context)
    try:
        if credentials.get('username'):
            client.login(credentials['username'], credentials['password'])
        client.send_message(message)
    finally:
        try:
            client.quit()
        except smtplib.SMTPException:
            pass
    return None


def send_due(installation, *, now, resolver=None, limit=50):
    """Deliver due outbox rows (claimed first, so a crash re-sends at least once). Returns a summary."""
    from numek_platform import egress
    from numek_platform.errors import PlatformError
    scope = installation.scope
    with installation.db.transaction() as conn:
        rows = [dict(r) for r in conn.execute(
            '''SELECT o.*, c.kind, c.destination, c.secret_name, c.config FROM ops_notification_outbox o
               JOIN ops_notification_channels c ON c.org_id = o.org_id AND c.id = o.channel_id
               WHERE o.org_id = %s AND o.state IN ('queued', 'held') AND o.next_attempt_at <= %s
               ORDER BY o.next_attempt_at, o.id LIMIT %s FOR UPDATE OF o SKIP LOCKED''', (scope.org_id, now, limit)).fetchall()]
        held_rules = {r['rule_id'] for r in rows if r['state'] == 'held'}
        for rule in held_rules:                    # a digest takes every held row of its rule, due or not yet
            extra = conn.execute('''SELECT o.*, c.kind, c.destination, c.secret_name, c.config FROM ops_notification_outbox o
                                    JOIN ops_notification_channels c ON c.org_id = o.org_id AND c.id = o.channel_id
                                    WHERE o.org_id = %s AND o.rule_id = %s AND o.state = 'held' AND o.id <> ALL(%s)
                                    FOR UPDATE OF o SKIP LOCKED''', (scope.org_id, rule, [r['id'] for r in rows])).fetchall()
            rows += [dict(r) for r in extra]
        if rows:
            conn.execute('UPDATE ops_notification_outbox SET next_attempt_at = %s WHERE org_id = %s AND id = ANY(%s)',
                         (now + timedelta(seconds=CLAIM_SECONDS), scope.org_id, [r['id'] for r in rows]))
        allowlist = egress.load_allowlist(conn, scope)
    batches = [[r] for r in rows if r['state'] == 'queued']
    for rule in sorted(held_rules):
        batches.append(sorted([r for r in rows if r['state'] == 'held' and r['rule_id'] == rule], key=lambda r: r['created_at']))
    summary = {'sent': 0, 'failed': 0, 'dead': 0}
    for batch in batches:
        head = batch[0]
        body = json.dumps(head['payload'] if len(batch) == 1 else {'digest': [r['payload'] for r in batch]},
                          sort_keys=True, separators=(',', ':')).encode()
        key = head['idempotency_key'] if len(batch) == 1 else 'digest:' + ':'.join(sorted(str(r['id']) for r in batch))[:200]
        try:
            secret = installation.secrets.get(head['secret_name'])
            error = (_webhook(head, secret, body, key, allowlist, now, resolver) if head['kind'] == 'webhook'
                     else _smtp(head, json.loads(secret or b'{}'), body, key, allowlist, resolver))
        except PlatformError as exc:
            error = {'code': exc.code}
        except (OSError, smtplib.SMTPException) as exc:
            error = {'code': 'delivery_failed', 'type': type(exc).__name__}
        _record(installation, batch, error, now)
        summary['sent' if error is None else 'failed'] += 1
        if error is not None and head['attempts'] + 1 >= MAX_ATTEMPTS:
            summary['dead'] += 1
    return summary


def _record(installation, batch, error, now):
    scope = installation.scope
    ids = [r['id'] for r in batch]
    with installation.db.transaction() as conn:
        if error is None:
            state = 'sent' if len(batch) == 1 else 'digested'
            conn.execute('UPDATE ops_notification_outbox SET state = %s, sent_at = %s, attempts = attempts + 1, last_error = NULL, '
                         'digest_of = %s WHERE org_id = %s AND id = ANY(%s)',
                         (state, now, ids if len(batch) > 1 else None, scope.org_id, ids))
            return
        attempts = batch[0]['attempts'] + 1
        if attempts >= MAX_ATTEMPTS:
            conn.execute("UPDATE ops_notification_outbox SET state = 'dead', attempts = %s, last_error = %s WHERE org_id = %s AND id = ANY(%s)",
                         (attempts, Jsonb(error), scope.org_id, ids))
            for row in batch:
                _dead_letter_signal(conn, scope, row, error)
            return
        delay = min(3600, 30 * 2 ** (attempts - 1))
        conn.execute('UPDATE ops_notification_outbox SET attempts = %s, last_error = %s, next_attempt_at = %s WHERE org_id = %s AND id = ANY(%s)',
                     (attempts, Jsonb(error), now + timedelta(seconds=delay), scope.org_id, ids))


def _dead_letter_signal(conn, scope, row, error):
    incident = conn.execute('SELECT deployment_id FROM ops_incidents WHERE org_id = %s AND id = %s', (scope.org_id, row['incident_id'])).fetchone()
    version = conn.execute("SELECT coalesce(max(version), 0) AS v FROM ops_monitoring_definitions WHERE org_id = %s AND deployment_id = %s "
                           "AND state = 'confirmed'", (scope.org_id, incident['deployment_id'])).fetchone()['v']
    conn.execute('''INSERT INTO ops_signals(org_id, id, deployment_id, definition_version, source, source_id, standing, severity, payload,
                        dedupe_key) VALUES (%s, %s, %s, %s, 'health', 'notification_dead_letter', 'D', 'high', %s, %s)
                    ON CONFLICT (org_id, dedupe_key) DO NOTHING''',
                 (scope.org_id, uuid.uuid4(), incident['deployment_id'], version,
                  Jsonb({'kind': 'notification_dead_letter', 'source': row['channel_id'], 'outbox': str(row['id']), 'error': error}),
                  f"{incident['deployment_id']}:dead_letter:{row['id']}"))
