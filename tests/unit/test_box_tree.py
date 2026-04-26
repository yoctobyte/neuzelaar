from neuzelaar.document.box import Box, BoxKind, build_box_tree, walk_box_tree
from neuzelaar.document.dom import Document, Element, NodeId, Text, append_child
from neuzelaar.document.styles import ComputedStyle, compute_styles


def test_build_box_tree_produces_block_and_text_boxes_for_simple_doc() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    paragraph = Element(id=NodeId("p"), tag="p")
    append_child(document, body)
    append_child(body, paragraph)
    append_child(paragraph, Text(id=NodeId("t"), data="hello"))

    root = build_box_tree(document, compute_styles(document))

    assert root is not None
    assert root.tag == "body"
    assert root.kind == BoxKind.BLOCK
    assert len(root.children) == 1
    p_box = root.children[0]
    assert p_box.tag == "p"
    assert p_box.kind == BoxKind.BLOCK
    assert len(p_box.children) == 1
    assert p_box.children[0].kind == BoxKind.TEXT
    assert p_box.children[0].text == "hello"


def test_build_box_tree_skips_head_title_script_and_display_none() -> None:
    document = Document(id=NodeId("doc"))
    head = Element(id=NodeId("head"), tag="head")
    title = Element(id=NodeId("title"), tag="title")
    script = Element(id=NodeId("s"), tag="script")
    style_block = Element(id=NodeId("st"), tag="style")
    body = Element(id=NodeId("body"), tag="body")
    hidden = Element(id=NodeId("h"), tag="div", attrs={"style": "display: none"})
    visible = Element(id=NodeId("v"), tag="div")
    for child in (head, body):
        append_child(document, child)
    append_child(head, title)
    append_child(head, script)
    append_child(head, style_block)
    append_child(body, hidden)
    append_child(body, visible)

    root = build_box_tree(document, compute_styles(document))

    assert root is not None
    assert root.tag == "body"
    tags = [child.tag for child in root.children]
    assert tags == ["div"]
    assert root.children[0].node_id == NodeId("v")


def test_build_box_tree_produces_replaced_box_for_img() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    img = Element(id=NodeId("img"), tag="img", attrs={"src": "x.png"})
    append_child(document, body)
    append_child(body, img)

    root = build_box_tree(document, compute_styles(document))

    img_box = root.children[0]
    assert img_box.kind == BoxKind.REPLACED
    assert img_box.tag == "img"
    assert img_box.element is img


def test_build_box_tree_wraps_inline_runs_when_mixed_with_blocks() -> None:
    # <body>
    #   "loose"            <- inline run (becomes anonymous block)
    #   <span>inline</span><- inline run (joins the same anonymous block)
    #   <p>block</p>       <- block
    #   <span>trailing</span> <- inline run (new anonymous block)
    # </body>
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    append_child(document, body)
    append_child(body, Text(id=NodeId("t1"), data="loose"))
    span = Element(id=NodeId("span"), tag="span", attrs={"style": "display: inline"})
    append_child(body, span)
    append_child(span, Text(id=NodeId("s1"), data="inline"))
    paragraph = Element(id=NodeId("p"), tag="p")
    append_child(body, paragraph)
    append_child(paragraph, Text(id=NodeId("p1"), data="block"))
    trailing = Element(id=NodeId("span2"), tag="span", attrs={"style": "display: inline"})
    append_child(body, trailing)
    append_child(trailing, Text(id=NodeId("s2"), data="trailing"))

    root = build_box_tree(document, compute_styles(document))

    kinds = [child.kind for child in root.children]
    assert kinds == [BoxKind.ANONYMOUS_BLOCK, BoxKind.BLOCK, BoxKind.ANONYMOUS_BLOCK]
    first_anon = root.children[0]
    assert [c.kind for c in first_anon.children] == [BoxKind.TEXT, BoxKind.INLINE]
    second_anon = root.children[2]
    assert [c.kind for c in second_anon.children] == [BoxKind.INLINE]


def test_build_box_tree_keeps_all_inline_children_inline_when_no_block_siblings() -> None:
    document = Document(id=NodeId("doc"))
    paragraph = Element(id=NodeId("p"), tag="p")
    append_child(document, paragraph)
    append_child(paragraph, Text(id=NodeId("t1"), data="hello "))
    strong = Element(id=NodeId("s"), tag="strong", attrs={"style": "display: inline"})
    append_child(paragraph, strong)
    append_child(strong, Text(id=NodeId("t2"), data="world"))

    root = build_box_tree(document, compute_styles(document))

    # <p> has only inline-level children (text + inline span). No
    # anonymous block should be introduced — the <p> establishes an
    # IFC directly.
    kinds = [child.kind for child in root.children]
    assert kinds == [BoxKind.TEXT, BoxKind.INLINE]


def test_walk_box_tree_visits_all_boxes_in_document_order() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    a = Element(id=NodeId("a"), tag="div")
    b = Element(id=NodeId("b"), tag="div")
    append_child(document, body)
    append_child(body, a)
    append_child(body, b)
    append_child(a, Text(id=NodeId("ta"), data="A"))
    append_child(b, Text(id=NodeId("tb"), data="B"))

    root = build_box_tree(document, compute_styles(document))

    tags_and_texts = [
        (box.tag, box.text) for box in walk_box_tree(root)
    ]

    assert tags_and_texts == [
        ("body", None),
        ("div", None),
        (None, "A"),
        ("div", None),
        (None, "B"),
    ]


def test_build_box_tree_marks_unordered_list_items_with_bullets() -> None:
    document = Document(id=NodeId("doc"))
    ul = Element(id=NodeId("ul"), tag="ul")
    li = Element(id=NodeId("li"), tag="li")
    append_child(document, ul)
    append_child(ul, li)
    append_child(li, Text(id=NodeId("t"), data="item"))

    root = build_box_tree(document, compute_styles(document))

    assert root.children[0].list_marker == "•"


def test_build_box_tree_numbers_ordered_list_items() -> None:
    document = Document(id=NodeId("doc"))
    ol = Element(id=NodeId("ol"), tag="ol")
    first = Element(id=NodeId("li1"), tag="li")
    second = Element(id=NodeId("li2"), tag="li")
    append_child(document, ol)
    append_child(ol, first)
    append_child(ol, second)
    append_child(first, Text(id=NodeId("t1"), data="first"))
    append_child(second, Text(id=NodeId("t2"), data="second"))

    root = build_box_tree(document, compute_styles(document))

    assert root.children[0].list_marker == "1."
    assert root.children[1].list_marker == "2."
