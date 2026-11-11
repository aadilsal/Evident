"""Summarise one Python module into the same JSON shape as universal/js.py.

`self`/`cls` become `this` so the shared linker resolves method calls the same way. Python-only
extras: decorators on scopes, call arguments (`a`/`kw`), class bases, class fields and Meta.
"""

from __future__ import annotations

from typing import Any

import tree_sitter as ts

from evident.syntax import end_line, line, text
from evident.universal.js import ENV_NAME, MODULE, FnKeys

JSON = dict[str, Any]
MAX_ARG_DEPTH = 3
BODY_ATTRS = frozenset({"json", "get_json", "body", "form", "data", "POST", "files", "stream"})
REQUEST_NAMES = frozenset({"request", "req"})
ENV_CALLS = (["os", "getenv"], ["getenv"], ["os", "environ", "get"], ["environ", "get"])


def py_string(node: ts.Node | None) -> str | None:
    """Value of a plain string literal (no f-string interpolation)."""
    if node is None or node.type != "string":
        return None
    if any(c.type == "interpolation" for c in node.named_children):
        return None
    return "".join(text(c) for c in node.named_children if c.type == "string_content")


def py_chain(node: ts.Node | None) -> list[str] | None:
    """`a.b.c` -> ["a", "b", "c"]; `self.x` -> ["this", "x"]."""
    parts: list[str] = []
    while node is not None:
        if node.type == "identifier":
            name = text(node)
            parts.append("this" if name in ("self", "cls") else name)
            return parts[::-1]
        if node.type == "attribute":
            parts.append(text(node.child_by_field_name("attribute")))
            node = node.child_by_field_name("object")
            continue
        if node.type == "parenthesized_expression" and node.named_children:
            node = node.named_children[0]
            continue
        return None
    return None


def py_describe(node: ts.Node, depth: int = 0) -> JSON:
    """An argument as data: string, identifier, member chain, call (with args), list, dict."""
    t = node.type
    value = py_string(node)
    if value is not None:
        return {"k": "str", "value": value}
    if t in ("identifier", "attribute"):
        c = py_chain(node)
        if c is None:
            return {"k": "other"}
        return {"k": "id", "name": c[0]} if len(c) == 1 else {"k": "member", "chain": c}
    if depth >= MAX_ARG_DEPTH:
        return {"k": "other"}
    if t == "call":
        args, kw = _call_args(node, depth + 1)
        return {
            "k": "call",
            "chain": py_chain(node.child_by_field_name("function")),
            "args": args,
            "kw": kw,
        }
    if t in ("list", "tuple", "set"):
        return {"k": "array", "items": [py_describe(c, depth + 1) for c in node.named_children]}
    if t == "dictionary":
        props: JSON = {}
        for pair in node.named_children:
            if pair.type == "pair":
                key = py_string(pair.child_by_field_name("key"))
                val = pair.child_by_field_name("value")
                if key is not None and val is not None:
                    props[key] = py_describe(val, depth + 1)
        return {"k": "obj", "props": props}
    if t == "integer":
        return {"k": "num", "value": text(node)}
    if t in ("true", "false"):
        return {"k": "bool", "value": t == "true"}
    if t == "none":
        return {"k": "none"}
    return {"k": "other"}


def _call_args(call: ts.Node, depth: int = 0) -> tuple[list[JSON], JSON]:
    args_node = call.child_by_field_name("arguments")
    args: list[JSON] = []
    kw: JSON = {}
    for a in args_node.named_children if args_node is not None else []:
        if a.type == "keyword_argument":
            name, val = a.child_by_field_name("name"), a.child_by_field_name("value")
            if name is not None and val is not None:
                kw[text(name)] = py_describe(val, depth)
        elif a.type not in ("comment", "list_splat", "dictionary_splat"):
            args.append(py_describe(a, depth))
    return args, kw


