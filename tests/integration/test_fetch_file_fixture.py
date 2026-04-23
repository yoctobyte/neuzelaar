from pathlib import Path

from neuzelaar.core.fetch.client import FetchClient
from neuzelaar.core.fetch.resource import FetchReason, Request
from neuzelaar.core.origin import parse_url


def test_fetch_local_file_fixture() -> None:
    fixture = Path("tests/fixtures/sites/example.html").resolve().as_uri()
    record = parse_url(fixture)
    request = Request(
        url=record.normalized,
        method="GET",
        headers={},
        body=None,
        reason=FetchReason.TOP_LEVEL,
        initiator=None,
        origin=record.origin,
        context_origin=record.origin,
    )

    resource = FetchClient().fetch(request)

    assert resource.status == 200
    assert resource.final_url == record.normalized
    assert b"Example Domain" in resource.body
    assert resource.content_hash
