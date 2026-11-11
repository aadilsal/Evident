"""SQLAlchemy adapter (and SQLModel): declarative models with `__tablename__`, `Column`/
`mapped_column`/`Field` columns, `relationship()` and `ForeignKey` relations, and reads/writes via
`session.query(M)`, `select/insert/update/delete(M)`, `session.get(M, id)` and
`session.add/merge/delete(M(...))`. Counting rules: docs/labelling-guide.md (SQLAlchemy).
"""

from __future__ import annotations

from typing import Any

from evident.link import Fact, LinkContext, Pkg, Project, Sym

JSON = dict[str, Any]
COLUMN_FNS = frozenset({"Column", "mapped_column", "Field", "relationship"})
STATEMENTS = {"select": "reads", "insert": "writes", "update": "writes", "delete": "writes"}
SESSION_WRITES = frozenset({"add", "merge", "delete"})
PACKAGES = ("sqlalchemy", "sqlmodel", "flask_sqlalchemy")


def _from_sqla(project: Project, file: str, name: str) -> bool:
    target = project.resolve(file, name)
    return isinstance(target, Pkg) and target.package.split(".")[0] in PACKAGES


def link(ctx: LinkContext) -> None:
    project = ctx.project
    py = {f: s for f, s in project.js.items() if f.endswith(".py")}
    bases: set[tuple[str, str]] = set()
    for f, s in py.items():
        for name, v in s["vars"].items():
            callee = v.get("callee") or []
            if callee and callee[-1] == "declarative_base" and _from_sqla(project, f, callee[0]):
                bases.add((f, name))
            if callee and callee[-1] == "SQLAlchemy" and _from_sqla(project, f, callee[0]):
                bases.add((f, f"{name}.Model"))  # flask_sqlalchemy: class User(db.Model)
        for cls, info in s["classes"].items():
            for base in info.get("bases", []):
                if base.split(".")[-1] == "DeclarativeBase" and _from_sqla(
                    project, f, base.split(".")[0]
                ):
                    bases.add((f, cls))

    def is_base(file: str, base: str) -> bool:
        if base.split(".")[-1] == "SQLModel" and _from_sqla(project, file, base.split(".")[0]):
            return True
        head, _, rest = base.partition(".")
        target = project.resolve(file, head)
        if isinstance(target, Sym):
            return (target.file, f"{target.name}.{rest}" if rest else target.name) in bases
        return False

    models: dict[tuple[str, str], JSON] = {}
    changed = True
    while changed:
        changed = False
        for f, s in py.items():
            for cls, info in s["classes"].items():
                if (f, cls) in models or (f, cls) in bases:
                    continue
                for base in info.get("bases", []):
                    target = project.resolve(f, base.split(".")[0])
                    parent = (target.file, target.name) if isinstance(target, Sym) else None
                    if is_base(f, base) or parent in models:
                        models[(f, cls)] = info
                        changed = True
                        break
    tables = {}
    concrete = {}
    for (f, cls), info in models.items():
        tname = (info.get("fields", {}).get("__tablename__", {}).get("value") or {}).get("value")
        sqlmodel_table = info.get("baseKw", {}).get("table") == "True"
        if tname or sqlmodel_table or any("Model" in b for b in info.get("bases", [])):
            concrete[(f, cls)] = info
            tables[str(tname or cls.lower())] = cls
    if not concrete:
        return
    ctx.adapters.append("sqlalchemy")
    names = {cls for _, cls in concrete}
    for (file, cls), info in sorted(concrete.items()):
        tname = (info.get("fields", {}).get("__tablename__", {}).get("value") or {}).get(
            "value"
        ) or cls.lower()
        fields, rels = [], []
        for fname, fld in info.get("fields", {}).items():
            value = fld.get("value", {})
            kind = (value.get("chain") or [""])[-1] if value.get("k") == "call" else ""
            if kind not in COLUMN_FNS:
                continue
            entry: JSON = {"name": fname, "type": fld.get("type") or kind}
            ref: str | None = None
            if kind == "relationship" and value.get("args"):
                a0 = value["args"][0]
                ref = a0.get("value") or a0.get("name")
                entry["isRelation"] = True
            for arg in value.get("args", []):
                if (
                    arg.get("k") == "call"
                    and (arg.get("chain") or [""])[-1] == "ForeignKey"
                    and arg.get("args")
                ):
                    fk = (arg["args"][0] or {}).get("value", "")
                    ref = tables.get(str(fk).split(".")[0]) or ref
            fk_kw = (value.get("kw", {}).get("foreign_key") or {}).get("value")
            if fk_kw:
                ref = tables.get(str(fk_kw).split(".")[0]) or ref
            if (value.get("kw", {}).get("primary_key") or {}).get("value") is True:
                entry["isId"] = True
            if ref in names:
                rels.append((fname, ref, fld["line"]))
            fields.append(entry)
        ctx.node(
            f"model:{cls}",
            "model",
            cls,
            [ctx.ev(file, info["line"], info["end"])],
            {"tableName": str(tname), "fields": fields, "orm": "sqlalchemy"},
        )
        for fname, ref, at in rels:
            if ref != cls:
                ctx.edge(
                    "relates",
                    f"model:{cls}",
                    f"model:{ref}",
                    [ctx.ev(file, at)],
                    {"relationField": fname},
                )

    def model_of(file: str, desc: JSON | None) -> str | None:
        if not desc or desc.get("k") != "id":
            return None
        target = project.resolve(file, desc["name"])
        if isinstance(target, Sym) and (target.file, target.name) in concrete:
            return target.name
        return None

    def classify(ctx: LinkContext, file: str, scope: str, call: JSON) -> Fact | None:
        if not file.endswith(".py"):
            return None
        c, args = call["c"], call.get("a", [])
        ev = ctx.ev(file, call["l"], call["e"])
        if len(c) == 3 and c[1] == "query":  # Flask-SQLAlchemy: Post.query.all()
            model = model_of(file, {"k": "id", "name": c[0]})
            if model:
                return ("reads", f"model:{model}", ev, {"operation": c[2]}, "extracted", 1.0)
        if not args:
            return None
        if c[-1] == "query" and len(c) >= 2:
            model = model_of(file, args[0])
            if model:
                return ("reads", f"model:{model}", ev, {"operation": "query"}, "extracted", 1.0)
        if len(c) == 1 and c[0] in STATEMENTS and _from_sqla(project, file, c[0]):
            model = model_of(file, args[0])
            if model:
                return (
                    STATEMENTS[c[0]],
                    f"model:{model}",
                    ev,
                    {"operation": c[0]},
                    "extracted",
                    1.0,
                )
        if len(c) >= 2 and c[-1] == "get" and len(args) >= 2:
            model = model_of(file, args[0])
            if model:
                return ("reads", f"model:{model}", ev, {"operation": "get"}, "extracted", 1.0)
        if len(c) >= 2 and c[-1] in SESSION_WRITES and args[0].get("k") == "id":
            local = project.local_binding(file, scope, args[0]["name"])
            callee = (local or {}).get("callee") or []
            # A constructed instance, or one loaded with Model.query.<get/first...>().
            loaded = len(callee) == 3 and callee[1] == "query"
            name = callee[0] if callee and (len(callee) == 1 or loaded) else None
            model = model_of(file, {"k": "id", "name": name}) if name else None
            if model:
                return ("writes", f"model:{model}", ev, {"operation": c[-1]}, "extracted", 1.0)
        return None

    ctx.classifiers.append(classify)
