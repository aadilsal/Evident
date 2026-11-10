"""Next.js App Router adapter: route handlers, pages, layouts, server actions, middleware.

Routes come from file paths under `app/` (or `src/app/`) of every package that depends on
`next`. Counting rules: docs/labelling-guide.md (Routes).
"""

from __future__ import annotations

import posixpath
import re
from typing import Any

from evident.link import FnKey, LinkContext, Sym

JSON = dict[str, Any]
HTTP_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")
FILE_KINDS = {"route": "api", "page": "page", "layout": "layout"}
EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs")
MIDDLEWARE_STEMS = ("middleware", "proxy")
FRAMEWORK = "next-app-router"


def _segment(seg: str) -> str | None:
    """One folder -> path part; "" drops it from the URL, None means not a route at all."""
    if seg.startswith("_"):
        return None  # private folder
    if seg.startswith("(") and seg.endswith(")"):
        return ""  # route group
    if seg.startswith("@"):
        return ""  # parallel route slot
    if seg.startswith("("):
        return None  # intercepting route: a second view of a route counted elsewhere
    if m := re.fullmatch(r"\[\[\.\.\.([^\]/]+)\]\]", seg):
        return f":{m.group(1)}*?"
    if m := re.fullmatch(r"\[\.\.\.([^\]/]+)\]", seg):
        return f":{m.group(1)}*"
    if m := re.fullmatch(r"\[([^\]/]+)\]", seg):
        return f":{m.group(1)}"
    return seg


def app_route(rel: str, roots: list[str]) -> tuple[str, str, str] | None:
    """(path, kind, package root) for an App Router file, else None."""
    for root in sorted(roots, key=len, reverse=True):
        prefix = f"{root}/" if root else ""
        if not rel.startswith(prefix):
            continue
        rest = rel[len(prefix) :]
        inner = next((rest[len(a) :] for a in ("app/", "src/app/") if rest.startswith(a)), None)
        if inner is None:
            continue
        directory, base = posixpath.split(inner)
        stem, ext = posixpath.splitext(base)
        if stem not in FILE_KINDS or ext not in EXTS:
            return None
        parts = []
        for seg in (s for s in directory.split("/") if s):
            part = _segment(seg)
            if part is None:
                return None
            if part:
                parts.append(part)
        return "/" + "/".join(parts), FILE_KINDS[stem], root
    return None


def _to_regex(pattern: str) -> str:
    """Next.js matcher (path-to-regexp style) -> a Python regex, approximately."""
    out: list[str] = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == ":" and (m := re.match(r":(\w+)([*+?]?)", pattern[i:])):
            mod = m.group(2)
            if mod in ("*", "?") and out and out[-1] == "/":
                out.pop()
                out.append("(?:/[^/]+)*" if mod == "*" else "(?:/[^/]+)?")
            elif mod == "+":
                out.append("[^/]+(?:/[^/]+)*")
            else:
                out.append("[^/]+")
            i += len(m.group(0))
            continue
        if ch == "(":
            depth, j = 0, i
            while j < len(pattern):
                depth += {"(": 1, ")": -1}.get(pattern[j], 0)
                j += 1
                if depth == 0:
                    break
            out.append(pattern[i:j])
            i = j
            continue
        out.append(re.escape(ch))
        i += 1
    return "".join(out)


def matches(patterns: list[str], path: str) -> bool:
    if not patterns:
        return True
    for p in patterns:
        try:
            if re.fullmatch(_to_regex(p), path):
                return True
        except re.error:
            return True  # unparseable matcher: assume it applies rather than invent a gap
    return False


def _export_line(s: JSON, name: str, fallback: int = 1) -> int:
    for re_exp in s["reexports"]:
        if any(alias == name for _, alias in re_exp["names"]):
            return int(re_exp["line"])
    local = s["exports"].get(name, name)
    if local in s["scopes"]:
        return int(s["scopes"][local]["line"])
    if local in s["vars"]:
        return int(s["vars"][local]["line"])
    return fallback


