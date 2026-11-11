"""Django adapter: URLconf tree (`ROOT_URLCONF`, `path`/`re_path`, `include`), function and
class-based views, Django REST Framework routers/ViewSets, and auth decorators/mixins/permissions.
Counting rules: docs/labelling-guide.md (Django).
"""

from __future__ import annotations

import re
from typing import Any

from evident.adapters._py import class_of, deco_desc, emit_route, flask_path, fn_of, join, str_list
from evident.link import LinkContext, Pkg, Project, Sym
from evident.universal.js import MODULE

JSON = dict[str, Any]
FRAMEWORK = "django"
URL_FNS = frozenset({"path", "re_path", "url"})
HTTP = ("get", "post", "put", "patch", "delete", "head", "options")
# Methods a generic class-based view handles without defining them itself.
GENERIC = {
    "TemplateView": ("GET",),
    "RedirectView": ("GET",),
    "ListView": ("GET",),
    "DetailView": ("GET",),
    "CreateView": ("GET", "POST"),
    "UpdateView": ("GET", "POST"),
    "DeleteView": ("GET", "POST"),
    "FormView": ("GET", "POST"),
    "ListAPIView": ("GET",),
    "RetrieveAPIView": ("GET",),
    "CreateAPIView": ("POST",),
    "UpdateAPIView": ("PUT", "PATCH"),
    "DestroyAPIView": ("DELETE",),
    "ListCreateAPIView": ("GET", "POST"),
    "RetrieveUpdateAPIView": ("GET", "PUT", "PATCH"),
    "RetrieveDestroyAPIView": ("GET", "DELETE"),
    "RetrieveUpdateDestroyAPIView": ("GET", "PUT", "PATCH", "DELETE"),
}
VIEWSET_ACTIONS = {
    "list": ("GET", False),
    "create": ("POST", False),
    "retrieve": ("GET", True),
    "update": ("PUT", True),
    "partial_update": ("PATCH", True),
    "destroy": ("DELETE", True),
}
VIEWSET_BASES = {
    "ModelViewSet": tuple(VIEWSET_ACTIONS),
    "ReadOnlyModelViewSet": ("list", "retrieve"),
    "ListModelMixin": ("list",),
    "CreateModelMixin": ("create",),
    "RetrieveModelMixin": ("retrieve",),
    "UpdateModelMixin": ("update", "partial_update"),
    "DestroyModelMixin": ("destroy",),
}
METHOD_DECORATORS = {
    "require_GET": ["GET"],
    "require_POST": ["POST"],
    "require_safe": ["GET", "HEAD"],
}
_REGEX_GROUP = re.compile(r"\(\?P<(\w+)>[^)]*\)")
Guard = tuple[str, JSON | str, int]


def _is_django(project: Project, file: str, chain: list[str] | None) -> bool:
    if not chain:
        return False
    target = project.resolve(file, chain[0])
    return isinstance(target, Pkg) and target.package.startswith("django")


def _route_path(fn: str, raw: str) -> tuple[str, bool]:
    """(path, dynamic) for a path()/re_path() pattern."""
    if fn == "path":
        return flask_path(raw), False
    p = raw.lstrip("^").rstrip("$")
    p = _REGEX_GROUP.sub(lambda m: f":{m.group(1)}", p)
    return p, bool(re.search(r"[\[\]()*+?|\\{}]", p))


def _base_names(info: JSON) -> list[str]:
    return [b.split(".")[-1].split("[")[0] for b in info.get("bases", [])]


def _class_guards(file: str, info: JSON) -> list[Guard]:
    out: list[Guard] = []
    for base in _base_names(info):
        if base.endswith("Mixin") and ("Login" in base or "Permission" in base):
            out.append((file, base, info["line"]))
    perms = info.get("fields", {}).get("permission_classes", {}).get("value", {})
    for item in perms.get("items", []) if perms.get("k") == "array" else []:
        name = item.get("name") or ".".join(item.get("chain") or [])
        if name:
            out.append((file, name, info["fields"]["permission_classes"]["line"]))
    for deco in info.get("decorators", []):
        if (deco.get("chain") or [""])[-1] == "method_decorator" and deco.get("args"):
            out.append((file, deco["args"][0], deco["line"]))
    return out


