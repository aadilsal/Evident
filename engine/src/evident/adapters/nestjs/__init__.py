"""NestJS adapter: `@Controller` classes, HTTP-method decorators, the global prefix, and guards
(`@UseGuards` on class or method, `APP_GUARD` providers, `app.useGlobalGuards`).

Handlers are controller methods; their calls into injected services resolve through
constructor parameter properties in the universal layer. Counting rules:
docs/labelling-guide.md (NestJS).
"""

from __future__ import annotations

import re
from typing import Any

import tree_sitter as ts

from evident.adapters._js import call_args, walk_calls
from evident.adapters.express import _join
from evident.link import FnKey, LinkContext, Pkg, Sym
from evident.syntax import chain, line, string_value, text, unwrap
from evident.universal.js import FnKeys

JSON = dict[str, Any]
FRAMEWORK = "nestjs"
HTTP = {
    "Get": "GET",
    "Post": "POST",
    "Put": "PUT",
    "Patch": "PATCH",
    "Delete": "DELETE",
    "All": "ALL",
    "Head": "HEAD",
    "Options": "OPTIONS",
}
_APP_GUARD = re.compile(r"provide\s*:\s*APP_GUARD\s*,\s*useClass\s*:\s*(\w+)")


def extract(rel_path: str, tree: ts.Tree, fn_keys: FnKeys) -> JSON | None:
    del fn_keys
    prefixes, guards = [], []
    for call in walk_calls(tree.root_node):
        fn = call.child_by_field_name("function")
        if call.type != "call_expression" or fn is None or fn.type != "member_expression":
            continue
        prop = text(fn.child_by_field_name("property"))
        args = call_args(call)
        if prop == "setGlobalPrefix" and args and string_value(args[0]) is not None:
            prefixes.append([string_value(args[0]), line(call)])
        elif prop == "useGlobalGuards":
            for a in args:
                a = unwrap(a)
                if a.type == "new_expression":
                    c = chain(a.child_by_field_name("constructor"))
                    if c and len(c) == 1:
                        guards.append([c[0], line(call)])
    source = text(tree.root_node)
    for m in _APP_GUARD.finditer(source):
        guards.append([m.group(1), source.count("\n", 0, m.start()) + 1])
    out: JSON = {}
    if prefixes:
        out["prefixes"] = prefixes
    if guards:
        out["guards"] = guards
    return out or None


def _path(args: list[JSON]) -> str | None:
    """Decorator path argument: 'users', ['a', 'b'] (first wins) or { path: 'users' }."""
    if not args:
        return ""
    a = args[0]
    if a["k"] == "str":
        return str(a["value"])
    if a["k"] == "array":
        first = next((i for i in a["items"] if i["k"] == "str"), None)
        return str(first["value"]) if first else None
    if a["k"] == "obj":
        p = a["props"].get("path")
        if p is None:
            return ""
        return str(p["value"]) if p["k"] == "str" else None
    return None


def _guard_id(ctx: LinkContext, file: str, desc: JSON, at: int) -> str | None:
    project = ctx.project
    name: str | None = None
    if desc["k"] == "id":
        name = desc["name"]
    elif desc["k"] == "call" and desc.get("chain"):
        name = desc["chain"][0]
    elif desc["k"] == "member":
        name = ".".join(desc["chain"])
    if not name:
        return None
    target = project.resolve(file, name.split(".")[0])
    if isinstance(target, Sym) and target.name in project.js[target.file]["classes"]:
        cls = project.js[target.file]["classes"][target.name]
        mid = f"middleware:{target.file}#{target.name}"
        ev = [ctx.ev(target.file, cls["line"], cls["end"])]
        attrs = {"file": target.file, "framework": FRAMEWORK, "name": target.name}
        return ctx.node(mid, "middleware", target.name, ev, attrs)
    mid = f"middleware:{file}#{name}"
    attrs = {"file": file, "framework": FRAMEWORK, "name": name}
    return ctx.node(mid, "middleware", name, [ctx.ev(file, at)], attrs, confidence=0.8)


def link(ctx: LinkContext) -> None:
    project = ctx.project
    prefix = ""
    global_guards: list[tuple[str, JSON, int]] = []
    for file, raw in sorted(project.raw.items()):
        nest = raw.get("nestjs", {})
        if nest.get("prefixes") and not prefix:
            prefix = str(nest["prefixes"][0][0])
        for name, at in nest.get("guards", []):
            global_guards.append((file, {"k": "id", "name": name}, at))
    found = False
    for file, s in sorted(project.js.items()):
        for cls, info in sorted(s["classes"].items()):
            ctrl = next((d for d in info.get("decorators", []) if d["name"] == "Controller"), None)
            if ctrl is None:
                continue
            origin = project.resolve(file, "Controller")
            if not (isinstance(origin, Pkg) and origin.package == "@nestjs/common"):
                continue
            base = _path(ctrl["args"])
            if base is None:
                continue
            class_guards = [
                (file, a, d["line"])
                for d in info.get("decorators", [])
                if d["name"] == "UseGuards"
                for a in d["args"]
            ]
            for method, m in sorted(info.get("methods", {}).items()):
                decos = m.get("decorators", [])
                verb = next((d for d in decos if d["name"] in HTTP), None)
                key: FnKey = (file, f"{cls}.{method}")
                if verb is None or key[1] not in s["scopes"]:
                    continue
                local = _path(verb["args"])
                dynamic = local is None
                path = _join(_join(prefix, base), "*" if dynamic else local or "")
                http = HTTP[verb["name"]]
                route_id = f"route:{http} {path}"
                attrs: JSON = {
                    "method": http,
                    "path": path,
                    "framework": FRAMEWORK,
                    "kind": "api",
                    "handlerRef": ctx.mark(key, "handler"),
                }
                if dynamic:
                    attrs["dynamic"] = True
                ev = ctx.ev(file, verb["line"], m["end"])
                ctx.node(
                    route_id,
                    "route",
                    f"{http} {path}",
                    [ev],
                    attrs,
                    source="inferred" if dynamic else "extracted",
                    confidence=0.4 if dynamic else 1.0,
                )
                ctx.edge("handles", route_id, attrs["handlerRef"], [ctx.ev(file, verb["line"])])
                method_guards = [
                    (file, a, d["line"])
                    for d in decos
                    if d["name"] == "UseGuards"
                    for a in d["args"]
                ]
                for gfile, desc, at in [*global_guards, *class_guards, *method_guards]:
                    gid = _guard_id(ctx, gfile, desc, at)
                    if gid is not None:
                        ctx.edge("guards", gid, route_id, [ctx.ev(gfile, at)])
                found = True
    if found:
        ctx.adapters.append("nestjs")
