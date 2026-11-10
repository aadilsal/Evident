"""Prisma adapter: models, fields, relations and `@@map` from schema files, plus the op table.

Call classification (`prisma.<model>.<op>()` -> read/write) happens in the universal layer once
the client instance has been traced; this module owns the counting rules for it.
Counting rules: docs/labelling-guide.md (Models, Route -> model edges).
"""

from __future__ import annotations

import re
from typing import Any

import tree_sitter as ts

from evident.adapters._js import call_args, enclosing_scope, walk_calls
from evident.link import Fact, LinkContext, Pkg, Sym
from evident.syntax import chain, end_line, line, text, unwrap
from evident.universal.js import FnKeys

JSON = dict[str, Any]
READ_OPS = frozenset(
    {
        "findUnique",
        "findUniqueOrThrow",
        "findFirst",
        "findFirstOrThrow",
        "findMany",
        "count",
        "aggregate",
        "groupBy",
    }
)
WRITE_OPS = frozenset(
    {
        "create",
        "createMany",
        "createManyAndReturn",
        "update",
        "updateMany",
        "updateManyAndReturn",
        "upsert",
        "delete",
        "deleteMany",
    }
)
# Nested writes inside `data` (labelling guide: count a write on the nested model too).
NESTED_WRITES = frozenset(
    {
        "create",
        "createMany",
        "connectOrCreate",
        "upsert",
        "update",
        "updateMany",
        "delete",
        "deleteMany",
    }
)
MAX_NESTING = 4
_BLOCK = re.compile(r"^\s*(model|view|enum|type|datasource|generator)\s+(\w+)\s*\{")
_FIELD = re.compile(r"^\s*(\w+)\s+(\w+)(\[\])?(\?)?(.*)$")
_MAP = re.compile(r"@@map\(\s*(?:name\s*:\s*)?\"([^\"]+)\"")
_ENV = re.compile(r"env\(\s*\"([A-Za-z_][A-Za-z0-9_]*)\"\s*\)")


def parse_schema(text: str) -> JSON:
    """Models with fields and line ranges, plus env() names. A small, tolerant line parser."""
    models: list[JSON] = []
    env: list[list[Any]] = []
    current: JSON | None = None
    depth = 0
    for no, raw in enumerate(text.splitlines(), start=1):
        ln = raw.split("//", 1)[0]
        for m in _ENV.finditer(ln):
            env.append([m.group(1), no])
        if current is None and depth == 0:
            block = _BLOCK.match(ln)
            if block:
                depth = 1
                if block.group(1) == "model":
                    current = {"name": block.group(2), "line": no, "end": no, "fields": []}
                continue
        if depth == 0:
            continue
        depth += ln.count("{") - ln.count("}")
        if depth <= 0:
            depth = 0
            if current is not None:
                current["end"] = no
                models.append(current)
                current = None
            continue
        if current is None:
            continue
        stripped = ln.strip()
        if stripped.startswith("@@"):
            mapped = _MAP.search(stripped)
            if mapped:
                current["map"] = mapped.group(1)
            continue
        f = _FIELD.match(ln)
        if f:
            attrs = f.group(5)
            field: JSON = {"name": f.group(1), "type": f.group(2), "line": no}
            if f.group(3):
                field["list"] = True
            if f.group(4):
                field["optional"] = True
            if re.search(r"@id\b", attrs):
                field["id"] = True
            if "@relation" in attrs:
                field["relation"] = True
            current["fields"].append(field)
    return {"models": models, "env": env}


PROVEN, THIS_FIELD, GUESS = 1.0, 0.8, 0.7


def _is_client(ctx: LinkContext, file: str, scope: str, recv: list[str]) -> bool:
    """The receiver is provably a PrismaClient (directly, re-exported or a subclass field)."""
    project = ctx.project
    if len(recv) == 1 and recv[0] != "this":
        return any(
            t.imported == "PrismaClient" or t.package == "@prisma/client"
            for t in project.taint(file, recv[0])
        )
    if len(recv) == 2 and recv[0] == "this":
        fld = project.field(file, scope, recv[1])
        target = project.type_target(file, (fld or {}).get("type"))
        if isinstance(target, Pkg):
            return target.imported == "PrismaClient" or target.package == "@prisma/client"
        if isinstance(target, Sym):
            ext = project.js[target.file]["classes"].get(target.name, {}).get("extends", "")
            return "PrismaClient" in ext
    return False


def classify(ctx: LinkContext, file: str, scope: str, call: JSON) -> Fact | None:
    """`<client>.<model>.<op>()` -> reads/writes on that model."""
    c = call["c"]
    if len(c) < 3:
        return None
    op, model = c[-1], ctx.models.get(c[-2])
    kind = "reads" if op in READ_OPS else "writes" if op in WRITE_OPS else None
    if model is None or kind is None:
        return None
    recv = c[:-2]
    if _is_client(ctx, file, scope, recv):
        source, conf = "extracted", PROVEN
    else:
        source, conf = "inferred", THIS_FIELD if recv[0] == "this" else GUESS
    ev = ctx.ev(file, call["l"], call["e"])
    return (kind, f"model:{model}", ev, {"operation": op}, source, conf)


