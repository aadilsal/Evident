"""Drizzle adapter: `pgTable`/`mysqlTable`/`sqliteTable` tables, `.references()` relations, and
reads/writes from the query builder (`select().from(t)`, `insert(t)`, `update(t)`, `delete(t)`,
joins) and the relational API (`db.query.<table>.findMany()`).

A Drizzle model is named by its table variable (`export const users = pgTable('users', …)`).
Counting rules: docs/labelling-guide.md (Drizzle).
"""

from __future__ import annotations

import re
from typing import Any

import tree_sitter as ts

from evident.adapters._js import binding_of, call_args, callee, enclosing_scope, walk_calls
from evident.link import Fact, LinkContext, Pkg, Sym
from evident.syntax import chain, end_line, line, string_value, text, unwrap
from evident.universal.js import FnKeys

JSON = dict[str, Any]
TABLE_FNS = frozenset({"pgTable", "mysqlTable", "sqliteTable"})
BUILDER_OPS = {
    "from": "reads",
    "innerJoin": "reads",
    "leftJoin": "reads",
    "rightJoin": "reads",
    "fullJoin": "reads",
    "insert": "writes",
    "update": "writes",
    "delete": "writes",
}
QUERY_OPS = frozenset({"findMany", "findFirst"})
_REF = re.compile(r"references\(\s*\(\s*\)\s*(?::\s*\w+\s*)?=>\s*(\w+)\.")


def _column_type(value: ts.Node) -> str:
    """`text('name').notNull()` -> "text"."""
    n = unwrap(value)
    while n.type == "call_expression":
        fn = n.child_by_field_name("function")
        if fn is None:
            break
        if fn.type == "member_expression":
            obj = fn.child_by_field_name("object")
            if obj is None:
                break
            n = unwrap(obj)
        else:
            return text(fn)
    return text(n)


def extract(rel_path: str, tree: ts.Tree, fn_keys: FnKeys) -> JSON | None:
    tables, ops = [], []
    for call in walk_calls(tree.root_node):
        if call.type != "call_expression":
            continue
        c = callee(call)
        args = call_args(call)
        if c and len(c) == 1 and c[0] in TABLE_FNS and len(args) >= 2:
            name, cols = string_value(args[0]), unwrap(args[1])
            bind = binding_of(call)
            if not name or not bind:
                continue
            columns = []
            if cols.type == "object":
                for pair in cols.named_children:
                    if pair.type != "pair":
                        continue
                    val = pair.child_by_field_name("value")
                    col: JSON = {
                        "name": text(pair.child_by_field_name("key")).strip("'\""),
                        "type": _column_type(val) if val is not None else "unknown",
                        "line": line(pair),
                    }
                    ref = _REF.search(text(val)) if val is not None else None
                    if ref:
                        col["ref"] = ref.group(1)
                    if val is not None and ".primaryKey(" in text(val):
                        col["id"] = True
                    columns.append(col)
            tables.append(
                {
                    "bind": bind,
                    "fn": c[0],
                    "table": name,
                    "line": line(call),
                    "end": end_line(call),
                    "columns": columns,
                }
            )
            continue
        fn = call.child_by_field_name("function")
        if fn is None or fn.type != "member_expression" or not args:
            continue
        prop = text(fn.child_by_field_name("property"))
        first = unwrap(args[0])
        if prop in BUILDER_OPS and first.type == "identifier":
            ops.append(
                {
                    "op": prop,
                    "table": text(first),
                    "recv": chain(fn.child_by_field_name("object")),
                    "l": line(call),
                    "e": end_line(call),
                    "s": enclosing_scope(call, fn_keys),
                }
            )
    out: JSON = {}
    if tables:
        out["tables"] = tables
    if ops:
        out["ops"] = ops
    return out or None


def link(ctx: LinkContext) -> None:
    project = ctx.project
    tables: dict[tuple[str, str], JSON] = {}
    for file, raw in project.raw.items():
        for t in raw.get("drizzle", {}).get("tables", []):
            origin = project.resolve(file, t["fn"])
            if isinstance(origin, Pkg) and origin.package == "drizzle-orm":
                tables[(file, t["bind"])] = {**t, "file": file}
    if not tables:
        return
    ctx.adapters.append("drizzle")
    by_name = {t["bind"]: t for t in tables.values()}
    for (file, bind), t in sorted(tables.items()):
        fields = []
        for col in t["columns"]:
            f: JSON = {"name": col["name"], "type": col["type"]}
            if col.get("id"):
                f["isId"] = True
            if col.get("ref") in by_name:
                f["isRelation"] = True
            fields.append(f)
        ctx.node(
            f"model:{bind}",
            "model",
            bind,
            [ctx.ev(file, t["line"], t["end"])],
            {"tableName": t["table"], "fields": fields, "orm": "drizzle"},
        )
        for col in t["columns"]:
            ref = col.get("ref")
            if ref in by_name and ref != bind:
                ctx.edge(
                    "relates",
                    f"model:{bind}",
                    f"model:{ref}",
                    [ctx.ev(file, col["line"])],
                    {"relationField": col["name"]},
                )

    def table_of(file: str, name: str) -> str | None:
        target = project.resolve(file, name)
        if isinstance(target, Sym) and (target.file, target.name) in tables:
            return target.name
        return None

    for file, raw in project.raw.items():
        for op in raw.get("drizzle", {}).get("ops", []):
            table = table_of(file, op["table"])
            if table is None or op["s"] == "<module>":
                continue
            fact: Fact = (
                BUILDER_OPS[op["op"]],
                f"model:{table}",
                ctx.ev(file, op["l"], op["e"]),
                {"operation": op["op"]},
                "extracted",
                1.0,
            )
            ctx.access.setdefault((file, op["s"]), []).append(fact)

    def classify(ctx: LinkContext, file: str, scope: str, call: JSON) -> Fact | None:
        c = call["c"]
        if len(c) >= 4 and c[-3] == "query" and c[-1] in QUERY_OPS and c[-2] in by_name:
            ev = ctx.ev(file, call["l"], call["e"])
            return ("reads", f"model:{c[-2]}", ev, {"operation": c[-1]}, "extracted", 1.0)
        return None

    ctx.classifiers.append(classify)
