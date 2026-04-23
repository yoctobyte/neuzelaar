from neuzelaar.core.fetch.cookies import SessionCookieJar
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


def test_session_cookie_jar_stores_and_adds_cookie_header() -> None:
    jar = SessionCookieJar()
    jar.store_from_resource(make_resource("https://example.com/", "sid=abc; Path=/"))
    headers: dict[str, str] = {}

    jar.add_cookie_header("https://example.com/docs", headers)

    assert headers == {"Cookie": "sid=abc"}
    assert jar.get("https://example.com/", "sid") == "abc"


def test_session_cookie_jar_does_not_send_to_other_origin() -> None:
    jar = SessionCookieJar()
    jar.store_from_resource(make_resource("https://example.com/", "sid=abc"))
    headers: dict[str, str] = {}

    jar.add_cookie_header("https://other.test/", headers)

    assert headers == {}
