"""Tokenizer for a narrow JavaScript expression subset."""

from __future__ import annotations

from dataclasses import dataclass

from neuzelaar.engines.js_own.errors import JavaScriptSyntaxError


KEYWORDS = {
    "true": "TRUE",
    "false": "FALSE",
    "null": "NULL",
    "var": "VAR",
    "let": "LET",
    "const": "CONST",
    "if": "IF",
    "else": "ELSE",
    "function": "FUNCTION",
    "async": "ASYNC",
    "await": "AWAIT",
    "class": "CLASS",
    "extends": "EXTENDS",
    "new": "NEW",
    "return": "RETURN",
    "super": "SUPER",
    "static": "STATIC",
    "this": "THIS",
    "throw": "THROW",
    "try": "TRY",
    "catch": "CATCH",
    "finally": "FINALLY",
    "instanceof": "INSTANCEOF",
    "yield": "YIELD",
    "typeof": "TYPEOF",
    "while": "WHILE",
    "for": "FOR",
    "break": "BREAK",
    "continue": "CONTINUE",
}

MULTI_CHAR_OPERATORS = (
    "=>",
    "===",
    "!==",
    "++",
    "--",
    "<=",
    ">=",
    "==",
    "!=",
    "&&",
    "||",
)

SINGLE_CHAR_TOKENS = {
    "+": "PLUS",
    "-": "MINUS",
    "*": "STAR",
    "/": "SLASH",
    "%": "PERCENT",
    "!": "BANG",
    "=": "EQUAL",
    "(": "LPAREN",
    ")": "RPAREN",
    "{": "LBRACE",
    "}": "RBRACE",
    "[": "LBRACKET",
    "]": "RBRACKET",
    ",": "COMMA",
    ".": "DOT",
    ":": "COLON",
    ";": "SEMICOLON",
    "<": "LT",
    ">": "GT",
    "?": "QUESTION",
}


@dataclass(frozen=True, slots=True)
class Token:
    kind: str
    lexeme: str
    value: object | None
    offset: int


def tokenize(source: str) -> tuple[Token, ...]:
    tokens: list[Token] = []
    index = 0
    while index < len(source):
        char = source[index]
        if char.isspace():
            index += 1
            continue
        if source.startswith("//", index):
            index = _skip_line_comment(source, index + 2)
            continue
        if source.startswith("/*", index):
            index = _skip_block_comment(source, index + 2)
            continue
        matched = _match_operator(source, index)
        if matched is not None:
            operator, kind = matched
            tokens.append(Token(kind=kind, lexeme=operator, value=None, offset=index))
            index += len(operator)
            continue
        if char.isdigit():
            token, index = _read_number(source, index)
            tokens.append(token)
            continue
        if char == "'" or char == '"':
            token, index = _read_string(source, index)
            tokens.append(token)
            continue
        if char == "`":
            token, index = _read_template(source, index)
            tokens.append(token)
            continue
        if char == "#" and index + 1 < len(source) and (source[index + 1].isalpha() or source[index + 1] in "_$"):
            token, index = _read_private_identifier(source, index)
            tokens.append(token)
            continue
        if char.isalpha() or char in "_$":
            token, index = _read_identifier(source, index)
            tokens.append(token)
            continue
        if char in SINGLE_CHAR_TOKENS:
            tokens.append(Token(kind=SINGLE_CHAR_TOKENS[char], lexeme=char, value=None, offset=index))
            index += 1
            continue
        raise JavaScriptSyntaxError(f"Unexpected character {char!r} at offset {index}")
    tokens.append(Token(kind="EOF", lexeme="", value=None, offset=len(source)))
    return tuple(tokens)


def _match_operator(source: str, index: int) -> tuple[str, str] | None:
    for operator in MULTI_CHAR_OPERATORS:
        if source.startswith(operator, index):
            return operator, operator
    return None


def _read_number(source: str, start: int) -> tuple[Token, int]:
    index = start
    while index < len(source) and source[index].isdigit():
        index += 1
    if index < len(source) and source[index] == ".":
        index += 1
        while index < len(source) and source[index].isdigit():
            index += 1
    lexeme = source[start:index]
    return Token(kind="NUMBER", lexeme=lexeme, value=float(lexeme), offset=start), index


def _read_string(source: str, start: int) -> tuple[Token, int]:
    quote = source[start]
    index = start + 1
    parts: list[str] = []
    while index < len(source):
        char = source[index]
        if char == quote:
            return Token(
                kind="STRING",
                lexeme=source[start : index + 1],
                value="".join(parts),
                offset=start,
            ), index + 1
        if char == "\\":
            index += 1
            if index >= len(source):
                break
            escape = source[index]
            if escape == "u" and index + 4 < len(source):
                codepoint = source[index + 1 : index + 5]
                if all(ch in "0123456789abcdefABCDEF" for ch in codepoint):
                    parts.append(chr(int(codepoint, 16)))
                    index += 5
                    continue
            parts.append(
                {
                    "n": "\n",
                    "r": "\r",
                    "t": "\t",
                    "\\": "\\",
                    "'": "'",
                    '"': '"',
                }.get(escape, escape)
            )
            index += 1
            continue
        parts.append(char)
        index += 1
    raise JavaScriptSyntaxError(f"Unterminated string literal at offset {start}")


