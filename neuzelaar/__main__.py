"""Command line entry point for early Neuzelaar milestones.

This module provides the 'headless' execution path for Milestone 1, 
driving the fetch, classify, parse, and render pipeline.
"""

from __future__ import annotations

import argparse

from neuzelaar.core.fetch.client import FetchClient
from neuzelaar.core.fetch.resource import FetchReason, Request
from neuzelaar.core.handlers.registry import default_registry
from neuzelaar.core.mime.classifier import classify_resource
from neuzelaar.core.origin import parse_url, resolve_url
from neuzelaar.core.policy.rules import PolicyEngine
from neuzelaar.document.subresources import extract_subresources
from neuzelaar.render.text_only import render_text


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m neuzelaar")
    parser.add_argument("url", help="URL or local path to fetch")
    args = parser.parse_args()

    url = args.url
    if "://" not in url:
        url = parse_url(url).normalized

    url_record = parse_url(url)
    request = Request(
        url=url_record.normalized,
        method="GET",
        headers={},
        body=None,
        reason=FetchReason.TOP_LEVEL,
        initiator=None,
        origin=url_record.origin,
        context_origin=url_record.origin,
    )
    resource = FetchClient().fetch(request)
    decision = classify_resource(resource)
    handled = default_registry().handle(resource, decision)
    print(f"{resource.status} {resource.final_url} [{decision.kind}]")
    if handled.kind == "document":
        print(render_text(handled.value))
        policy = PolicyEngine()
        for planned in extract_subresources(handled.value):
            subresource_record = resolve_url(resource.final_url, planned.url)
            subresource_request = Request(
                url=subresource_record.normalized,
                method="GET",
                headers={},
                body=None,
                reason=planned.reason,
                initiator=resource.id,
                origin=subresource_record.origin,
                context_origin=url_record.origin,
            )
            policy_decision = policy.evaluate_fetch(subresource_request)
            print(
                f"[{policy_decision.action.value}] "
                f"{planned.reason.name.lower()} {subresource_record.normalized}: "
                f"{policy_decision.reason}"
            )
    elif handled.kind == "text":
        print(handled.value)
    else:
        print(f"[{handled.kind}] {handled.value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
