from neuzelaar.document.dom import Document, Element, NodeId, Text, append_child, walk


def test_append_child_sets_parent_and_preserves_order() -> None:
    document = Document(id=NodeId("doc"), url="https://example.com/")
    body = Element(id=NodeId("body"), tag="body")
    text = Text(id=NodeId("text"), data="hello")

    append_child(document, body)
    append_child(body, text)

    assert document.children == [body]
    assert body.parent is document
    assert body.children == [text]
    assert text.parent is body


def test_walk_visits_tree_depth_first() -> None:
    document = Document(id=NodeId("doc"))
    first = Element(id=NodeId("first"), tag="p")
    second = Element(id=NodeId("second"), tag="p")
    text = Text(id=NodeId("text"), data="hello")
    append_child(document, first)
    append_child(document, second)
    append_child(first, text)

    assert [node.id for node in walk(document)] == [
        NodeId("doc"),
        NodeId("first"),
        NodeId("text"),
        NodeId("second"),
    ]
