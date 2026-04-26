"""AST nodes for the standalone JS interpreter."""

from __future__ import annotations

from dataclasses import dataclass


class Expr:
    """Base type for JS expressions."""


class Stmt:
    """Base type for JS statements."""


@dataclass(frozen=True, slots=True)
class NumberLiteral(Expr):
    value: float


@dataclass(frozen=True, slots=True)
class StringLiteral(Expr):
    value: str


@dataclass(frozen=True, slots=True)
class BooleanLiteral(Expr):
    value: bool


@dataclass(frozen=True, slots=True)
class NullLiteral(Expr):
    pass


@dataclass(frozen=True, slots=True)
class TemplateLiteral(Expr):
    parts: tuple[str | Expr, ...]
    raw_parts: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AwaitExpr(Expr):
    value: Expr


@dataclass(frozen=True, slots=True)
class ConditionalExpr(Expr):
    test: Expr
    consequent: Expr
    alternate: Expr


@dataclass(frozen=True, slots=True)
class CompoundAssignmentExpr(Expr):
    target: Expr
    operator: str
    value: Expr


@dataclass(frozen=True, slots=True)
class Identifier(Expr):
    name: str


@dataclass(frozen=True, slots=True)
class ThisExpr(Expr):
    pass


@dataclass(frozen=True, slots=True)
class SuperExpr(Expr):
    pass


@dataclass(frozen=True, slots=True)
class UnaryExpr(Expr):
    operator: str
    operand: Expr


@dataclass(frozen=True, slots=True)
class UpdateExpr(Expr):
    target: Expr
    operator: str
    prefix: bool = False


@dataclass(frozen=True, slots=True)
class BinaryExpr(Expr):
    left: Expr
    operator: str
    right: Expr


@dataclass(frozen=True, slots=True)
class AssignmentExpr(Expr):
    target: Expr
    value: Expr


@dataclass(frozen=True, slots=True)
class NewExpr(Expr):
    callee: Expr
    arguments: tuple[Expr, ...]


@dataclass(frozen=True, slots=True)
class ClassField:
    name: str | None
    key_expr: Expr | None
    initializer: Expr | None
    is_static: bool = False
    is_private: bool = False


@dataclass(frozen=True, slots=True)
class ClassMethod:
    name: str | None
    key_expr: Expr | None
    params: tuple[str, ...]
    body: "BlockStatement"
    is_static: bool = False
    accessor_kind: str | None = None
    is_private: bool = False
    is_async: bool = False


@dataclass(frozen=True, slots=True)
class ClassExpr(Expr):
    name: str | None
    superclass: Expr | None
    methods: tuple[ClassMethod, ...]
    fields: tuple[ClassField, ...]


@dataclass(frozen=True, slots=True)
class FunctionExpr(Expr):
    name: str | None
    params: tuple[str, ...]
    body: "BlockStatement"
    is_async: bool = False


@dataclass(frozen=True, slots=True)
class ArrowFunctionExpr(Expr):
    params: tuple[str, ...]
    body: "BlockStatement | Expr"
    is_async: bool = False


@dataclass(frozen=True, slots=True)
class CallExpr(Expr):
    callee: Expr
    arguments: tuple[Expr, ...]


@dataclass(frozen=True, slots=True)
class TaggedTemplateExpr(Expr):
    callee: Expr
    template: TemplateLiteral


@dataclass(frozen=True, slots=True)
class MemberExpr(Expr):
    object: Expr
    property_name: str
    is_private: bool = False


@dataclass(frozen=True, slots=True)
class IndexExpr(Expr):
    object: Expr
    index: Expr


@dataclass(frozen=True, slots=True)
class ArrayLiteral(Expr):
    elements: tuple[Expr, ...]


@dataclass(frozen=True, slots=True)
class ObjectProperty:
    key: str
    value: Expr


@dataclass(frozen=True, slots=True)
class ObjectLiteral(Expr):
    properties: tuple[ObjectProperty, ...]


@dataclass(frozen=True, slots=True)
class ExpressionStatement(Stmt):
    expression: Expr


@dataclass(frozen=True, slots=True)
class VariableDeclaration(Stmt):
    kind: str
    name: str
    initializer: Expr | None


@dataclass(frozen=True, slots=True)
class FunctionDeclaration(Stmt):
    name: str
    params: tuple[str, ...]
    body: "BlockStatement"
    is_async: bool = False


@dataclass(frozen=True, slots=True)
class ClassDeclaration(Stmt):
    name: str
    superclass: Expr | None
    methods: tuple[ClassMethod, ...]
    fields: tuple[ClassField, ...]


@dataclass(frozen=True, slots=True)
class BlockStatement(Stmt):
    statements: tuple[Stmt, ...]


@dataclass(frozen=True, slots=True)
class IfStatement(Stmt):
    test: Expr
    consequent: Stmt
    alternate: Stmt | None


@dataclass(frozen=True, slots=True)
class WhileStatement(Stmt):
    test: Expr
    body: Stmt


@dataclass(frozen=True, slots=True)
class ForStatement(Stmt):
    init: Stmt | None
    test: Expr | None
    update: Expr | None
    body: Stmt


@dataclass(frozen=True, slots=True)
class BreakStatement(Stmt):
    pass


@dataclass(frozen=True, slots=True)
class ContinueStatement(Stmt):
    pass


@dataclass(frozen=True, slots=True)
class ReturnStatement(Stmt):
    value: Expr | None


@dataclass(frozen=True, slots=True)
class ThrowStatement(Stmt):
    value: Expr


@dataclass(frozen=True, slots=True)
class TryStatement(Stmt):
    body: BlockStatement
    catch_name: str | None
    catch_body: BlockStatement | None
    finally_body: BlockStatement | None


@dataclass(frozen=True, slots=True)
class Program:
    statements: tuple[Stmt, ...]
