"""Std-lib HTTP plumbing shared by every source.

:class:`HttpClient` does retrying JSON GET/POST over per-thread keep-alive connections:
every worker thread holds one persistent connection per host. This uses ``http.client``
rather than ``urllib`` because the latter sends ``Connection: close``, paying a fresh
TCP+TLS handshake per request — the dominant cost when thousands of small requests hit
the same host. The price of going low-level is handled here: redirects are followed
manually (the PyPI JSON API redirects non-normalised package names), and a reused
connection the server has meanwhile closed gets one immediate retry on a fresh one
before counting as a failure.
"""
import http.client
import json
import threading
import time
import urllib.parse
import xmlrpc.client
from typing import Any, Dict, Optional, Tuple

from . import logger
from .config import HTTP_BACKOFF_SECONDS, HTTP_RETRIES, USER_AGENT

RETRYABLE_HTTP_STATUS = (429, 500, 502, 503, 504)
REDIRECT_STATUS = (301, 302, 303, 307, 308)
MAX_REDIRECTS = 5


class TimeoutTransport(xmlrpc.client.Transport):
    """XML-RPC transport that applies a per-connection timeout."""

    def __init__(self, timeout: int) -> None:
        super().__init__()
        self.user_agent = USER_AGENT
        self._timeout = timeout

    def make_connection(self, host) -> http.client.HTTPConnection:
        connection = super().make_connection(host)
        connection.timeout = self._timeout
        return connection


class HttpClient:
    """Retrying std-lib JSON HTTP client (GET/POST) with per-thread keep-alive connections."""

    def __init__(self, timeout: int, user_agent: str = USER_AGENT) -> None:
        self.timeout = timeout
        self.user_agent = user_agent
        self._local = threading.local()

    def get_json(self, url: str, accept: str = 'application/json',
                 headers: Optional[dict] = None) -> Optional[Any]:
        return self._request_json(url, accept=accept, headers=headers)

    def post_json(self, url: str, payload: Any, accept: str = 'application/json',
                  headers: Optional[dict] = None) -> Optional[Any]:
        body = json.dumps(payload).encode('utf-8')
        return self._request_json(url, accept=accept, headers=headers, data=body)

    def _request_json(self, url: str, accept: str, headers: Optional[dict],
                      data: Optional[bytes] = None) -> Optional[Any]:
        merged = {'User-Agent': self.user_agent, 'Accept': accept}
        if data is not None:
            merged['Content-Type'] = 'application/json'
        merged.update(headers or {})
        method = 'POST' if data is not None else 'GET'

        for attempt in range(1, HTTP_RETRIES + 1):
            try:
                status, body = self._exchange(method, url, merged, data)
            except (OSError, http.client.HTTPException) as error:
                if attempt == HTTP_RETRIES:
                    logger.warning('%s %s failed: %s', method, url, error)
                    return None
            else:
                if status == 404:
                    return None

                if 200 <= status < 300:
                    try:
                        return json.loads(body)
                    except json.JSONDecodeError as error:
                        if attempt == HTTP_RETRIES:
                            logger.warning('%s %s failed: %s', method, url, error)
                            return None

                elif status not in RETRYABLE_HTTP_STATUS or attempt == HTTP_RETRIES:
                    logger.warning('%s %s failed: HTTP %s', method, url, status)
                    return None

            time.sleep(HTTP_BACKOFF_SECONDS * attempt)

        return None

    def _exchange(self, method: str, url: str, headers: dict,
                  data: Optional[bytes]) -> Tuple[int, bytes]:
        """One request/response on the calling thread's keep-alive connection.

        Follows redirects (also cross-host); a reused connection the server has closed in
        the meantime is retried once on a fresh one before the error propagates to the
        outer retry loop. The body is always read in full so the connection stays reusable.
        """
        for _hop in range(MAX_REDIRECTS):
            parts = urllib.parse.urlsplit(url)
            target = urllib.parse.urlunsplit(('', '', parts.path or '/', parts.query, ''))

            for is_retry in (False, True):
                connection = self._connection(parts)
                try:
                    connection.request(method, target, body=data, headers=headers)
                    response = connection.getresponse()
                    body = response.read()
                    break
                except (OSError, http.client.HTTPException):
                    self._drop(parts)
                    if is_retry:
                        raise

            location = response.getheader('Location')
            if response.status in REDIRECT_STATUS and location:
                url = urllib.parse.urljoin(url, location)
                if response.status == 303:
                    method, data = 'GET', None
                continue

            return response.status, body

        raise http.client.HTTPException('too many redirects for %s' % url)

    def _pool(self) -> Dict[Tuple[str, str], http.client.HTTPConnection]:
        if not hasattr(self._local, 'pool'):
            self._local.pool = {}
        return self._local.pool

    def _connection(self, parts: urllib.parse.SplitResult) -> http.client.HTTPConnection:
        pool = self._pool()
        key = (parts.scheme, parts.netloc)

        if key not in pool:
            factory = http.client.HTTPSConnection if parts.scheme == 'https' else http.client.HTTPConnection
            pool[key] = factory(parts.netloc, timeout=self.timeout)

        return pool[key]

    def _drop(self, parts: urllib.parse.SplitResult) -> None:
        connection = self._pool().pop((parts.scheme, parts.netloc), None)

        if connection is not None:
            connection.close()