def _decorators(node: ts.Node) -> list[JSON]:
    out = []
    for d in node.children:
        if d.type != "decorator" or not d.named_children:
            continue
        expr = d.named_children[0]
        entry: JSON = {"line": line(d)}
        if expr.type == "call":
            c = py_chain(expr.child_by_field_name("function"))
            entry["name"] = ".".join(c) if c else ""
            entry["chain"] = c
            entry["args"], entry["kw"] = _call_args(expr)
        else:
            c = py_chain(expr)
            entry["name"] = ".".join(c) if c else ""
            entry["chain"] = c
            entry["args"], entry["kw"] = [], {}
        out.append(entry)
    return out


def _params(fn: ts.Node) -> tuple[list[str], JSON, JSON]:
    """Parameter names, default values (Depends(...)) and annotations (Annotated[...])."""
    names: list[str] = []
    defaults: JSON = {}
    annos: JSON = {}
    params = fn.child_by_field_name("parameters")
    for p in params.named_children if params is not None else []:
        name_node = p if p.type == "identifier" else p.child_by_field_name("name")
        if name_node is None and p.named_children and p.named_children[0].type == "identifier":
            name_node = p.named_children[0]
        if name_node is None:
            continue
        name = text(name_node)
        names.append(name)
        value = p.child_by_field_name("value")
        if value is not None:
            defaults[name] = py_describe(value)
        anno = p.child_by_field_name("type")
        if anno is not None:
            annos[name] = text(anno)[:200]
    return names, defaults, annos


