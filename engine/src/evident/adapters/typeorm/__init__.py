"""TypeORM adapter: `@Entity` classes, column and relation decorators, and reads/writes through
repositories (`dataSource.getRepository(User)`, `@InjectRepository(User)` fields,
`Repository<User>` fields).

Counting rules: docs/labelling-guide.md (TypeORM).
"""

from __future__ import annotations

from typing import Any

import tree_sitter as ts

from evident.adapters._js import binding_of, call_args, enclosing_scope, walk_calls
from evident.link import Fact, LinkContext, Pkg, Sym
from evident.syntax import chain, end_line, line, text, unwrap
from evident.universal.js import FnKeys

JSON = dict[str, Any]
COLUMNS = frozenset(
    {
        "Column",
        "PrimaryColumn",
        "PrimaryGeneratedColumn",
        "CreateDateColumn",
        "UpdateDateColumn",
        "DeleteDateColumn",
        "VersionColumn",
        "ObjectIdColumn",
    }
)
RELATIONS = frozenset({"OneToMany", "ManyToOne", "OneToOne", "ManyToMany"})
READ_OPS = frozenset(
    {
        "find",
        "findOne",
        "findBy",
        "findOneBy",
        "findAndCount",
        "findAndCountBy",
        "findOneOrFail",
        "findOneByOrFail",
        "count",
        "countBy",
        "exist",
        "exists",
        "existsBy",
        "sum",
        "average",
        "minimum",
        "maximum",
    }
)
WRITE_OPS = frozenset(
    {
        "save",
        "insert",
        "update",
        "upsert",
        "delete",
        "remove",
        "softDelete",
        "softRemove",
        "restore",
        "increment",
        "decrement",
        "clear",
    }
)


def extract(rel_path: str, tree: ts.Tree, fn_keys: FnKeys) -> JSON | None:
    """Repository bindings and inline `x.getRepository(E).op()` calls."""
    repos, inline = [], []
    for call in walk_calls(tree.root_node):
        if call.type != "call_expression":
            continue
        fn = call.child_by_field_name("function")
        c = chain(fn)
        args = call_args(call)
        if c and c[-1] == "getRepository" and args and unwrap(args[0]).type == "identifier":
            entity = text(unwrap(args[0]))
            bind = binding_of(call)
            if bind:
                repos.append({"bind": bind, "entity": entity, "s": enclosing_scope(call, fn_keys)})
            continue
        if fn is not None and fn.type == "member_expression":
            obj = unwrap(fn.child_by_field_name("object") or fn)
            if (
                obj.type == "call_expression"
                and (chain(obj.child_by_field_name("function")) or [""])[-1] == "getRepository"
            ):
                inner = call_args(obj)
                if inner and unwrap(inner[0]).type == "identifier":
                    inline.append(
                        {
                            "entity": text(unwrap(inner[0])),
                            "op": text(fn.child_by_field_name("property")),
                            "l": line(call),
                            "e": end_line(call),
                            "s": enclosing_scope(call, fn_keys),
                        }
                    )
    out: JSON = {}
    if repos:
        out["repos"] = repos
    if inline:
        out["inline"] = inline
    return out or None


def _deco(decos: list[JSON], names: frozenset[str]) -> JSON | None:
    return next((d for d in decos if d["name"] in names), None)


