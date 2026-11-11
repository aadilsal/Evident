"""Helpers shared by the Python adapters (FastAPI, Flask, Django, Django ORM, SQLAlchemy)."""

from __future__ import annotations

import re
from typing import Any

from evident.link import AUTH_RE, FnKey, LinkContext, Ns, Pkg, Project, Sym

JSON = dict[str, Any]
_FASTAPI_PARAM = re.compile(r"\{(\w+)(?::path)?\}")
_FLASK_PARAM = re.compile(r"<(?:(\w+):)?(\w+)>")


def from_package(project: Project, file: str, chain: list[str] | None, package: str) -> Pkg | None:
    """The package binding a call chain starts from, if it's `package` (or a submodule)."""
    if not chain:
        return None
    target = project.resolve(file, chain[0])
    if isinstance(target, Pkg) and (
        target.package == package or target.package.startswith(package + ".")
    ):
        return target
    return None


def fastapi_path(path: str) -> str:
    """`/items/{item_id}` -> `/items/:item_id`; `{p:path}` -> `:p*`."""
    return _FASTAPI_PARAM.sub(
        lambda m: f":{m.group(1)}" + ("*" if ":path" in m.group(0) else ""), path
    )


def flask_path(path: str) -> str:
    """`/users/<int:user_id>` -> `/users/:user_id`; `<path:p>` -> `:p*`."""
    return _FLASK_PARAM.sub(
        lambda m: f":{m.group(2)}" + ("*" if m.group(1) == "path" else ""), path
    )


def join(*parts: str) -> str:
    joined = "/" + "/".join(p.strip("/") for p in parts if p and p.strip("/"))
    return joined.rstrip("/") or "/"


def fn_of(project: Project, file: str, desc: JSON) -> FnKey | None:
    """A function a descriptor names: `handler`, `views.handler`, `Depends(get_user)`."""
    k = desc.get("k")
    if k == "id":
        return project.scope_of(project.resolve(file, desc["name"]))
    if k == "member" and len(desc["chain"]) == 2:
        return project.member_scope(file, desc["chain"][0], desc["chain"][1])
    if k == "call" and desc.get("chain") in (["Depends"], ["Security"], ["fastapi", "Depends"]):
        args = desc.get("args") or []
        return fn_of(project, file, args[0]) if args else None
    return None


def class_of(project: Project, file: str, desc: JSON) -> Sym | None:
    """A first-party class a descriptor names (`UserView`, `views.UserView`)."""
    k = desc.get("k")
    target: object = None
    if k == "id":
        target = project.resolve(file, desc["name"])
    elif k == "member" and len(desc["chain"]) == 2:
        ns = project.resolve(file, desc["chain"][0])
        if isinstance(ns, Ns):
            target = project.resolve_export(ns.file, desc["chain"][1])
    if isinstance(target, Sym) and target.name in project.js[target.file]["classes"]:
        return target
    return None


def guard_node(
    ctx: LinkContext, file: str, desc_or_name: JSON | str, at: int, framework: str
) -> str | None:
    """A middleware node for a dependency / decorator / permission class.

    First-party functions become (role) middleware; library names only when they look like auth.
    """
    project = ctx.project
    if isinstance(desc_or_name, str):
        name, key = (
            desc_or_name,
            project.scope_of(project.resolve(file, desc_or_name.split(".")[0])),
        )
    else:
        key = fn_of(project, file, desc_or_name)
        chain = desc_or_name.get("chain") or [desc_or_name.get("name", "")]
        inner = (desc_or_name.get("args") or [{}])[0] if desc_or_name.get("k") == "call" else {}
        name = inner.get("name") or ".".join(c for c in chain if c) or ""
    if key is not None:
        ctx.fn_meta.setdefault(key, {"framework": framework, "name": key[1]})
        return ctx.mark(key, "middleware")
    if name and AUTH_RE.search(name):
        mid = f"middleware:{file}#{name}"
        attrs = {"file": file, "framework": framework, "name": name}
        return ctx.node(mid, "middleware", name, [ctx.ev(file, at)], attrs, confidence=0.8)
    return None


def emit_route(
    ctx: LinkContext,
    *,
    file: str,
    method: str,
    path: str,
    framework: str,
    start: int,
    end: int,
    handler: FnKey | None,
    guards: list[tuple[str, JSON | str, int]],
    inferred: bool = False,
    dynamic: bool = False,
) -> str:
    method = method.upper()
    route_id = f"route:{method} {path}"
    attrs: JSON = {"method": method, "path": path, "framework": framework, "kind": "api"}
    if dynamic:
        attrs["dynamic"] = True
    if handler is not None:
        attrs["handlerRef"] = ctx.mark(handler, "handler")
    source = "inferred" if inferred or dynamic else "extracted"
    conf = 0.4 if dynamic else 0.5 if inferred else 1.0
    ctx.node(
        route_id,
        "route",
        f"{method} {path}",
        [ctx.ev(file, start, end)],
        attrs,
        source=source,
        confidence=conf,
    )
    if handler is not None:
        ctx.edge("handles", route_id, attrs["handlerRef"], [ctx.ev(file, start)])
    for gfile, desc, at in guards:
        gid = guard_node(ctx, gfile, desc, at, framework)
        if gid is not None:
            ctx.edge("guards", gid, route_id, [ctx.ev(gfile, at)])
    return route_id


def deco_desc(deco: JSON) -> JSON:
    """A decorator as an argument descriptor, so guards resolve like any other reference."""
    chain = deco.get("chain") or []
    if len(chain) == 1:
        return {"k": "id", "name": chain[0]}
    return {"k": "member", "chain": chain} if chain else {"k": "other"}


def str_list(desc: JSON | None) -> list[str]:
    if not desc:
        return []
    if desc.get("k") == "str":
        return [str(desc["value"])]
    if desc.get("k") == "array":
        return [str(i["value"]) for i in desc["items"] if i.get("k") == "str"]
    return []
