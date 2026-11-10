"""Fastify adapter: `Fastify()` instances, `register(plugin, { prefix })` encapsulation,
`METHOD(path, [opts], handler)`, `route({ method, url, handler })`, and auth hooks
(`addHook('onRequest', â€¦)`, route `preHandler`/`onRequest`).

Reuses the Express extractor's captured member calls. Counting rules:
docs/labelling-guide.md (Fastify).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from evident.adapters.express import METHODS, Route, _join, emit_route, fn_target
from evident.link import FnKey, LinkContext, Pkg, Project, Sym
from evident.universal.js import MODULE

JSON = dict[str, Any]
FRAMEWORK = "fastify"
HOOKS = frozenset({"onRequest", "preParsing", "preValidation", "preHandler"})
GUARD_OPTS = ("onRequest", "preValidation", "preHandler")
IKey = tuple[str, str, str]  # (file, scope, binding)


@dataclass
class _Instance:
    root: bool
    routes: list[Route] = field(default_factory=list)
    hooks: list[tuple[str, JSON, int]] = field(default_factory=list)
    children: list[tuple[str, IKey]] = field(default_factory=list)


def _is_fastify(project: Project, file: str, callee: list[str] | None) -> bool:
    if not callee or len(callee) != 1:
        return False
    target = project.resolve(file, callee[0])
    return isinstance(target, Pkg) and target.package == "fastify"


def _flat(desc: JSON | None) -> list[JSON]:
    if desc is None:
        return []
    return [i for d in desc["items"] for i in _flat(d)] if desc["k"] == "array" else [desc]


def _plugin_key(project: Project, file: str, desc: JSON) -> IKey | None:
    key: FnKey | None = None
    if desc["k"] == "require":
        res = project.resolve_spec(file, desc["spec"])
        if res is not None and res[0] == "file":
            key = project.scope_of(project.resolve_export(res[1], "default"))
    else:
        key = fn_target(project, file, desc)
    if key is None:
        return None
    params = project.js[key[0]]["scopes"][key[1]].get("params", [])
    return (key[0], key[1], params[0]) if params and params[0] else None


def link(ctx: LinkContext) -> None:
    project = ctx.project
    instances: dict[IKey, _Instance] = {}
    for file, s in project.js.items():
        for name, var in s["vars"].items():
            if _is_fastify(project, file, var.get("callee")):
                instances[(file, MODULE, name)] = _Instance(root=True)
        for scope, info in s["scopes"].items():
            for name, local in info.get("locals", {}).items():
                if _is_fastify(project, file, local.get("callee")):
                    instances[(file, scope, name)] = _Instance(root=True)
    if not instances:
        return

    def lookup(file: str, scope: str, name: str) -> IKey | None:
        scopes = project.js[file]["scopes"]
        cur: str | None = scope
        while cur is not None and cur != MODULE:
            if (file, cur, name) in instances:
                return (file, cur, name)
            params = scopes.get(cur, {}).get("params", [])
            if params and params[0] == name:  # plugin body: `async (fastify, opts) => {…}`
                instances.setdefault((file, cur, name), _Instance(root=False))
                return (file, cur, name)
            cur = scopes.get(cur, {}).get("parent")
        target = project.resolve(file, name)
        if isinstance(target, Sym) and (target.file, MODULE, target.name) in instances:
            return (target.file, MODULE, target.name)
        return None

    for file, raw in sorted(project.raw.items()):
        for c in raw.get("express", {}).get("calls", []):
            if len(c["recv"]) != 1:
                continue
            key = lookup(file, c.get("s", MODULE), c["recv"][0])
            if key is None:
                continue
            inst = instances[key]
            args, m = c["args"], c["m"]
            if m in METHODS and len(args) >= 2 and args[0]["k"] == "str":
                opts = args[1] if len(args) > 2 and args[1]["k"] == "obj" else None
                mws = [
                    (file, d, c["l"])
                    for o in GUARD_OPTS
                    for d in _flat((opts or {}).get("props", {}).get(o))
                ]
                inst.routes.append(Route(file, m, args[0], args[-1], mws, c["l"], c["e"]))
            elif m == "route" and args and args[0]["k"] == "obj":
                props = args[0]["props"]
                url, handler = props.get("url") or props.get("path"), props.get("handler")
                if url is None or handler is None:
                    continue
                mws = [(file, d, c["l"]) for o in GUARD_OPTS for d in _flat(props.get(o))]
                for verb in _flat(props.get("method")):
                    if verb["k"] == "str" and verb["value"].lower() in METHODS:
                        inst.routes.append(
                            Route(file, verb["value"].lower(), url, handler, mws, c["l"], c["e"])
                        )
            elif m == "register" and args:
                child = _plugin_key(project, file, args[0])
                if child is None:
                    continue
                instances.setdefault(child, _Instance(root=False))
                prefix = ""
                if len(args) > 1 and args[1]["k"] == "obj":
                    p = args[1]["props"].get("prefix")
                    prefix = p["value"] if p is not None and p["k"] == "str" else ""
                inst.children.append((prefix, child))
            elif m == "addHook" and len(args) >= 2 and args[0].get("value") in HOOKS:
                inst.hooks.extend((file, d, c["l"]) for d in _flat(args[1]))

    reached: set[IKey] = set()

    def walk(
        key: IKey,
        base: str,
        inherited: list[tuple[str, JSON, int]],
        seen: frozenset[IKey],
        inferred: bool,
    ) -> None:
        reached.add(key)
        inst = instances[key]
        hooks = [*inherited, *inst.hooks]
        for route in sorted(inst.routes, key=lambda r: r.line):
            local = route.path.get("value") if route.path["k"] == "str" else None
            emit_route(ctx, route, base, local, [*hooks, *route.mws], inferred, FRAMEWORK)
        for prefix, child in inst.children:
            if child not in seen:
                walk(child, _join(base, prefix), hooks, seen | {child}, inferred)

    for key, inst in sorted(instances.items()):
        if inst.root:
            walk(key, "", [], frozenset({key}), False)
    for key, inst in sorted(instances.items()):
        if key not in reached and inst.routes:
            walk(key, "", [], frozenset({key}), True)
    if any(i.routes for i in instances.values()):
        ctx.adapters.append("fastify")
