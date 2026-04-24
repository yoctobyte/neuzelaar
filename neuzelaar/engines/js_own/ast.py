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
class Identifier(Expr):
    name: str


@dataclass(frozen=True, slots=True)
class ThisExpr(Expr):
    pass


@dataclass(frozen=True, slots=True)
class UnaryExpr(Expr):
    operator: str
    operand: Expr


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
class FunctionExpr(Expr):
    name: str | None
    params: tuple[str, ...]
    body: "BlockStatement"


@dataclass(frozen=True, slots=True)
class ArrowFunctionExpr(Expr):
    params: tuple[str, ...]
    body: "BlockStatement | Expr"


@dataclass(frozen=True, slots=True)
class CallExpr(Expr):
    callee: Expr
    arguments: tuple[Expr, ...]


@dataclass(frozen=True, slots=True)
class MemberExpr(Expr):
    object: Expr
    property_name: str


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


@dataclass(frozen=True, slots=True)
class BlockStatement(Stmt):
    statements: tuple[Stmt, ...]


@dataclass(frozen=True, slots=True)
class IfStatement(Stmt):
    test: Expr
    consequent: Stmt
    alternate: Stmt | None


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
