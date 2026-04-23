"""Headless shell for one-shot page loading."""

from __future__ import annotations

from neuzelaar.core.page import PageLoader, PageLoadResult


class HeadlessShell:
    def __init__(self, loader: PageLoader | None = None) -> None:
        self.loader = loader or PageLoader()

    def open_url(self, url: str) -> PageLoadResult:
        return self.loader.load(url)

    def format_result(self, result: PageLoadResult) -> str:
        lines = [
            f"{result.resource.status} {result.resource.final_url} [{result.mime_decision.kind}]",
            result.rendered_text,
        ]
        for planned in result.planned_subresources:
            lines.append(
                f"[{planned.decision.action.value}] "
                f"{planned.request.reason.name.lower()} {planned.normalized_url}: "
                f"{planned.decision.reason}"
            )
        return "\n".join(line for line in lines if line)
