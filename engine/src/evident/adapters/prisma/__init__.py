"""Prisma adapter: models, fields, relations and `@@map` from schema files, plus the op table.

Call classification (`prisma.<model>.<op>()` -> read/write) happens in the universal layer once
the client instance has been traced; this module owns the counting rules for it.
Counting rules: docs/labelling-guide.md (Models, Route -> model edges).
"""

from __future__ import annotations

import re
from typing import Any

from evident.link import LinkContext

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


def accessor(model: str) -> str:
    """`prisma.<accessor>` for a model: AuditLog -> auditLog."""
    return model[:1].lower() + model[1:]


def link(ctx: LinkContext) -> None:
    schemas = {f: r["prisma"] for f, r in ctx.project.raw.items() if "prisma" in r}
    models = {m["name"]: (f, m) for f, s in schemas.items() for m in s["models"]}
    if not models:
        return
    ctx.adapters.append("prisma")
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
            {"tableName": m.get("map", name), "fields": fields},
        )
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