def _evidence(ctx: LinkContext, file: str, key: FnKey | None, s: JSON, name: str) -> list[Any]:
    if key is not None and key[0] == file:
        scope = ctx.project.js[file]["scopes"][key[1]]
        return [ctx.ev(file, scope["line"], scope["end"])]
    return [ctx.ev(file, _export_line(s, name))]


def _route(
    ctx: LinkContext,
    file: str,
    method: str,
    path: str,
    kind: str,
    key: FnKey | None,
    s: JSON,
    export: str,
) -> str:
    route_id = f"route:{method} {path}" + (" (layout)" if kind == "layout" else "")
    attrs: JSON = {"method": method, "path": path, "framework": FRAMEWORK, "kind": kind}
    if key is not None:
        attrs["handlerRef"] = ctx.mark(key, "handler")
    label = route_id.removeprefix("route:")
    ctx.node(route_id, "route", label, _evidence(ctx, file, key, s, export), attrs)
    if key is not None:
        ctx.edge("handles", route_id, attrs["handlerRef"], _evidence(ctx, file, key, s, export)[:1])
    return route_id


def link(ctx: LinkContext) -> None:
    project = ctx.project
    roots = [d for d, pkg in project.packages.items() if "next" in pkg.get("deps", [])]
    emitted: dict[str, list[tuple[str, str]]] = {r: [] for r in roots}
    found = False
    for file, s in sorted(project.js.items()):
        hit = app_route(file, roots)
        if hit is not None:
            path, kind, root = hit
            found = True
            if kind == "api":
                for m in HTTP_METHODS:
                    if m in s["exports"] or any(
                        m == a for r in s["reexports"] for _, a in r["names"]
                    ):
                        key = project.scope_of(project.resolve_export(file, m))
                        emitted[root].append((_route(ctx, file, m, path, kind, key, s, m), kind))
            elif "default" in s["exports"]:
                key = project.scope_of(project.resolve_export(file, "default"))
                emitted[root].append(
                    (_route(ctx, file, "GET", path, kind, key, s, "default"), kind)
                )
        if s.get("directive") == "use server":
            for name in sorted(s["exports"]):
                target = project.resolve_export(file, name)
                key = project.scope_of(target)
                if key is None or not isinstance(target, Sym) or target.file != file:
                    continue
                found = True
                _route(ctx, file, "POST", f"action:{file}#{name}", "serverAction", key, s, name)
    for root in roots:
        prefix = f"{root}/" if root else ""
        for stem in MIDDLEWARE_STEMS:
            for base in ("", "src/"):
                for ext in EXTS:
                    file = f"{prefix}{base}{stem}{ext}"
                    if file in project.js:
                        found = True
                        _middleware(ctx, file, emitted[root])
    if found:
        ctx.adapters.append("nextjs")


def _middleware(ctx: LinkContext, file: str, routes: list[tuple[str, str]]) -> None:
    project = ctx.project
    s = project.js[file]
    config = s["vars"].get("config", {})
    matchers = [m for m in config.get("strings", []) if m.startswith("/")]
    name = next((n for n in (*MIDDLEWARE_STEMS, "default") if n in s["exports"]), None)
    if name is None:
        name = next(
            (
                a
                for r in s["reexports"]
                for _, a in r["names"]
                if a in (*MIDDLEWARE_STEMS, "default")
            ),
            None,
        )
    if name is None:
        return
    key = project.scope_of(project.resolve_export(file, name))
    if key is not None:
        mid = ctx.mark(key, "middleware")
        ctx.fn_meta[key] = {"framework": FRAMEWORK, "name": name, "matchers": matchers}
    else:
        mid = ctx.node(
            f"middleware:{file}#{name}",
            "middleware",
            name,
            [ctx.ev(file, _export_line(s, name))],
            {"file": file, "framework": FRAMEWORK, "name": name, "matchers": matchers},
            confidence=0.8,
        )
    line = _export_line(s, name)
    for route_id, _kind in routes:
        path = ctx.nodes[route_id].attrs["path"]
        if matches(matchers, path):
            ctx.edge("guards", mid, route_id, [ctx.ev(file, line)])
