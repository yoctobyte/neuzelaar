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
}

MULTI_CHAR_OPERATORS = (
    "=>",
    "===",
    "!==",
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
        matched = _match_operator(source, index)
        if matched is not None:
            operator, kind = matched
            tokens.append(Token(kind=kind, lexeme=operator, value=None, offset=index))
            index += len(operator)
            continue
        if char in SINGLE_CHAR_TOKENS:
            tokens.append(Token(kind=SINGLE_CHAR_TOKENS[char], lexeme=char, value=None, offset=index))
            index += 1
            continue
        if char.isdigit():
            token, index = _read_number(source, index)
            tokens.append(token)
            continue
        if char == "'" or char == '"':
            token, index = _read_string(source, index)
            tokens.append(token)
            continue
        if char.isalpha() or char in "_$":
            token, index = _read_identifier(source, index)
            tokens.append(token)
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
