"""Reusable page loading pipeline for headless and future shells."""

from __future__ import annotations

from dataclasses import dataclass

from neuzelaar.core.bus import Bus
from neuzelaar.core.fetch.client import FetchClient
from neuzelaar.core.fetch.cookies import SessionCookieJar
from neuzelaar.core.fetch.resource import FetchReason, Request, Resource
from neuzelaar.core.handlers.registry import HandlerResult, default_registry
from neuzelaar.core.mime.classifier import MimeDecision, classify_resource
from neuzelaar.core.origin import parse_url, resolve_url
from neuzelaar.core.policy.rules import PolicyDecision, PolicyEngine
from neuzelaar.document.links import DocumentLink, extract_links
from neuzelaar.document.subresources import SubresourceRequest, extract_subresources
from neuzelaar.render.text_only import render_text
from neuzelaar.shell_api.events import PageFailed, PageLoadFinished, PageLoadStarted, ResourceBlocked


@dataclass(frozen=True, slots=True)
class PlannedSubresourceDecision:
    request: SubresourceRequest
    decision: PolicyDecision
    normalized_url: str


@dataclass(frozen=True, slots=True)
class PageLoadResult:
    resource: Resource
    mime_decision: MimeDecision
    handler_result: HandlerResult
    rendered_text: str
    links: tuple[DocumentLink, ...]
    planned_subresources: tuple[PlannedSubresourceDecision, ...]


class PageLoader:
    def __init__(
        self,
        *,
        fetch_client: FetchClient | None = None,
        policy_engine: PolicyEngine | None = None,
        cookie_jar: SessionCookieJar | None = None,
        bus: Bus | None = None,
    ) -> None:
        self.fetch_client = fetch_client or FetchClient()
        self.policy_engine = policy_engine or PolicyEngine()
        self.cookie_jar = cookie_jar
        self.bus = bus

    def load(self, url: str) -> PageLoadResult:
        url_record = parse_url(url)
        headers: dict[str, str] = {}
        if self.cookie_jar is not None:
            self.cookie_jar.add_cookie_header(url_record.normalized, headers)
        top_level_request = Request(
            url=url_record.normalized,
            method="GET",
            headers=headers,
            body=None,
            reason=FetchReason.TOP_LEVEL,
            initiator=None,
            origin=url_record.origin,
            context_origin=url_record.origin,
        )
        self._publish(PageLoadStarted(url_record.normalized))
        try:
            resource = self.fetch_client.fetch(top_level_request)
        except Exception as exc:
            self._publish(PageFailed(url_record.normalized, str(exc)))
            raise
        if self.cookie_jar is not None:
            self.cookie_jar.store_from_resource(resource)
        mime_decision = classify_resource(resource)
        handler_result = default_registry().handle(resource, mime_decision)
        rendered_text = self._render(handler_result)
        links = self._extract_links(handler_result)
        planned = self._evaluate_planned_subresources(resource, handler_result)
        self._publish(PageLoadFinished(resource.final_url, resource.status))
        return PageLoadResult(
            resource=resource,
            mime_decision=mime_decision,
            handler_result=handler_result,
            rendered_text=rendered_text,
            links=links,
            planned_subresources=tuple(planned),
        )

    def _render(self, handler_result: HandlerResult) -> str:
        if handler_result.kind == "document":
            return render_text(handler_result.value)
        if handler_result.kind == "text":
            return handler_result.value
        return f"[{handler_result.kind}] {handler_result.value}"

    def _extract_links(self, handler_result: HandlerResult) -> tuple[DocumentLink, ...]:
        if handler_result.kind != "document":
            return ()
        return extract_links(handler_result.value)

    def _evaluate_planned_subresources(
        self,
        resource: Resource,
        handler_result: HandlerResult,
    ) -> list[PlannedSubresourceDecision]:
        if handler_result.kind != "document":
            return []

        result: list[PlannedSubresourceDecision] = []
        for planned in extract_subresources(handler_result.value):
            subresource_record = resolve_url(resource.final_url, planned.url)
            subresource_request = Request(
                url=subresource_record.normalized,
                method="GET",
                headers={},
                body=None,
                reason=planned.reason,
                initiator=resource.id,
                origin=subresource_record.origin,
                context_origin=resource.request.context_origin,
            )
            decision = self.policy_engine.evaluate_fetch(subresource_request)
            if not decision.allowed:
                self._publish(ResourceBlocked(subresource_record.normalized, decision.reason))
            result.append(
                PlannedSubresourceDecision(
                    request=planned,
                    decision=decision,
                    normalized_url=subresource_record.normalized,
                )
            )
        return result

    def _publish(self, event: object) -> None:
        if self.bus is not None:
            self.bus.publish(event)
