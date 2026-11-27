"""Serving the operations API and console under gunicorn (plan C.2, H.10; S10 packaging).

``confidenceguard ops serve`` runs gunicorn's ``gthread`` workers in-process (no separate gunicorn command line), so
the serving guard always applies: beyond loopback, serving needs TLS or a declared trusted reverse proxy.

- **Process model.** One master and ``workers`` forked processes, each with ``threads`` request threads. The app is
  not preloaded, so every worker opens its own database connections after the fork. On a P-LOCAL installation the
  master starts the cluster before forking, so workers never race to start it.
- **Recycling.** Workers are recycled after ``max_requests`` requests (with jitter); a worker silent for ``timeout``
  seconds is replaced.
- **TLS** terminates in gunicorn (``certfile`` / ``keyfile``), or at a trusted proxy. With ``trusted_proxy``, the
  proxy's ``X-Forwarded-Proto`` and ``X-Forwarded-For`` are honoured only from ``proxy_ips``.
- **Logs.** Access logs are one JSON object per request with the path and no query string, and never a body.
"""

ACCESS_LOG_FORMAT = ('{"at":"%(t)s","method":"%(m)s","path":"%(U)s","status":%(s)s,"bytes":"%(B)s","ms":%(M)s,'
                     '"worker":"%(p)s"}')


def options(host, port, *, workers=2, threads=8, timeout=60, tls_cert=None, tls_key=None, trusted_proxy=False,
            proxy_ips='127.0.0.1', max_requests=1000):
    """gunicorn settings for the operations API. Pure, so tests can check them without serving."""
    from . import api
    tls = bool(tls_cert and tls_key)
    api.serve_guard(host, tls=tls, trusted_proxy=trusted_proxy)
    if workers < 1 or threads < 1:
        raise ValueError('workers and threads are at least 1')
    bind = f'[{host}]:{port}' if ':' in host else f'{host}:{port}'
    settings = {
        'bind': [bind], 'workers': workers, 'worker_class': 'gthread', 'threads': threads, 'timeout': timeout,
        'graceful_timeout': 30, 'keepalive': 5, 'preload_app': False, 'max_requests': max_requests,
        'max_requests_jitter': max(1, max_requests // 10), 'accesslog': '-', 'errorlog': '-', 'loglevel': 'info',
        'access_log_format': ACCESS_LOG_FORMAT, 'proc_name': 'numek-ops-api',
        # Only the declared proxy may set the scheme and client address.
        'forwarded_allow_ips': proxy_ips if trusted_proxy else '', 'proxy_allow_ips': proxy_ips if trusted_proxy else '',
        'secure_scheme_headers': {'X-FORWARDED-PROTO': 'https'} if trusted_proxy else {},
    }
    if tls:
        settings.update(certfile=tls_cert, keyfile=tls_key)
    return settings


def serve(root, host, port, **kwargs):
    """Run the API under gunicorn until SIGTERM / SIGINT (graceful)."""
    from gunicorn.app.base import BaseApplication
    from numek_platform.installation import Installation
    from . import api
    settings = options(host, port, **kwargs)
    secure = bool(settings.get('certfile')) or bool(kwargs.get('trusted_proxy'))
    Installation(root).dsn()                       # P-LOCAL: start the cluster in the master, before forking

    class OperationsApplication(BaseApplication):
        def load_config(self):
            for key, value in settings.items():
                self.cfg.set(key, value)

        def load(self):                            # runs in each worker after the fork (preload_app is off)
            return api.create_app(Installation(root), secure_cookies=secure)

    OperationsApplication().run()
