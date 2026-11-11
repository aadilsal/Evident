"""FastAPI adapter: `FastAPI()`/`APIRouter()` instances, decorator routes, `include_router`
prefixes and `Depends(...)` dependencies as guards. Counting rules: docs/labelling-guide.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from evident.adapters._py import emit_route, fastapi_path, from_package, join, str_list
from evident.link import AUTH_RE, LinkContext, Ns, Sym

JSON = dict[str, Any]
FRAMEWORK = "fastapi"
VERBS = frozenset({"get", "post", "put", "patch", "delete", "head", "options"})
_ANNOTATED_DEP = re.compile(r"Depends\(\s*(\w+)")
Key = tuple[str, str]  # (file, binding)


@dataclass
class _Inst:
    kind: str  # app | router
    prefix: str = ""
    deps: list[tuple[str, JSON, int]] = field(default_factory=list)
    routes: list[tuple[str, str, str, int, int, list[tuple[str, JSON, int]]]] = field(
        default_factory=list
    )
    children: list[tuple[str, Key, list[tuple[str, JSON, int]]]] = field(default_factory=list)


def _dep_name(desc: JSON) -> str:
    inner = (desc.get("args") or [{}])[0]
    return str(inner.get("name") or ".".join(inner.get("chain") or []))


def _deps(file: str, desc: JSON | None, at: int) -> list[tuple[str, JSON, int]]:
    """Auth-like `Depends(...)` only: `get_db` is plumbing, `get_current_user` is a guard."""
    if not desc or desc.get("k") != "array":
        return []
    return [
        (file, d, at)
        for d in desc["items"]
        if d.get("k") == "call" and AUTH_RE.search(_dep_name(d))
    ]


def link(ctx: LinkContext) -> None:
    project = ctx.project
    insts: dict[Key, _Inst] = {}
    for file, s in project.js.items():
        if not file.endswith(".py"):
            continue
        bindings = [(name, v) for name, v in s["vars"].items()]
        bindings += [
            (name, loc) for sc in s["scopes"].values() for name, loc in sc.get("locals", {}).items()
        ]
        for name, v in bindings:
            pkg = from_package(project, file, v.get("callee"), "fastapi")
            if pkg is None:
                continue
            ctor = (v.get("callee") or [""])[-1]
            if ctor not in ("FastAPI", "APIRouter"):
                continue
            kw = v.get("kw", {})
            prefix = (
                kw.get("prefix", {}).get("value", "")
                if kw.get("prefix", {}).get("k") == "str"
                else ""
            )
            insts[(file, name)] = _Inst(
                "app" if ctor == "FastAPI" else "router",
                prefix,
                _deps(file, kw.get("dependencies"), v.get("line", 1)),
            )
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
            for deco in info.get("decorators", []):
                chain = deco.get("chain") or []
                if len(chain) != 2 or (chain[1] not in VERBS and chain[1] != "api_route"):
                    continue
                key = inst_of(file, {"k": "id", "name": chain[0]})
                if key is None:
                    continue
                args, kw = deco.get("args", []), deco.get("kw", {})
                path_desc = args[0] if args else kw.get("path")
                if not path_desc or path_desc.get("k") != "str":
                    continue
                methods = str_list(kw.get("methods")) if chain[1] == "api_route" else [chain[1]]
                guards = _deps(file, kw.get("dependencies"), deco["line"])
                deps = [d for d in info.get("defaults", {}).values() if d.get("k") == "call"]
                deps = [d for d in deps if (d.get("chain") or [""])[-1] in ("Depends", "Security")]
                for anno in info.get("annos", {}).values():
                    deps += [
                        {"k": "call", "chain": ["Depends"], "args": [{"k": "id", "name": n}]}
                        for n in _ANNOTATED_DEP.findall(anno)
                    ]
                guards += [(file, d, deco["line"]) for d in deps if AUTH_RE.search(_dep_name(d))]
                for m in methods or ["GET"]:
                    insts[key].routes.append(
                        (m, path_desc["value"], scope, info["line"], info["end"], guards)
                    )
            for call in info["calls"]:
                c = call["c"]
                if len(c) != 2 or c[1] != "include_router" or not call.get("a"):
                    continue
                parent = inst_of(file, {"k": "id", "name": c[0]})
                child = inst_of(file, call["a"][0])
                if parent is None or child is None:
                    continue
                kw = call.get("kw", {})
                prefix = (
                    kw.get("prefix", {}).get("value", "")
                    if kw.get("prefix", {}).get("k") == "str"
                    else ""
                )
                insts[parent].children.append(
                    (prefix, child, _deps(file, kw.get("dependencies"), call["l"]))
                )

    reached: set[Key] = set()

    def walk(
        key: Key,
        base: str,
        inherited: list[tuple[str, JSON, int]],
        seen: frozenset[Key],
        inferred: bool,
    ) -> None:
        reached.add(key)
        inst = insts[key]
        base = join(base, inst.prefix)
        deps = [*inherited, *inst.deps]
        for method, path, scope, start, end, guards in inst.routes:
            emit_route(
                ctx,
                file=key[0],
                method=method,
                path=join(base, fastapi_path(path)),
                framework=FRAMEWORK,
                start=start,
                end=end,
                handler=(key[0], scope),
                guards=[*deps, *guards],
                inferred=inferred,
            )
        for prefix, child, child_deps in inst.children:
            if child not in seen:
                walk(child, join(base, prefix), [*deps, *child_deps], seen | {child}, inferred)

    for key, inst in sorted(insts.items()):
        if inst.kind == "app":
            walk(key, "", [], frozenset({key}), False)
    for key, inst in sorted(insts.items()):
        if key not in reached and inst.routes:
            walk(key, "", [], frozenset({key}), True)
    if any(i.routes for i in insts.values()):
        ctx.adapters.append("fastapi")
