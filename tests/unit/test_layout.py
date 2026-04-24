from neuzelaar.core.page import ImageAsset
from neuzelaar.document.dom import Document, Element, NodeId, Text, append_child
from neuzelaar.document.layout import LayoutBox, LayoutImage, LayoutText, layout_document
from neuzelaar.document.styles import ComputedStyle
from neuzelaar.engines.image.pillow_adapter import DecodedImageBitmap


def test_layout_uses_margin_padding_and_font_size() -> None:
    document = Document(id=NodeId("doc"), title="Spacing")
    body = Element(id=NodeId("body"), tag="body")
    paragraph = Element(id=NodeId("p"), tag="p")
    append_child(document, body)
    append_child(body, paragraph)
    append_child(paragraph, Text(id=NodeId("t1"), data="hello"))

    styles = {
        NodeId("body"): ComputedStyle(background_color="#eeeeee", padding="10px"),
        NodeId("p"): ComputedStyle(color="blue", font_size="20px", margin="12px", padding="6px"),
    }

    layout = layout_document(document, styles=styles, root_style=ComputedStyle(color="red"))

    assert any(isinstance(item, LayoutBox) and item.color == "#eeeeee" for item in layout.items)
    text_item = next(item for item in layout.items if isinstance(item, LayoutText) and item.text == "hello")
    assert text_item.color == "blue"
    assert text_item.y > 50


def test_layout_propagates_text_align_and_max_width_to_text_items() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    paragraph = Element(id=NodeId("p"), tag="p")
    append_child(document, body)
    append_child(body, paragraph)
    append_child(paragraph, Text(id=NodeId("t"), data="hello"))

    styles = {
        NodeId("body"): ComputedStyle(text_align="center"),
        NodeId("p"): ComputedStyle(text_align="center"),
    }

    layout = layout_document(document, width=400, styles=styles, root_style=ComputedStyle(text_align="center"))

    text_item = next(item for item in layout.items if isinstance(item, LayoutText) and item.text == "hello")
    assert text_item.text_align == "center"
    assert text_item.max_width > 0


def test_layout_uses_image_width_and_height_attributes() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    image = Element(id=NodeId("img"), tag="img", attrs={"src": "x.png", "width": "24", "height": "18"})
    append_child(document, body)
    append_child(body, image)

    images = {
        NodeId("img"): ImageAsset(
            url="file:///tmp/x.png",
            bitmap=DecodedImageBitmap(width=1, height=1, stride=4, pixels=b"\xff\x00\x00\xff", format="PNG"),
        )
    }

    layout = layout_document(document, images=images)

    image_item = next(item for item in layout.items if isinstance(item, LayoutImage))
    assert image_item.width == 24
    assert image_item.height == 18
