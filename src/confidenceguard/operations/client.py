"""``OpsClient``: a small Python client for the CG7 operations API (standard library only).

    client = OpsClient('https://numek.example')
    client.login('alice', password)                     # session cookie + CSRF, or OpsClient(url, token='nmk_...')
    incidents = client.get('/incidents', state='open')['items']
    client.post(f"/incidents/{incidents[0]['id']}/transition", {'to': 'acknowledged'})

Errors raise ``OpsError(code, message, status)``, which carries the API's error code.
"""
import http.cookiejar
import json
import urllib.error
import urllib.parse
import urllib.request

PREFIX = '/api/ops/v1'


class OpsError(Exception):
    def __init__(self, code, message, status):
        super().__init__(f'{code}: {message}')
        self.code, self.message, self.status = code, message, status


class OpsClient:
    def __init__(self, endpoint, *, token=None, timeout=30.0):
        self.base = endpoint.rstrip('/') + PREFIX
        self.token, self.timeout, self.csrf = token, timeout, None
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def _request(self, method, path, body=None, query=None, raw=False):
        url = self.base + path + ('?' + urllib.parse.urlencode({k: v for k, v in (query or {}).items() if v is not None}) if query else '')
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(url, data=data, method=method, headers={'Content-Type': 'application/json'})
        if self.token:
            request.add_header('Authorization', f'Bearer {self.token}')
        if self.csrf and method not in ('GET', 'HEAD'):
            request.add_header('X-CSRF-Token', self.csrf)
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                payload = response.read()
        except urllib.error.HTTPError as exc:
            try:
                error = json.loads(exc.read())['error']
            except Exception:
                error = {'code': 'http_error', 'message': str(exc)}
            raise OpsError(error['code'], error['message'], exc.code) from None
        if raw:
            return payload.decode()
        return json.loads(payload)['data']

    def login(self, name, password):
        self.csrf = self._request('POST', '/session', {'name': name, 'password': password})['csrf']
        return self

    def logout(self):
        return self._request('DELETE', '/session')

    def get(self, path, **query):
        return self._request('GET', path, query=query)

    def post(self, path, body=None):
        return self._request('POST', path, body or {})

    def report_html(self, incident_id, audience='shareable'):
        return self._request('GET', f'/incidents/{incident_id}/report', query={'format': 'html', 'audience': audience}, raw=True)
