"""Universal layer, link step: modules, imports, services, env vars and the function graph.

Runs after the adapters, which mark handlers and middleware. Functions become nodes when they
are reachable through calls from a handler/middleware, or touch a model, service or env var.
"""

from __future__ import annotations

import json
import posixpath
import re
from collections import deque
from functools import cache
from importlib.resources import files
from typing import Any

from evident.adapters.prisma import READ_OPS, WRITE_OPS
from evident.link import AUTH_RE, FnKey, LinkContext, Project, Sym, fn_ref, package_name
from evident.universal.js import MODULE

JSON = dict[str, Any]
_ANON = re.compile(r"^L\d+(@L\d+)?$")
PRISMA_PROVEN = 1.0
PRISMA_THIS = 0.8
PRISMA_GUESS = 0.7


@cache
def _catalogue() -> JSON:
    data: JSON = json.loads(files("evident.universal").joinpath("services.json").read_text("utf-8"))
    return data


def provider_for(package: str) -> str | None:
    pkgs: dict[str, str] = _catalogue()["packages"]
    if package in pkgs:
        return pkgs[package]
    return next((v for k, v in pkgs.items() if k.endswith("/") and package.startswith(k)), None)


def _service_node(ctx: LinkContext, provider: str, package: str, evidence: list[Any]) -> str:
    sid = f"service:{provider}"
    label = _catalogue()["labels"].get(provider, provider)
    ctx.node(sid, "service", label, evidence, {"provider": provider, "packages": [package]})
    pkgs = ctx.nodes[sid].attrs["packages"]
    if package not in pkgs:
        pkgs.append(package)
        pkgs.sort()
    return sid


def _workspace(project: Project, file: str) -> str | None:
    if len(project.packages) < 2:
        return None
    d = posixpath.dirname(file)
    while True:
        pkg = project.packages.get(d)
        if pkg is not None and isinstance(pkg.get("name"), str):
            return str(pkg["name"])
        if not d:
            return None
        d = posixpath.dirname(d)


def _local_ctor(project: Project, file: str, scope: str, name: str) -> list[str] | None:
    """`new C()` bound to a local in this scope or an enclosing callback's scope."""
    scopes = project.js[file]["scopes"]
    cur: str | None = scope
    while cur is not None and cur != MODULE:
        local = scopes.get(cur, {}).get("locals", {}).get(name)
        if local is not None:
            ctor: list[str] | None = local.get("new")
            return ctor
        cur = scopes.get(cur, {}).get("parent")
    return None


def _call_target(project: Project, file: str, scope: str, c: list[str]) -> FnKey | None:
    if len(c) == 1:
        return project.scope_of(project.resolve(file, c[0]))
    if len(c) == 2:
        if c[0] == "this" and "." in scope:
            key = f"{scope.split('.', 1)[0]}.{c[1]}"
            return (file, key) if key in project.js[file]["scopes"] else None
        ctor = _local_ctor(project, file, scope, c[0])
        if ctor and len(ctor) == 1:
            cls = project.resolve(file, ctor[0])
            if isinstance(cls, Sym) and f"{cls.name}.{c[1]}" in project.js[cls.file]["scopes"]:
                return (cls.file, f"{cls.name}.{c[1]}")
        return project.member_scope(file, c[0], c[1])
    return None


def _prisma_call(
    ctx: LinkContext, file: str, c: list[str]
) -> tuple[str, str, str, str, float] | None:
    """(edge type, model, op, source, confidence) for `<client>.<model>.<op>()`."""
    if len(c) < 3 or not ctx.models:
        return None
    op, model = c[-1], ctx.models.get(c[-2])
    if model is None:
        return None
    kind = "reads" if op in READ_OPS else "writes" if op in WRITE_OPS else None
    if kind is None:
        return None
    recv = c[:-2]
    if len(recv) == 1 and recv[0] != "this":
        taint = ctx.project.taint(file, recv[0])
        if any(t.imported == "PrismaClient" or t.package == "@prisma/client" for t in taint):
            return kind, model, op, "extracted", PRISMA_PROVEN
        return kind, model, op, "inferred", PRISMA_GUESS
    return kind, model, op, "inferred", PRISMA_THIS if recv[0] == "this" else PRISMA_GUESS


