"""Identity, authorization, audit anchoring, data keys, keyrings and egress control."""
import http.server
import socket
import threading

import psycopg
import pytest

from numek_platform import audit, identity
from numek_platform.egress import AllowEntry, check_destination, post
from numek_platform.errors import PlatformError
from numek_platform.secrets import DataKeys, FileSecretStore, export_keyring, import_keyring

PASSWORD = 'correct horse battery staple'


def _user(platform, name='ana', role='viewer', kind='user', scope=None):
    scope = scope or platform.scope
    with platform.db.transaction() as conn:
        principal = identity.create_principal(conn, scope, kind, name)
        if kind == 'user':
            identity.set_password(conn, scope, principal, PASSWORD)
        if role:
            identity.bind_role(conn, scope, principal, role)
    return principal


def test_passwords_sessions_and_csrf(platform):
    _user(platform)
    with platform.db.transaction() as conn:
        with pytest.raises(PlatformError):
            identity.verify_password(conn, platform.scope, 'ana', 'wrong password!!')
        principal = identity.verify_password(conn, platform.scope, 'ana', PASSWORD)
        token, csrf = identity.create_session(conn, principal)
        auth = identity.authenticate_session(conn, token)
        assert auth.principal.name == 'ana'
        with pytest.raises(PlatformError) as caught:
            identity.authenticate_session(conn, token, mutating=True, csrf='forged')
        assert caught.value.code == 'csrf_failed'
        identity.authenticate_session(conn, token, mutating=True, csrf=csrf)
        conn.execute("UPDATE sessions SET last_seen_at = now() - interval '2 hours'")
        with pytest.raises(PlatformError):
            identity.authenticate_session(conn, token)            # idle timeout


def test_tokens_narrow_authority_and_ingest_is_explicit(platform):
    analyst = _user(platform, 'al', role='analyst')
    service = _user(platform, 'collector', role=None, kind='service')
    with platform.db.transaction() as conn:
        read_token, _ = identity.issue_token(conn, platform.scope, analyst, ['role:viewer'])
        auth = identity.authenticate_token(conn, read_token)
        assert identity.permissions(conn, auth) == {'read'}           # analyst holds more; token narrows
        with pytest.raises(PlatformError):
            identity.issue_token(conn, platform.scope, analyst, ['ingest:source:s1'])
        ingest_token, token_id = identity.issue_token(conn, platform.scope, service, ['ingest:source:s1'])
        ingest = identity.authenticate_token(conn, ingest_token)
        identity.authorize(conn, ingest, 'ingest', 'source', 's1')
        with pytest.raises(PlatformError):
            identity.authorize(conn, ingest, 'ingest', 'source', 's2')
        with pytest.raises(PlatformError):
            identity.authorize(conn, ingest, 'read')                  # ingest tokens cannot read
        identity.revoke_token(conn, platform.scope, token_id)
        with pytest.raises(PlatformError):
            identity.authenticate_token(conn, ingest_token)


def test_separation_of_duties_and_no_execution_permission(platform):
    service = _user(platform, 'bot', role=None, kind='service')
    with platform.db.transaction() as conn, pytest.raises(PlatformError) as caught:
        identity.bind_role(conn, platform.scope, service, 'approver')
    assert caught.value.code == 'separation_of_duties'
    assert not any('execute' in p for perms in identity.ROLE_PERMISSIONS.values() for p in perms)


def test_cross_org_role_binding_is_refused_by_constraint(platform):
    other_scope, _ = platform.new_org('other')
    stranger = _user(platform, 'stranger', role=None, scope=other_scope)
    with platform.db.transaction() as conn, pytest.raises(psycopg.errors.ForeignKeyViolation):
        conn.execute("INSERT INTO role_bindings(org_id, principal_id, role, scope_kind) VALUES (%s, %s, 'admin', 'org')",
                     (platform.scope.org_id, stranger.id))


def test_audit_chain_detects_tampering_against_anchors(platform):
    sink = platform.root / 'anchors.jsonl'
    with platform.db.transaction() as conn:
        for i in range(3):
            audit.append(conn, platform.scope, 'ana', 'incident.acknowledge', f'incident:{i}', {'i': i})
        audit.export_anchor(conn, platform.scope, sink)
        assert audit.verify_against_anchors(conn, platform.scope, sink) == (True, None)
        conn.execute("UPDATE audit_log SET payload = '{\"i\": 99}' WHERE seq = 2")
        assert audit.verify_chain(conn, platform.scope) == (False, 2)


def test_data_keys_keyrings_and_live_destruction(platform):
    store = FileSecretStore(platform.root / 'secrets')
    keys = DataKeys(store)
    with platform.db.transaction() as conn:
        key_id = keys.create(conn, platform.scope, 'raw_batch')
    envelope = keys.encrypt(platform.scope, key_id, b'raw body', aad=b'batch-1')
    assert keys.decrypt(platform.scope, envelope, aad=b'batch-1') == b'raw body'
    with pytest.raises(PlatformError):
        keys.decrypt(platform.scope, envelope, aad=b'batch-2')
    ring = export_keyring(store, [(platform.scope.org_id, key_id)], 'backup passphrase 1')
    restored = FileSecretStore(platform.root / 'restored')
    with pytest.raises(PlatformError):
        import_keyring(restored, ring, 'wrong passphrase!!')
    assert import_keyring(restored, ring, 'backup passphrase 1') == 1
    assert DataKeys(restored).decrypt(platform.scope, envelope, aad=b'batch-1') == b'raw body'
    with platform.db.transaction() as conn:
        keys.destroy_live(conn, platform.scope, key_id)
    with pytest.raises(PlatformError):
        keys.decrypt(platform.scope, envelope, aad=b'batch-1')
    with pytest.raises(PlatformError) as caught:
        export_keyring(store, [(platform.scope.org_id, key_id)], 'backup passphrase 1')
    assert caught.value.code == 'backup_key_missing'


