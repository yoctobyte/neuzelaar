"""Reusable page loading pipeline for headless and future shells."""

from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from urllib.parse import urlencode

from neuzelaar.core.bus import Bus
from neuzelaar.core.diagnostics import LoadDiagnostics
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
from neuzelaar.document.dom import Document, Element, NodeId, Text, walk
from neuzelaar.document.scripts import extract_scripts
from neuzelaar.document.styles import ComputedStyle, StyleRule, compute_styles, root_style, style_text_blocks
from neuzelaar.document.subresources import SubresourceRequest, extract_subresources
from neuzelaar.engines.css.tinycss2_adapter import parse_stylesheet
from neuzelaar.engines.image.pillow_adapter import DecodedImageBitmap, ImageDecodeError, decode_image_bitmap
from neuzelaar.engines.js.interface import (
    DomBridge,
    JavaScriptEngine,
    PageContext,
    PageContextNode,
    ScriptExecutionRequest,
    ScriptExecutionResult,
    ScriptExecutionStatus,
    required_capability_for,
)
from neuzelaar.engines.js.noop import NoopJavaScriptEngine
from neuzelaar.render.text_only import render_text
from neuzelaar.shell_api.events import (
    DomMutated,
    ImageReady,
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
class _PreparedPage:
    resource: Resource
    mime_decision: MimeDecision
    handler_result: HandlerResult
    rendered_text: str
    links: tuple[DocumentLink, ...]
    forms: tuple[DocumentForm, ...]
    plan: tuple[SubresourceRequest, ...]
    gates: dict
    stylesheet_urls: tuple[str, ...]
    styles: dict
    style_rules: tuple[StyleRule, ...]
    root_style: ComputedStyle
    planned_subresources: tuple[PlannedSubresourceDecision, ...]


@dataclass(frozen=True, slots=True)
class PageLoadResult:
    resource: Resource
    mime_decision: MimeDecision
    handler_result: HandlerResult
    rendered_text: str
    links: tuple[DocumentLink, ...]
    forms: tuple[DocumentForm, ...]
    styles: dict
    style_rules: tuple[StyleRule, ...]
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
        diagnostics: LoadDiagnostics | None = None,
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
        self.diagnostics = diagnostics or LoadDiagnostics()
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
        prepared = self._prepare(url, method=method, form_data=form_data, reason=reason)
        if prepared is None:
            raise FetchError("aborted", "page preparation aborted", url=url)
        images = self._fetch_images(
            prepared.resource, prepared.handler_result, prepared.plan, prepared.gates
        )
        self.diagnostics.mark(f"fetched images ({len(images)})")
        scripts = self._plan_scripts(prepared.resource, prepared.handler_result)
        self.diagnostics.mark(f"planned scripts ({len(scripts)})")
        self._publish(PageLoadFinished(prepared.resource.final_url, prepared.resource.status))
        self.diagnostics.mark("page load finished")
        return self._build_result(prepared, images=images, scripts=scripts)

    def load_async(
        self,
        url: str,
        *,
        method: str = "GET",
        form_data: dict[str, str] | None = None,
        reason: FetchReason = FetchReason.TOP_LEVEL,
    ) -> tuple[PageLoadResult, Future[None]]:
        """Load a page, returning once the document and styles are ready.

        Image fetches run on a background pool; each completion mutates
        ``result.images`` and publishes an ImageReady event so the shell
        can repaint. The returned Future resolves when image work has
        settled. Headless callers should keep using ``load()``.
        """
        prepared = self._prepare(url, method=method, form_data=form_data, reason=reason)
        if prepared is None:
            raise FetchError("aborted", "page preparation aborted", url=url)
        scripts = self._plan_scripts(prepared.resource, prepared.handler_result)
        self.diagnostics.mark(f"planned scripts ({len(scripts)})")
        images: dict[NodeId, ImageAsset] = {}
        result = self._build_result(prepared, images=images, scripts=scripts)
        future = self._stream_images(
            prepared.handler_result, prepared.plan, prepared.gates, images
        )
        resource = prepared.resource

        def _on_images_done(_fut: Future[None]) -> None:
            self._publish(PageLoadFinished(resource.final_url, resource.status))
            self.diagnostics.mark(
                f"page load finished (streamed {len(images)} images)"
            )

        future.add_done_callback(_on_images_done)
        return result, future

    def _prepare(
        self,
        url: str,
        *,
        method: str,
        form_data: dict[str, str] | None,
        reason: FetchReason,
    ) -> "_PreparedPage | None":
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
        self.diagnostics.start(f"open {url_record.normalized}")
        try:
            resource = self.fetch_client.fetch(top_level_request)
        except Exception as exc:
            self._publish(PageFailed(url_record.normalized, str(exc)))
            raise
        cache_note = " (from cache)" if resource.cache.from_cache else ""
        self.diagnostics.mark(
            f"fetched top-level ({len(resource.body)} bytes, status {resource.status}){cache_note}"
        )
        if self.cookie_jar is not None:
            self.cookie_jar.store_from_resource(resource)
        mime_decision = classify_resource(resource)
        handler_result = default_registry().handle(resource, mime_decision)
        self.diagnostics.mark(f"parsed {mime_decision.kind}")
        rendered_text = self._render(handler_result)
        links = self._extract_links(handler_result)
        forms = self._extract_forms(handler_result)
        plan = self._build_subresource_plan(handler_result)
        gates = self.gateway.evaluate_plan(plan, resource)
        self.diagnostics.mark(f"planned subresources ({len(plan)})")
        stylesheet_urls, styles, style_rules = self._compute_styles(resource, handler_result, plan, gates)
        self.diagnostics.mark(f"computed styles ({len(stylesheet_urls)} stylesheets fetched)")
        page_root_style = self._root_style(handler_result, styles)
        planned = self._collect_planned_subresources(plan, gates)
        return _PreparedPage(
            resource=resource,
            mime_decision=mime_decision,
            handler_result=handler_result,
            rendered_text=rendered_text,
            links=links,
            forms=forms,
            plan=plan,
            gates=gates,
            stylesheet_urls=stylesheet_urls,
            styles=styles,
            style_rules=style_rules,
            root_style=page_root_style,
            planned_subresources=tuple(planned),
        )

    def _build_result(
        self,
        prepared: "_PreparedPage",
        *,
        images: dict[NodeId, ImageAsset],
        scripts: dict[NodeId, ScriptExecutionRecord],
    ) -> PageLoadResult:
        return PageLoadResult(
            resource=prepared.resource,
            mime_decision=prepared.mime_decision,
            handler_result=prepared.handler_result,
            rendered_text=prepared.rendered_text,
            links=prepared.links,
            forms=prepared.forms,
            styles=prepared.styles,
            style_rules=prepared.style_rules,
            root_style=prepared.root_style,
            stylesheet_urls=prepared.stylesheet_urls,
            planned_subresources=prepared.planned_subresources,
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
    ) -> tuple[tuple[str, ...], dict, tuple[StyleRule, ...]]:
        if handler_result.kind != "document":
            return (), {}, ()
        rules: list[StyleRule] = []
        stylesheet_urls: list[str] = []
        inline_blocks = list(style_text_blocks(handler_result.value))
        for block in inline_blocks:
            rules.extend(parse_stylesheet(block))
        self.diagnostics.mark(f"  parsed inline <style> ({len(inline_blocks)})")
        fetched = self._fetch_stylesheets(plan, gates)
        self.diagnostics.mark(f"  fetched external stylesheets ({len(fetched)})")
        for stylesheet_url, css_text in fetched:
            stylesheet_urls.append(stylesheet_url)
            rules.extend(parse_stylesheet(css_text))
        self.diagnostics.mark(f"  parsed all stylesheets ({len(rules)} rules total)")
        rules_tuple = tuple(rules)
        styles = compute_styles(handler_result.value, rules_tuple)
        self.diagnostics.mark(f"  applied styles to DOM ({len(styles)} nodes)")
        return tuple(stylesheet_urls), styles, rules_tuple

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

        # Phase 1: filter the plan in main-thread order so policy
        # gates, the count budget, and ResourceBlocked publication
        # stay deterministic. We collect the candidates, then dispatch
        # the slow fetch+decode work to a small thread pool.
        candidates: list[SubresourceRequest] = []
        for planned in plan:
            if planned.reason != FetchReason.IMAGE:
                continue
            if len(candidates) >= self.passive_budget.max_images:
                self._publish(ResourceBlocked(planned.url, "passive image budget exceeded"))
                continue
            gate = gates[planned]
            if not gate.allowed:
                continue
            candidates.append(planned)
        if not candidates:
            return {}

        # Phase 2: parallel fetch + decode. Each worker handles one
        # image; the FetchClient builds a fresh urllib opener per call,
        # so concurrent fetches don't share mutable redirect state.
        fetched: dict[SubresourceRequest, tuple[Resource, "DecodedImageBitmap"]] = {}
        max_workers = min(8, len(candidates))
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(self._fetch_and_decode_image, gates[planned].request): planned
                for planned in candidates
            }
            for future in as_completed(futures):
                planned = futures[future]
                try:
                    image_resource, bitmap = future.result()
                except FetchError as exc:
                    self._publish(
                        ResourceBlocked(gates[planned].normalized_url, f"image fetch failed: {exc}")
                    )
                    continue
                except ImageDecodeError:
                    continue
                fetched[planned] = (image_resource, bitmap)

        # Phase 3: apply the cumulative byte budget back in plan order
        # so behavior matches the previous serial implementation —
        # earlier images keep their slot when the budget overflows.
        result: dict[NodeId, ImageAsset] = {}
        used_bytes = 0
        for planned in candidates:
            entry = fetched.get(planned)
            if entry is None:
                continue
            image_resource, bitmap = entry
            if used_bytes + len(image_resource.body) > self.passive_budget.max_bytes:
                self._publish(
                    ResourceBlocked(image_resource.final_url, "passive resource byte budget exceeded")
                )
                continue
            used_bytes += len(image_resource.body)
            result[planned.node_id] = ImageAsset(url=image_resource.final_url, bitmap=bitmap)
        return result

    def _fetch_and_decode_image(self, request: Request) -> tuple[Resource, "DecodedImageBitmap"]:
        image_resource = self.fetch_client.fetch(request)
        bitmap = decode_image_bitmap(image_resource.body)
        return image_resource, bitmap

    def _stream_images(
        self,
        handler_result: HandlerResult,
        plan: tuple[SubresourceRequest, ...],
        gates: dict[SubresourceRequest, GateDecision],
        images_out: dict[NodeId, ImageAsset],
    ) -> Future[None]:
        """Fetch images in the background, mutating ``images_out`` and
        publishing ImageReady as each one decodes.

        Unlike the sync path the byte budget is applied in arrival order,
        not plan order — the trade-off for being able to commit results
        as they come in. Returns a Future that resolves when every image
        worker has finished (success, fetch error, or decode error).
        """
        done: Future[None] = Future()
        if handler_result.kind != "document":
            done.set_result(None)
            return done

        candidates: list[SubresourceRequest] = []
        for planned in plan:
            if planned.reason != FetchReason.IMAGE:
                continue
            if len(candidates) >= self.passive_budget.max_images:
                self._publish(ResourceBlocked(planned.url, "passive image budget exceeded"))
                continue
            gate = gates[planned]
            if not gate.allowed:
                continue
            candidates.append(planned)
        if not candidates:
            done.set_result(None)
            return done

        budget_lock = threading.Lock()
        used_bytes = [0]
        pending = [len(candidates)]
        pending_lock = threading.Lock()

        def finish_one() -> None:
            with pending_lock:
                pending[0] -= 1
                if pending[0] == 0:
                    done.set_result(None)

        def worker(planned: SubresourceRequest) -> None:
            try:
                gate = gates[planned]
                try:
                    image_resource, bitmap = self._fetch_and_decode_image(gate.request)
                except FetchError as exc:
                    self._publish(
                        ResourceBlocked(gate.normalized_url, f"image fetch failed: {exc}")
                    )
                    return
                except ImageDecodeError:
                    return
                with budget_lock:
                    if used_bytes[0] + len(image_resource.body) > self.passive_budget.max_bytes:
                        self._publish(
                            ResourceBlocked(
                                image_resource.final_url,
                                "passive resource byte budget exceeded",
                            )
                        )
                        return
                    used_bytes[0] += len(image_resource.body)
                    images_out[planned.node_id] = ImageAsset(
                        url=image_resource.final_url, bitmap=bitmap
                    )
                self._publish(ImageReady(node_id=planned.node_id, url=image_resource.final_url))
            finally:
                finish_one()

        pool = ThreadPoolExecutor(
            max_workers=min(8, len(candidates)),
            thread_name_prefix="neuz-image",
        )
        for planned in candidates:
            pool.submit(worker, planned)
        pool.shutdown(wait=False)
        return done

    def _plan_scripts(self, resource: Resource, handler_result: HandlerResult) -> dict[NodeId, ScriptExecutionRecord]:
        if handler_result.kind != "document":
            return {}

        # Each page starts with a fresh JS runtime: any timers/intervals
        # scheduled by the previous page must not survive navigation.
        # The PageContext lets ticked engines rebuild a host ``document``
        # tied to this page's real URL, title, and id-bearing nodes.
        # The DomBridge routes JS writes (textContent, innerHTML,
        # className, setAttribute, …) back into the page DOM and
        # publishes DomMutated so shells can repaint. No-op for engines
        # without persistent state.
        document: Document = handler_result.value
        bridge = _build_dom_bridge(document, self.bus)
        self.js_engine.reset_for_page(
            _build_page_context(resource, handler_result),
            dom_bridge=bridge,
        )

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