def build(ctx: LinkContext) -> None:
    project = ctx.project
    documented: set[str] = set()
    for raw in project.raw.values():
        documented.update(raw.get("envDoc", []))
    env_evidence: dict[str, list[Any]] = {}

    # Modules, imports and SDK services.
    for file in sorted(project.js):
        ctx.node(
            f"module:{file}",
            "module",
            file,
            [ctx.ev(file, 1)],
            {"path": file, "workspace": _workspace(project, file)},
        )
    for file, s in sorted(project.js.items()):
        for dep, at in project.module_deps(file):
            ctx.edge("imports", f"module:{file}", f"module:{dep}", [ctx.ev(file, at)])
        for imp in s["imports"]:
            res = project.resolve_spec(file, imp["spec"])
            if res is None or res[0] != "pkg":
                continue
            provider = provider_for(res[1])
            if provider is not None:
                sid = _service_node(ctx, provider, res[1], [ctx.ev(file, imp["line"])])
                ctx.edge("uses", f"module:{file}", sid, [ctx.ev(file, imp["line"])])

    # Facts per function scope.
    calls: dict[FnKey, list[tuple[FnKey, int]]] = {}
    access: dict[FnKey, list[tuple[str, str, Any, JSON, str, float]]] = {}
    for file, s in project.js.items():
        imported = project.imports_of(file)
        for scope, info in s["scopes"].items():
            facts: list[tuple[str, str, Any, JSON, str, float]] = []
            for name, at in info.get("env", []):
                env_evidence.setdefault(name, []).append(ctx.ev(file, at))
                facts.append(("reads", f"envVar:{name}", ctx.ev(file, at), {}, "extracted", 1.0))
            if scope == MODULE:
                continue
            key = (file, scope)
            targets = []
            for call in info["calls"]:
                hit = _prisma_call(ctx, file, call["c"])
                if hit is not None:
                    kind, model, op, source, conf = hit
                    ev = ctx.ev(file, call["l"], call["e"])
                    facts.append((kind, f"model:{model}", ev, {"operation": op}, source, conf))
                    continue
                target = _call_target(project, file, scope, call["c"])
                if target is not None and target != key:
                    targets.append((target, call["l"]))
            for name, at in info["refs"].items():
                if name not in imported and name not in s["vars"]:
                    continue
                for pkg in project.taint(file, name):
                    provider = provider_for(package_name(pkg.package))
                    sid = f"service:{provider}"
                    if provider is not None and sid in ctx.nodes:
                        facts.append(("uses", sid, ctx.ev(file, at), {}, "extracted", 1.0))
            calls[key] = targets
            if facts:
                access[key] = facts

    # Function nodes: the call closure of every handler/middleware, plus direct accessors.
    keep: set[FnKey] = set()
    queue = deque(sorted(ctx.entries))
    while queue:
        key = queue.popleft()
        if key in keep or key[0] not in project.js or key[1] not in project.js[key[0]]["scopes"]:
            continue
        keep.add(key)
        queue.extend(t for t, _ in calls.get(key, []))
    keep |= set(access)
    exported = {
        (f, local): name for f, s in project.js.items() for name, local in s["exports"].items()
    }
    wrapped = {
        (f, fn)
        for f, s in project.js.items()
        for var in s["vars"].values()
        if AUTH_RE.search(".".join(var.get("callee", [])) or "")
        for fn in var.get("fns", [])
    }
    for key in sorted(keep):
        file, scope = key
        info = project.js[file]["scopes"][scope]
        role = ctx.roles.get(key, "function")
        kind = role if role != "function" else "callback"
        label = (
            f"{posixpath.basename(file)}:{info['line']} {kind}"
            if _ANON.match(scope)
            else f"{scope}()"
        )
        attrs: JSON = {"file": file}
        if role == "middleware":
            meta = ctx.fn_meta.get(key, {})
            attrs.update(framework=meta.get("framework", "express"), name=meta.get("name", scope))
            if meta.get("matchers") is not None:
                attrs["matchers"] = meta["matchers"]
        else:
            attrs["exportName"] = exported.get(key)
            if role == "handler":
                attrs["checksAuth"] = key in wrapped or any(
                    AUTH_RE.search(c["c"][-1]) or AUTH_RE.search(c["c"][0]) for c in info["calls"]
                )
        ctx.node(ctx.fn_id(key), role, label, [ctx.ev(file, info["line"], info["end"])], attrs)

    for key in keep:
        src = fn_ref(key)
        for target, at in calls.get(key, []):
            if target in keep:
                ctx.edge("calls", src, fn_ref(target), [ctx.ev(key[0], at)])
        for kind, dst, ev, attrs, source, conf in access.get(key, []):
            ctx.edge(kind, src, dst, [ev], attrs, source=source, confidence=conf)

    # Env vars, including env("X") in Prisma schemas.
    for file, raw in project.raw.items():
        for name, at in raw.get("prisma", {}).get("env", []):
            env_evidence.setdefault(name, []).append(ctx.ev(file, at))
    for name, evidence in sorted(env_evidence.items()):
        ctx.node(
            f"envVar:{name}",
            "envVar",
            name,
            evidence,
            {"name": name, "documented": name in documented},
        )
