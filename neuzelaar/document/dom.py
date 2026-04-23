"""Internal DOM-like tree owned by Neuzelaar."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import NewType


NodeId = NewType("NodeId", str)


@dataclass(slots=True)
class Node:
    id: NodeId
    parent: "Element | Document | None" = None


@dataclass(slots=True)
class Document(Node):
    url: str = ""
    title: str = ""
    children: list[Node] = field(default_factory=list)


@dataclass(slots=True)
class Element(Node):
    tag: str = ""
    attrs: dict[str, str] = field(default_factory=dict)
    children: list[Node] = field(default_factory=list)

    def attr(self, name: str) -> str | None:
        return self.attrs.get(name.lower())


@dataclass(slots=True)
class Text(Node):
    data: str = ""


@dataclass(slots=True)
class Comment(Node):
    data: str = ""


@dataclass(slots=True)
class SurfaceBox(Node):
    kind: str = ""
    bounds: object | None = None
    fallback: str = ""


def append_child(parent: Document | Element, child: Node) -> None:
    child.parent = parent
    parent.children.append(child)


def walk(node: Node) -> Iterator[Node]:
    yield node
    children = getattr(node, "children", None)
    if children is None:
        return
    for child in children:
        yield from walk(child)