def _resolver(address):
    return lambda host, port, type=None: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (address, port))]


@pytest.mark.parametrize('address', ['127.0.0.1', '10.1.2.3', '169.254.169.254', '192.168.0.4', '100.64.1.1'])
def test_egress_refuses_protected_ranges_unless_explicitly_allowed(address):
    entry = AllowEntry('https', 'hooks.example', 443)
    with pytest.raises(PlatformError) as caught:
        check_destination('https://hooks.example/notify', [entry], resolver=_resolver(address))
    assert caught.value.code == 'egress_denied'
    internal = AllowEntry('https', 'hooks.example', 443, cidr=f'{address}/32')
    assert check_destination('https://hooks.example/x', [internal], resolver=_resolver(address))[3].compressed == address


def test_egress_requires_allowlist_and_rejects_credentials():
    entry = AllowEntry('https', 'hooks.example', 443)
    for url in ('https://other.example/x', 'https://hooks.example:8443/x', 'ftp://hooks.example/x',
                'https://user:pw@hooks.example/x'):
        with pytest.raises(PlatformError):
            check_destination(url, [entry], resolver=_resolver('93.184.216.34'))


def test_egress_never_follows_redirects():
    class Redirect(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get('Content-Length', 0)))
            self.send_response(302)
            self.send_header('Location', 'http://169.254.169.254/latest/meta-data')
            self.end_headers()

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(('127.0.0.1', 0), Redirect)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        entry = AllowEntry('http', 'receiver.internal', port, cidr='127.0.0.1/32')
        status, _ = post(f'http://receiver.internal:{port}/hook', b'{}', {'Content-Type': 'application/json'},
                         [entry], resolver=_resolver('127.0.0.1'))
        assert status == 302                                         # returned, not followed
    finally:
        server.shutdown()


# S10 (M.4 remaining items) --------------------------------------------------------------------------------------------

def test_sessions_rotate_on_login_expire_absolutely_and_revoke(platform):
    """No fixation: a session exists only after authentication and every login gets a new id and secret. The
    absolute lifetime ends a session even while it is in use; revocation ends it at once. Secrets are stored hashed."""
    principal = _user(platform, 'rotating')
    with platform.db.transaction() as conn:
        first, _ = identity.create_session(conn, principal)
        second, _ = identity.create_session(conn, principal)
        assert first.split('_')[1] != second.split('_')[1] and first.split('_')[2] != second.split('_')[2]
        stored = conn.execute('SELECT secret_hash FROM sessions').fetchall()
        assert all(first.split('_', 2)[2].encode() not in bytes(r['secret_hash']) for r in stored)
        identity.authenticate_session(conn, first)
        identity.revoke_session(conn, first)
        with pytest.raises(PlatformError):
            identity.authenticate_session(conn, first)
        identity.authenticate_session(conn, second)                  # other sessions are unaffected
        conn.execute("UPDATE sessions SET absolute_expires_at = now() - interval '1 second', last_seen_at = now()")
        with pytest.raises(PlatformError) as expired:
            identity.authenticate_session(conn, second)               # active, but past its absolute lifetime
        assert expired.value.code == 'unauthenticated'
        with pytest.raises(PlatformError):
            identity.authenticate_session(conn, 'nms_' + second.split('_')[1] + '_forged-secret')


def test_tokens_expire_and_only_their_hash_is_stored(platform):
    service = _user(platform, 'expiring', role=None, kind='service')
    with platform.db.transaction() as conn:
        token, token_id = identity.issue_token(conn, platform.scope, service, ['ingest:source:s1'], expires_in='1 hour')
        identity.authenticate_token(conn, token)
        row = conn.execute('SELECT * FROM api_tokens WHERE id = %s', (token_id,)).fetchone()
        assert token.split('_', 2)[2] not in repr(dict(row))         # the secret is never stored, only its SHA-256
        conn.execute("UPDATE api_tokens SET expires_at = now() - interval '1 second' WHERE id = %s", (token_id,))
        with pytest.raises(PlatformError) as expired:
            identity.authenticate_token(conn, token)
        assert expired.value.code == 'unauthenticated'


def test_secret_files_are_owner_only_and_loosened_or_linked_files_are_refused(tmp_path):
    import os
    import stat
    store = FileSecretStore(tmp_path / 'secrets')
    store.put('channels/hook', b'signing key')
    path = tmp_path / 'secrets' / 'channels' / 'hook'
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE((tmp_path / 'secrets').stat().st_mode) == 0o700
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert store.get('channels/hook') == b'signing key'
    os.chmod(path, 0o640)                                            # someone loosened the file
    with pytest.raises(PlatformError) as loose:
        store.get('channels/hook')
    assert loose.value.code == 'unsafe_path'
    os.chmod(path, 0o600)
    os.link(path, tmp_path / 'secrets' / 'second-name')              # a hard link elsewhere could expose it
    with pytest.raises(PlatformError):
        store.get('channels/hook')
    os.unlink(tmp_path / 'secrets' / 'second-name')
    path.unlink()
    os.symlink(tmp_path / 'elsewhere', path)                         # a planted symlink is not followed
    with pytest.raises(PlatformError):
        store.get('channels/hook')
    with pytest.raises(PlatformError):
        store.put('../escape', b'x')
