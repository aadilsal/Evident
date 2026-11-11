"""tree-sitter parsing and small node helpers. Parsing only: nothing here runs repo code."""

from __future__ import annotations

from functools import cache

import tree_sitter as ts
import tree_sitter_javascript as tsj
import tree_sitter_python as tsp
import tree_sitter_typescript as tst

JS_SUFFIXES = (".js", ".jsx", ".mjs", ".cjs")
TS_SUFFIXES = (".ts", ".mts", ".cts")
TSX_SUFFIXES = (".tsx",)


@cache
def language(kind: str) -> ts.Language:
    if kind == "typescript":
        return ts.Language(tst.language_typescript())
    if kind == "tsx":
        return ts.Language(tst.language_tsx())
    if kind == "python":
        return ts.Language(tsp.language())
    return ts.Language(tsj.language())


def grammar_for(rel_path: str) -> str | None:
    if rel_path.endswith(".d.ts"):
        return None  # type declarations carry no runtime facts
    if rel_path.endswith(TSX_SUFFIXES):
        return "tsx"
    if rel_path.endswith(TS_SUFFIXES):
        return "typescript"
    if rel_path.endswith(JS_SUFFIXES):
        return "javascript"
    if rel_path.endswith(".py"):
        return "python"
    return None


def is_js(rel_path: str) -> bool:
    return grammar_for(rel_path) not in (None, "python")


def parse(rel_path: str, text: str) -> ts.Tree | None:
    kind = grammar_for(rel_path)
    if kind is None:
        return None
    return ts.Parser(language(kind)).parse(text.encode("utf-8"))


def query(kind: str, source: str) -> ts.Query:
    return _query(kind, source)


@cache
def _query(kind: str, source: str) -> ts.Query:
    return ts.Query(language(kind), source)


def captures(q: ts.Query, node: ts.Node) -> list[tuple[int, dict[str, list[ts.Node]]]]:
    return ts.QueryCursor(q).matches(node)


def text(node: ts.Node | None) -> str:
    if node is None or node.text is None:
        return ""
    return node.text.decode("utf-8", errors="replace")


def line(node: ts.Node) -> int:
    return node.start_point[0] + 1


def end_line(node: ts.Node) -> int:
    return node.end_point[0] + 1


def string_value(node: ts.Node | None) -> str | None:
    """Value of a string literal, or a template string with no substitutions."""
    if node is None:
        return None
    if node.type == "string":
        return "".join(text(c) for c in node.named_children)
    if node.type == "template_string":
        if any(c.type == "template_substitution" for c in node.named_children):
            return None
        return text(node)[1:-1]
    return None


def unwrap(node: ts.Node) -> ts.Node:
    """Skip wrappers that don't change what an expression refers to."""
    while node.type in (
        "parenthesized_expression",
        "await_expression",
        "non_null_expression",
        "as_expression",
        "satisfies_expression",
        "type_assertion",
    ):
        inner = node.named_children[0] if node.named_children else None
        if inner is None:
            break
        node = inner
    return node


def chain(node: ts.Node | None) -> list[str] | None:
    """`a.b.c` -> ["a", "b", "c"]; `this.x` -> ["this", "x"]; None if not a plain chain."""
    parts: list[str] = []
    while node is not None:
        node = unwrap(node)
        if node.type == "identifier":
            parts.append(text(node))
            return parts[::-1]
        if node.type == "this":
            parts.append("this")
            return parts[::-1]
        if node.type == "member_expression":
            prop = node.child_by_field_name("property")
            if prop is None:
                return None
            parts.append(text(prop))
            node = node.child_by_field_name("object")
            continue
        return None
    return None
