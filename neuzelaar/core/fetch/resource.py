"""Resource and request dataclasses for fetch planning/results."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Mapping, NewType

from neuzelaar.core.origin import Origin


ResourceId = NewType("ResourceId", str)
HandlerId = NewType("HandlerId", str)


class FetchReason(Enum):
    TOP_LEVEL = auto()
    STYLESHEET = auto()
    IMAGE = auto()
    SCRIPT = auto()
    FORM_SUBMIT = auto()
    IFRAME = auto()
    MEDIA = auto()
    SCRIPT_INITIATED = auto()
    FAVICON = auto()


class TrustDecision(Enum):
    ALLOW = auto()
    BLOCK = auto()
    PROMPT = auto()
    DOWNLOAD = auto()


@dataclass(frozen=True, slots=True)
class Request:
    url: str
    method: str
    headers: dict[str, str]
    body: bytes | None
    reason: FetchReason
    initiator: ResourceId | None
    origin: Origin
    context_origin: Origin


@dataclass(frozen=True, slots=True)
class CacheMeta:
    from_cache: bool = False


@dataclass(frozen=True, slots=True)
class Resource:
    id: ResourceId
    request: Request
    final_url: str
    status: int
    headers: Mapping[str, str]
    body: bytes
    encoding: str | None
    claimed_mime: str | None
    detected_mime: str | None
    mime_confidence: float
    trust: TrustDecision
    handler: HandlerId | None
    cache: CacheMeta = field(default_factory=CacheMeta)
    content_hash: bytes = b""

    @classmethod
    def from_body(
        cls,
        *,
        request: Request,
        final_url: str,
        status: int,
        headers: Mapping[str, str],
        body: bytes,
        encoding: str | None = None,
        claimed_mime: str | None = None,
        detected_mime: str | None = None,
        mime_confidence: float = 0.0,
        trust: TrustDecision = TrustDecision.ALLOW,
        handler: HandlerId | None = None,
    ) -> "Resource":
        digest = hashlib.sha256(body).digest()
        return cls(
            id=ResourceId(hashlib.sha256(f"{final_url}:{digest.hex()}".encode()).hexdigest()),
            request=request,
            final_url=final_url,
            status=status,
            headers=dict(headers),
            body=body,
            encoding=encoding,
            claimed_mime=claimed_mime,
            detected_mime=detected_mime,
            mime_confidence=mime_confidence,
            trust=trust,
            handler=handler,
            content_hash=digest,
        )
