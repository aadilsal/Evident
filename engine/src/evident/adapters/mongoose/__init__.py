"""Mongoose adapter: `model('Name', schema)` definitions, schema fields, `ref` relations, and
reads/writes through model bindings (`User.find()`, `new User().save()`, `@InjectModel` fields).

Counting rules: docs/labelling-guide.md (Mongoose).
"""

from __future__ import annotations

from typing import Any

import tree_sitter as ts

from evident.adapters._js import binding_of, call_args, callee, walk_calls
from evident.link import Fact, LinkContext, Pkg, Sym
from evident.syntax import end_line, line, string_value, text, unwrap
from evident.universal.js import FnKeys

JSON = dict[str, Any]
READ_OPS = frozenset(
    {
        "find",
        "findOne",
        "findById",
        "countDocuments",
        "estimatedDocumentCount",
        "exists",
        "aggregate",
        "distinct",
        "where",
    }
)
WRITE_OPS = frozenset(
    {
        "create",
        "insertMany",
        "updateOne",
        "updateMany",
        "deleteOne",
        "deleteMany",
        "replaceOne",
        "bulkWrite",
        "findOneAndUpdate",
        "findByIdAndUpdate",
        "findOneAndDelete",
        "findByIdAndDelete",
        "findOneAndReplace",
        "findByIdAndRemove",
        "findOneAndRemove",
        "save",
    }
)


def _schema_fields(obj: ts.Node) -> list[JSON]:
    fields = []
    for pair in obj.named_children:
        if pair.type != "pair":
            continue
        name = text(pair.child_by_field_name("key")).strip("'\"")
        val = pair.child_by_field_name("value")
        if val is None:
            continue
        val = unwrap(val)
        field: JSON = {"name": name, "line": line(pair)}
        target = val
        if val.type == "array" and val.named_children:
            field["list"] = True
            target = unwrap(val.named_children[0])
        if target.type == "object":
            for p in target.named_children:
                if p.type != "pair":
                    continue
                key = text(p.child_by_field_name("key")).strip("'\"")
                pv = p.child_by_field_name("value")
                if key == "type" and pv is not None:
                    field["type"] = text(pv)
                elif key == "ref" and pv is not None and string_value(pv):
                    field["ref"] = string_value(pv)
                elif key == "required" and pv is not None and text(pv) == "false":
                    field["optional"] = True
            field.setdefault("type", "Object")
        else:
            field["type"] = text(target)
        fields.append(field)
    return fields


def extract(rel_path: str, tree: ts.Tree, fn_keys: FnKeys) -> JSON | None:
    del fn_keys
    models, schemas = [], {}
    for call in walk_calls(tree.root_node):
        c = callee(call)
        if not c:
            continue
        args = call_args(call)
        if call.type == "call_expression" and c[-1] == "model" and args:
            name = string_value(args[0])
            if not name:
                continue
            entry: JSON = {"name": name, "fn": c, "line": line(call), "end": end_line(call)}
            bind = binding_of(call)
            if bind:
                entry["bind"] = bind
            if len(args) > 1:
                schema = unwrap(args[1])
                if schema.type == "identifier":
                    entry["schema"] = text(schema)
                elif schema.type == "new_expression":
                    inner = call_args(schema)
                    if inner and unwrap(inner[0]).type == "object":
                        entry["fields"] = _schema_fields(unwrap(inner[0]))
            if len(args) > 2 and string_value(args[2]):
                entry["collection"] = string_value(args[2])
            models.append(entry)
        elif call.type == "new_expression" and c[-1] == "Schema" and args:
            bind = binding_of(call)
            obj = unwrap(args[0])
            if bind and obj.type == "object":
                schemas[bind] = {"fn": c, "line": line(call), "fields": _schema_fields(obj)}
    out: JSON = {}
    if models:
        out["models"] = models
    if schemas:
        out["schemas"] = schemas
    return out or None


def _from_mongoose(ctx: LinkContext, file: str, chain: list[str]) -> bool:
    target = ctx.project.resolve(file, chain[0])
    return isinstance(target, Pkg) and target.package == "mongoose"


def link(ctx: LinkContext) -> None:
    project = ctx.project
    bindings: dict[tuple[str, str], str] = {}
    defs: list[tuple[str, JSON]] = []
    for file, raw in project.raw.items():
        for m in raw.get("mongoose", {}).get("models", []):
            if _from_mongoose(ctx, file, m["fn"]):
                defs.append((file, m))
                if m.get("bind"):
                    bindings[(file, m["bind"])] = m["name"]
    if not defs:
        return
    ctx.adapters.append("mongoose")
    names = {m["name"] for _, m in defs}
    for file, m in defs:
        fields = m.get("fields")
        if fields is None and m.get("schema"):
            target = project.resolve(file, m["schema"])
            if isinstance(target, Sym):
                schema = project.raw[target.file].get("mongoose", {}).get("schemas", {})
                fields = schema.get(target.name, {}).get("fields")
        fields = fields or []
        attrs: JSON = {
            "tableName": m.get("collection") or m["name"].lower() + "s",
            "fields": [
                {
                    "name": f["name"],
                    "type": f.get("ref") or f.get("type", "Mixed"),
                    **({"isList": True} if f.get("list") else {}),
                    **({"isOptional": True} if f.get("optional") else {}),
                    **({"isRelation": True} if f.get("ref") in names else {}),
                }
                for f in fields
            ],
            "orm": "mongoose",
        }
        mid = f"model:{m['name']}"
        ctx.node(mid, "model", m["name"], [ctx.ev(file, m["line"], m["end"])], attrs)
        schema_file = file
        if m.get("schema"):
            target = project.resolve(file, m["schema"])
            if isinstance(target, Sym):
                schema_file = target.file
        for f in fields:
            if f.get("ref") in names and f["ref"] != m["name"]:
                ctx.edge(
                    "relates",
                    mid,
                    f"model:{f['ref']}",
                    [ctx.ev(schema_file, f["line"])],
                    {"relationField": f["name"]},
                )

    def model_for(file: str, scope: str, recv: list[str]) -> tuple[str, bool] | None:
        """(model name, via an instance) for a call receiver."""
        if len(recv) == 1:
            local = project.local_binding(file, scope, recv[0])
            if local is not None and local.get("new") and len(local["new"]) == 1:
                t = project.resolve(file, local["new"][0])
                if isinstance(t, Sym) and (t.file, t.name) in bindings:
                    return bindings[(t.file, t.name)], True
                return None
            t = project.resolve(file, recv[0])
            if isinstance(t, Sym) and (t.file, t.name) in bindings:
                return bindings[(t.file, t.name)], False
        if len(recv) == 2 and recv[0] == "this":
            fld = project.field(file, scope, recv[1]) or {}
            arg = project.generic_arg(fld.get("type"))
            if arg is not None and fld.get("type", "").startswith("Model<") and arg in names:
                return arg, False
        return None

    def classify(ctx: LinkContext, file: str, scope: str, call: JSON) -> Fact | None:
        c = call["c"]
        op = c[-1]
        if len(c) < 2 or (op not in READ_OPS and op not in WRITE_OPS):
            return None
        hit = model_for(file, scope, c[:-1])
        if hit is None:
            return None
        model, instance = hit
        if instance != (op == "save"):
            return None  # `.save()` only on instances; statics only on the model
        kind = "reads" if op in READ_OPS else "writes"
        ev = ctx.ev(file, call["l"], call["e"])
        return (kind, f"model:{model}", ev, {"operation": op}, "extracted", 1.0)

    ctx.classifiers.append(classify)
