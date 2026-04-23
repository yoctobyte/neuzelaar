"""Gateway that gates planned subresource fetches through policy.

Takes a SubresourceRequest produced by document-level subresource
extraction, shapes it into a fetch Request (with proper cookie headers
and origin context), runs it through the policy engine, and publishes
a ResourceBlocked event on denial.

Returns a structured GateDecision regardless of allow or deny so callers
can append to their own result structures uniformly. A single gate pass
over a plan means each denied subresource emits exactly one
ResourceBlocked event, avoiding the double-publish and silent-skip
inconsistencies that accumulated when each consumer evaluated policy
independently.
"""

from __future__ import annotations

from dataclasses import dataclass

from neuzelaar.core.bus import Bus
from neuzelaar.core.fetch.cookies import SessionCookieJar
from neuzelaar.core.fetch.resource import Request, Resource
from neuzelaar.core.origin import resolve_url
from neuzelaar.core.policy.rules import PolicyDecision, PolicyEngine
from neuzelaar.document.subresources import SubresourceRequest
from neuzelaar.shell_api.events import ResourceBlocked


@dataclass(frozen=True, slots=True)
class GateDecision:
    allowed: bool
    request: Request
    policy: PolicyDecision
    normalized_url: str


class SubresourceGateway:
    def __init__(
        self,
        *,
        policy_engine: PolicyEngine,
        bus: Bus | None = None,
        cookie_jar: SessionCookieJar | None = None,
    ) -> None:
        self.policy_engine = policy_engine
        self.bus = bus
        self.cookie_jar = cookie_jar

    def evaluate(
        self,
        planned: SubresourceRequest,
        page_resource: Resource,
    ) -> GateDecision:
        record = resolve_url(page_resource.final_url, planned.url)
        headers: dict[str, str] = {}
        if self.cookie_jar is not None:
            self.cookie_jar.add_cookie_header(record.normalized, headers)
        request = Request(
            url=record.normalized,
            method="GET",
            headers=headers,
            body=None,
            reason=planned.reason,
            initiator=page_resource.id,
            origin=record.origin,
            context_origin=page_resource.request.context_origin,
        )
        decision = self.policy_engine.evaluate_fetch(request)
        if not decision.allowed and self.bus is not None:
            self.bus.publish(ResourceBlocked(record.normalized, decision.reason))
        return GateDecision(
            allowed=decision.allowed,
            request=request,
            policy=decision,
            normalized_url=record.normalized,
        )

    def evaluate_plan(
        self,
        plan: tuple[SubresourceRequest, ...],
        page_resource: Resource,
    ) -> dict[SubresourceRequest, GateDecision]:
        return {planned: self.evaluate(planned, page_resource) for planned in plan}
