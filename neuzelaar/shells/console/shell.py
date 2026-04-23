"""Small command-oriented console shell for M2."""

from __future__ import annotations

from dataclasses import dataclass, field

from neuzelaar.core.session import BrowserSession, SessionError


@dataclass(slots=True)
class ConsoleShell:
    session: BrowserSession = field(default_factory=BrowserSession)

    def run_command(self, command: str) -> str:
        parts = command.strip().split(maxsplit=1)
        if not parts:
            return ""

        name = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        try:
            if name == "open":
                if not arg:
                    return "usage: open <url>"
                return self._format_page(self.session.open_url(arg))
            if name == "back":
                return self._format_page(self.session.back())
            if name == "forward":
                return self._format_page(self.session.forward())
            if name == "links":
                return self.format_links()
            if name == "resources":
                return self.format_resources()
            if name == "follow":
                if not arg or not arg.isdigit():
                    return "usage: follow <link-number>"
                return self._format_page(self.session.follow_link(int(arg)))
            if name in {"quit", "exit"}:
                return "quit"
        except SessionError as exc:
            return f"error: {exc}"

        return f"unknown command: {name}"

    def format_links(self) -> str:
        current = self.session.current
        if current is None:
            return "no page loaded"
        if not current.links:
            return "no links"
        return "\n".join(
            f"{link.index}. {link.text} <{link.resolved_url}>" for link in current.links
        )

    def format_resources(self) -> str:
        current = self.session.current
        if current is None:
            return "no page loaded"
        if not current.planned_subresources:
            return "no planned subresources"
        return "\n".join(
            f"[{planned.decision.action.value}] "
            f"{planned.request.reason.name.lower()} {planned.normalized_url}: "
            f"{planned.decision.reason}"
            for planned in current.planned_subresources
        )

    def _format_page(self, result) -> str:
        lines = [
            f"{result.resource.status} {result.resource.final_url} [{result.mime_decision.kind}]",
            result.rendered_text,
        ]
        if result.links:
            lines.append(f"{len(result.links)} link(s)")
        if result.planned_subresources:
            lines.append(f"{len(result.planned_subresources)} planned resource(s)")
        return "\n".join(line for line in lines if line)
