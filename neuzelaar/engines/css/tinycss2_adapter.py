"""Adapter from tinycss2 output to Neuzelaar style rules."""

from __future__ import annotations

import tinycss2

from neuzelaar.document.styles import SUPPORTED_PROPERTIES, StyleRule


def parse_stylesheet(css: str) -> tuple[StyleRule, ...]:
    rules: list[StyleRule] = []
    for rule in tinycss2.parse_stylesheet(css, skip_comments=True, skip_whitespace=True):
        if rule.type != "qualified-rule":
            continue
        selector = tinycss2.serialize(rule.prelude).strip()
        declarations = {}
        important: set[str] = set()
        for declaration in tinycss2.parse_declaration_list(
            rule.content,
            skip_comments=True,
            skip_whitespace=True,
        ):
            if declaration.type != "declaration":
                continue
            name = declaration.name.lower()
            if name in SUPPORTED_PROPERTIES:
                declarations[name] = tinycss2.serialize(declaration.value).strip()
                if declaration.important:
                    important.add(name)
        if declarations:
            rules.append(
                StyleRule(
                    selector=selector,
                    declarations=declarations,
                    important=frozenset(important),
                )
            )
    return tuple(rules)
