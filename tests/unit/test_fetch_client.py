from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import pytest

from neuzelaar.core.fetch.client import FetchClient, FetchError
from neuzelaar.core.fetch.resource import FetchReason, Request
from neuzelaar.core.origin import parse_url


def make_request(url: str, *, method: str = "GET") -> Request:
    record = parse_url(url)
    return Request(
        url=record.normalized,
        method=method,
        headers={},
        body=None,
        reason=FetchReason.TOP_LEVEL,
        initiator=None,
        origin=record.origin,
        context_origin=record.origin,
    )


def test_fetch_file_success() -> None:
    url = Path("tests/fixtures/sites/example.html").resolve().as_uri()

    resource = FetchClient().fetch(make_request(url))

    assert resource.status == 200
    assert b"Example Domain" in resource.body


def test_fetch_file_missing_raises_not_found() -> None:
    url = Path("tests/fixtures/sites/missing.html").resolve().as_uri()

    with pytest.raises(FetchError) as exc:
        FetchClient().fetch(make_request(url))

    assert exc.value.kind == "not_found"
    assert exc.value.url == url


def test_fetch_file_byte_cap_raises() -> None:
    url = Path("tests/fixtures/sites/example.html").resolve().as_uri()

    with pytest.raises(FetchError) as exc:
        FetchClient(max_bytes=4).fetch(make_request(url))

    assert exc.value.kind == "byte_cap"


def test_unsupported_method_raises() -> None:
    request = make_request("https://example.com/", method="PUT")

    with pytest.raises(FetchError) as exc:
        FetchClient().fetch(request)

    assert exc.value.kind == "unsupported_method"


def test_file_url_rejects_post() -> None:
    request = make_request(Path("tests/fixtures/sites/example.html").resolve().as_uri(), method="POST")

    with pytest.raises(FetchError) as exc:
        FetchClient().fetch(request)

    assert exc.value.kind == "unsupported_method"


def test_http_post_sends_request_body() -> None:
    server = HTTPServer(("127.0.0.1", 0), _PostEchoHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/submit"
        request = make_request(url, method="POST")
        request = Request(
            url=request.url,
            method=request.method,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            body=b"q=hello",
            reason=request.reason,
            initiator=request.initiator,
            origin=request.origin,
            context_origin=request.context_origin,
        )

        resource = FetchClient().fetch(request)

        assert resource.status == 200
        assert resource.body == b"q=hello"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_redirect_cap_is_explicit_contract() -> None:
    assert FetchClient(max_redirects=3).redirect_cap() == 3


class _PostEchoHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args) -> None:
        return
