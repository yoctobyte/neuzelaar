"""Parser for a narrow JavaScript subset."""

from __future__ import annotations

from dataclasses import dataclass

from neuzelaar.engines.js_own.ast import (
    ArrayLiteral,
    AssignmentExpr,
    ArrowFunctionExpr,
    AwaitExpr,
    BinaryExpr,
    BlockStatement,
    BooleanLiteral,
    BreakStatement,
    CallExpr,
    ClassDeclaration,
    ClassExpr,
    ClassField,
    ClassMethod,
    CompoundAssignmentExpr,
    ConditionalExpr,
    ContinueStatement,
    Expr,
    ExpressionStatement,
    ForStatement,
    FunctionDeclaration,
    FunctionExpr,
    Identifier,
    IndexExpr,
    IfStatement,
    MemberExpr,
    NewExpr,
    NullLiteral,
    NumberLiteral,
    ObjectLiteral,
    ObjectProperty,
    Program,
    ReturnStatement,
    Stmt,
    StringLiteral,
    SuperExpr,
    TemplateLiteral,
    TaggedTemplateExpr,
    ThisExpr,
    ThrowStatement,
    TryStatement,
    UnaryExpr,
    UpdateExpr,
    VariableDeclaration,
    WhileStatement,
)
from neuzelaar.engines.js_own.errors import JavaScriptSyntaxError
from neuzelaar.engines.js_own.tokenizer import Token, tokenize

PRECEDENCE = {
    "EQUAL": 1,
    "QUESTION": 1,
    "+=": 1,
    "-=": 1,
    "*=": 1,
    "/=": 1,
    "%=": 1,
    "||": 2,
    "??": 2,
    "&&": 3,
    "==": 4,
    "!=": 4,
    "===": 4,
    "!==": 4,
    "INSTANCEOF": 5,
    "LT": 5,
    "GT": 5,
    "<=": 5,
    ">=": 5,
    "PLUS": 6,
    "MINUS": 6,
    "STAR": 7,
    "SLASH": 7,
    "PERCENT": 7,
    "**": 8,
    "LPAREN": 9,
    "DOT": 9,
    "LBRACKET": 9,
    "TEMPLATE": 9,
    "++": 9,
    "--": 9,
}

PROPERTY_NAME_TOKENS = {
    "IDENTIFIER",
    "TRUE",
    "FALSE",
    "NULL",
    "IF",
    "ELSE",
    "FUNCTION",
    "CLASS",
    "EXTENDS",
    "NEW",
    "RETURN",
    "SUPER",
    "STATIC",
    "THIS",
    "THROW",
    "TRY",
    "CATCH",
    "FINALLY",
    "ASYNC",
    "AWAIT",
    "TYPEOF",
    "WHILE",
}


