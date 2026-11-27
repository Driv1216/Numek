"""Principals, credentials, sessions, tokens and role-based authorization.

Authentication providers map external subjects onto platform principals
(``IdentityProvider``). Local passwords and service tokens are implemented
now; OIDC can be added later without changing principals or bindings.

There is deliberately no permission that executes production changes.
``intervention:approve`` records approval only.
"""
import datetime as dt
import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from ..errors import PlatformError

ROLE_PERMISSIONS = {
    'viewer': {'read'},
    'operator': {'read', 'operate'},
    'analyst': {'read', 'operate', 'analyze', 'evidence:protected:read'},
    'approver': {'read', 'intervention:approve'},
    'reserve_steward': {'read', 'reserve:consume'},     # restricted (reserve-consuming) investigations; never automatic
    'admin': {'read', 'operate', 'admin'},
}
SERVICE_FORBIDDEN_ROLES = {'approver', 'reserve_steward'}
SCOPE_KINDS = ('org', 'system', 'deployment', 'catalog', 'source')
SESSION_IDLE = dt.timedelta(minutes=30)
LOGIN_FAILURE_LIMIT = 10                       # failed sign-ins per name ...
LOGIN_FAILURE_WINDOW = dt.timedelta(minutes=15)  # ... inside this window lock the name out until they age out
SESSION_ABSOLUTE = dt.timedelta(hours=12)
_hasher = PasswordHasher()  # argon2id with the library's current recommended parameters


@dataclass(frozen=True)
class Principal:
    org_id: uuid.UUID
    id: uuid.UUID
    kind: str
    name: str


@dataclass(frozen=True)
class Authenticated:
    principal: Principal
    via: str                       # 'session' | 'token'
    token_scopes: tuple = ()
    session_id: uuid.UUID | None = None


def _sha(value):
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).digest()


# Principals ---------------------------------------------------------------------

def create_principal(conn, scope, kind, name):
    if kind not in ('user', 'service', 'system'):
        raise ValueError(kind)
    principal_id = uuid.uuid4()
    conn.execute('INSERT INTO principals(org_id, id, kind, name) VALUES (%s, %s, %s, %s)',
                 (scope.org_id, principal_id, kind, name))
    return Principal(scope.org_id, principal_id, kind, name)


def get_principal(conn, scope, principal_id):
    row = conn.execute('SELECT * FROM principals WHERE org_id = %s AND id = %s', (scope.org_id, principal_id)).fetchone()
    if row is None or row['disabled']:
        raise PlatformError('Unknown or disabled principal.', 'unauthenticated')
    return Principal(row['org_id'], row['id'], row['kind'], row['name'])


# Passwords ------------------------------------------------------------------------

def set_password(conn, scope, principal, password):
    if principal.kind != 'user':
        raise PlatformError('Only user principals have passwords.', 'invalid_principal')
    if len(password) < 12:
        raise PlatformError('Passwords must have at least 12 characters.', 'weak_password')
    conn.execute(
        '''INSERT INTO password_credentials(org_id, principal_id, hash) VALUES (%s, %s, %s)
           ON CONFLICT (org_id, principal_id) DO UPDATE SET hash = EXCLUDED.hash, updated_at = now()''',
        (scope.org_id, principal.id, _hasher.hash(password)))


def login_throttled(conn, scope, name):
    """True while ``name`` has reached the failed sign-in limit inside the window (soft lockout, ASVS L1)."""
    row = conn.execute('SELECT count(*) AS n FROM login_failures WHERE org_id = %s AND name = %s AND failed_at > now() - %s',
                       (scope.org_id, str(name)[:200], LOGIN_FAILURE_WINDOW)).fetchone()
    return row['n'] >= LOGIN_FAILURE_LIMIT


def record_login_failure(conn, scope, name):
    """Record one failed sign-in (call in its own transaction, so a failed attempt's rollback cannot erase it)."""
    conn.execute('DELETE FROM login_failures WHERE org_id = %s AND name = %s AND failed_at <= now() - %s',
                 (scope.org_id, str(name)[:200], LOGIN_FAILURE_WINDOW))
    conn.execute('INSERT INTO login_failures(org_id, name) VALUES (%s, %s)', (scope.org_id, str(name)[:200]))