class _PySummary:
    def __init__(self, root: ts.Node) -> None:
        self.root = root
        self.imports: list[JSON] = []
        self.vars: dict[str, JSON] = {}
        self.classes: dict[str, JSON] = {}
        self.scopes: dict[str, JSON] = {
            MODULE: {"line": 1, "end": end_line(root), "calls": [], "refs": {}}
        }
        self.fn_keys: FnKeys = {}

    def run(self) -> None:
        for stmt in self.root.named_children:
            self._top(stmt)
        self._walk(self.root, MODULE, skip_defs=True)

    # --- module level ----------------------------------------------------------

    def _top(self, stmt: ts.Node) -> None:
        t = stmt.type
        if t == "import_statement":
            for item in stmt.named_children:
                if item.type == "aliased_import":
                    spec = text(item.child_by_field_name("name"))
                    alias = text(item.child_by_field_name("alias"))
                    self.imports.append(
                        {
                            "spec": spec,
                            "line": line(stmt),
                            "names": [],
                            "namespace": alias,
                            "kind": "import",
                        }
                    )
                elif item.type == "dotted_name":
                    spec = text(item)
                    root = spec.split(".")[0]
                    self.imports.append(
                        {
                            "spec": spec,
                            "line": line(stmt),
                            "names": [],
                            "namespace": root,
                            "kind": "import",
                            "root": True,
                        }
                    )
        elif t == "import_from_statement":
            mod = stmt.child_by_field_name("module_name")
            spec = text(mod) if mod is not None else ""
            names = []
            for item in stmt.children_by_field_name("name"):
                if item.type == "aliased_import":
                    names.append(
                        [
                            text(item.child_by_field_name("name")),
                            text(item.child_by_field_name("alias")),
                        ]
                    )
                else:
                    names.append([text(item), text(item).split(".")[-1]])
            if spec:
                self.imports.append(
                    {"spec": spec, "line": line(stmt), "names": names, "kind": "import"}
                )
        elif t == "decorated_definition":
            definition = stmt.child_by_field_name("definition")
            if definition is not None:
                self._definition(definition, _decorators(stmt))
        elif t in ("function_definition", "class_definition"):
            self._definition(stmt, [])
        elif t == "expression_statement" and stmt.named_children:
            expr = stmt.named_children[0]
            if expr.type == "assignment":
                self._module_assign(expr)
        elif t in ("if_statement", "try_statement", "with_statement"):
            for block in stmt.named_children:
                if block.type == "block":
                    for inner in block.named_children:
                        self._top(inner)

    def _module_assign(self, expr: ts.Node) -> None:
        left, right = expr.child_by_field_name("left"), expr.child_by_field_name("right")
        if left is None or right is None or left.type != "identifier":
            return
        info: JSON = {"line": line(expr), "end": end_line(expr), "refs": sorted(_idents(right))}
        if right.type == "call":
            callee = py_chain(right.child_by_field_name("function"))
            if callee:
                info["callee"] = callee
            info["args"], info["kw"] = _call_args(right)
        elif right.type in ("list", "tuple"):
            info["items"] = len(right.named_children)
        value = py_string(right)
        if value is not None:
            info["string"] = value
        self.vars[text(left)] = info

    def _definition(self, node: ts.Node, decos: list[JSON]) -> None:
        if node.type == "function_definition":
            self._function(node, text(node.child_by_field_name("name")), decos, MODULE)
        elif node.type == "class_definition":
            self._class(node, decos)

    def _function(self, fn: ts.Node, key: str, decos: list[JSON], parent: str) -> str:
        if key in self.scopes:
            key = f"{key}@L{line(fn)}"
        params, defaults, annos = _params(fn)
        scope: JSON = {"line": line(fn), "end": end_line(fn), "calls": [], "refs": {}}
        if decos:
            scope["decorators"] = decos
            scope["line"] = min(d["line"] for d in decos)
        if params:
            scope["params"] = ["this" if p in ("self", "cls") else p for p in params]
        if defaults:
            scope["defaults"] = defaults
        if annos:
            scope["annos"] = annos
        if parent != MODULE:
            scope["parent"] = parent
        self.scopes[key] = scope
        self.fn_keys[(fn.start_byte, fn.end_byte)] = key
        body = fn.child_by_field_name("body")
        if body is not None:
            self._walk(body, key, skip_defs=False)
        return key

    def _class(self, node: ts.Node, decos: list[JSON]) -> None:
        name = text(node.child_by_field_name("name"))
        info: JSON = {"line": line(node), "end": end_line(node)}
        if decos:
            info["decorators"] = decos
        supers = node.child_by_field_name("superclasses")
        bases = (
            [text(b) for b in supers.named_children if b.type != "keyword_argument"]
            if supers
            else []
        )
        if bases:
            info["bases"] = bases
            info["extends"] = bases[0]
        base_kw = {
            text(b.child_by_field_name("name")): text(b.child_by_field_name("value"))
            for b in (supers.named_children if supers else [])
            if b.type == "keyword_argument"
        }
        if base_kw:
            info["baseKw"] = base_kw  # e.g. SQLModel's table=True
        fields: JSON = {}
        methods: JSON = {}
        meta: JSON = {}
        body = node.child_by_field_name("body")
        for stmt in body.named_children if body is not None else []:
            target, decorators = stmt, []
            if stmt.type == "decorated_definition":
                target = stmt.child_by_field_name("definition") or stmt
                decorators = _decorators(stmt)
            if target.type == "function_definition":
                mname = text(target.child_by_field_name("name"))
                key = self._function(target, f"{name}.{mname}", decorators, MODULE)
                methods[mname] = {"line": self.scopes[key]["line"], "end": end_line(target)}
                if decorators:
                    methods[mname]["decorators"] = decorators
            elif (
                target.type == "class_definition"
                and text(target.child_by_field_name("name")) == "Meta"
            ):
                inner = target.child_by_field_name("body")
                for m in inner.named_children if inner is not None else []:
                    if (
                        m.type == "expression_statement"
                        and m.named_children
                        and m.named_children[0].type == "assignment"
                    ):
                        a = m.named_children[0]
                        left, right = a.child_by_field_name("left"), a.child_by_field_name("right")
                        if left is not None and right is not None:
                            meta[text(left)] = py_describe(right)
            elif stmt.type == "expression_statement" and stmt.named_children:
                a = stmt.named_children[0]
                if a.type == "assignment":
                    left, right = a.child_by_field_name("left"), a.child_by_field_name("right")
                    if left is None or left.type != "identifier":
                        continue
                    field: JSON = {"line": line(a)}
                    anno = a.child_by_field_name("type")
                    if anno is not None:
                        field["type"] = text(anno)[:200]
                    if right is not None:
                        field["value"] = py_describe(right)
                    fields[text(left)] = field
        if fields:
            info["fields"] = fields
        if methods:
            info["methods"] = methods
        if meta:
            info["meta"] = meta
        self.classes[name] = info

    # --- bodies ----------------------------------------------------------------

    def _walk(self, node: ts.Node, scope: str, *, skip_defs: bool) -> None:
        stack = list(reversed(node.children))
        while stack:
            n = stack.pop()
            t = n.type
            if skip_defs and t in (
                "function_definition",
                "class_definition",
                "decorated_definition",
            ):
                if t == "decorated_definition":
                    # Decorator arguments run at import time: record their calls in the module.
                    stack.extend(reversed([c for c in n.children if c.type == "decorator"]))
                continue
            if not skip_defs and t in ("function_definition", "class_definition"):
                if t == "function_definition":
                    key = f"{scope}.{text(n.child_by_field_name('name'))}"
                    self._function(n, key, [], scope)
                continue
            if t == "call":
                self._call(n, scope)
            elif t == "subscript":
                if py_chain(n.child_by_field_name("value")) == ["os", "environ"]:
                    sub = n.child_by_field_name("subscript")
                    self._env(scope, py_string(sub), n)
            elif t == "attribute":
                c = py_chain(n)
                if c and len(c) == 2 and c[0] in REQUEST_NAMES and c[1] in BODY_ATTRS:
                    self.scopes[scope].setdefault("body", line(n))
            elif t == "identifier":
                self.scopes[scope]["refs"].setdefault(text(n), line(n))
            elif t == "assignment" and scope != MODULE:
                self._local(n, scope)
            elif t == "return_statement" and scope != MODULE and n.named_children:
                ret = n.named_children[0]
                if ret.type == "identifier":
                    self.scopes[scope].setdefault("returns", []).append(text(ret))
            stack.extend(reversed(n.children))

    def _call(self, node: ts.Node, scope: str) -> None:
        c = py_chain(node.child_by_field_name("function"))
        if c is None:
            return
        args, kw = _call_args(node)
        if c in ENV_CALLS and args and args[0]["k"] == "str":
            self._env(scope, args[0]["value"], node)
        if len(c) == 2 and c[0] in REQUEST_NAMES and c[1] in BODY_ATTRS:
            self.scopes[scope].setdefault("body", line(node))
        call: JSON = {"c": c, "l": line(node), "e": end_line(node)}
        if args:
            call["a"] = args
        if kw:
            call["kw"] = kw
        self.scopes[scope]["calls"].append(call)

    def _env(self, scope: str, name: str | None, node: ts.Node) -> None:
        if name and ENV_NAME.match(name):
            self.scopes[scope].setdefault("env", []).append([name, line(node)])

    def _local(self, node: ts.Node, scope: str) -> None:
        left, right = node.child_by_field_name("left"), node.child_by_field_name("right")
        if left is None or right is None or left.type != "identifier" or right.type != "call":
            return
        c = py_chain(right.child_by_field_name("function"))
        if c:
            self.scopes[scope].setdefault("locals", {})[text(left)] = {"l": line(node), "callee": c}

    def to_json(self) -> JSON:
        return {
            "lang": "py",
            "imports": self.imports,
            "reexports": [],
            "exports": {},
            "vars": self.vars,
            "classes": self.classes,
            "scopes": self.scopes,
        }


def _idents(node: ts.Node) -> set[str]:
    out: set[str] = set()
    stack = [node]
    while stack:
        n = stack.pop()
        if n.type == "identifier":
            out.add(text(n))
        elif n.type == "lambda":
            continue
        stack.extend(n.children)
    return out


def summarise(tree: ts.Tree) -> tuple[JSON, FnKeys]:
    s = _PySummary(tree.root_node)
    s.run()
    return s.to_json(), s.fn_keys
