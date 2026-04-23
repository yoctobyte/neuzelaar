"""Form extraction from the internal document tree."""

from __future__ import annotations

from dataclasses import dataclass

from neuzelaar.core.origin import resolve_url
from neuzelaar.document.dom import Document, Element, Node, NodeId, Text, walk


@dataclass(frozen=True, slots=True)
class FormControl:
    name: str
    value: str
    type: str = "text"


@dataclass(frozen=True, slots=True)
class DocumentForm:
    index: int
    node_id: NodeId
    method: str
    action: str
    resolved_action: str
    controls: tuple[FormControl, ...]


def extract_forms(document: Document) -> tuple[DocumentForm, ...]:
    forms: list[DocumentForm] = []
    for node in walk(document):
        if not isinstance(node, Element) or node.tag.lower() != "form":
            continue
        method = (node.attr("method") or "get").lower()
        action = node.attr("action") or document.url
        forms.append(
            DocumentForm(
                index=len(forms) + 1,
                node_id=node.id,
                method=method,
                action=action,
                resolved_action=resolve_url(document.url, action).normalized,
                controls=tuple(_extract_controls(node)),
            )
        )
    return tuple(forms)


def _extract_controls(form: Element) -> list[FormControl]:
    controls: list[FormControl] = []
    for node in walk(form):
        if not isinstance(node, Element):
            continue
        tag = node.tag.lower()
        name = node.attr("name")
        if not name:
            continue
        if tag == "input":
            input_type = (node.attr("type") or "text").lower()
            if input_type in {"submit", "button", "reset"}:
                continue
            controls.append(FormControl(name=name, value=node.attr("value") or "", type=input_type))
        elif tag == "textarea":
            controls.append(FormControl(name=name, value=_text_content(node), type="textarea"))
        elif tag == "select":
            controls.append(FormControl(name=name, value=_selected_option_value(node), type="select"))
    return controls


def _selected_option_value(select: Element) -> str:
    first_value = ""
    for child in select.children:
        if not isinstance(child, Element) or child.tag.lower() != "option":
            continue
        value = child.attr("value") or _text_content(child)
        if not first_value:
            first_value = value
        if child.attr("selected") is not None:
            return value
    return first_value


def _text_content(node: Node) -> str:
    if isinstance(node, Text):
        return node.data
    children = getattr(node, "children", None)
    if not children:
        return ""
    return "".join(_text_content(child) for child in children).strip()
