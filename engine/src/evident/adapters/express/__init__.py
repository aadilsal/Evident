"""Express adapter: app/router instances, METHOD registrations, `use` mounts and middleware.

Counting rules: docs/labelling-guide.md (Routes). Full paths come from resolving every mount
prefix up to an `express()` app; routers never reached from an app keep their local path and are
marked inferred.
"""

from __future__ import annotations

import posixpath
from dataclasses import dataclass, field
from typing import Any

import tree_sitter as ts

from evident.adapters._js import args_of, describe, enclosing_scope, load_query
from evident.link import AUTH_RE, FnKey, LinkContext, Ns, Pkg, Project, Sym
from evident.syntax import captures, chain, end_line, line, text, unwrap
from evident.universal.js import MODULE, FnKeys

JSON = dict[str, Any]
METHODS = frozenset({"get", "post", "put", "patch", "delete", "del", "all", "head", "options"})
CAPTURED = METHODS | {"use", "route", "register", "addHook"}  # route/register/addHook: Fastify
UNMOUNTED_CONFIDENCE = 0.5
DYNAMIC_CONFIDENCE = 0.4


def extract(rel_path: str, tree: ts.Tree, fn_keys: FnKeys) -> JSON | None:
    q = load_query(__name__, "routes.scm", rel_path)
    if q is None:
        return None
    calls = []
    for _, caps in captures(q, tree.root_node):
        call, recv, args = caps["call"][0], caps["recv"][0], caps["args"][0]
        if text(caps["method"][0]) not in CAPTURED:
            continue
        entry: JSON = {
            "m": text(caps["method"][0]),
            "l": line(call),
            "e": end_line(call),
            "args": args_of(args, fn_keys),
            "s": enclosing_scope(call, fn_keys),
        }
        r = unwrap(recv)
        if r.type == "call_expression":
            # router.route('/x').get(a).post(b): walk down to the .route(path) call.
            while r.type == "call_expression":
                fn = r.child_by_field_name("function")
                if fn is None or fn.type != "member_expression":
                    break
                prop = text(fn.child_by_field_name("property"))
                obj = fn.child_by_field_name("object")
                if prop == "route" and obj is not None:
                    route_args = r.child_by_field_name("arguments")
                    first = route_args.named_children if route_args is not None else []
                    entry["recv"] = chain(obj)
                    entry["path"] = describe(first[0], fn_keys) if first else {"k": "other"}
                    break
                if prop not in METHODS or obj is None:
                    break
                r = unwrap(obj)
            if "path" not in entry or not entry.get("recv"):
                continue
        else:
            c = chain(r)
            if not c:
                continue
            entry["recv"] = c
        calls.append(entry)
    return {"calls": calls} if calls else None


# --- linking ------------------------------------------------------------------


RKey = tuple[str, str, str]  # (file, scope, binding): module-level or in a factory


@dataclass
class Route:
    file: str
    method: str
    path: JSON
    handler: JSON | None
    mws: list[tuple[str, JSON, int]]
    line: int
    end: int


@dataclass
class _Router:
    kind: str
    routes: list[Route] = field(default_factory=list)
    uses: list[tuple[str | None, list[tuple[str, JSON, int]], int]] = field(default_factory=list)
    mounts: list[tuple[str | None, RKey, list[tuple[str, JSON, int]], int]] = field(
        default_factory=list
    )


def _router_kind(project: Project, file: str, callee: list[str] | None) -> str | None:
    if not callee:
        return None
    head = project.resolve(file, callee[0])
    if not isinstance(head, Pkg) or head.package != "express":
        return None
    if len(callee) == 1:
        if head.imported in ("default", "*"):
            return "app"
        if head.imported == "Router":
            return "router"
    if len(callee) == 2 and callee[1] == "Router" and head.imported in ("default", "*"):
        return "router"
    return None


def _flatten(args: list[JSON]) -> list[JSON]:
    out: list[JSON] = []
    for a in args:
        out.extend(_flatten(a["items"]) if a["k"] == "array" else [a])
    return out


def _lookup(
    project: Project, file: str, scope: str, name: str, routers: dict[RKey, _Router]
) -> RKey | None:
    """A binding seen from a scope: its own locals, then enclosing callbacks, then the module."""
    scopes = project.js[file]["scopes"]
    cur: str | None = scope
    while cur is not None and cur != MODULE:
        if (file, cur, name) in routers:
            return (file, cur, name)
        cur = scopes.get(cur, {}).get("parent")
    target = project.resolve(file, name)
    if isinstance(target, Sym) and (target.file, MODULE, target.name) in routers:
        return (target.file, MODULE, target.name)
    return None


