from neuzelaar.core.fetch.resource import FetchReason, Request
from neuzelaar.core.origin import parse_url
from neuzelaar.core.policy.profile import PolicyProfile
from neuzelaar.core.policy.rules import PolicyAction, PolicyEngine


def make_request(url: str, context_url: str, reason: FetchReason) -> Request:
    record = parse_url(url)
    context = parse_url(context_url)
    return Request(
        url=record.normalized,
        method="GET",
        headers={},
        body=None,
        reason=reason,
        initiator=None,
        origin=record.origin,
        context_origin=context.origin,
    )


def test_top_level_navigation_is_allowed() -> None:
    request = make_request("https://third.test/", "https://example.com/", FetchReason.TOP_LEVEL)

    assert PolicyEngine().evaluate_fetch(request).action == PolicyAction.ALLOW


def test_strict_profile_blocks_third_party_script() -> None:
    request = make_request("https://cdn.test/app.js", "https://example.com/", FetchReason.SCRIPT)

    assert PolicyEngine(PolicyProfile.STRICT).evaluate_fetch(request).action == PolicyAction.BLOCK


def test_strict_profile_allows_first_party_image() -> None:
    request = make_request("https://example.com/logo.png", "https://example.com/", FetchReason.IMAGE)

    assert PolicyEngine(PolicyProfile.STRICT).evaluate_fetch(request).action == PolicyAction.ALLOW


def test_strict_profile_blocks_third_party_passive_resource() -> None:
    request = make_request("https://cdn.test/logo.png", "https://example.com/", FetchReason.IMAGE)

    decision = PolicyEngine(PolicyProfile.STRICT).evaluate_fetch(request)

    assert decision.action == PolicyAction.BLOCK
    assert decision.reason == "strict mode blocks third-party resources"


def test_tracker_host_is_blocked_even_for_passive_resource() -> None:
    request = make_request(
        "https://www.google-analytics.com/pixel.gif",
        "https://example.com/",
        FetchReason.IMAGE,
    )

    decision = PolicyEngine(PolicyProfile.COMPATIBILITY).evaluate_fetch(request)

    assert decision.action == PolicyAction.BLOCK
    assert decision.reason == "known tracker/ad host"
