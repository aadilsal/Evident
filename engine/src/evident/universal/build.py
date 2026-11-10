"""Universal layer, link step: modules, imports, services, env vars and the function graph.

Runs after the adapters, which mark handlers and middleware and register ORM call classifiers.
Functions become nodes when they are reachable through calls from a handler/middleware, or
touch a model, service or env var.
"""

from __future__ import annotations

import json
import posixpath
import re
from collections import deque
from functools import cache
from importlib.resources import files
from typing import Any

from evident.link import AUTH_RE, Fact, FnKey, LinkContext, Project, Sym, fn_ref, package_name
from evident.universal.js import MODULE

JSON = dict[str, Any]
_ANON = re.compile(r"^L\d+(@L\d+)?$")
# Calls that validate input: zod/yup/joi/class-validator/ajv, express-validator, celebrate.
VALIDATE_CALLS = frozenset(
    {
        "parse",
        "safeParse",
        "parseAsync",
        "safeParseAsync",
        "validate",
        "validateAsync",
        "validateSync",
        "validateOrReject",
        "assert",
        "validationResult",
        "plainToInstance",
    }
)
VALIDATE_RE = re.compile(r"(?i)(valid|schema|celebrate|zod|joi|yup|sanitiz)")


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


def _method_of(project: Project, target: object, method: str) -> FnKey | None:
    if isinstance(target, Sym) and target.name in project.js[target.file]["classes"]:
        key = f"{target.name}.{method}"
        if key in project.js[target.file]["scopes"]:
            return (target.file, key)
    return None


def call_target(project: Project, file: str, scope: str, c: list[str]) -> FnKey | None:
    """The first-party function a call chain lands in, if it can be proven."""
    if len(c) == 1:
        return project.scope_of(project.resolve(file, c[0]))
    if c[0] == "this":
        cls = project.class_of_scope(file, scope)
        if cls is None:
            return None
        if len(c) == 2:
            key = f"{cls}.{c[1]}"
            return (file, key) if key in project.js[file]["scopes"] else None
        if len(c) == 3:  # this.users.findOne(): constructor-injected or typed field
            fld = project.field(file, scope, c[1])
            if fld is not None:
                return _method_of(project, project.type_target(file, fld.get("type")), c[2])
        return None
    if len(c) == 2:
        local = project.local_binding(file, scope, c[0])
        if local is not None and local.get("new") and len(local["new"]) == 1:
            return _method_of(project, project.resolve(file, local["new"][0]), c[1])
        return project.member_scope(file, c[0], c[1])
    return None


def _validates(info: JSON) -> bool:
    return any(
        call["c"][-1] in VALIDATE_CALLS or VALIDATE_RE.search(call["c"][0])
        for call in info["calls"]
    )


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
    access: dict[FnKey, list[Fact]] = {k: list(v) for k, v in ctx.access.items()}
    for file, s in project.js.items():
        imported = project.imports_of(file)
        for scope, info in s["scopes"].items():
            facts: list[Fact] = []
            for name, at in info.get("env", []):
                env_evidence.setdefault(name, []).append(ctx.ev(file, at))
                facts.append(("reads", f"envVar:{name}", ctx.ev(file, at), {}, "extracted", 1.0))
            if scope == MODULE:
                continue
            key = (file, scope)
            targets = []
            for call in info["calls"]:
                fact = next(
                    (f for clf in ctx.classifiers if (f := clf(ctx, file, scope, call))), None
                )
                if fact is not None:
                    facts.append(fact)
                    continue
                target = call_target(project, file, scope, call["c"])
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
                access.setdefault(key, []).extend(facts)

    # Function nodes: the call closure of every handler/middleware, plus direct accessors.
    keep: set[FnKey] = set()
    queue = deque(sorted(ctx.entries))
    while queue:
        key = queue.popleft()
        if key in keep or key[0] not in project.js or key[1] not in project.js[key[0]]["scopes"]:
            continue
        keep.add(key)
        queue.extend(t for t, _ in calls.get(key, []))
    keep |= {k for k in access if k[0] in project.js and k[1] in project.js[k[0]]["scopes"]}
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
        calls_auth = key in wrapped or any(
            AUTH_RE.search(c["c"][-1]) or AUTH_RE.search(c["c"][0]) for c in info["calls"]
        )
        attrs: JSON = {"file": file}
        if role == "middleware":
            meta = ctx.fn_meta.get(key, {})
            attrs.update(framework=meta.get("framework", "express"), name=meta.get("name", scope))
            if meta.get("matchers") is not None:
                attrs["matchers"] = meta["matchers"]
            attrs["checksAuth"] = calls_auth or any(AUTH_RE.search(r) for r in info["refs"])
        else:
            attrs["exportName"] = exported.get(key)
            if role == "handler":
                attrs["checksAuth"] = calls_auth
            if info.get("body"):
                attrs["bodyLine"] = info["body"]
            if _validates(info):
                attrs["validatesBody"] = True
        ctx.node(ctx.fn_id(key), role, label, [ctx.ev(file, info["line"], info["end"])], attrs)

    for key in keep:
        src = fn_ref(key)
        for target, at in calls.get(key, []):
            if target in keep:
                ctx.edge("calls", src, fn_ref(target), [ctx.ev(key[0], at)])
        for kind, dst, ev, attrs, source, conf in access.get(key, []):
            ctx.edge(kind, src, dst, [ev], attrs, source=source, confidence=conf)

    # Containers from docker-compose (names, images, ports; never environment values).
    for file, raw in sorted(project.raw.items()):
        for svc in raw.get("compose", []):
            attrs = {"file": file, "name": svc["name"]}
            attrs.update({k: svc[k] for k in ("image", "build", "ports", "dependsOn") if k in svc})
            ctx.node(
                f"container:{svc['name']}",
                "container",
                svc["name"],
                [ctx.ev(file, svc["line"], svc["end"])],
                attrs,
            )

    # Env vars, including env("X") in Prisma schemas.
    for file, raw in project.raw.items():
        for name, at in raw.get("prisma", {}).get("env", []) if "js" not in raw else []:
            env_evidence.setdefault(name, []).append(ctx.ev(file, at))
    for name, evidence in sorted(env_evidence.items()):
        ctx.node(
            f"envVar:{name}",
            "envVar",
            name,
            evidence,
            {"name": name, "documented": name in documented},
        )
