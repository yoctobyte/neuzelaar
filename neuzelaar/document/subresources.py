"""Subresource discovery from the internal document tree."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from neuzelaar.core.fetch.resource import FetchReason
from neuzelaar.core.origin import resolve_url
from neuzelaar.document.dom import Document, Element, NodeId, walk


class PolicyHint(Enum):
    PASSIVE = "passive"
    ACTIVE = "active"


@dataclass(frozen=True, slots=True)
class SubresourceRequest:
    url: str
    reason: FetchReason
    node_id: NodeId
    attr: str
    policy_hint: PolicyHint


def extract_subresources(document: Document) -> list[SubresourceRequest]:
    requests: list[SubresourceRequest] = []
    for node in walk(document):
        if not isinstance(node, Element):
            continue
        tag = node.tag.lower()
        if tag == "script":
            _append_if_present(
                requests,
                document,
                node,
                attr="src",
                reason=FetchReason.SCRIPT,
                policy_hint=PolicyHint.ACTIVE,
            )
        elif tag == "img":
            _append_if_present(
                requests,
                document,
                node,
                attr="src",
                reason=FetchReason.IMAGE,
                policy_hint=PolicyHint.PASSIVE,
            )
        elif tag == "link" and _is_stylesheet_link(node):
            _append_if_present(
                requests,
                document,
                node,
                attr="href",
                reason=FetchReason.STYLESHEET,
                policy_hint=PolicyHint.PASSIVE,
            )
        elif tag == "iframe":
            _append_if_present(
                requests,
                document,
                node,
                attr="src",
                reason=FetchReason.IFRAME,
                policy_hint=PolicyHint.ACTIVE,
            )
    return requests


def _append_if_present(
    requests: list[SubresourceRequest],
    document: Document,
    node: Element,
    *,
    attr: str,
    reason: FetchReason,
    policy_hint: PolicyHint,
) -> None:
    raw_url = node.attr(attr)
    if not raw_url:
        return
    requests.append(
        SubresourceRequest(
            url=resolve_url(document.url, raw_url).normalized,
            reason=reason,
            node_id=node.id,
            attr=attr,
            policy_hint=policy_hint,
        )
    )


def _is_stylesheet_link(node: Element) -> bool:
    rel = node.attr("rel")
    if not rel:
        return False
    return "stylesheet" in {part.strip().lower() for part in rel.split()}