def link(ctx: LinkContext) -> None:
    project = ctx.project
    py = {f: s for f, s in project.js.items() if f.endswith(".py")}
    urlconfs = {
        f
        for f, s in py.items()
        if any(
            c["c"][-1:] and c["c"][0] in URL_FNS and _is_django(project, f, c["c"])
            for c in s["scopes"][MODULE]["calls"]
        )
    }
    if not urlconfs:
        return
    root: str | None = None
    for f, s in py.items():
        conf = s["vars"].get("ROOT_URLCONF", {}).get("string")
        if conf:
            res = project.resolve_spec(f, conf)
            if res is not None and res[0] == "file":
                root = res[1]
                break
    routers: dict[tuple[str, str], list[tuple[str, JSON, int]]] = {}
    for f, s in py.items():
        for name, v in s["vars"].items():
            if (v.get("callee") or [""])[-1] in ("DefaultRouter", "SimpleRouter"):
                routers[(f, name)] = []
        for call in s["scopes"][MODULE]["calls"]:
            c = call["c"]
            if (
                len(c) == 2
                and c[1] == "register"
                and (f, c[0]) in routers
                and len(call.get("a", [])) >= 2
            ):
                prefix = call["a"][0]
                if prefix.get("k") == "str":
                    routers[(f, c[0])].append((prefix["value"], call["a"][1], call["l"]))
    included: set[str] = set()
    emitted = False

    def view_routes(file: str, view: JSON, path: str, dynamic: bool, at: tuple[int, int]) -> None:
        nonlocal emitted
        start, end = at
        if view.get("k") == "call" and (view.get("chain") or [""])[-1] == "as_view":
            chain = view["chain"][:-1]
            cls = class_of(
                project,
                file,
                {"k": "id", "name": chain[0]}
                if len(chain) == 1
                else {"k": "member", "chain": chain},
            )
            if cls is None:
                return
            info = project.js[cls.file]["classes"][cls.name]
            defined = [m for m in HTTP if m in info.get("methods", {})]
            methods = [m.upper() for m in defined]
            for base in _base_names(info):
                methods += [m for m in GENERIC.get(base, ()) if m not in methods]
            guards = _class_guards(cls.file, info)
            # No defined or known-generic methods (e.g. a library base view): the method is a
            # guess, so the route is marked dynamic and scored like an optional item.
            unknown = not methods
            for m in methods or ["ALL"]:
                key = (cls.file, f"{cls.name}.{m.lower()}")
                handler = key if key[1] in project.js[cls.file]["scopes"] else None
                emit_route(
                    ctx,
                    file=file,
                    method=m,
                    path=path,
                    framework=FRAMEWORK,
                    start=start,
                    end=end,
                    handler=handler,
                    guards=guards,
                    dynamic=dynamic or unknown,
                )
                emitted = True
            return
        handler = fn_of(project, file, view)
        if handler is None:
            return
        scope = project.js[handler[0]]["scopes"][handler[1]]
        fn_methods: list[str] = []
        fn_guards: list[Guard] = []
        for deco in scope.get("decorators", []):
            name = (deco.get("chain") or [""])[-1]
            if name in ("require_http_methods", "api_view"):
                fn_methods = [m.upper() for m in str_list((deco.get("args") or [None])[0])] or [
                    "GET"
                ]
            elif name in METHOD_DECORATORS:
                fn_methods = METHOD_DECORATORS[name]
            elif name == "permission_classes":
                for item in ((deco.get("args") or [{}])[0] or {}).get("items", []):
                    fn_guards.append((handler[0], item.get("name", ""), deco["line"]))
            else:
                fn_guards.append((handler[0], deco_desc(deco), deco["line"]))
        for m in fn_methods or ["ALL"]:
            emit_route(
                ctx,
                file=file,
                method=m,
                path=path,
                framework=FRAMEWORK,
                start=start,
                end=end,
                handler=handler,
                guards=fn_guards,
                dynamic=dynamic,
            )
            emitted = True

    def router_routes(rkey: tuple[str, str], base: str) -> None:
        nonlocal emitted
        file = rkey[0]
        for prefix, view, at in routers[rkey]:
            cls = class_of(project, file, view)
            if cls is None:
                continue
            info = project.js[cls.file]["classes"][cls.name]
            actions = [a for a in VIEWSET_ACTIONS if a in info.get("methods", {})]
            for b in _base_names(info):
                actions += [a for a in VIEWSET_BASES.get(b, ()) if a not in actions]
            guards = _class_guards(cls.file, info)
            for action in actions:
                method, detail = VIEWSET_ACTIONS[action]
                path = join(base, prefix, ":pk" if detail else "")
                key = (cls.file, f"{cls.name}.{action}")
                handler = key if key[1] in project.js[cls.file]["scopes"] else None
                emit_route(
                    ctx,
                    file=file,
                    method=method,
                    path=path,
                    framework=FRAMEWORK,
                    start=at,
                    end=at,
                    handler=handler,
                    guards=guards,
                )
                emitted = True
            for mname, m in info.get("methods", {}).items():
                deco = next(
                    (
                        d
                        for d in m.get("decorators", [])
                        if (d.get("chain") or [""])[-1] == "action"
                    ),
                    None,
                )
                if deco is None:
                    continue
                kw = deco.get("kw", {})
                detail = (kw.get("detail") or {}).get("value") is True
                url_path = _route_path("re_path", (kw.get("url_path") or {}).get("value") or mname)[
                    0
                ]
                for method in [x.upper() for x in str_list(kw.get("methods"))] or ["GET"]:
                    path = join(base, prefix, ":pk" if detail else "", url_path)
                    emit_route(
                        ctx,
                        file=file,
                        method=method,
                        path=path,
                        framework=FRAMEWORK,
                        start=at,
                        end=at,
                        handler=(cls.file, f"{cls.name}.{mname}"),
                        guards=guards,
                    )
                    emitted = True

    def walk(file: str, base: str, seen: frozenset[str]) -> None:
        mounted: set[tuple[str, str]] = set()
        for call in project.js[file]["scopes"][MODULE]["calls"]:
            c, args = call["c"], call.get("a", [])
            if (
                len(c) != 1
                or c[0] not in URL_FNS
                or not _is_django(project, file, c)
                or len(args) < 2
            ):
                continue
            if args[0].get("k") != "str":
                continue
            local, dynamic = _route_path(c[0], args[0]["value"])
            view = args[1]
            if view.get("k") == "call" and (view.get("chain") or [""])[-1] == "include":
                inner = (view.get("args") or [{}])[0]
                if inner.get("k") == "str":
                    res = project.resolve_spec(file, inner["value"])
                    if res is not None and res[0] == "file" and res[1] not in seen:
                        included.add(res[1])
                        walk(res[1], join(base, local), seen | {res[1]})
                elif inner.get("k") == "member" and inner["chain"][-1] == "urls":
                    target = project.resolve(file, inner["chain"][0])
                    rkey = (
                        (target.file, target.name)
                        if isinstance(target, Sym)
                        else (file, inner["chain"][0])
                    )
                    if rkey in routers:
                        mounted.add(rkey)
                        router_routes(rkey, join(base, local))
                continue
            view_routes(file, view, join(base, local), dynamic, (call["l"], call["e"]))
        for rkey in routers:
            if rkey[0] == file and rkey not in mounted:
                router_routes(rkey, base)  # urlpatterns += router.urls

    roots = [root] if root in urlconfs else []
    if not roots:
        referenced = {
            res[1]
            for f in urlconfs
            for call in project.js[f]["scopes"][MODULE]["calls"]
            if call["c"] == ["include"]
            and call.get("a")
            and call["a"][0].get("k") == "str"
            and (res := project.resolve_spec(f, call["a"][0]["value"])) is not None
            and res[0] == "file"
        }
        roots = sorted(urlconfs - referenced)
    for r in roots:
        walk(r, "", frozenset({r}))
    if emitted:
        ctx.adapters.append("django")
