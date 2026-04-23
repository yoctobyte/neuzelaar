from neuzelaar.core.bus import Bus
from neuzelaar.core.fetch.gateway import SubresourceGateway
from neuzelaar.core.fetch.resource import FetchReason, Request, Resource
from neuzelaar.core.origin import parse_url
from neuzelaar.core.policy.rules import PolicyAction, PolicyEngine
from neuzelaar.document.subresources import PolicyHint, SubresourceRequest
from neuzelaar.shell_api.events import ResourceBlocked


def _page_resource(url: str = "https://example.com/") -> Resource:
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
        headers={},
        body=b"",
        claimed_mime="text/html",
        detected_mime="text/html",
        mime_confidence=1.0,
    )


def _planned(url: str, reason: FetchReason) -> SubresourceRequest:
    return SubresourceRequest(
        url=url,
        reason=reason,
        node_id=0,
        attr="src",
        policy_hint=PolicyHint.ACTIVE if reason == FetchReason.SCRIPT else PolicyHint.PASSIVE,
    )


def test_gateway_allows_same_origin_stylesheet() -> None:
    gateway = SubresourceGateway(policy_engine=PolicyEngine())

    decision = gateway.evaluate(
        _planned("https://example.com/styles.css", FetchReason.STYLESHEET),
        _page_resource(),
    )

    assert decision.allowed is True
    assert decision.policy.action == PolicyAction.ALLOW
    assert decision.normalized_url == "https://example.com/styles.css"
    assert decision.request.reason == FetchReason.STYLESHEET


def test_gateway_blocks_third_party_script_and_publishes_one_event() -> None:
    bus = Bus()
    blocked: list[ResourceBlocked] = []
    bus.subscribe(ResourceBlocked, blocked.append)
    gateway = SubresourceGateway(policy_engine=PolicyEngine(), bus=bus)

    decision = gateway.evaluate(
        _planned("https://cdn.third-party.test/app.js", FetchReason.SCRIPT),
        _page_resource(),
    )

    assert decision.allowed is False
    assert decision.policy.action == PolicyAction.BLOCK
    assert len(blocked) == 1
    assert blocked[0].url == "https://cdn.third-party.test/app.js"


def test_gateway_does_not_publish_when_bus_is_none() -> None:
    gateway = SubresourceGateway(policy_engine=PolicyEngine(), bus=None)

    decision = gateway.evaluate(
        _planned("https://cdn.third-party.test/app.js", FetchReason.SCRIPT),
        _page_resource(),
    )

    assert decision.allowed is False


def test_gateway_evaluate_plan_returns_decision_per_planned_request() -> None:
    gateway = SubresourceGateway(policy_engine=PolicyEngine())
    allowed = _planned("https://example.com/styles.css", FetchReason.STYLESHEET)
    blocked = _planned("https://cdn.third-party.test/app.js", FetchReason.SCRIPT)
    plan = (allowed, blocked)

    gates = gateway.evaluate_plan(plan, _page_resource())

    assert gates[allowed].allowed is True
    assert gates[blocked].allowed is False
    assert set(gates.keys()) == {allowed, blocked}
