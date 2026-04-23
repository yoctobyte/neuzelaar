from pathlib import Path

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
    request = make_request("https://example.com/", method="POST")

    with pytest.raises(FetchError) as exc:
        FetchClient().fetch(request)

    assert exc.value.kind == "unsupported_method"


def test_redirect_cap_is_explicit_contract() -> None:
    assert FetchClient(max_redirects=3).redirect_cap() == 3