def _props(obj: ts.Node) -> dict[str, ts.Node]:
    out = {}
    for pair in obj.named_children:
        if pair.type == "pair":
            val = pair.child_by_field_name("value")
            if val is not None:
                out[text(pair.child_by_field_name("key")).strip("'\"")] = unwrap(val)
    return out


def _nested(obj: ts.Node, path: list[str], depth: int) -> list[list[Any]]:
    """[[relation path], op] for every nested write under a `data` object."""
    if depth > MAX_NESTING or obj.type != "object":
        return []
    out: list[list[Any]] = []
    for key, val in _props(obj).items():
        if val.type != "object":
            continue
        for op, inner in _props(val).items():
            if op not in NESTED_WRITES:
                continue
            out.append([[*path, key], op])
            targets = inner.named_children if inner.type == "array" else [inner]
            for t in targets:
                t = unwrap(t)
                if t.type == "object":
                    data = _props(t).get("data", t) if op in ("upsert", "update") else t
                    out.extend(_nested(data, [*path, key], depth + 1))
    return out


def extract(rel_path: str, tree: ts.Tree, fn_keys: FnKeys) -> JSON | None:
    """Nested writes per Prisma call, so linking can attribute them to the nested models."""
    found = []
    for call in walk_calls(tree.root_node):
        if call.type != "call_expression":
            continue
        c = chain(call.child_by_field_name("function"))
        args = call_args(call)
        if not c or len(c) < 3 or c[-1] not in WRITE_OPS or not args:
            continue
        arg = unwrap(args[0])
        if arg.type != "object":
            continue
        props = _props(arg)
        nested: list[list[Any]] = []
        for key in ("data", "create", "update"):
            if key in props:
                nested.extend(_nested(props[key], [], 0))
        if nested:
            found.append(
                {
                    "c": c,
                    "l": line(call),
                    "e": end_line(call),
                    "s": enclosing_scope(call, fn_keys),
                    "nested": nested,
                }
            )
    return {"nested": found} if found else None


def accessor(model: str) -> str:
    """`prisma.<accessor>` for a model: AuditLog -> auditLog."""
    return model[:1].lower() + model[1:]


def link(ctx: LinkContext) -> None:
    schemas = {
        f: r["prisma"] for f, r in ctx.project.raw.items() if "prisma" in r and "js" not in r
    }
    models = {m["name"]: (f, m) for f, s in schemas.items() for m in s["models"]}
    if not models:
        return
    ctx.adapters.append("prisma")
    ctx.classifiers.append(classify)
    for name in models:
        ctx.models[accessor(name)] = name
    for name, (file, m) in sorted(models.items()):
        fields = []
        for fl in m["fields"]:
            out: JSON = {"name": fl["name"], "type": fl["type"]}
            for src, dst in (("optional", "isOptional"), ("list", "isList"), ("id", "isId")):
                if fl.get(src):
                    out[dst] = True
            if fl["type"] in models:
                out["isRelation"] = True
            fields.append(out)
        ctx.node(
            f"model:{name}",
            "model",
            name,
            [ctx.ev(file, m["line"], m["end"])],
            {"tableName": m.get("map", name), "fields": fields, "orm": "prisma"},
        )
    relation = {
        (name, fl["name"]): fl["type"] for name, (_, m) in models.items() for fl in m["fields"]
    }
    for file, raw in ctx.project.raw.items():
        for call in raw.get("prisma", {}).get("nested", []) if "js" in raw else []:
            root = ctx.models.get(call["c"][-2])
            if root is None or call["s"] == "<module>":
                continue
            proven = _is_client(ctx, file, call["s"], call["c"][:-2])
            for path, op in call["nested"]:
                model: str | None = root
                for key in path:
                    model = relation.get((model, key)) if model else None
                if model is None or model not in models:
                    continue
                fact: Fact = (
                    "writes",
                    f"model:{model}",
                    ctx.ev(file, call["l"], call["e"]),
                    {"operation": f"nested {op}"},
                    "extracted" if proven else "inferred",
                    PROVEN if proven else GUESS,
                )
                ctx.access.setdefault((file, call["s"]), []).append(fact)
    for name, (file, m) in models.items():
        for fl in m["fields"]:
            if fl["type"] in models and fl["type"] != name:
                ctx.edge(
                    "relates",
                    f"model:{name}",
                    f"model:{fl['type']}",
                    [ctx.ev(file, fl["line"])],
                    {"relationField": fl["name"]},
                )
