import http.client
from unittest.mock import patch

from addon_harvester.http import HttpClient

EXCHANGE = 'addon_harvester.http.HttpClient._exchange'
HTTPS_CONNECTION = 'http.client.HTTPSConnection'
SLEEP = 'time.sleep'


class FakeResponse:
    def __init__(self, status=200, body=b'{}', headers=None):
        self.status = status
        self._body = body
        self._headers = headers or {}

    def read(self):
        return self._body

    def getheader(self, name):
        return self._headers.get(name)


class FakeConnection:
    """Scripted http.client connection: pops one (response | exception) per request."""

    def __init__(self, script):
        self.script = list(script)
        self.requests = []
        self.bodies = []
        self._pending = None

    def request(self, method, target, body=None, headers=None):
        self.requests.append((method, target))
        self.bodies.append(body)
        self._pending = self.script.pop(0)

    def getresponse(self):
        if isinstance(self._pending, Exception):
            raise self._pending
        return self._pending

    def close(self):
        pass


class TestHttpClient:
    def test_holds_the_timeout(self):
        # do it
        client = HttpClient(42)

        # postcondition
        assert client.timeout == 42

    def test_get_json_returns_parsed_payload(self):
        # do it
        with patch(EXCHANGE, return_value=(200, b'{"ok": true}')):
            result = HttpClient(10).get_json('https://example.test/x')

        # postcondition
        assert result == {'ok': True}

    def test_get_json_returns_none_on_404(self):
        # do it
        with patch(EXCHANGE, return_value=(404, b'')):
            result = HttpClient(10).get_json('https://example.test/x')

        # postcondition
        assert result is None

    def test_retries_retryable_status_then_succeeds(self):
        # setup
        responses = [(503, b''), (200, b'{"ok": true}')]

        # do it
        with patch(EXCHANGE, side_effect=responses) as exchange, patch(SLEEP):
            result = HttpClient(10).get_json('https://example.test/x')

        # postcondition
        assert result == {'ok': True}
        assert exchange.call_count == 2

    def test_post_json_sends_the_encoded_payload(self):
        # setup
        connection = FakeConnection([FakeResponse(body=b'{"ok": true}')])

        # do it
        with patch(HTTPS_CONNECTION, return_value=connection):
            result = HttpClient(10).post_json('https://example.test/x', {'a': 1})

        # postcondition
        assert result == {'ok': True}
        assert connection.requests == [('POST', '/x')]


class TestKeepAlive:
    def test_reuses_one_connection_per_host(self):
        # setup
        connection = FakeConnection([FakeResponse(body=b'1'), FakeResponse(body=b'2')])

        # do it
        with patch(HTTPS_CONNECTION, return_value=connection) as factory:
            client = HttpClient(10)
            first = client.get_json('https://example.test/a')
            second = client.get_json('https://example.test/b')

        # postcondition
        assert (first, second) == (1, 2)
        assert factory.call_count == 1
        assert connection.requests == [('GET', '/a'), ('GET', '/b')]

    def test_follows_redirects(self):
        # setup
        connection = FakeConnection([
            FakeResponse(status=301, body=b'', headers={'Location': 'https://example.test/moved'}),
            FakeResponse(body=b'{"ok": true}'),
        ])

        # do it
        with patch(HTTPS_CONNECTION, return_value=connection):
            result = HttpClient(10).get_json('https://example.test/old')

        # postcondition
        assert result == {'ok': True}
        assert connection.requests == [('GET', '/old'), ('GET', '/moved')]

    def test_retries_once_on_a_stale_connection(self):
        # setup
        stale = FakeConnection([http.client.RemoteDisconnected('gone away')])
        fresh = FakeConnection([FakeResponse(body=b'{"ok": true}')])

        # do it
        with patch(HTTPS_CONNECTION, side_effect=[stale, fresh]) as factory:
            result = HttpClient(10).get_json('https://example.test/x')

        # postcondition
        assert result == {'ok': True}
        assert factory.call_count == 2
        assert fresh.requests == [('GET', '/x')]

    def test_303_redirect_turns_a_post_into_a_get(self):
        # setup
        connection = FakeConnection([
            FakeResponse(status=303, body=b'', headers={'Location': 'https://example.test/result'}),
            FakeResponse(body=b'{"ok": true}'),
        ])

        # do it
        with patch(HTTPS_CONNECTION, return_value=connection):
            result = HttpClient(10).post_json('https://example.test/job', {'a': 1})

        # postcondition
        assert result == {'ok': True}
        assert connection.requests == [('POST', '/job'), ('GET', '/result')]
        assert connection.bodies[1] is None

    def test_gives_up_after_too_many_redirects(self):
        # setup: every request answers with another redirect
        loop = FakeResponse(status=302, body=b'', headers={'Location': 'https://example.test/loop'})
        connection = FakeConnection([loop] * 50)

        # do it
        with patch(HTTPS_CONNECTION, return_value=connection), patch(SLEEP):
            result = HttpClient(10).get_json('https://example.test/start')

        # postcondition
        assert result is None

    def test_invalid_json_is_retried_then_dropped(self):
        # do it
        with patch(EXCHANGE, return_value=(200, b'not json')) as exchange, patch(SLEEP):
            result = HttpClient(10).get_json('https://example.test/x')

        # postcondition
        assert result is None
        assert exchange.call_count == 3
