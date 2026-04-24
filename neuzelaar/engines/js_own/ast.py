"""AST nodes for the standalone JS interpreter."""

from __future__ import annotations

from dataclasses import dataclass


class Expr:
    """Base type for JS expressions."""


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
class UnaryExpr(Expr):
    operator: str
    operand: Expr


@dataclass(frozen=True, slots=True)
class BinaryExpr(Expr):
    left: Expr
    operator: str
    right: Expr


@dataclass(frozen=True, slots=True)
class Program:
    expressions: tuple[Expr, ...]
