from pathlib import Path

from neuzelaar.core.fetch.cookies import PersistentCookieJar
from neuzelaar.core.fetch.resource import FetchReason, Request, Resource
from neuzelaar.core.origin import parse_url


def make_resource(url: str, set_cookie: str) -> Resource:
    record = parse_url(url)
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
    return Resource.from_body(
        request=request,
        final_url=record.normalized,
        status=200,
        headers={"Set-Cookie": set_cookie},
        body=b"",
    )


def test_persistent_cookie_jar_round_trips_to_disk(tmp_path) -> None:
    path = tmp_path / "cookies.json"
    jar = PersistentCookieJar(path=path)
    jar.store_from_resource(make_resource("https://example.com/", "sid=abc; Path=/"))

    reloaded = PersistentCookieJar(path=path)

    assert reloaded.get("https://example.com/", "sid") == "abc"
    headers: dict[str, str] = {}
    reloaded.add_cookie_header("https://example.com/docs", headers)
    assert headers == {"Cookie": "sid=abc"}