@dataclass(slots=True)
class Parser:
    tokens: tuple[Token, ...]
    index: int = 0
    function_depth: int = 0
    loop_depth: int = 0

    def maybe_parse_arrow_expression(self) -> ArrowFunctionExpr | None:
        checkpoint = self.index
        is_async = self._match("ASYNC")
        params = self._maybe_parse_arrow_params()
        if params is None or not self._match("=>"):
            self.index = checkpoint
            return None
        if self._check("LBRACE"):
            self.function_depth += 1
            try:
                body = self._parse_block_statement()
            finally:
                self.function_depth -= 1
        else:
            body = self.parse_expression()
        return ArrowFunctionExpr(params=params, body=body, is_async=is_async)

    def parse_expression(self, precedence: int = 0) -> Expr:
        if precedence == 0:
            checkpoint = self.index
            arrow = self.maybe_parse_arrow_expression()
            if arrow is not None:
                return arrow
            self.index = checkpoint
        token = self._advance()
        left = self._parse_prefix(token)
        while precedence < self._current_precedence():
            operator = self._advance()
            left = self._parse_infix(left, operator)
        return left

    def _maybe_parse_arrow_params(self) -> tuple[str, ...] | None:
        if self._check("IDENTIFIER"):
            return (str(self._advance().value),)
        if not self._match("LPAREN"):
            return None
        params: list[str] = []
        if not self._check("RPAREN"):
            while True:
                if not self._check("IDENTIFIER"):
                    return None
                params.append(str(self._advance().value))
                if not self._match("COMMA"):
                    break
        if not self._match("RPAREN"):
            return None
        return tuple(params)

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
        if self._check("ASYNC") and self.index + 1 < len(self.tokens) and self.tokens[self.index + 1].kind == "FUNCTION":
            self._advance()
            return self._parse_function_declaration(is_async=True)
        if self._check("CLASS"):
            return self._parse_class_declaration()
        if self._check("IF"):
            return self._parse_if_statement()
        if self._check("WHILE"):
            return self._parse_while_statement()
        if self._check("FOR"):
            return self._parse_for_statement()
        if self._check("BREAK"):
            return self._parse_break_statement()
        if self._check("CONTINUE"):
            return self._parse_continue_statement()
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

    def _parse_while_statement(self) -> WhileStatement:
        self._consume("WHILE", "Expected 'while'")
        self._consume("LPAREN", "Expected '(' after while")
        test = self.parse_expression()
        self._consume("RPAREN", "Expected ')' after while condition")
        self.loop_depth += 1
        try:
            body = self.parse_statement()
        finally:
            self.loop_depth -= 1
        return WhileStatement(test=test, body=body)

    def _parse_for_statement(self) -> ForStatement:
        self._consume("FOR", "Expected 'for'")
        self._consume("LPAREN", "Expected '(' after for")
        init: Stmt | None
        if self._match("SEMICOLON"):
            init = None
        elif self._check("VAR") or self._check("LET") or self._check("CONST"):
            init = self._parse_variable_declaration()
        else:
            init_expr = self.parse_expression()
            self._consume("SEMICOLON", "Expected ';' after for initializer")
            init = ExpressionStatement(init_expr)
        test: Expr | None = None
        if not self._check("SEMICOLON"):
            test = self.parse_expression()
        self._consume("SEMICOLON", "Expected ';' after for condition")
        update: Expr | None = None
        if not self._check("RPAREN"):
            update = self.parse_expression()
        self._consume("RPAREN", "Expected ')' after for clause")
        self.loop_depth += 1
        try:
            body = self.parse_statement()
        finally:
            self.loop_depth -= 1
        return ForStatement(init=init, test=test, update=update, body=body)

    def _parse_break_statement(self) -> BreakStatement:
        token = self._advance()
        if self.loop_depth <= 0:
            raise JavaScriptSyntaxError(f"Illegal break statement at offset {token.offset}")
        self._consume_optional_semicolon()
        return BreakStatement()

    def _parse_continue_statement(self) -> ContinueStatement:
        token = self._advance()
        if self.loop_depth <= 0:
            raise JavaScriptSyntaxError(f"Illegal continue statement at offset {token.offset}")
        self._consume_optional_semicolon()
        return ContinueStatement()

    def _parse_return_statement(self) -> ReturnStatement:
        if self.function_depth <= 0:
            raise JavaScriptSyntaxError(f"Illegal return statement at offset {self._peek().offset}")
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

    def _parse_function_declaration(self, *, is_async: bool = False) -> FunctionDeclaration:
        function_expr = self._parse_function_expression(require_name=True, is_async=is_async)
        assert function_expr.name is not None
        return FunctionDeclaration(
            name=function_expr.name,
            params=function_expr.params,
            body=function_expr.body,
            is_async=function_expr.is_async,
        )

    def _parse_class_declaration(self) -> ClassDeclaration:
        class_expr = self._parse_class_expression(require_name=True)
        assert class_expr.name is not None
        return ClassDeclaration(
            name=class_expr.name,
            superclass=class_expr.superclass,
            methods=class_expr.methods,
            fields=class_expr.fields,
        )

    def _parse_class_member(self) -> ClassMethod | ClassField:
        is_static = self._match("STATIC")
        accessor_kind: str | None = None
        computed_key: Expr | None = None
        name: str | None = None
        is_private = False
        is_async = False
        if (
            self._check("ASYNC")
            and self.index + 2 < len(self.tokens)
            and self.tokens[self.index + 1].kind in {"IDENTIFIER", "PRIVATE_IDENTIFIER", "STRING", "LBRACKET"}
        ):
            next_kind = self.tokens[self.index + 2].kind
            if next_kind == "LPAREN" or (self.tokens[self.index + 1].kind == "LBRACKET"):
                is_async = True
                self._advance()
        if (
            self._check("IDENTIFIER")
            and str(self._peek().value) in {"get", "set"}
            and self.index + 1 < len(self.tokens)
            and self.tokens[self.index + 1].kind == "LBRACKET"
        ):
            accessor_kind = str(self._advance().value)
            self._consume("LBRACKET", "Expected '[' after accessor keyword")
            computed_key = self.parse_expression()
            self._consume("RBRACKET", "Expected ']' after computed class key")
        elif self._match("LBRACKET"):
            computed_key = self.parse_expression()
            self._consume("RBRACKET", "Expected ']' after computed class key")
        elif (
            self._check("IDENTIFIER")
            and str(self._peek().value) in {"get", "set"}
            and self.index + 2 < len(self.tokens)
            and self.tokens[self.index + 1].kind == "IDENTIFIER"
            and self.tokens[self.index + 2].kind == "LPAREN"
        ):
            accessor_kind = str(self._advance().value)
            name_token = self._consume("IDENTIFIER", "Expected class method name")
            name = str(name_token.value)
        elif (
            self._check("IDENTIFIER")
            and str(self._peek().value) in {"get", "set"}
            and self.index + 2 < len(self.tokens)
            and self.tokens[self.index + 1].kind == "PRIVATE_IDENTIFIER"
            and self.tokens[self.index + 2].kind == "LPAREN"
        ):
            accessor_kind = str(self._advance().value)
            name_token = self._consume("PRIVATE_IDENTIFIER", "Expected private class method name")
            name = str(name_token.value)
            is_private = True
        elif self._check("IDENTIFIER"):
            name = str(self._advance().value)
        elif self._check("PRIVATE_IDENTIFIER"):
            name = str(self._advance().value)
            is_private = True
        elif self._check("STRING"):
            name = str(self._advance().value)
        else:
            raise JavaScriptSyntaxError(f"Expected class member name at offset {self._peek().offset}")
        if not self._check("LPAREN"):
            initializer = self.parse_expression() if self._match("EQUAL") else None
            self._consume_optional_semicolon()
            return ClassField(
                name=name,
                key_expr=computed_key,
                initializer=initializer,
                is_static=is_static,
                is_private=is_private,
            )
        self._consume("LPAREN", "Expected '(' after method name")
        params: list[str] = []
        if not self._check("RPAREN"):
            while True:
                param = self._consume("IDENTIFIER", "Expected parameter name")
                params.append(str(param.value))
                if not self._match("COMMA"):
                    break
        self._consume("RPAREN", "Expected ')' after method parameters")
        self.function_depth += 1
        try:
            body = self._parse_block_statement()
        finally:
            self.function_depth -= 1
        return ClassMethod(
            name=name,
            key_expr=computed_key,
            params=tuple(params),
            body=body,
            is_static=is_static,
            accessor_kind=accessor_kind,
            is_private=is_private,
            is_async=is_async,
        )

    def _parse_class_expression(self, *, require_name: bool) -> ClassExpr:
        self._consume("CLASS", "Expected 'class'")
        name: str | None = None
        if self._check("IDENTIFIER"):
            name = str(self._advance().value)
        elif require_name:
            raise JavaScriptSyntaxError(f"Expected class name at offset {self._peek().offset}")
        superclass = self.parse_expression() if self._match("EXTENDS") else None
        self._consume("LBRACE", "Expected '{' after class name")
        methods: list[ClassMethod] = []
        fields: list[ClassField] = []
        while not self._check("RBRACE") and not self._check("EOF"):
            member = self._parse_class_member()
            if isinstance(member, ClassMethod):
                methods.append(member)
            else:
                fields.append(member)
        self._consume("RBRACE", "Expected '}' after class body")
        return ClassExpr(name=name, superclass=superclass, methods=tuple(methods), fields=tuple(fields))

    def _parse_function_expression(self, *, require_name: bool, is_async: bool = False) -> FunctionExpr:
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
        self.function_depth += 1
        try:
            body = self._parse_block_statement()
        finally:
            self.function_depth -= 1
        return FunctionExpr(name=name, params=tuple(params), body=body, is_async=is_async)

    def _parse_prefix(self, token: Token) -> Expr:
        if token.kind == "NUMBER":
            return NumberLiteral(value=float(token.value))
        if token.kind == "STRING":
            return StringLiteral(value=str(token.value))
        if token.kind == "TEMPLATE":
            parts: list[str | Expr] = []
            raw_parts: list[str] = []
            for chunk in token.value:
                if isinstance(chunk, tuple) and len(chunk) == 2 and chunk[0] == "expr":
                    nested = parse_expression(chunk[1])
                    parts.append(nested)
                elif isinstance(chunk, tuple) and len(chunk) == 3 and chunk[0] == "text":
                    parts.append(str(chunk[1]))
                    raw_parts.append(str(chunk[2]))
                else:
                    parts.append(str(chunk))
                    raw_parts.append(str(chunk))
            return TemplateLiteral(parts=tuple(parts), raw_parts=tuple(raw_parts))
        if token.kind in {"TRUE", "FALSE"}:
            return BooleanLiteral(value=bool(token.value))
        if token.kind == "NULL":
            return NullLiteral()
        if token.kind == "IDENTIFIER":
            return Identifier(name=str(token.value))
        if token.kind == "THIS":
            return ThisExpr()
        if token.kind == "AWAIT":
            return AwaitExpr(value=self.parse_expression(8))
        if token.kind == "YIELD":
            raise JavaScriptSyntaxError(f"Unexpected token {token.lexeme!r} at offset {token.offset}")
        if token.kind == "SUPER":
            return SuperExpr()
        if token.kind == "CLASS":
            self.index -= 1
            return self._parse_class_expression(require_name=False)
        if token.kind == "ASYNC":
            if self._check("FUNCTION"):
                return self._parse_function_expression(require_name=False, is_async=True)
            raise JavaScriptSyntaxError(f"Unexpected token {token.lexeme!r} at offset {token.offset}")
        if token.kind == "FUNCTION":
            self.index -= 1
            return self._parse_function_expression(require_name=False)
        if token.kind == "NEW":
            return self._parse_new_expression()
        if token.kind == "LBRACKET":
            return self._parse_array_literal()
        if token.kind == "LBRACE":
            return self._parse_object_literal()
        if token.kind in {"PLUS", "MINUS", "BANG"}:
            return UnaryExpr(operator=token.lexeme, operand=self.parse_expression(8))
        if token.kind == "TYPEOF":
            return UnaryExpr(operator="typeof", operand=self.parse_expression(8))
        if token.kind in ("++", "--"):
            target = self.parse_expression(8)
            if not isinstance(target, (Identifier, MemberExpr, IndexExpr)):
                raise JavaScriptSyntaxError(f"Invalid update target at offset {token.offset}")
            return UpdateExpr(target=target, operator=token.lexeme, prefix=True)
        if token.kind == "LPAREN":
            expr = self.parse_expression()
            self._consume("RPAREN", "Expected ')' after expression")
            return expr
        raise JavaScriptSyntaxError(f"Unexpected token {token.lexeme!r} at offset {token.offset}")

    def _parse_new_expression(self) -> Expr:
        target = self._parse_prefix(self._advance())
        while self._check("DOT") or self._check("LBRACKET"):
            target = self._parse_infix(target, self._advance())
        arguments: list[Expr] = []
        if self._match("LPAREN"):
            if not self._check("RPAREN"):
                while True:
                    arguments.append(self.parse_expression())
                    if not self._match("COMMA"):
                        break
            self._consume("RPAREN", "Expected ')' after constructor arguments")
        return NewExpr(callee=target, arguments=tuple(arguments))

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
        if token.kind == "TEMPLATE":
            self.index -= 1
            template = self._parse_prefix(self._advance())
            assert isinstance(template, TemplateLiteral)
            return TaggedTemplateExpr(callee=left, template=template)
        if token.kind in ("++", "--"):
            if not isinstance(left, (Identifier, MemberExpr, IndexExpr)):
                raise JavaScriptSyntaxError(f"Invalid update target at offset {token.offset}")
            return UpdateExpr(target=left, operator=token.lexeme, prefix=False)
        if token.kind == "DOT":
            if self._peek().kind in PROPERTY_NAME_TOKENS:
                property_token = self._advance()
                return MemberExpr(object=left, property_name=str(property_token.value))
            if self._check("PRIVATE_IDENTIFIER"):
                property_token = self._advance()
                return MemberExpr(object=left, property_name=str(property_token.value), is_private=True)
            raise JavaScriptSyntaxError(f"Expected property name after '.' at offset {self._peek().offset}")
        if token.kind == "LBRACKET":
            index = self.parse_expression()
            self._consume("RBRACKET", "Expected ']' after index expression")
            return IndexExpr(object=left, index=index)
        if token.kind == "EQUAL":
            if not isinstance(left, (Identifier, MemberExpr, IndexExpr)):
                raise JavaScriptSyntaxError(f"Invalid assignment target at offset {token.offset}")
            return AssignmentExpr(target=left, value=self.parse_expression(PRECEDENCE["EQUAL"] - 1))
        if token.kind in ("+=", "-=", "*=", "/=", "%="):
            if not isinstance(left, (Identifier, MemberExpr, IndexExpr)):
                raise JavaScriptSyntaxError(f"Invalid assignment target at offset {token.offset}")
            return CompoundAssignmentExpr(
                target=left,
                operator=token.kind,
                value=self.parse_expression(PRECEDENCE[token.kind] - 1),
            )
        if token.kind == "QUESTION":
            consequent = self.parse_expression()
            self._consume("COLON", "Expected ':' in ternary expression")
            alternate = self.parse_expression()
            return ConditionalExpr(test=left, consequent=consequent, alternate=alternate)
        if token.kind == "**":
            # Right-associative: a ** b ** c parses as a ** (b ** c).
            right = self.parse_expression(PRECEDENCE["**"] - 1)
            return BinaryExpr(left=left, operator="**", right=right)
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
                if self._check("LPAREN"):
                    self._consume("LPAREN", "Expected '(' after method name")
                    params: list[str] = []
                    if not self._check("RPAREN"):
                        while True:
                            param = self._consume("IDENTIFIER", "Expected parameter name")
                            params.append(str(param.value))
                            if not self._match("COMMA"):
                                break
                    self._consume("RPAREN", "Expected ')' after method parameters")
                    self.function_depth += 1
                    try:
                        body = self._parse_block_statement()
                    finally:
                        self.function_depth -= 1
                    value = FunctionExpr(name=key, params=tuple(params), body=body, is_async=False)
                else:
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
