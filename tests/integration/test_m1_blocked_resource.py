from pathlib import Path

from neuzelaar.core.fetch.client import FetchClient
from neuzelaar.core.fetch.resource import FetchReason, Request
from neuzelaar.core.handlers.registry import default_registry
from neuzelaar.core.mime.classifier import classify_resource
from neuzelaar.core.origin import parse_url, resolve_url
from neuzelaar.core.policy.rules import PolicyAction, PolicyEngine
from neuzelaar.document.subresources import extract_subresources


def test_third_party_script_is_blocked_before_fetch() -> None:
    record = parse_url(Path("tests/fixtures/sites/third_party_script.html").resolve().as_uri())
    top_level_request = Request(
        url=record.normalized,
        method="GET",
        headers={},
        body=None,
        reason=FetchReason.TOP_LEVEL,
        initiator=None,
        origin=record.origin,
        context_origin=record.origin,
    )

    resource = FetchClient().fetch(top_level_request)
    handled = default_registry().handle(resource, classify_resource(resource))
    planned = extract_subresources(handled.value)

    assert len(planned) == 1

    subresource_record = resolve_url(record.normalized, planned[0].url)
    subresource_request = Request(
        url=subresource_record.normalized,
        method="GET",
        headers={},
        body=None,
        reason=planned[0].reason,
        initiator=resource.id,
        origin=subresource_record.origin,
        context_origin=record.origin,
    )
    decision = PolicyEngine().evaluate_fetch(subresource_request)

    assert decision.action == PolicyAction.BLOCK
    assert "third-party scripts" in decision.reason