def link(ctx: LinkContext) -> None:
    project = ctx.project
    entities: dict[tuple[str, str], JSON] = {}
    for file, s in project.js.items():
        for cls, info in s["classes"].items():
            entity = _deco(info.get("decorators", []), frozenset({"Entity"}))
            if entity is None:
                continue
            origin = project.resolve(file, "Entity")
            if isinstance(origin, Pkg) and origin.package == "typeorm":
                entities[(file, cls)] = {"info": info, "deco": entity}
    if not entities:
        return
    ctx.adapters.append("typeorm")
    names = {cls for _, cls in entities}
    for (file, cls), e in sorted(entities.items()):
        args = e["deco"]["args"]
        table = cls
        if args and args[0]["k"] == "str":
            table = args[0]["value"]
        elif args and args[0]["k"] == "obj" and args[0]["props"].get("name", {}).get("k") == "str":
            table = args[0]["props"]["name"]["value"]
        fields, relations = [], []
        for fname, f in e["info"].get("fields", {}).items():
            decos = f.get("decorators", [])
            col, rel = _deco(decos, COLUMNS), _deco(decos, RELATIONS)
            if col is None and rel is None:
                continue
            entry: JSON = {"name": fname, "type": (f.get("type") or "unknown").rstrip("[]")}
            if col is not None and col["name"].startswith("Primary"):
                entry["isId"] = True
            if rel is not None and rel["args"] and rel["args"][0]["k"] == "id":
                target = rel["args"][0]["name"]
                entry["type"] = target
                if target in names:
                    entry["isRelation"] = True
                    relations.append((fname, target, f["line"]))
                if rel["name"] in ("OneToMany", "ManyToMany"):
                    entry["isList"] = True
            fields.append(entry)
        ctx.node(
            f"model:{cls}",
            "model",
            cls,
            [ctx.ev(file, e["info"]["line"], e["info"]["end"])],
            {"tableName": table, "fields": fields, "orm": "typeorm"},
        )
        for fname, target, at in relations:
            if target != cls:
                ctx.edge(
                    "relates",
                    f"model:{cls}",
                    f"model:{target}",
                    [ctx.ev(file, at)],
                    {"relationField": fname},
                )

    def entity_name(file: str, name: str) -> str | None:
        target = project.resolve(file, name)
        if isinstance(target, Sym) and (target.file, target.name) in entities:
            return target.name
        return None

    repos: dict[tuple[str, str, str], str] = {}
    for file, raw in project.raw.items():
        typeorm = raw.get("typeorm", {})
        for r in typeorm.get("repos", []):
            ent = entity_name(file, r["entity"])
            if ent is not None:
                repos[(file, r["s"], r["bind"])] = ent
        for op in typeorm.get("inline", []):
            ent = entity_name(file, op["entity"])
            kind = "reads" if op["op"] in READ_OPS else "writes" if op["op"] in WRITE_OPS else None
            if ent is None or kind is None or op["s"] == "<module>":
                continue
            fact: Fact = (
                kind,
                f"model:{ent}",
                ctx.ev(file, op["l"], op["e"]),
                {"operation": op["op"]},
                "extracted",
                1.0,
            )
            ctx.access.setdefault((file, op["s"]), []).append(fact)

    def repo_entity(file: str, scope: str, recv: list[str]) -> str | None:
        if len(recv) == 1:
            cur: str | None = scope
            scopes = project.js[file]["scopes"]
            while cur is not None:
                if (file, cur, recv[0]) in repos:
                    return repos[(file, cur, recv[0])]
                cur = None if cur == "<module>" else scopes.get(cur, {}).get("parent", "<module>")
            target = project.resolve(file, recv[0])
            if isinstance(target, Sym):
                return repos.get((target.file, "<module>", target.name))
        if len(recv) == 2 and recv[0] == "this":
            fld = project.field(file, scope, recv[1]) or {}
            inject = _deco(fld.get("decorators", []), frozenset({"InjectRepository"}))
            if inject is not None and inject["args"] and inject["args"][0]["k"] == "id":
                return entity_name(file, inject["args"][0]["name"])
            if (fld.get("type") or "").startswith("Repository<"):
                arg = project.generic_arg(fld.get("type"))
                return entity_name(file, arg) if arg else None
        return None

    def classify(ctx: LinkContext, file: str, scope: str, call: JSON) -> Fact | None:
        c = call["c"]
        op = c[-1]
        kind = "reads" if op in READ_OPS else "writes" if op in WRITE_OPS else None
        if kind is None or len(c) < 2:
            return None
        ent = repo_entity(file, scope, c[:-1])
        if ent is None:
            return None
        ev = ctx.ev(file, call["l"], call["e"])
        return (kind, f"model:{ent}", ev, {"operation": op}, "extracted", 1.0)

    ctx.classifiers.append(classify)
