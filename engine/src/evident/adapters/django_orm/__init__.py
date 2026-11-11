"""Django ORM adapter: `models.Model` subclasses (table from `Meta.db_table` or
`<app>_<model>`), relation fields, and reads/writes through `Model.objects.<op>()`,
`get_object_or_404(Model)` and instance `.save()`/`.delete()`.
Counting rules: docs/labelling-guide.md (Django ORM).
"""

from __future__ import annotations

import posixpath
from typing import Any

from evident.link import Fact, LinkContext, Pkg, Project, Sym

JSON = dict[str, Any]
READ_OPS = frozenset(
    {
        "all",
        "filter",
        "get",
        "exclude",
        "first",
        "last",
        "count",
        "exists",
        "aggregate",
        "annotate",
        "values",
        "values_list",
        "order_by",
        "select_related",
        "prefetch_related",
        "in_bulk",
        "iterator",
        "latest",
        "earliest",
        "distinct",
        "only",
        "defer",
        "raw",
    }
)
WRITE_OPS = frozenset(
    {
        "create",
        "bulk_create",
        "update",
        "delete",
        "get_or_create",
        "update_or_create",
        "bulk_update",
    }
)
RELATIONS = frozenset({"ForeignKey", "OneToOneField", "ManyToManyField"})
INSTANCE_FROM = frozenset({"get", "create", "get_or_create", "first", "last", "latest", "earliest"})
SHORTCUTS = frozenset({"get_object_or_404", "get_list_or_404"})


def _app_label(file: str) -> str:
    parts = file.split("/")
    if parts[-1] == "models.py":
        return parts[-2] if len(parts) > 1 else ""
    if len(parts) > 2 and parts[-2] == "models":
        return parts[-3]
    return posixpath.basename(posixpath.dirname(file))


def _is_django_model_base(project: Project, file: str, base: str) -> bool:
    chain = base.split("(")[0].split(".")
    target = project.resolve(file, chain[0])
    return isinstance(target, Pkg) and target.package.startswith("django") and chain[-1] == "Model"


def link(ctx: LinkContext) -> None:
    project = ctx.project
    models: dict[tuple[str, str], JSON] = {}
    changed = True
    while changed:  # fixpoint: subclasses of first-party models are models too
        changed = False
        for file, s in project.js.items():
            if not file.endswith(".py"):
                continue
            for cls, info in s["classes"].items():
                if (file, cls) in models:
                    continue
                for base in info.get("bases", []):
                    target = project.resolve(file, base.split(".")[0])
                    parent = (target.file, target.name) if isinstance(target, Sym) else None
                    if _is_django_model_base(project, file, base) or (parent in models):
                        models[(file, cls)] = info
                        changed = True
                        break
    concrete = {
        k: v
        for k, v in models.items()
        if (v.get("meta", {}).get("abstract") or {}).get("value") is not True
    }
    if not concrete:
        return
    ctx.adapters.append("django-orm")
    names = {cls for _, cls in concrete}
    for (file, cls), info in sorted(concrete.items()):
        db_table = (info.get("meta", {}).get("db_table") or {}).get("value")
        table = db_table or f"{_app_label(file)}_{cls.lower()}"
        fields, rels = [], []
        for fname, f in info.get("fields", {}).items():
            value = f.get("value", {})
            kind = (value.get("chain") or [""])[-1] if value.get("k") == "call" else ""
            if not (kind.endswith("Field") or kind in RELATIONS):
                continue
            entry: JSON = {"name": fname, "type": kind}
            if kind in RELATIONS and value.get("args"):
                target = value["args"][0]
                ref = target.get("value") or target.get("name") or (target.get("chain") or [""])[-1]
                ref = cls if ref == "self" else str(ref).split(".")[-1]
                if ref == "AUTH_USER_MODEL":
                    ref = "User"
                if ref in names:
                    entry["type"], entry["isRelation"] = ref, True
                    rels.append((fname, ref, f["line"]))
                if kind == "ManyToManyField":
                    entry["isList"] = True
            if (value.get("kw", {}).get("primary_key") or {}).get("value") is True:
                entry["isId"] = True
            fields.append(entry)
        ctx.node(
            f"model:{cls}",
            "model",
            cls,
            [ctx.ev(file, info["line"], info["end"])],
            {"tableName": table, "fields": fields, "orm": "django-orm"},
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

    def model_of(file: str, name: str) -> str | None:
        target = project.resolve(file, name)
        if isinstance(target, Sym) and (target.file, target.name) in concrete:
            return target.name
        return None

    def classify(ctx: LinkContext, file: str, scope: str, call: JSON) -> Fact | None:
        if not file.endswith(".py"):
            return None
        c, args = call["c"], call.get("a", [])
        ev = ctx.ev(file, call["l"], call["e"])
        if len(c) == 3 and c[1] == "objects" and (c[2] in READ_OPS or c[2] in WRITE_OPS):
            model = model_of(file, c[0])
            if model is not None:
                kind = "writes" if c[2] in WRITE_OPS else "reads"
                return (kind, f"model:{model}", ev, {"operation": c[2]}, "extracted", 1.0)
        if c and c[-1] in SHORTCUTS and len(c) == 1 and args and args[0].get("k") == "id":
            model = model_of(file, args[0]["name"])
            if model is not None:
                return ("reads", f"model:{model}", ev, {"operation": c[0]}, "extracted", 1.0)
        if len(c) == 2 and c[1] in ("save", "delete"):
            if c[0] == "this":
                cls = project.class_of_scope(file, scope)
                if cls is not None and (file, cls) in concrete:
                    return ("writes", f"model:{cls}", ev, {"operation": c[1]}, "extracted", 1.0)
                return None
            local = project.local_binding(file, scope, c[0])
            callee = (local or {}).get("callee") or []
            model = model_of(file, callee[0]) if callee else None
            if model is not None and (
                len(callee) == 1 or (len(callee) == 3 and callee[2] in INSTANCE_FROM)
            ):
                return ("writes", f"model:{model}", ev, {"operation": c[1]}, "extracted", 1.0)
        return None

    ctx.classifiers.append(classify)
