from neuzelaar.core.origin import is_third_party, parse_url, resolve_url, same_origin


def test_http_default_port_normalizes_to_same_origin() -> None:
    left = parse_url("http://Example.com/")
    right = parse_url("http://example.com:80/path")

    assert left.normalized == "http://example.com/"
    assert same_origin(left.origin, right.origin)


def test_non_default_port_is_different_origin() -> None:
    left = parse_url("https://example.com/")
    right = parse_url("https://example.com:8443/")

    assert is_third_party(right.origin, left.origin)


def test_relative_url_resolution() -> None:
    resolved = resolve_url("https://example.com/docs/page.html", "../img/logo.png")

    assert resolved.normalized == "https://example.com/img/logo.png"


def test_opaque_origins_are_never_same_origin() -> None:
    left = parse_url("data:text/plain,hello")
    right = parse_url("data:text/plain,hello")

    assert not same_origin(left.origin, right.origin)


def test_resolve_url_with_absolute_path() -> None:
    resolved = resolve_url("https://example.com/a/b", "/c")
    assert resolved.normalized == "https://example.com/c"


def test_resolve_url_with_full_url() -> None:
    resolved = resolve_url("https://example.com/", "https://other.com/")
    assert resolved.normalized == "https://other.com/"