def _read_identifier(source: str, start: int) -> tuple[Token, int]:
    index = start
    while index < len(source) and (source[index].isalnum() or source[index] in "_$"):
        index += 1
    lexeme = source[start:index]
    keyword_kind = KEYWORDS.get(lexeme)
    if keyword_kind is not None:
        if keyword_kind == "TRUE":
            return Token(kind=keyword_kind, lexeme=lexeme, value=True, offset=start), index
        if keyword_kind == "FALSE":
            return Token(kind=keyword_kind, lexeme=lexeme, value=False, offset=start), index
        if keyword_kind == "NULL":
            return Token(kind=keyword_kind, lexeme=lexeme, value=None, offset=start), index
        return Token(kind=keyword_kind, lexeme=lexeme, value=lexeme, offset=start), index
    return Token(kind="IDENTIFIER", lexeme=lexeme, value=lexeme, offset=start), index


def _read_private_identifier(source: str, start: int) -> tuple[Token, int]:
    index = start + 1
    while index < len(source) and (source[index].isalnum() or source[index] in "_$"):
        index += 1
    lexeme = source[start:index]
    return Token(kind="PRIVATE_IDENTIFIER", lexeme=lexeme, value=lexeme[1:], offset=start), index


def _read_template(source: str, start: int) -> tuple[Token, int]:
    index = start + 1
    cooked_parts: list[str] = []
    raw_parts: list[str] = []
    chunks: list[tuple[str, str, str] | tuple[str, str]] = []
    last_chunk_was_expr = False
    while index < len(source):
        char = source[index]
        if char == "`":
            if cooked_parts or raw_parts or not chunks or last_chunk_was_expr:
                chunks.append(("text", "".join(cooked_parts), "".join(raw_parts)))
            return (
                Token(
                    kind="TEMPLATE",
                    lexeme=source[start : index + 1],
                    value=tuple(chunks),
                    offset=start,
                ),
                index + 1,
            )
        if char == "\\":
            index += 1
            if index >= len(source):
                break
            escape = source[index]
            raw_parts.append("\\" + escape)
            if escape == "u" and index + 4 < len(source):
                codepoint = source[index + 1 : index + 5]
                if all(ch in "0123456789abcdefABCDEF" for ch in codepoint):
                    cooked_parts.append(chr(int(codepoint, 16)))
                    raw_parts[-1] = "\\u" + codepoint
                    index += 5
                    continue
            cooked_parts.append(
                {
                    "n": "\n",
                    "r": "\r",
                    "t": "\t",
                    "\\": "\\",
                    "`": "`",
                    "$": "$",
                }.get(escape, escape)
            )
            index += 1
            continue
        if char == "$" and index + 1 < len(source) and source[index + 1] == "{":
            if cooked_parts or raw_parts:
                chunks.append(("text", "".join(cooked_parts), "".join(raw_parts)))
                cooked_parts = []
                raw_parts = []
            expr_source, index = _read_template_expression(source, index + 2)
            chunks.append(("expr", expr_source))
            last_chunk_was_expr = True
            continue
        cooked_parts.append(char)
        raw_parts.append(char)
        last_chunk_was_expr = False
        index += 1
    raise JavaScriptSyntaxError(f"Unterminated template literal at offset {start}")


def _skip_line_comment(source: str, start: int) -> int:
    index = start
    while index < len(source) and source[index] not in "\r\n":
        index += 1
    return index


def _skip_block_comment(source: str, start: int) -> int:
    index = start
    while index + 1 < len(source):
        if source[index] == "*" and source[index + 1] == "/":
            return index + 2
        index += 1
    raise JavaScriptSyntaxError(f"Unterminated block comment at offset {start - 2}")


def _read_template_expression(source: str, start: int) -> tuple[str, int]:
    index = start
    depth = 1
    parts: list[str] = []
    while index < len(source):
        char = source[index]
        if char in {"'", '"'}:
            literal, index = _consume_string_segment(source, index, char)
            parts.append(literal)
            continue
        if char == "`":
            literal, index = _consume_template_segment(source, index)
            parts.append(literal)
            continue
        if char == "{":
            depth += 1
            parts.append(char)
            index += 1
            continue
        if char == "}":
            depth -= 1
            if depth == 0:
                return "".join(parts), index + 1
            parts.append(char)
            index += 1
            continue
        parts.append(char)
        index += 1
    raise JavaScriptSyntaxError(f"Unterminated template expression at offset {start}")


def _consume_string_segment(source: str, start: int, quote: str) -> tuple[str, int]:
    index = start + 1
    parts = [quote]
    while index < len(source):
        char = source[index]
        parts.append(char)
        if char == "\\":
            index += 1
            if index >= len(source):
                break
            parts.append(source[index])
            index += 1
            continue
        if char == quote:
            return "".join(parts), index + 1
        index += 1
    raise JavaScriptSyntaxError(f"Unterminated string literal at offset {start}")


def _consume_template_segment(source: str, start: int) -> tuple[str, int]:
    index = start + 1
    parts = ["`"]
    while index < len(source):
        char = source[index]
        parts.append(char)
        if char == "\\":
            index += 1
            if index >= len(source):
                break
            parts.append(source[index])
            index += 1
            continue
        if char == "$" and index + 1 < len(source) and source[index + 1] == "{":
            expr_source, next_index = _read_template_expression(source, index + 2)
            parts.append(source[index + 1 : next_index])
            index = next_index
            continue
        if char == "`":
            return "".join(parts), index + 1
        index += 1
    raise JavaScriptSyntaxError(f"Unterminated template literal at offset {start}")