def _router_ref(
    project: Project, file: str, scope: str, arg: JSON, routers: dict[RKey, _Router]
) -> RKey | None:
    target: object = None
    k = arg["k"]
    if k == "id":
        return _lookup(project, file, scope, arg["name"], routers)
    if k == "require":
        res = project.resolve_spec(file, arg["spec"])
        if res is not None and res[0] == "file":
            target = project.resolve_export(res[1], "default")
    elif k == "member" and len(arg["chain"]) == 2:
        ns = project.resolve(file, arg["chain"][0])
        if isinstance(ns, Ns):
            target = project.resolve_export(ns.file, arg["chain"][1])
    elif k == "call" and arg.get("chain"):
        # A router factory: createUsersRouter(deps) -> the router its body returns.
        c = arg["chain"]
        fn: FnKey | None = None
        if len(c) == 1:
            fn = project.scope_of(project.resolve(file, c[0]))
        elif len(c) == 2:
            fn = project.member_scope(file, c[0], c[1])
        if fn is not None:
            for ret in project.js[fn[0]]["scopes"][fn[1]].get("returns", []):
                hit = _lookup(project, fn[0], fn[1], ret, routers)
                if hit is not None:
                    return hit
    if isinstance(target, Sym) and (target.file, MODULE, target.name) in routers:
        return (target.file, MODULE, target.name)
    return None


def _join(base: str, path: str) -> str:
    joined = posixpath.normpath("/" + "/".join(p.strip("/") for p in (base, path) if p.strip("/")))
    return "/" if joined in ("/", ".", "//") else joined.rstrip("/")


def _applies(prefix: str | None, path: str | None) -> bool:
    if not prefix or prefix == "/" or path is None:
        return True
    p, pre = _join("", path), _join("", prefix)
    return p == pre or p.startswith(pre + "/")


def fn_target(project: Project, file: str, desc: JSON) -> FnKey | None:
    """The function a handler argument refers to, unwrapping `asyncHandler(fn)` style wrappers."""
    k = desc["k"]
    if k == "fn":
        return (file, desc["scope"]) if desc.get("scope") else None
    if k == "id":
        return project.scope_of(project.resolve(file, desc["name"]))
    if k == "member" and len(desc["chain"]) == 2:
        return project.member_scope(file, *desc["chain"])
    if k == "call":
        for inner in reversed(desc.get("args", [])):
            hit = fn_target(project, file, inner)
            if hit is not None:
                return hit
    return None


def middleware_id(
    ctx: LinkContext, file: str, desc: JSON, at_line: int, framework: str
) -> str | None:
    """A middleware node for one `use`/route argument; library middleware only if auth-like."""
    project = ctx.project
    key: FnKey | None = None
    name: str | None = None
    k = desc["k"]
    if k == "fn":
        key = (file, desc["scope"]) if desc.get("scope") else None
        name = "anonymous middleware"
    elif k == "id":
        name = desc["name"]
        key = project.scope_of(project.resolve(file, name))
    elif k == "member":
        name = ".".join(desc["chain"])
        if len(desc["chain"]) == 2:
            key = project.member_scope(file, *desc["chain"])
    elif k == "call" and desc.get("chain"):
        c = desc["chain"]
        name = ".".join(c)
        if len(c) == 1:
            key = project.scope_of(project.resolve(file, c[0]))
        elif len(c) == 2:
            key = project.member_scope(file, c[0], c[1])
    if key is not None:
        ctx.fn_meta.setdefault(key, {"framework": framework, "name": key[1]})
        return ctx.mark(key, "middleware")
    if name and AUTH_RE.search(name):
        mid = f"middleware:{file}#{name}"
        return ctx.node(
            mid,
            "middleware",
            name,
            [ctx.ev(file, at_line)],
            {"file": file, "framework": framework, "name": name},
            confidence=0.8,
        )
    return None


