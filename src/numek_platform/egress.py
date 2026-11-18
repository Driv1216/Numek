"""Allowlisted outbound HTTP for notifications and integrations.

Rules:

* destination (scheme, host, port) must match an organisation allowlist entry;
* the host is resolved once and every address is checked: loopback,
  link-local (including cloud metadata), private, shared, multicast, reserved and
  unspecified ranges are refused unless the entry's CIDR explicitly covers them,
  so legitimate internal customer endpoints can be allowed deliberately;
* the connection goes to the *checked* address (no second DNS lookup, which
  defeats rebinding), with TLS verification and SNI for the original host;
* redirects are never followed, and timeouts and response size are bounded.
"""
import http.client
import ipaddress
import socket
import ssl
from dataclasses import dataclass
from urllib.parse import urlsplit

from .errors import PlatformError

MAX_RESPONSE = 64 * 1024


@dataclass(frozen=True)
class AllowEntry:
    scheme: str
    host: str
    port: int
    cidr: str | None = None


def load_allowlist(conn, scope):
    rows = conn.execute('SELECT scheme, host, port, cidr FROM egress_allowlist WHERE org_id = %s', (scope.org_id,)).fetchall()
    return [AllowEntry(r['scheme'], r['host'].lower(), r['port'], None if r['cidr'] is None else str(r['cidr'])) for r in rows]


def _sensitive(address):
    return (address.is_loopback or address.is_link_local or address.is_private or address.is_multicast
            or address.is_reserved or address.is_unspecified or getattr(address, 'is_site_local', False)
            or (isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None)
            or address in ipaddress.ip_network('100.64.0.0/10'))


def check_destination(url, allowlist, *, resolver=socket.getaddrinfo):
    """Return (entry, host, port, checked_address) or raise ``egress_denied``."""
    parts = urlsplit(url)
    scheme, host = parts.scheme.lower(), (parts.hostname or '').lower()
    if scheme not in ('https', 'http') or not host or parts.username or parts.password:
        raise PlatformError('Destination is not permitted.', 'egress_denied')
    port = parts.port or (443 if scheme == 'https' else 80)
    entry = next((e for e in allowlist if e.scheme == scheme and e.host == host and e.port == port), None)
    if entry is None:
        raise PlatformError('Destination is not on the allowlist.', 'egress_denied')
    try:
        infos = resolver(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise PlatformError('Destination could not be resolved.', 'egress_unresolved', retryable=True) from exc
    addresses = []
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if _sensitive(address) and not (entry.cidr and address in ipaddress.ip_network(entry.cidr)):
            raise PlatformError('Destination resolves to a protected network range.', 'egress_denied')
        addresses.append(address)
    if not addresses:
        raise PlatformError('Destination could not be resolved.', 'egress_unresolved', retryable=True)
    return entry, host, port, addresses[0]


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, port, address, **kwargs):
        super().__init__(host, port, context=ssl.create_default_context(), **kwargs)
        self._address = str(address)

    def connect(self):
        sock = socket.create_connection((self._address, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host, port, address, **kwargs):
        super().__init__(host, port, **kwargs)
        self._address = str(address)

    def connect(self):
        self.sock = socket.create_connection((self._address, self.port), self.timeout)


def post(url, body, headers, allowlist, *, timeout=10, resolver=socket.getaddrinfo):
    """POST to an allowlisted destination. Returns (status, bounded body). Never follows redirects."""
    entry, host, port, address = check_destination(url, allowlist, resolver=resolver)
    parts = urlsplit(url)
    path = (parts.path or '/') + (f'?{parts.query}' if parts.query else '')
    cls = _PinnedHTTPSConnection if entry.scheme == 'https' else _PinnedHTTPConnection
    connection = cls(host, port, address, timeout=timeout)
    try:
        connection.request('POST', path, body=body, headers=headers)
        response = connection.getresponse()
        data = response.read(MAX_RESPONSE + 1)[:MAX_RESPONSE]
        return response.status, data
    except OSError as exc:
        raise PlatformError('Destination did not respond.', 'egress_failed', retryable=True) from exc
    finally:
        connection.close()
