"""Parser for a narrow JavaScript subset."""

from __future__ import annotations

from dataclasses import dataclass

from neuzelaar.engines.js_own.ast import (
    AssignmentExpr,
    BinaryExpr,
    BlockStatement,
    BooleanLiteral,
    Expr,
    ExpressionStatement,
    Identifier,
    IfStatement,
    NullLiteral,
    NumberLiteral,
    Program,
    Stmt,
    StringLiteral,
    UnaryExpr,
    VariableDeclaration,
)
from neuzelaar.engines.js_own.errors import JavaScriptSyntaxError
from neuzelaar.engines.js_own.tokenizer import Token, tokenize

PRECEDENCE = {
    "EQUAL": 1,
    "||": 2,
    "&&": 3,
    "==": 4,
    "!=": 4,
    "===": 4,
    "!==": 4,
    "LT": 5,
    "GT": 5,
    "<=": 5,
    ">=": 5,
    "PLUS": 6,
    "MINUS": 6,
    "STAR": 7,
    "SLASH": 7,
    "PERCENT": 7,
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
        statements: list[Stmt] = []
        while not self._check("EOF"):
            statements.append(self.parse_statement())
        return Program(statements=tuple(statements))

    def parse_statement(self) -> Stmt:
        if self._match("SEMICOLON"):
            return ExpressionStatement(NumberLiteral(0.0))
        if self._check("LBRACE"):
            return self._parse_block_statement()
        if self._check("IF"):
            return self._parse_if_statement()
        if self._check("VAR") or self._check("LET") or self._check("CONST"):
            return self._parse_variable_declaration()
        expression = self.parse_expression()
        self._consume_optional_semicolon()
        return ExpressionStatement(expression)

    def _parse_block_statement(self) -> BlockStatement:
        self._consume("LBRACE", "Expected '{' to start block")
        statements: list[Stmt] = []
        while not self._check("RBRACE") and not self._check("EOF"):
            statements.append(self.parse_statement())
        self._consume("RBRACE", "Expected '}' to close block")
        return BlockStatement(statements=tuple(statements))

    def _parse_if_statement(self) -> IfStatement:
        self._consume("IF", "Expected 'if'")
        self._consume("LPAREN", "Expected '(' after if")
        test = self.parse_expression()
        self._consume("RPAREN", "Expected ')' after if condition")
        consequent = self.parse_statement()
        alternate = self.parse_statement() if self._match("ELSE") else None
        return IfStatement(test=test, consequent=consequent, alternate=alternate)

    def _parse_variable_declaration(self) -> VariableDeclaration:
        kind_token = self._advance()
        identifier = self._consume("IDENTIFIER", "Expected identifier after declaration keyword")
        initializer = None
        if self._match("EQUAL"):
            initializer = self.parse_expression()
        elif kind_token.kind == "CONST":
            raise JavaScriptSyntaxError(f"Missing initializer in const declaration at offset {identifier.offset}")
        self._consume_optional_semicolon()
        return VariableDeclaration(
            kind=kind_token.lexeme,
            name=str(identifier.value),
            initializer=initializer,
        )

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
            return UnaryExpr(operator=token.lexeme, operand=self.parse_expression(8))
        if token.kind == "LPAREN":
            expr = self.parse_expression()
            self._consume("RPAREN", "Expected ')' after expression")
            return expr
        raise JavaScriptSyntaxError(f"Unexpected token {token.lexeme!r} at offset {token.offset}")

    def _parse_infix(self, left: Expr, token: Token) -> Expr:
        if token.kind == "EQUAL":
            if not isinstance(left, Identifier):
                raise JavaScriptSyntaxError(f"Invalid assignment target at offset {token.offset}")
            return AssignmentExpr(target=left, value=self.parse_expression(PRECEDENCE["EQUAL"] - 1))
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

    def _consume_optional_semicolon(self) -> None:
        self._match("SEMICOLON")


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