def link(ctx: LinkContext) -> None:
    project = ctx.project
    routers: dict[RKey, _Router] = {}
    for file, s in project.js.items():
        for name, var in s["vars"].items():
            kind = _router_kind(project, file, var.get("callee"))
            if kind:
                routers[(file, MODULE, name)] = _Router(kind)
        for scope, info in s["scopes"].items():
            for name, local in info.get("locals", {}).items():
                kind = _router_kind(project, file, local.get("callee"))
                if kind:
                    routers[(file, scope, name)] = _Router(kind)
    if not routers:
        return
    ctx.adapters.append("express")

    for file, raw in project.raw.items():
        for c in raw.get("express", {}).get("calls", []):
            recv = c["recv"]
            if len(recv) != 1 or c["m"] not in METHODS | {"use"}:
                continue
            target = _lookup(project, file, c.get("s", MODULE), recv[0], routers)
            if target is None:
                continue
            r = routers[target]
            args = _flatten(c["args"])
            if c["m"] == "use":
                prefix = None
                if args and args[0]["k"] == "str":
                    prefix, args = args[0]["value"], args[1:]
                pending: list[tuple[str, JSON, int]] = []
                mounted = False
                for a in args:
                    child = _router_ref(project, file, c.get("s", MODULE), a, routers)
                    if child is not None:
                        r.mounts.append((prefix, child, list(pending), c["l"]))
                        mounted = True
                    else:
                        pending.append((file, a, c["l"]))
                if not mounted and pending:
                    r.uses.append((prefix, pending, c["l"]))
                continue
            if "path" in c:  # router.route(path).METHOD(...handlers)
                path, handlers = c["path"], args
            else:
                if len(args) < 2:
                    continue  # app.get('setting') is a getter, not a route
                path, handlers = args[0], args[1:]
            if not handlers:
                continue
            r.routes.append(
                Route(
                    file,
                    c["m"],
                    path,
                    handlers[-1],
                    [(file, h, c["l"]) for h in handlers[:-1]],
                    c["l"],
                    c["e"],
                )
            )

    reached: set[RKey] = set()

    def walk(
        sym: RKey,
        base: str,
        inherited: list[tuple[str, JSON, int]],
        seen: frozenset[RKey],
        inferred: bool,
    ) -> None:
        reached.add(sym)
        r = routers[sym]
        for route in sorted(r.routes, key=lambda x: x.line):
            local = route.path.get("value") if route.path["k"] == "str" else None
            mws = [*inherited]
            for prefix, use_mws, at in r.uses:
                if at < route.line and _applies(prefix, local):
                    mws.extend(use_mws)
            mws.extend(route.mws)
            emit_route(ctx, route, base, local, mws, inferred)
        for prefix, child, mount_mws, at in r.mounts:
            if child in seen:
                continue
            mws = [*inherited]
            for use_prefix, use_mws, use_at in r.uses:
                if use_at < at and _applies(use_prefix, prefix):
                    mws.extend(use_mws)
            mws.extend(mount_mws)
            walk(child, _join(base, prefix or ""), mws, seen | {child}, inferred)

    for sym, r in sorted(routers.items()):
        if r.kind == "app":
            walk(sym, "", [], frozenset({sym}), False)
    for sym, r in sorted(routers.items()):
        if sym not in reached and (r.routes or r.mounts):
            walk(sym, "", [], frozenset({sym}), True)


def emit_route(
    ctx: LinkContext,
    route: Route,
    base: str,
    local: str | None,
    mws: list[tuple[str, JSON, int]],
    inferred: bool,
    framework: str = "express",
) -> None:
    method = "DELETE" if route.method.lower() in ("delete", "del") else route.method.upper()
    dynamic = local is None
    path = _join(base, "/*" if dynamic else local or "")
    route_id = f"route:{method} {path}"
    confidence = DYNAMIC_CONFIDENCE if dynamic else UNMOUNTED_CONFIDENCE if inferred else 1.0
    source = "inferred" if dynamic or inferred else "extracted"
    attrs: JSON = {"method": method, "path": path, "framework": framework, "kind": "api"}
    if dynamic:
        attrs["dynamic"] = True
    key = fn_target(ctx.project, route.file, route.handler) if route.handler else None
    if key is not None:
        attrs["handlerRef"] = ctx.mark(key, "handler")
    ctx.node(
        route_id,
        "route",
        f"{method} {path}",
        [ctx.ev(route.file, route.line, route.end)],
        attrs,
        source=source,
        confidence=confidence,
    )
    if key is not None:
        ctx.edge("handles", route_id, attrs["handlerRef"], [ctx.ev(route.file, route.line)])
    for file, desc, at in mws:
        mid = middleware_id(ctx, file, desc, at, framework)
        if mid is not None:
            ctx.edge("guards", mid, route_id, [ctx.ev(file, at)])
