"""Helpers shared by JS/TS adapters: describing call arguments as cacheable JSON."""

from __future__ import annotations

from importlib.resources import files
from typing import Any

import tree_sitter as ts

from evident.syntax import chain, grammar_for, query, string_value, text, unwrap
from evident.universal.js import FUNC_TYPES, MODULE, FnKeys

JSON = dict[str, Any]


def load_query(package: str, name: str, rel_path: str) -> ts.Query | None:
    kind = grammar_for(rel_path)
    if kind is None:
        return None
    source = files(package).joinpath(name).read_text(encoding="utf-8")
    return query(kind, source)


def describe(node: ts.Node, fn_keys: FnKeys) -> JSON:
    """One argument as data: a function scope, an identifier, a member chain, a call, a string…"""
    n = unwrap(node)
    t = n.type
    if t in FUNC_TYPES:
        return {"k": "fn", "scope": fn_keys.get((n.start_byte, n.end_byte))}
    if t == "identifier":
        return {"k": "id", "name": text(n)}
    if t == "member_expression":
        c = chain(n)
        return {"k": "member", "chain": c} if c else {"k": "other"}
    if t == "call_expression":
        c = chain(n.child_by_field_name("function"))
        args = n.child_by_field_name("arguments")
        first = args.named_children[0] if args is not None and args.named_children else None
        if c == ["require"] and first is not None:
            spec = string_value(first)
            if spec:
                return {"k": "require", "spec": spec}
        inner = [describe(a, fn_keys) for a in args.named_children] if args is not None else []
        return {"k": "call", "chain": c, "args": inner}
    value = string_value(n)
    if value is not None:
        return {"k": "str", "value": value}
    if t == "array":
        return {"k": "array", "items": [describe(c, fn_keys) for c in n.named_children]}
    return {"k": "other"}


def enclosing_scope(node: ts.Node, fn_keys: FnKeys) -> str:
    """Key of the innermost function scope containing a node (the module if none)."""
    p = node.parent
    while p is not None:
        key = fn_keys.get((p.start_byte, p.end_byte))
        if key is not None:
            return key
        p = p.parent
    return MODULE


def args_of(call_args: ts.Node, fn_keys: FnKeys) -> list[JSON]:
    return [describe(a, fn_keys) for a in call_args.named_children if a.type != "comment"]
