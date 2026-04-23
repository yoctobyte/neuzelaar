from pathlib import Path

from neuzelaar.core.page import PageLoader
from neuzelaar.document.forms import extract_forms


def test_extract_forms_with_controls_and_defaults() -> None:
    result = PageLoader().load(Path("tests/fixtures/sites/basic_form.html").resolve().as_uri())

    forms = extract_forms(result.handler_result.value)

    assert len(forms) == 1
    assert forms[0].method == "get"
    assert forms[0].resolved_action.endswith("/tests/fixtures/sites/form_result.html")
    assert [(control.name, control.value, control.type) for control in forms[0].controls] == [
        ("q", "default", "text"),
        ("note", "hello", "textarea"),
        ("kind", "b", "select"),
    ]
