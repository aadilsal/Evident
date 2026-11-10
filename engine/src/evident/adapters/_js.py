"""Helpers shared by JS/TS adapters: describing call arguments as cacheable JSON."""

from __future__ import annotations

from collections.abc import Iterator
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
    if t == "object":
        props: JSON = {}
        for pair in n.named_children:
            if pair.type == "pair":
                key = text(pair.child_by_field_name("key")).strip("'\"")
                val = pair.child_by_field_name("value")
                if val is not None:
                    props[key] = describe(val, fn_keys)
            elif pair.type == "shorthand_property_identifier":
                props[text(pair)] = {"k": "id", "name": text(pair)}
            elif pair.type == "method_definition":
                props[text(pair.child_by_field_name("name"))] = {
                    "k": "fn",
                    "scope": fn_keys.get((pair.start_byte, pair.end_byte)),
                }
        return {"k": "obj", "props": props}
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


def binding_of(node: ts.Node) -> str | None:
    """Name an expression is bound to: `const X = …`, `export default …`, `module.exports = …`."""
    p = node.parent
    while p is not None and p.type in (
        "binary_expression",
        "parenthesized_expression",
        "await_expression",
        "as_expression",
        "satisfies_expression",
        "ternary_expression",
        "non_null_expression",
    ):
        p = p.parent
    if p is None:
        return None
    if p.type == "variable_declarator":
        name = p.child_by_field_name("name")
        return text(name) if name is not None and name.type == "identifier" else None
    if p.type == "export_statement":
        return "default"
    if p.type == "assignment_expression" and chain(p.child_by_field_name("left")) == [
        "module",
        "exports",
    ]:
        return "default"
    return None


def walk_calls(root: ts.Node) -> Iterator[ts.Node]:
    """Every call_expression / new_expression in a tree, iteratively."""
    stack = [root]
    while stack:
        n = stack.pop()
        if n.type in ("call_expression", "new_expression"):
            yield n
        stack.extend(n.children)


def callee(call: ts.Node) -> list[str] | None:
    fn = call.child_by_field_name("function") or call.child_by_field_name("constructor")
    return chain(fn)


def call_args(call: ts.Node) -> list[ts.Node]:
    args = call.child_by_field_name("arguments")
    return [a for a in args.named_children if a.type != "comment"] if args is not None else []
