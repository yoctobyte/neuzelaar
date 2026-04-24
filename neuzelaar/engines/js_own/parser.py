"""Pratt parser for a narrow JavaScript expression subset."""

from __future__ import annotations

from dataclasses import dataclass

from neuzelaar.engines.js_own.ast import (
    BinaryExpr,
    BooleanLiteral,
    Expr,
    Identifier,
    NullLiteral,
    NumberLiteral,
    Program,
    StringLiteral,
    UnaryExpr,
)
from neuzelaar.engines.js_own.errors import JavaScriptSyntaxError
from neuzelaar.engines.js_own.tokenizer import Token, tokenize

PRECEDENCE = {
    "||": 1,
    "&&": 2,
    "==": 3,
    "!=": 3,
    "===": 3,
    "!==": 3,
    "LT": 4,
    "GT": 4,
    "<=": 4,
    ">=": 4,
    "PLUS": 5,
    "MINUS": 5,
    "STAR": 6,
    "SLASH": 6,
    "PERCENT": 6,
}


@dataclass(slots=True)
class Parser:
    tokens: tuple[Token, ...]
    index: int = 0

    def parse_expression(self, precedence: int = 0) -> Expr:
        token = self._advance()
        left = self._parse_prefix(token)
        while precedence < self._current_precedence():
            operator = self._advance()
            left = self._parse_infix(left, operator)
        return left

    def parse_program(self) -> Program:
        expressions: list[Expr] = []
        while not self._check("EOF"):
            expressions.append(self.parse_expression())
            if self._match("SEMICOLON"):
                while self._match("SEMICOLON"):
                    pass
            elif not self._check("EOF"):
                raise JavaScriptSyntaxError(
                    f"Expected ';' or end of input at offset {self._peek().offset}"
                )
        return Program(expressions=tuple(expressions))

    def _parse_prefix(self, token: Token) -> Expr:
        if token.kind == "NUMBER":
            return NumberLiteral(value=float(token.value))
        if token.kind == "STRING":
            return StringLiteral(value=str(token.value))
        if token.kind in {"TRUE", "FALSE"}:
            return BooleanLiteral(value=bool(token.value))
        if token.kind == "NULL":
            return NullLiteral()
        if token.kind == "IDENTIFIER":
            return Identifier(name=str(token.value))
        if token.kind in {"PLUS", "MINUS", "BANG"}:
            return UnaryExpr(operator=token.lexeme, operand=self.parse_expression(7))
        if token.kind == "LPAREN":
            expr = self.parse_expression()
            self._consume("RPAREN", "Expected ')' after expression")
            return expr
        raise JavaScriptSyntaxError(f"Unexpected token {token.lexeme!r} at offset {token.offset}")

    def _parse_infix(self, left: Expr, token: Token) -> Expr:
        precedence = PRECEDENCE[token.kind]
        right = self.parse_expression(precedence)
        return BinaryExpr(left=left, operator=token.lexeme, right=right)

    def _current_precedence(self) -> int:
        token = self._peek()
        return PRECEDENCE.get(token.kind, 0)

    def _peek(self) -> Token:
        return self.tokens[self.index]

    def _advance(self) -> Token:
        token = self.tokens[self.index]
        self.index += 1
        return token

    def _check(self, kind: str) -> bool:
        return self._peek().kind == kind

    def _match(self, kind: str) -> bool:
        if self._check(kind):
            self.index += 1
            return True
        return False

    def _consume(self, kind: str, message: str) -> Token:
        if self._check(kind):
            return self._advance()
        raise JavaScriptSyntaxError(f"{message} at offset {self._peek().offset}")


def parse_expression(source: str) -> Expr:
    parser = Parser(tokens=tokenize(source))
    expr = parser.parse_expression()
    if not parser._check("EOF"):
        raise JavaScriptSyntaxError(
            f"Unexpected trailing token {parser._peek().lexeme!r} at offset {parser._peek().offset}"
        )
    return expr


def parse_program(source: str) -> Program:
    return Parser(tokens=tokenize(source)).parse_program()
