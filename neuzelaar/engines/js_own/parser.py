"""Parser for a narrow JavaScript subset."""

from __future__ import annotations

from dataclasses import dataclass

from neuzelaar.engines.js_own.ast import (
    ArrayLiteral,
    AssignmentExpr,
    BinaryExpr,
    BlockStatement,
    BooleanLiteral,
    CallExpr,
    Expr,
    ExpressionStatement,
    FunctionDeclaration,
    FunctionExpr,
    Identifier,
    IndexExpr,
    IfStatement,
    MemberExpr,
    NullLiteral,
    NumberLiteral,
    ObjectLiteral,
    ObjectProperty,
    Program,
    ReturnStatement,
    Stmt,
    StringLiteral,
    ThisExpr,
    ThrowStatement,
    TryStatement,
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
    "LPAREN": 9,
    "DOT": 9,
    "LBRACKET": 9,
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
        if self._check("FUNCTION"):
            return self._parse_function_declaration()
        if self._check("IF"):
            return self._parse_if_statement()
        if self._check("RETURN"):
            return self._parse_return_statement()
        if self._check("THROW"):
            return self._parse_throw_statement()
        if self._check("TRY"):
            return self._parse_try_statement()
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

    def _parse_return_statement(self) -> ReturnStatement:
        self._advance()
        if self._check("SEMICOLON") or self._check("RBRACE") or self._check("EOF"):
            self._consume_optional_semicolon()
            return ReturnStatement(value=None)
        value = self.parse_expression()
        self._consume_optional_semicolon()
        return ReturnStatement(value=value)

    def _parse_throw_statement(self) -> ThrowStatement:
        self._consume("THROW", "Expected 'throw'")
        value = self.parse_expression()
        self._consume_optional_semicolon()
        return ThrowStatement(value=value)

    def _parse_try_statement(self) -> TryStatement:
        self._consume("TRY", "Expected 'try'")
        body = self._parse_block_statement()
        catch_name: str | None = None
        catch_body: BlockStatement | None = None
        finally_body: BlockStatement | None = None
        if self._match("CATCH"):
            self._consume("LPAREN", "Expected '(' after catch")
            catch_name = str(self._consume("IDENTIFIER", "Expected catch binding").value)
            self._consume("RPAREN", "Expected ')' after catch binding")
            catch_body = self._parse_block_statement()
        if self._match("FINALLY"):
            finally_body = self._parse_block_statement()
        if catch_body is None and finally_body is None:
            raise JavaScriptSyntaxError(f"Expected catch or finally after try at offset {self._peek().offset}")
        return TryStatement(
            body=body,
            catch_name=catch_name,
            catch_body=catch_body,
            finally_body=finally_body,
        )

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

    def _parse_function_declaration(self) -> FunctionDeclaration:
        function_expr = self._parse_function_expression(require_name=True)
        assert function_expr.name is not None
        return FunctionDeclaration(
            name=function_expr.name,
            params=function_expr.params,
            body=function_expr.body,
        )

    def _parse_function_expression(self, *, require_name: bool) -> FunctionExpr:
        self._consume("FUNCTION", "Expected 'function'")
        name: str | None = None
        if self._check("IDENTIFIER"):
            name = str(self._advance().value)
        elif require_name:
            raise JavaScriptSyntaxError(f"Expected function name at offset {self._peek().offset}")
        self._consume("LPAREN", "Expected '(' after function name")
        params: list[str] = []
        if not self._check("RPAREN"):
            while True:
                param = self._consume("IDENTIFIER", "Expected parameter name")
                params.append(str(param.value))
                if not self._match("COMMA"):
                    break
        self._consume("RPAREN", "Expected ')' after function parameters")
        body = self._parse_block_statement()
        return FunctionExpr(name=name, params=tuple(params), body=body)

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
        if token.kind == "THIS":
            return ThisExpr()
        if token.kind == "FUNCTION":
            self.index -= 1
            return self._parse_function_expression(require_name=False)
        if token.kind == "LBRACKET":
            return self._parse_array_literal()
        if token.kind == "LBRACE":
            return self._parse_object_literal()
        if token.kind in {"PLUS", "MINUS", "BANG"}:
            return UnaryExpr(operator=token.lexeme, operand=self.parse_expression(8))
        if token.kind == "LPAREN":
            expr = self.parse_expression()
            self._consume("RPAREN", "Expected ')' after expression")
            return expr
        raise JavaScriptSyntaxError(f"Unexpected token {token.lexeme!r} at offset {token.offset}")

    def _parse_infix(self, left: Expr, token: Token) -> Expr:
        if token.kind == "LPAREN":
            arguments: list[Expr] = []
            if not self._check("RPAREN"):
                while True:
                    arguments.append(self.parse_expression())
                    if not self._match("COMMA"):
                        break
            self._consume("RPAREN", "Expected ')' after arguments")
            return CallExpr(callee=left, arguments=tuple(arguments))
        if token.kind == "DOT":
            property_token = self._consume("IDENTIFIER", "Expected property name after '.'")
            return MemberExpr(object=left, property_name=str(property_token.value))
        if token.kind == "LBRACKET":
            index = self.parse_expression()
            self._consume("RBRACKET", "Expected ']' after index expression")
            return IndexExpr(object=left, index=index)
        if token.kind == "EQUAL":
            if not isinstance(left, (Identifier, MemberExpr, IndexExpr)):
                raise JavaScriptSyntaxError(f"Invalid assignment target at offset {token.offset}")
            return AssignmentExpr(target=left, value=self.parse_expression(PRECEDENCE["EQUAL"] - 1))
        precedence = PRECEDENCE[token.kind]
        right = self.parse_expression(precedence)
        return BinaryExpr(left=left, operator=token.lexeme, right=right)

    def _parse_array_literal(self) -> ArrayLiteral:
        elements: list[Expr] = []
        if not self._check("RBRACKET"):
            while True:
                elements.append(self.parse_expression())
                if not self._match("COMMA"):
                    break
        self._consume("RBRACKET", "Expected ']' after array literal")
        return ArrayLiteral(elements=tuple(elements))

    def _parse_object_literal(self) -> ObjectLiteral:
        properties: list[ObjectProperty] = []
        if not self._check("RBRACE"):
            while True:
                key_token = self._advance()
                if key_token.kind == "IDENTIFIER":
                    key = str(key_token.value)
                elif key_token.kind == "STRING":
                    key = str(key_token.value)
                else:
                    raise JavaScriptSyntaxError(
                        f"Expected object property key at offset {key_token.offset}"
                    )
                self._consume("COLON", "Expected ':' after object property key")
                value = self.parse_expression()
                properties.append(ObjectProperty(key=key, value=value))
                if not self._match("COMMA"):
                    break
        self._consume("RBRACE", "Expected '}' after object literal")
        return ObjectLiteral(properties=tuple(properties))

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
