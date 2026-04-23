"""Small command-oriented console shell for M2."""

from __future__ import annotations

from dataclasses import dataclass, field

from neuzelaar.core.browser import BrowserState, BrowserStateError
from neuzelaar.core.session import SessionError


@dataclass(slots=True)
class ConsoleShell:
    browser: BrowserState = field(default_factory=BrowserState)

    def __post_init__(self) -> None:
        if not self.browser.tabs:
            self.browser.new_tab()

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
                return self._format_page(self.browser.open_url(arg))
            if name == "back":
                return self._format_page(self.browser.back())
            if name == "forward":
                return self._format_page(self.browser.forward())
            if name == "links":
                return self.format_links()
            if name == "resources":
                return self.format_resources()
            if name == "permissions":
                return self.format_permissions()
            if name == "follow":
                if not arg or not arg.isdigit():
                    return "usage: follow <link-number>"
                return self._format_page(self.browser.follow_link(int(arg)))
            if name == "tabs":
                return self.format_tabs()
            if name == "newtab":
                tab = self.browser.new_tab(arg or None, activate=True)
                if tab.current is None:
                    return f"tab {tab.id} created"
                return self._format_page(tab.current)
            if name == "switch":
                if not arg or not arg.isdigit():
                    return "usage: switch <tab-id>"
                tab = self.browser.switch_tab(int(arg))
                if tab.current is None:
                    return f"tab {tab.id} active"
                return self._format_page(tab.current)
            if name == "closetab":
                if not arg or not arg.isdigit():
                    return "usage: closetab <tab-id>"
                self.browser.close_tab(int(arg))
                if self.browser.active_tab_id is None:
                    return "all tabs closed"
                return f"active tab {self.browser.active_tab_id}"
            if name in {"quit", "exit"}:
                return "quit"
        except (SessionError, BrowserStateError) as exc:
            return f"error: {exc}"

        return f"unknown command: {name}"

    def format_links(self) -> str:
        current = self.browser.active_tab.current
        if current is None:
            return "no page loaded"
        if not current.links:
            return "no links"
        return "\n".join(
            f"{link.index}. {link.text} <{link.resolved_url}>" for link in current.links
        )

    def format_resources(self) -> str:
        current = self.browser.active_tab.current
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

    def format_permissions(self) -> str:
        current = self.browser.active_tab.current
        if current is None:
            return "no page loaded"
        if not current.scripts:
            return "no active content requests"
        lines = []
        for node_id, script in current.scripts.items():
            capability = script.result.requested_capabilities[0].name.lower() if script.result.requested_capabilities else "unknown"
            source = script.url or "inline"
            lines.append(
                f"[{script.result.status.value}] {capability} {source} ({node_id}): {script.result.reason}"
            )
        return "\n".join(lines)

    def format_tabs(self) -> str:
        lines = []
        for tab in self.browser.list_tabs():
            marker = "*" if tab.id == self.browser.active_tab_id else " "
            title = tab.current.handler_result.value.title if tab.current and tab.current.handler_result.kind == "document" else "empty"
            lines.append(f"{marker} {tab.id}: {title}")
        return "\n".join(lines) if lines else "no tabs"

    def _format_page(self, result) -> str:
        lines = [
            f"{result.resource.status} {result.resource.final_url} [{result.mime_decision.kind}]",
            result.rendered_text,
        ]
        if result.links:
            lines.append(f"{len(result.links)} link(s)")
        if result.planned_subresources:
            lines.append(f"{len(result.planned_subresources)} planned resource(s)")
        if result.scripts:
            lines.append(f"{len(result.scripts)} active content request(s)")
        return "\n".join(line for line in lines if line)
