"""Flask adapter: `Flask()`/`Blueprint()` instances, `@x.route` and `@x.get` views,
`add_url_rule`, `register_blueprint(url_prefix=...)`, decorator and `before_request` guards.
Counting rules: docs/labelling-guide.md (Flask).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from evident.adapters._py import (
    deco_desc,
    emit_route,
    flask_path,
    fn_of,
    from_package,
    join,
    str_list,
)
from evident.link import FnKey, LinkContext, Ns, Sym

JSON = dict[str, Any]
FRAMEWORK = "flask"
VERBS = frozenset({"get", "post", "put", "patch", "delete"})
Key = tuple[str, str]
Guard = tuple[str, JSON | str, int]


@dataclass
class _Inst:
    kind: str  # app | blueprint
    prefix: str = ""
    routes: list[tuple[list[str], str, FnKey | None, str, int, int, list[Guard]]] = field(
        default_factory=list
    )
    hooks: list[Guard] = field(default_factory=list)
    children: list[tuple[str, Key]] = field(default_factory=list)


def _kw_str(kw: JSON, name: str) -> str:
    v = kw.get(name) or {}
    return str(v.get("value", "")) if v.get("k") == "str" else ""


def link(ctx: LinkContext) -> None:
    project = ctx.project
    insts: dict[Key, _Inst] = {}
    for file, s in project.js.items():
        if not file.endswith(".py"):
            continue
        bindings = list(s["vars"].items())
        bindings += [
            (n, loc) for sc in s["scopes"].values() for n, loc in sc.get("locals", {}).items()
        ]
        for name, v in bindings:
            if from_package(project, file, v.get("callee"), "flask") is None:
                continue
            ctor = (v.get("callee") or [""])[-1]
            if ctor == "Flask":
                insts[(file, name)] = _Inst("app")
            elif ctor == "Blueprint":
                insts[(file, name)] = _Inst("blueprint", _kw_str(v.get("kw", {}), "url_prefix"))
    if not insts:
        return

    def inst_of(file: str, desc: JSON) -> Key | None:
        target: object = None
        if desc.get("k") == "id":
            target = project.resolve(file, desc["name"])
        elif desc.get("k") == "member" and len(desc["chain"]) == 2:
            ns = project.resolve(file, desc["chain"][0])
            if isinstance(ns, Ns):
                target = project.resolve_export(ns.file, desc["chain"][1])
        if isinstance(target, Sym) and (target.file, target.name) in insts:
            return (target.file, target.name)
        if desc.get("k") == "id" and (file, desc["name"]) in insts:
            return (file, desc["name"])
        return None

    for file, s in project.js.items():
        if not file.endswith(".py"):
            continue
        for scope, info in s["scopes"].items():
            decos = info.get("decorators", [])
            others: list[Guard] = []
            routes: list[tuple[Key, list[str], str, int]] = []
            for deco in decos:
                chain = deco.get("chain") or []
                key = inst_of(file, {"k": "id", "name": chain[0]}) if len(chain) == 2 else None
                if key is not None and chain[1] in ("route", *VERBS):
                    args, kw = deco.get("args", []), deco.get("kw", {})
                    if not args or args[0].get("k") != "str":
                        continue
                    methods = str_list(kw.get("methods")) if chain[1] == "route" else [chain[1]]
                    routes.append((key, methods or ["GET"], args[0]["value"], deco["line"]))
                elif key is not None and chain[1] in ("before_request", "before_app_request"):
                    insts[key].hooks.append((file, {"k": "id", "name": scope}, deco["line"]))
                else:
                    others.append((file, deco_desc(deco), deco["line"]))
            for key, methods, path, _at in routes:
                insts[key].routes.append(
                    (methods, path, (file, scope), file, info["line"], info["end"], others)
                )
            for call in info["calls"]:
                c = call["c"]
                if len(c) != 2:
                    continue
                parent = inst_of(file, {"k": "id", "name": c[0]})
                if parent is None:
                    continue
                args, kw = call.get("a", []), call.get("kw", {})
                if c[1] == "register_blueprint" and args:
                    child = inst_of(file, args[0])
                    if child is not None:
                        insts[parent].children.append((_kw_str(kw, "url_prefix"), child))
                elif c[1] == "add_url_rule" and args and args[0].get("k") == "str":
                    view = kw.get("view_func") or (args[2] if len(args) > 2 else None)
                    handler = fn_of(project, file, view) if view else None
                    methods = str_list(kw.get("methods")) or ["GET"]
                    insts[parent].routes.append(
                        (methods, args[0]["value"], handler, file, call["l"], call["e"], [])
                    )
                elif c[1] == "before_request" and args:
                    insts[parent].hooks.append((file, args[0], call["l"]))

    reached: set[Key] = set()

    def walk(
        key: Key, base: str, inherited: list[Guard], seen: frozenset[Key], inferred: bool
    ) -> None:
        reached.add(key)
        inst = insts[key]
        base = join(base, inst.prefix)
        hooks = [*inherited, *inst.hooks]
        for methods, path, handler, file, start, end, guards in inst.routes:
            for m in methods:
                emit_route(
                    ctx,
                    file=file,
                    method=m,
                    path=join(base, flask_path(path)),
                    framework=FRAMEWORK,
                    start=start,
                    end=end,
                    handler=handler,
                    guards=[*hooks, *guards],
                    inferred=inferred,
                )
        for prefix, child in inst.children:
            if child not in seen:
                walk(child, join(base, prefix), hooks, seen | {child}, inferred)

    for key, inst in sorted(insts.items()):
        if inst.kind == "app":
            walk(key, "", [], frozenset({key}), False)
    for key, inst in sorted(insts.items()):
        if key not in reached and inst.routes:
            walk(key, "", [], frozenset({key}), True)
    if any(i.routes for i in insts.values()):
        ctx.adapters.append("flask")
