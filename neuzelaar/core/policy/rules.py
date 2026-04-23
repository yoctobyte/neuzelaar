"""Early fetch policy rules."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from neuzelaar.core.fetch.resource import FetchReason, Request
from neuzelaar.core.origin import is_third_party
from neuzelaar.core.policy.profile import PolicyProfile


TRACKER_HOST_FRAGMENTS = {
    "doubleclick.net",
    "google-analytics.com",
    "googletagmanager.com",
    "facebook.net",
}


class PolicyAction(Enum):
    ALLOW = "allow"
    BLOCK = "block"
    PROMPT = "prompt"


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    action: PolicyAction
    reason: str

    @property
    def allowed(self) -> bool:
        return self.action == PolicyAction.ALLOW


class PolicyEngine:
    def __init__(self, profile: PolicyProfile = PolicyProfile.STRICT) -> None:
        self.profile = profile

    def evaluate_fetch(self, request: Request) -> PolicyDecision:
        if request.reason == FetchReason.TOP_LEVEL:
            return PolicyDecision(PolicyAction.ALLOW, "top-level navigation")

        if _matches_tracker_host(request.origin.host):
            return PolicyDecision(PolicyAction.BLOCK, "known tracker/ad host")

        third_party = is_third_party(request.origin, request.context_origin)
        if self.profile == PolicyProfile.STRICT:
            if request.reason == FetchReason.SCRIPT and third_party:
                return PolicyDecision(PolicyAction.BLOCK, "strict mode blocks third-party scripts")
            if request.reason == FetchReason.IFRAME and third_party:
                return PolicyDecision(PolicyAction.BLOCK, "strict mode blocks third-party iframes")

        if self.profile == PolicyProfile.BALANCED:
            if request.reason == FetchReason.SCRIPT and third_party:
                return PolicyDecision(PolicyAction.BLOCK, "balanced mode blocks third-party scripts")

        return PolicyDecision(PolicyAction.ALLOW, "allowed by policy")


def _matches_tracker_host(host: str | None) -> bool:
    if not host:
        return False
    return any(fragment in host for fragment in TRACKER_HOST_FRAGMENTS)