def verify_password(conn, scope, name, password):
    row = conn.execute(
        '''SELECT p.*, c.hash FROM principals p JOIN password_credentials c
               ON c.org_id = p.org_id AND c.principal_id = p.id
           WHERE p.org_id = %s AND p.kind = 'user' AND p.name = %s AND NOT p.disabled''',
        (scope.org_id, name)).fetchone()
    if row is None:
        _hasher.hash(password)  # equalize timing for unknown users
        raise PlatformError('Invalid credentials.', 'unauthenticated')
    try:
        _hasher.verify(row['hash'], password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        raise PlatformError('Invalid credentials.', 'unauthenticated') from None
    if _hasher.check_needs_rehash(row['hash']):
        conn.execute('UPDATE password_credentials SET hash = %s WHERE org_id = %s AND principal_id = %s',
                     (_hasher.hash(password), scope.org_id, row['id']))
    return Principal(row['org_id'], row['id'], row['kind'], row['name'])


# Sessions -------------------------------------------------------------------------

def create_session(conn, principal):
    """New session for a freshly authenticated user (always a new id: rotation on login)."""
    session_id, secret, csrf = uuid.uuid4(), secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    conn.execute(
        '''INSERT INTO sessions(org_id, id, principal_id, secret_hash, csrf_hash, absolute_expires_at)
           VALUES (%s, %s, %s, %s, %s, now() + %s)''',
        (principal.org_id, session_id, principal.id, _sha(secret), _sha(csrf), SESSION_ABSOLUTE))
    return f'nms_{session_id.hex}_{secret}', csrf


def _split(token, prefix):
    try:
        head, ident, secret = token.split('_', 2)
        if head != prefix:
            raise ValueError
        return uuid.UUID(hex=ident), secret
    except (ValueError, AttributeError):
        raise PlatformError('Invalid credentials.', 'unauthenticated') from None


def authenticate_session(conn, token, *, csrf=None, mutating=False):
    session_id, secret = _split(token, 'nms')
    row = conn.execute(
        '''SELECT s.*, now() - s.last_seen_at > %s AS idle, now() > s.absolute_expires_at AS expired
           FROM sessions s WHERE s.id = %s''', (SESSION_IDLE, session_id)).fetchone()
    if (row is None or row['revoked_at'] is not None or row['idle'] or row['expired']
            or not hmac.compare_digest(bytes(row['secret_hash']), _sha(secret))):
        raise PlatformError('Invalid or expired session.', 'unauthenticated')
    if mutating and (csrf is None or not hmac.compare_digest(bytes(row['csrf_hash']), _sha(csrf))):
        raise PlatformError('Missing or invalid CSRF token.', 'csrf_failed')
    conn.execute('UPDATE sessions SET last_seen_at = now() WHERE id = %s', (session_id,))
    from ..scope import OrgScope
    principal = get_principal(conn, OrgScope(row['org_id']), row['principal_id'])
    return Authenticated(principal, 'session', session_id=session_id)


def revoke_session(conn, token):
    session_id, _ = _split(token, 'nms')
    conn.execute('UPDATE sessions SET revoked_at = now() WHERE id = %s AND revoked_at IS NULL', (session_id,))


# Tokens -------------------------------------------------------------------------------

def issue_token(conn, scope, principal, scopes, *, expires_in=None):
    """Issue a scoped API token. The secret is returned once and stored only as SHA-256."""
    if not scopes:
        raise PlatformError('A token needs at least one scope.', 'invalid_scope')
    for item in scopes:
        if _parse_token_scope(item)[0] == 'ingest' and principal.kind != 'service':
            raise PlatformError('Ingestion scopes are issued only to service principals.', 'invalid_scope')
    token_id, secret = uuid.uuid4(), secrets.token_urlsafe(32)
    conn.execute(
        '''INSERT INTO api_tokens(org_id, id, principal_id, secret_hash, scopes, expires_at)
           VALUES (%s, %s, %s, %s, %s, CASE WHEN %s::interval IS NULL THEN NULL ELSE now() + %s::interval END)''',
        (scope.org_id, token_id, principal.id, _sha(secret), list(scopes), expires_in, expires_in))
    return f'nmk_{token_id.hex}_{secret}', token_id


def authenticate_token(conn, token):
    token_id, secret = _split(token, 'nmk')
    row = conn.execute(
        '''SELECT t.*, t.expires_at IS NOT NULL AND now() > t.expires_at AS expired FROM api_tokens t WHERE t.id = %s''',
        (token_id,)).fetchone()
    if (row is None or row['revoked_at'] is not None or row['expired']
            or not hmac.compare_digest(bytes(row['secret_hash']), _sha(secret))):
        raise PlatformError('Invalid or expired token.', 'unauthenticated')
    conn.execute('UPDATE api_tokens SET last_used_at = now() WHERE id = %s', (token_id,))
    from ..scope import OrgScope
    principal = get_principal(conn, OrgScope(row['org_id']), row['principal_id'])
    return Authenticated(principal, 'token', token_scopes=tuple(row['scopes']))


def revoke_token(conn, scope, token_id):
    conn.execute('UPDATE api_tokens SET revoked_at = now() WHERE org_id = %s AND id = %s AND revoked_at IS NULL',
                 (scope.org_id, token_id))


def _parse_token_scope(item):
    """Token scopes: 'role:<role>' or '<permission>:<scope_kind>:<scope_id>'."""
    parts = item.split(':')
    if len(parts) == 2 and parts[0] == 'role' and parts[1] in ROLE_PERMISSIONS:
        return ('role', parts[1])
    if len(parts) == 3 and parts[0] in ('ingest', 'read') and parts[1] in SCOPE_KINDS and parts[2]:
        return tuple(parts)
    raise PlatformError('Unsupported token scope.', 'invalid_scope')


# Authorization ------------------------------------------------------------------------

def bind_role(conn, scope, principal, role, scope_kind='org', scope_id=''):
    if role not in ROLE_PERMISSIONS or scope_kind not in SCOPE_KINDS:
        raise PlatformError('Unknown role or scope.', 'invalid_scope')
    if principal.kind == 'service' and role in SERVICE_FORBIDDEN_ROLES:
        raise PlatformError('Service principals cannot hold approval authority.', 'separation_of_duties')
    conn.execute(
        '''INSERT INTO role_bindings(org_id, principal_id, role, scope_kind, scope_id) VALUES (%s, %s, %s, %s, %s)
           ON CONFLICT DO NOTHING''', (scope.org_id, principal.id, role, scope_kind, scope_id))


def permissions(conn, auth, scope_kind='org', scope_id=''):
    """Effective permissions of an authenticated principal for one resource scope."""
    rows = conn.execute(
        '''SELECT role FROM role_bindings WHERE org_id = %s AND principal_id = %s
           AND (scope_kind = 'org' OR (scope_kind = %s AND scope_id = %s))''',
        (auth.principal.org_id, auth.principal.id, scope_kind, scope_id)).fetchall()
    granted = set().union(*(ROLE_PERMISSIONS[r['role']] for r in rows)) if rows else set()
    if auth.via != 'token':
        return granted
    # A token narrows its principal's role authority and never widens it. The
    # one exception is 'ingest', which exists only as an explicit per-source
    # token scope issued to a service principal.
    allowed, ingest = set(), False
    for item in auth.token_scopes:
        parsed = _parse_token_scope(item)
        if parsed[0] == 'role':
            allowed |= ROLE_PERMISSIONS[parsed[1]]
        elif parsed[1] == scope_kind and parsed[2] == scope_id:
            if parsed[0] == 'read':
                allowed.add('read')
            else:
                ingest = True
    granted &= allowed
    if ingest and auth.principal.kind == 'service':
        granted.add('ingest')
    return granted


def authorize(conn, auth, permission, scope_kind='org', scope_id=''):
    if permission not in permissions(conn, auth, scope_kind, scope_id):
        raise PlatformError('Not permitted.', 'forbidden')
