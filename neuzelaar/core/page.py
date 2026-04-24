"""Reusable page loading pipeline for headless and future shells."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

from neuzelaar.core.bus import Bus
from neuzelaar.core.fetch.client import FetchClient, FetchError
from neuzelaar.core.fetch.cookies import SessionCookieJar
from neuzelaar.core.fetch.gateway import GateDecision, SubresourceGateway
from neuzelaar.core.fetch.resource import FetchReason, Request, Resource
from neuzelaar.core.handlers.registry import HandlerResult, default_registry
from neuzelaar.core.mime.classifier import MimeDecision, classify_resource
from neuzelaar.core.origin import Origin, parse_url, resolve_url
from neuzelaar.core.policy.permission_service import PermissionService
from neuzelaar.core.policy.permissions import PermissionStore
from neuzelaar.core.policy.rules import PolicyDecision, PolicyEngine
from neuzelaar.core.watchdog import check_resources
from neuzelaar.document.forms import DocumentForm, extract_forms
from neuzelaar.document.links import DocumentLink, extract_links
from neuzelaar.document.dom import NodeId
from neuzelaar.document.scripts import extract_scripts
from neuzelaar.document.styles import ComputedStyle, compute_styles, root_style, style_text_blocks
from neuzelaar.document.subresources import SubresourceRequest, extract_subresources
from neuzelaar.engines.css.tinycss2_adapter import parse_stylesheet
from neuzelaar.engines.image.pillow_adapter import DecodedImageBitmap, ImageDecodeError, decode_image_bitmap
from neuzelaar.engines.js.interface import (
    JavaScriptEngine,
    ScriptExecutionRequest,
    ScriptExecutionResult,
    ScriptExecutionStatus,
    required_capability_for,
)
from neuzelaar.engines.js.noop import NoopJavaScriptEngine
from neuzelaar.render.text_only import render_text
from neuzelaar.shell_api.events import (
    PageFailed,
    PageLoadFinished,
    PageLoadStarted,
    ResourceBlocked,
    ScriptBlocked,
)


@dataclass(frozen=True, slots=True)
class PlannedSubresourceDecision:
    request: SubresourceRequest
    decision: PolicyDecision
    normalized_url: str


@dataclass(frozen=True, slots=True)
class ImageAsset:
    url: str
    bitmap: DecodedImageBitmap


@dataclass(frozen=True, slots=True)
class ScriptExecutionRecord:
    url: str | None
    origin: Origin
    inline: bool
    source: str
    result: ScriptExecutionResult


@dataclass(frozen=True, slots=True)
class PassiveResourceBudget:
    max_stylesheets: int = 4
    max_images: int = 16
    max_bytes: int = 500_000


@dataclass(frozen=True, slots=True)
class PageLoadResult:
    resource: Resource
    mime_decision: MimeDecision
    handler_result: HandlerResult
    rendered_text: str
    links: tuple[DocumentLink, ...]
    forms: tuple[DocumentForm, ...]
    styles: dict
    root_style: ComputedStyle
    stylesheet_urls: tuple[str, ...]
    planned_subresources: tuple[PlannedSubresourceDecision, ...]
    images: dict[NodeId, ImageAsset]
    scripts: dict[NodeId, ScriptExecutionRecord]


class PageLoader:
    def __init__(
        self,
        *,
        fetch_client: FetchClient | None = None,
        policy_engine: PolicyEngine | None = None,
        cookie_jar: SessionCookieJar | None = None,
        bus: Bus | None = None,
        passive_budget: PassiveResourceBudget | None = None,
        js_engine: JavaScriptEngine | None = None,
        permission_store: PermissionStore | None = None,
        permission_service: PermissionService | None = None,
    ) -> None:
        self.fetch_client = fetch_client or FetchClient()
        self.policy_engine = policy_engine or PolicyEngine()
        self.cookie_jar = cookie_jar
        self.bus = bus
        self.passive_budget = passive_budget or PassiveResourceBudget()
        self.js_engine = js_engine or NoopJavaScriptEngine()
        self.permission_service = permission_service or PermissionService(
            store=permission_store or PermissionStore(),
            bus=self.bus,
        )
        self.permission_store = self.permission_service.store
        self.gateway = SubresourceGateway(
            policy_engine=self.policy_engine,
            bus=self.bus,
            cookie_jar=self.cookie_jar,
        )

    def load(
        self,
        url: str,
        *,
        method: str = "GET",
        form_data: dict[str, str] | None = None,
        reason: FetchReason = FetchReason.TOP_LEVEL,
    ) -> PageLoadResult:
        check_resources()
        url_record = parse_url(url)
        body = None
        final_url = url_record.normalized
        request_method = method.upper()
        if form_data and request_method == "GET":
            separator = "&" if "?" in final_url else "?"
            final_url = f"{final_url}{separator}{urlencode(form_data)}"
            url_record = parse_url(final_url)
        elif form_data and request_method == "POST":
            body = urlencode(form_data).encode("utf-8")
        headers: dict[str, str] = {}
        if body is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        if self.cookie_jar is not None:
            self.cookie_jar.add_cookie_header(url_record.normalized, headers)
        top_level_request = Request(
            url=url_record.normalized,
            method=request_method,
            headers=headers,
            body=body,
            reason=reason,
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
        forms = self._extract_forms(handler_result)
        plan = self._build_subresource_plan(handler_result)
        gates = self.gateway.evaluate_plan(plan, resource)
        stylesheet_urls, styles = self._compute_styles(resource, handler_result, plan, gates)
        page_root_style = self._root_style(handler_result, styles)
        planned = self._collect_planned_subresources(plan, gates)
        images = self._fetch_images(resource, handler_result, plan, gates)
        scripts = self._plan_scripts(resource, handler_result)
        self._publish(PageLoadFinished(resource.final_url, resource.status))
        return PageLoadResult(
            resource=resource,
            mime_decision=mime_decision,
            handler_result=handler_result,
            rendered_text=rendered_text,
            links=links,
            forms=forms,
            styles=styles,
            root_style=page_root_style,
            stylesheet_urls=stylesheet_urls,
            planned_subresources=tuple(planned),
            images=images,
            scripts=scripts,
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

    def _extract_forms(self, handler_result: HandlerResult) -> tuple[DocumentForm, ...]:
        if handler_result.kind != "document":
            return ()
        return extract_forms(handler_result.value)

    def _build_subresource_plan(
        self, handler_result: HandlerResult
    ) -> tuple[SubresourceRequest, ...]:
        if handler_result.kind != "document":
            return ()
        return tuple(extract_subresources(handler_result.value))

    def _compute_styles(
        self,
        resource: Resource,
        handler_result: HandlerResult,
        plan: tuple[SubresourceRequest, ...],
        gates: dict[SubresourceRequest, GateDecision],
    ) -> tuple[tuple[str, ...], dict]:
        if handler_result.kind != "document":
            return (), {}
        rules = []
        stylesheet_urls: list[str] = []
        for block in style_text_blocks(handler_result.value):
            rules.extend(parse_stylesheet(block))
        for stylesheet_url, css_text in self._fetch_stylesheets(plan, gates):
            stylesheet_urls.append(stylesheet_url)
            rules.extend(parse_stylesheet(css_text))
        return tuple(stylesheet_urls), compute_styles(handler_result.value, tuple(rules))

    def _root_style(self, handler_result: HandlerResult, styles: dict) -> ComputedStyle:
        if handler_result.kind != "document":
            return ComputedStyle()
        return root_style(handler_result.value, styles)

    def _fetch_stylesheets(
        self,
        plan: tuple[SubresourceRequest, ...],
        gates: dict[SubresourceRequest, GateDecision],
    ) -> list[tuple[str, str]]:
        results: list[tuple[str, str]] = []
        used_bytes = 0
        for planned in plan:
            if planned.reason != FetchReason.STYLESHEET:
                continue
            if len(results) >= self.passive_budget.max_stylesheets:
                self._publish(ResourceBlocked(planned.url, "passive stylesheet budget exceeded"))
                continue
            gate = gates[planned]
            if not gate.allowed:
                continue
            try:
                stylesheet_resource = self.fetch_client.fetch(gate.request)
            except FetchError as exc:
                self._publish(ResourceBlocked(gate.normalized_url, f"stylesheet fetch failed: {exc}"))
                continue
            if used_bytes + len(stylesheet_resource.body) > self.passive_budget.max_bytes:
                self._publish(ResourceBlocked(stylesheet_resource.final_url, "passive resource byte budget exceeded"))
                continue
            used_bytes += len(stylesheet_resource.body)
            if self.cookie_jar is not None:
                self.cookie_jar.store_from_resource(stylesheet_resource)
            css_text = stylesheet_resource.body.decode(
                stylesheet_resource.encoding or "utf-8",
                errors="replace",
            )
            results.append((stylesheet_resource.final_url, css_text))
        return results

    def _collect_planned_subresources(
        self,
        plan: tuple[SubresourceRequest, ...],
        gates: dict[SubresourceRequest, GateDecision],
    ) -> list[PlannedSubresourceDecision]:
        return [
            PlannedSubresourceDecision(
                request=planned,
                decision=gates[planned].policy,
                normalized_url=gates[planned].normalized_url,
            )
            for planned in plan
        ]

    def _fetch_images(
        self,
        resource: Resource,
        handler_result: HandlerResult,
        plan: tuple[SubresourceRequest, ...],
        gates: dict[SubresourceRequest, GateDecision],
    ) -> dict[NodeId, ImageAsset]:
        if handler_result.kind != "document":
            return {}

        result: dict[NodeId, ImageAsset] = {}
        used_bytes = 0
        for planned in plan:
            if planned.reason != FetchReason.IMAGE:
                continue
            if len(result) >= self.passive_budget.max_images:
                self._publish(ResourceBlocked(planned.url, "passive image budget exceeded"))
                continue
            gate = gates[planned]
            if not gate.allowed:
                continue
            try:
                image_resource = self.fetch_client.fetch(gate.request)
            except FetchError as exc:
                self._publish(ResourceBlocked(gate.normalized_url, f"image fetch failed: {exc}"))
                continue
            if used_bytes + len(image_resource.body) > self.passive_budget.max_bytes:
                self._publish(ResourceBlocked(image_resource.final_url, "passive resource byte budget exceeded"))
                continue
            used_bytes += len(image_resource.body)
            try:
                bitmap = decode_image_bitmap(image_resource.body)
            except ImageDecodeError:
                continue
            result[planned.node_id] = ImageAsset(url=image_resource.final_url, bitmap=bitmap)
        return result

    def _plan_scripts(self, resource: Resource, handler_result: HandlerResult) -> dict[NodeId, ScriptExecutionRecord]:
        if handler_result.kind != "document":
            return {}

        result: dict[NodeId, ScriptExecutionRecord] = {}
        for request in extract_scripts(handler_result.value):
            same_origin = None
            normalized_url = None
            origin = resource.request.context_origin
            if request.url is not None:
                script_record = resolve_url(resource.final_url, request.url)
                normalized_url = script_record.normalized
                same_origin = script_record.origin == resource.request.context_origin
                origin = script_record.origin
            execution_request = ScriptExecutionRequest(
                source=request.source,
                url=normalized_url,
                inline=request.inline,
                same_origin=same_origin,
                node_id=request.node_id,
            )
            # Permission check happens before execute so the grant flow is
            # correctly ordered for the day a real JS engine replaces the
            # noop. See chat/claude-to-codex.md, section on permission
            # service, for why this matters.
            self.permission_service.request(
                required_capability_for(execution_request),
                origin,
                resource.final_url,
            )
            execution = self.js_engine.execute(execution_request)
            record = ScriptExecutionRecord(
                url=normalized_url,
                origin=origin,
                inline=request.inline,
                source=request.source,
                result=execution,
            )
            result[request.node_id] = record
            if execution.status == ScriptExecutionStatus.BLOCKED:
                self._publish(ScriptBlocked(normalized_url or resource.final_url, execution.reason))
        return result

    def _publish(self, event: object) -> None:
        if self.bus is not None:
            self.bus.publish(event)
