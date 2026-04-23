"""HTML resource handling."""

from __future__ import annotations

from neuzelaar.core.fetch.resource import Resource
from neuzelaar.engines.html.html5lib_adapter import parse_html


def handle_html(resource: Resource):
    encoding = resource.encoding or "utf-8"
    html = resource.body.decode(encoding, errors="replace")
    return parse_html(html, url=resource.final_url)
