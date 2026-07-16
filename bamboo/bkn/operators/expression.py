"""Safe expression operator evaluation."""

from __future__ import annotations

import ast
from typing import Any

ALLOWED_FUNCTIONS = {
    "abs": abs,
    "max": max,
    "min": min,
    "round": round,
    "sum": sum,
}
ALLOWED_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.BoolOp,
    ast.Compare,
    ast.IfExp,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.Call,
    ast.List,
    ast.Tuple,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.USub,
    ast.UAdd,
    ast.And,
    ast.Or,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
)


def evaluate_expression_operator(expression: str, attrs: dict[str, Any]) -> Any:
    """Evaluate a side-effect-free expression against attrs."""
    tree = ast.parse(expression, mode="eval")
    _validate_tree(tree, attrs)
    return eval(compile(tree, "<bkn-expression>", "eval"), {"__builtins__": {}}, {**ALLOWED_FUNCTIONS, **attrs})


def _validate_tree(tree: ast.AST, attrs: dict[str, Any]) -> None:
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_NODES):
            raise ValueError(f"unsupported expression node: {type(node).__name__}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_FUNCTIONS:
                raise ValueError("only safe built-in functions are allowed")
        if isinstance(node, ast.Name) and node.id not in attrs and node.id not in ALLOWED_FUNCTIONS:
            raise ValueError(f"unknown expression name: {node.id}")