def _build_page_context(resource: Resource, handler_result: HandlerResult) -> PageContext:
    if handler_result.kind != "document":
        return PageContext(url=resource.final_url)
    document: Document = handler_result.value
    nodes: list[PageContextNode] = []
    for node in walk(document):
        if not isinstance(node, Element):
            continue
        element_id = node.attr("id")
        if not element_id:
            continue
        nodes.append(
            PageContextNode(
                id=element_id,
                tag=node.tag,
                text_content=_element_text(node),
                attributes=tuple(node.attrs.items()),
            )
        )
    return PageContext(
        url=resource.final_url,
        title=document.title,
        nodes=tuple(nodes),
    )


def _element_text(element: Element) -> str:
    parts: list[str] = []
    for descendant in walk(element):
        if isinstance(descendant, Text):
            parts.append(descendant.data)
    return "".join(parts)


def _build_dom_bridge(document: Document, bus: Bus | None) -> DomBridge:
    """Build the per-page DOM bridge handed to the JS engine.

    Maps the engine's view (node_id strings = HTML id attribute) back
    to real page Elements. Handles all the structural / attribute
    writes the engine knows how to forward and publishes DomMutated
    after each successful change so shells can debounce a repaint.

    Mutations against unknown ids or unhandled properties are silently
    ignored: the engine has already updated its host-side mirror, so
    JS reads stay consistent even when the page side can't follow.
    """
    elements_by_id: dict[str, Element] = {}
    for node in walk(document):
        if isinstance(node, Element):
            element_id = node.attr("id")
            if element_id:
                elements_by_id[element_id] = node
    fragment_id_counter = [0]

    def publish(node_id: str, property_name: str) -> None:
        if bus is not None:
            bus.publish(DomMutated(node_id=node_id, property=property_name))

    def replace_with_text(element: Element, value: object) -> None:
        text_id = NodeId(f"{element.id}.text")
        text_node = Text(id=text_id, parent=element, data=_to_str(value))
        element.children = [text_node]

    def mint_fragment_id() -> NodeId:
        n = fragment_id_counter[0]
        fragment_id_counter[0] = n + 1
        return NodeId(f"m{n}")

    def replace_children_html(element: Element, html_fragment: str) -> None:
        from neuzelaar.engines.html.html5lib_adapter import parse_html_fragment

        element.children = parse_html_fragment(
            html_fragment, parent=element, mint_id=mint_fragment_id
        )
        index_id_bearing_descendants(element)

    def index_id_bearing_descendants(root: Element) -> None:
        for node in walk(root):
            if isinstance(node, Element):
                element_id = node.attr("id")
                if element_id:
                    elements_by_id[element_id] = node

    def forget_id_bearing_descendants(root: Element) -> None:
        for node in walk(root):
            if isinstance(node, Element):
                element_id = node.attr("id")
                if element_id:
                    elements_by_id.pop(element_id, None)

    def set_property(node_id: str, property_name: str, value: object) -> None:
        element = elements_by_id.get(node_id)
        if element is None:
            return
        if property_name == "textContent":
            replace_with_text(element, value)
            publish(node_id, property_name)
            return
        if property_name == "innerHTML":
            replace_children_html(element, _to_str(value))
            publish(node_id, property_name)
            return
        if property_name == "className":
            element.attrs["class"] = _to_str(value)
            publish(node_id, property_name)
            return
        # Unknown: leave the host-side mirror alone (already updated).

    def get_attribute(node_id: str, name: str) -> str | None:
        element = elements_by_id.get(node_id)
        if element is None:
            return None
        return element.attr(name)

    def set_attribute(node_id: str, name: str, value: str) -> None:
        element = elements_by_id.get(node_id)
        if element is None:
            return
        element.attrs[name.lower()] = value
        publish(node_id, name.lower())

    def remove_attribute(node_id: str, name: str) -> None:
        element = elements_by_id.get(node_id)
        if element is None:
            return
        element.attrs.pop(name.lower(), None)
        publish(node_id, name.lower())

    def set_style_property(node_id: str, name: str, value: object) -> None:
        element = elements_by_id.get(node_id)
        if element is None:
            return
        from neuzelaar.document.styles import parse_declarations

        declarations = parse_declarations(element.attr("style") or "")
        css_name = _css_property_name(name)
        css_value = _to_str(value).strip()
        if css_value:
            declarations[css_name] = css_value
        else:
            declarations.pop(css_name, None)
        element.attrs["style"] = _serialize_style(declarations)
        publish(node_id, f"style.{css_name}")

    def insert_adjacent_html(node_id: str, position: str, html_fragment: str) -> None:
        element = elements_by_id.get(node_id)
        if element is None:
            return
        from neuzelaar.engines.html.html5lib_adapter import parse_html_fragment

        nodes = parse_html_fragment(
            html_fragment, parent=element, mint_id=mint_fragment_id
        )
        normalized = position.strip().lower()
        if normalized == "afterbegin":
            element.children[:0] = nodes
        elif normalized == "beforeend":
            element.children.extend(nodes)
        else:
            return
        index_id_bearing_descendants(element)
        publish(node_id, f"insertAdjacentHTML.{normalized}")

    def remove_node(node_id: str) -> None:
        element = elements_by_id.get(node_id)
        if element is None:
            return
        parent = element.parent
        children = getattr(parent, "children", None)
        if not isinstance(children, list):
            return
        try:
            children.remove(element)
        except ValueError:
            return
        forget_id_bearing_descendants(element)
        element.parent = None
        publish(node_id, "remove")

    return DomBridge(
        set_property=set_property,
        get_attribute=get_attribute,
        set_attribute=set_attribute,
        remove_attribute=remove_attribute,
        set_style_property=set_style_property,
        insert_adjacent_html=insert_adjacent_html,
        remove_node=remove_node,
    )


def _to_str(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _css_property_name(name: str) -> str:
    parts: list[str] = []
    for char in name:
        if char.isupper():
            parts.append("-")
            parts.append(char.lower())
        else:
            parts.append(char)
    return "".join(parts).strip().lower()


def _serialize_style(declarations: dict[str, str]) -> str:
    return "; ".join(f"{name}: {value}" for name, value in declarations.items())
