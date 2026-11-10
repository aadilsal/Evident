"""Summarise one JS/TS module: imports, exports, module vars, function scopes, calls, env reads.

The summary is plain JSON so it can be cached per file. The linker resolves it across files.
"""

from __future__ import annotations

import re
from typing import Any

import tree_sitter as ts

from evident.syntax import chain, end_line, line, string_value, text, unwrap

JSON = dict[str, Any]
FnKeys = dict[tuple[int, int], str]

MODULE = "<module>"
FUNC_TYPES = frozenset(
    {
        "function_declaration",
        "generator_function_declaration",
        "function_expression",
        "function",
        "generator_function",
        "arrow_function",
        "method_definition",
    }
)
# Callbacks passed to these member calls are handlers, so they get their own scope even when nested.
CALLBACK_METHODS = frozenset(
    {"get", "post", "put", "patch", "delete", "del", "all", "head", "options", "use", "route"}
)
ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
MAX_STRINGS = 50


def _span(node: ts.Node) -> tuple[int, int]:
    return (node.start_byte, node.end_byte)


class _Summary:
    def __init__(self, root: ts.Node) -> None:
        self.root = root
        self.imports: list[JSON] = []
        self.reexports: list[JSON] = []
        self.exports: dict[str, str] = {}
        self.vars: dict[str, JSON] = {}
        self.classes: dict[str, JSON] = {}
        self.scopes: dict[str, JSON] = {}
        self.fn_keys: FnKeys = {}
        self._var_spans: dict[str, tuple[int, int]] = {}
        self.directive: str | None = None

    # --- scopes ------------------------------------------------------------

    def _new_scope(self, key: str, node: ts.Node) -> str:
        if key in self.scopes:
            key = f"{key}@L{line(node)}"
        self.scopes[key] = {"line": line(node), "end": end_line(node), "calls": [], "refs": {}}
        params = _param_names(node)
        if params:
            self.scopes[key]["params"] = params
        self.fn_keys[_span(node)] = key
        return key

    def _owner_of_object(self, obj: ts.Node) -> str | None:
        p = obj.parent
        if p is None:
            return None
        if p.type == "variable_declarator":
            return text(p.child_by_field_name("name")) or None
        if p.type == "export_statement":
            return "default"
        if p.type == "assignment_expression":
            left = chain(p.child_by_field_name("left"))
            if left == ["module", "exports"]:
                return "default"
        return None

    def _name_for(self, node: ts.Node) -> str:
        p = node.parent
        if node.type in ("function_declaration", "generator_function_declaration"):
            name = text(node.child_by_field_name("name"))
            if name:
                return name
        if node.type == "method_definition":
            method = text(node.child_by_field_name("name")).strip("'\"")
            container = p
            if container is not None and container.type == "class_body":
                cls = container.parent
                cname = text(cls.child_by_field_name("name")) if cls is not None else ""
                return f"{cname or 'default'}.{method}"
            if container is not None and container.type == "object":
                owner = self._owner_of_object(container)
                return f"{owner}.{method}" if owner else method
            return method
        if p is not None:
            if p.type == "variable_declarator" and p.child_by_field_name("value") == node:
                var = p.child_by_field_name("name")
                if var is not None and var.type == "identifier":
                    return text(var)
            if p.type == "pair":
                key = text(p.child_by_field_name("key")).strip("'\"")
                owner = self._owner_of_object(p.parent) if p.parent is not None else None
                return f"{owner}.{key}" if owner else key
            if p.type == "export_statement":
                return "default"
            if p.type == "assignment_expression":
                left = chain(p.child_by_field_name("left"))
                if left == ["module", "exports"]:
                    return "default"
                if left and len(left) >= 2 and left[:-1] in (["exports"], ["module", "exports"]):
                    return left[-1]
        return f"L{line(node)}"

    def _is_callback_arg(self, node: ts.Node) -> bool:
        p = node.parent
        if p is None or p.type != "arguments" or p.parent is None:
            return False
        fn = p.parent.child_by_field_name("function")
        if fn is None or fn.type != "member_expression":
            return False
        return text(fn.child_by_field_name("property")) in CALLBACK_METHODS

    # --- walk --------------------------------------------------------------

    def run(self) -> None:
        self.scopes[MODULE] = {
            "line": 1,
            "end": end_line(self.root),
            "calls": [],
            "refs": {},
        }
        first = self.root.named_children[0] if self.root.named_children else None
        if first is not None and first.type == "expression_statement":
            value = string_value(first.named_children[0]) if first.named_children else None
            if value in ("use server", "use client"):
                self.directive = value
        for child in self.root.named_children:
            self._top_level(child)
        stack: list[tuple[ts.Node, str]] = [(c, MODULE) for c in reversed(self.root.children)]
        while stack:
            node, scope = stack.pop()
            t = node.type
            if t in FUNC_TYPES and (scope == MODULE or self._is_callback_arg(node)):
                parent = scope
                scope = self._new_scope(self._name_for(node), node)
                if parent != MODULE:
                    self.scopes[scope]["parent"] = parent
            elif t in ("import_statement",):
                continue
            elif t == "call_expression":
                self._call(node, scope)
            elif t == "new_expression":
                c = chain(node.child_by_field_name("constructor"))
                if c:
                    self._record_call(scope, c, node, new=True)
            elif t == "member_expression":
                obj = node.child_by_field_name("object")
                obj_chain = chain(obj)
                if obj_chain == ["process", "env"]:
                    self._env(scope, text(node.child_by_field_name("property")), node)
                elif (
                    obj_chain is not None
                    and len(obj_chain) == 1
                    and text(node.child_by_field_name("property")) == "body"
                    and self._is_request(scope, obj_chain[0])
                ):
                    self.scopes[scope].setdefault("body", line(node))
            elif t == "subscript_expression":
                obj = node.child_by_field_name("object")
                if chain(obj) == ["process", "env"]:
                    self._env(scope, string_value(node.child_by_field_name("index")), node)
            elif t in ("identifier", "shorthand_property_identifier"):
                refs = self.scopes[scope]["refs"]
                refs.setdefault(text(node), line(node))
            elif t == "variable_declarator":
                self._destructured_env(node, scope)
                if scope != MODULE:
                    self._local(node, scope)
            elif t == "return_statement" and scope != MODULE and node.named_children:
                ret = unwrap(node.named_children[0])
                if ret.type == "identifier":
                    self.scopes[scope].setdefault("returns", []).append(text(ret))
            stack.extend((c, scope) for c in reversed(node.children))
        self._link_var_fns()

    def _local(self, node: ts.Node, scope: str) -> None:
        """Function-local bindings made by a call or `new` (factories: `const r = Router()`)."""
        name, value = node.child_by_field_name("name"), node.child_by_field_name("value")
        if name is None or value is None or name.type != "identifier":
            return
        v = unwrap(value)
        info: JSON = {"l": line(node)}
        if v.type == "call_expression":
            c = chain(v.child_by_field_name("function"))
            if c:
                info["callee"] = c
        elif v.type == "new_expression":
            c = chain(v.child_by_field_name("constructor"))
            if c:
                info["new"] = c
        if len(info) > 1:
            self.scopes[scope].setdefault("locals", {})[text(name)] = info

    def _record_call(self, scope: str, c: list[str], node: ts.Node, *, new: bool = False) -> None:
        call: JSON = {"c": c, "l": line(node), "e": end_line(node)}
        if new:
            call["new"] = True
        self.scopes[scope]["calls"].append(call)

    def _call(self, node: ts.Node, scope: str) -> None:
        fn = node.child_by_field_name("function")
        if fn is None:
            return
        if fn.type == "import":
            spec = _first_string_arg(node)
            if spec:
                self.imports.append(
                    {"spec": spec, "line": line(node), "names": [], "kind": "dynamic"}
                )
            return
        c = chain(fn)
        if c is None:
            return
        if c == ["require"]:
            spec = _first_string_arg(node)
            if spec and not _is_declared_require(node):
                self.imports.append(
                    {"spec": spec, "line": line(node), "names": [], "kind": "require"}
                )
            return
        if len(c) == 2 and c[1] in ("json", "formData") and self._is_request(scope, c[0]):
            self.scopes[scope].setdefault("body", line(node))
        self._record_call(scope, c, node)

    def _is_request(self, scope: str, name: str) -> bool:
        """`req`/`request`, or the first parameter of the handler scope."""
        if name in ("req", "request"):
            return True
        params = self.scopes.get(scope, {}).get("params", [])
        return bool(params) and params[0] == name

    def _env(self, scope: str, name: str | None, node: ts.Node) -> None:
        if name and ENV_NAME.match(name):
            self.scopes[scope].setdefault("env", []).append([name, line(node)])

    def _destructured_env(self, node: ts.Node, scope: str) -> None:
        name, value = node.child_by_field_name("name"), node.child_by_field_name("value")
        if name is None or value is None or name.type != "object_pattern":
            return
        if chain(unwrap(value)) == ["process", "env"]:
            for key in _pattern_keys(name):
                self._env(scope, key[0], node)

    # --- module-level statements -------------------------------------------

    def _top_level(self, node: ts.Node) -> None:
        t = node.type
        if t == "import_statement":
            self._import(node)
        elif t == "export_statement":
            self._export(node)
        elif t in ("lexical_declaration", "variable_declaration"):
            self._declaration(node, exported=False)
        elif t == "class_declaration":
            self._class(node)
        elif t == "expression_statement" and node.named_children:
            expr = node.named_children[0]
            if expr.type == "assignment_expression":
                self._cjs_export(expr)

    def _import(self, node: ts.Node) -> None:
        if any(c.type == "type" for c in node.children):
            return  # type-only imports have no runtime effect
        spec = string_value(node.child_by_field_name("source"))
        if not spec:
            return
        imp: JSON = {"spec": spec, "line": line(node), "names": [], "kind": "import"}
        clause = next((c for c in node.named_children if c.type == "import_clause"), None)
        for part in clause.named_children if clause is not None else []:
            if part.type == "identifier":
                imp["default"] = text(part)
            elif part.type == "namespace_import":
                ident = next((c for c in part.named_children if c.type == "identifier"), None)
                if ident is not None:
                    imp["namespace"] = text(ident)
            elif part.type == "named_imports":
                for spec_node in part.named_children:
                    if spec_node.type != "import_specifier":
                        continue
                    if any(c.type == "type" for c in spec_node.children):
                        continue
                    name = text(spec_node.child_by_field_name("name"))
                    alias = text(spec_node.child_by_field_name("alias")) or name
                    imp["names"].append([name, alias])
        self.imports.append(imp)

    def _export(self, node: ts.Node) -> None:
        source = node.child_by_field_name("source")
        clause = next((c for c in node.named_children if c.type == "export_clause"), None)
        if source is not None:
            spec = string_value(source)
            if not spec:
                return
            re_exp: JSON = {"spec": spec, "line": line(node), "names": [], "star": False}
            if clause is not None:
                for s in clause.named_children:
                    if s.type == "export_specifier":
                        name = text(s.child_by_field_name("name"))
                        alias = text(s.child_by_field_name("alias")) or name
                        re_exp["names"].append([name, alias])
            else:
                ns = next((c for c in node.named_children if c.type == "namespace_export"), None)
                if ns is not None:
                    re_exp["names"].append(["*", text(ns.named_children[-1])])
                else:
                    re_exp["star"] = True
            self.reexports.append(re_exp)
            return
        if clause is not None:
            for s in clause.named_children:
                if s.type == "export_specifier":
                    name = text(s.child_by_field_name("name"))
                    alias = text(s.child_by_field_name("alias")) or name
                    self.exports[alias] = name
            return
        is_default = any(c.type == "default" for c in node.children)
        decl = node.child_by_field_name("declaration")
        if decl is not None:
            name = text(decl.child_by_field_name("name"))
            if decl.type in ("lexical_declaration", "variable_declaration"):
                self._declaration(decl, exported=True)
                return
            if decl.type in ("class_declaration", "abstract_class_declaration"):
                self._class(decl)
            if name:
                self.exports["default" if is_default else name] = name
            elif is_default:
                self.exports["default"] = "default"
            return
        value = node.child_by_field_name("value")
        if value is None:
            value = next((c for c in node.named_children if c.type != "comment"), None)
        if value is None:
            return
        value = unwrap(value)
        if value.type == "identifier":
            self.exports["default"] = text(value)
        elif value.type in FUNC_TYPES:
            self.exports["default"] = "default"
        else:
            self._pseudo_var("default", value)
            self.exports["default"] = "default"

    def _declaration(self, node: ts.Node, *, exported: bool) -> None:
        for decl in node.named_children:
            if decl.type != "variable_declarator":
                continue
            name, value = decl.child_by_field_name("name"), decl.child_by_field_name("value")
            if name is None:
                continue
            if value is not None and _require_spec(value):
                self._require_binding(name, value, decl)
                continue
            if name.type == "identifier":
                if value is not None:
                    self._pseudo_var(text(name), value, decl)
                else:
                    self.vars[text(name)] = {"line": line(decl), "refs": []}
                if exported:
                    self.exports[text(name)] = text(name)
            elif name.type in ("object_pattern", "array_pattern") and value is not None:
                for key, local in _pattern_keys(name):
                    self._pseudo_var(local, value, decl)
                    self.vars[local]["member"] = key
                    if exported:
                        self.exports[local] = local

    def _pseudo_var(self, name: str, value: ts.Node, decl: ts.Node | None = None) -> None:
        v = unwrap(value)
        info: JSON = {"line": line(decl or value), "refs": sorted(_refs_outside_functions(v))}
        if v.type == "call_expression":
            c = chain(v.child_by_field_name("function"))
            if c:
                info["callee"] = c
        elif v.type == "new_expression":
            c = chain(v.child_by_field_name("constructor"))
            if c:
                info["new"] = c
        if name == "config":
            info["strings"] = _strings(v)[:MAX_STRINGS]
        self.vars[name] = info
        self._var_spans[name] = _span(v)

    def _require_binding(self, name: ts.Node, value: ts.Node, decl: ts.Node) -> None:
        spec = _require_spec(value)
        imp: JSON = {"spec": spec, "line": line(decl), "names": [], "kind": "require"}
        if name.type == "identifier":
            imp["default"] = text(name)
            imp["cjs"] = True
        elif name.type == "object_pattern":
            imp["names"] = [[k, local] for k, local in _pattern_keys(name)]
        self.imports.append(imp)

    def _class(self, node: ts.Node) -> None:
        name = text(node.child_by_field_name("name"))
        if not name:
            return
        info: JSON = {"line": line(node), "end": end_line(node)}
        decos = [d for d in node.children if d.type == "decorator"]
        if node.parent is not None and node.parent.type == "export_statement":
            decos = [d for d in node.parent.children if d.type == "decorator"] + decos
        if decos:
            info["decorators"] = [_decorator(d) for d in decos]
        heritage = next((c for c in node.named_children if c.type == "class_heritage"), None)
        if heritage is not None:
            ext = next((c for c in heritage.named_children if c.type == "extends_clause"), heritage)
            value = ext.child_by_field_name("value") or (
                ext.named_children[0] if ext.named_children else None
            )
            if value is not None:
                info["extends"] = text(value)
        body = node.child_by_field_name("body")
        fields: JSON = {}
        methods: JSON = {}
        pending: list[JSON] = []
        for member in body.named_children if body is not None else []:
            if member.type == "decorator":
                pending.append(_decorator(member))
                continue
            if member.type == "method_definition":
                mname = text(member.child_by_field_name("name"))
                if mname == "constructor":
                    fields.update(_ctor_fields(member))
                else:
                    entry: JSON = {"line": line(member), "end": end_line(member)}
                    if pending:
                        entry["decorators"] = pending
                    methods[mname] = entry
            elif member.type in ("public_field_definition", "field_definition"):
                fname = text(member.child_by_field_name("name"))
                own = [_decorator(d) for d in member.children if d.type == "decorator"]
                field: JSON = {"line": line(member)}
                ftype = member.child_by_field_name("type")
                if ftype is not None:
                    field["type"] = text(ftype).lstrip(":").strip()
                if own or pending:
                    field["decorators"] = pending + own
                if fname:
                    fields[fname] = field
            pending = []
        if fields:
            info["fields"] = fields
        if methods:
            info["methods"] = methods
        self.classes[name] = info

    def _cjs_export(self, expr: ts.Node) -> None:
        left = chain(expr.child_by_field_name("left"))
        right = expr.child_by_field_name("right")
        if left is None or right is None:
            return
        right = unwrap(right)
        if left == ["module", "exports"]:
            target = "default"
        elif len(left) >= 2 and left[:-1] in (["exports"], ["module", "exports"]):
            target = left[-1]
        else:
            return
        if right.type == "identifier":
            self.exports[target] = text(right)
        elif right.type in FUNC_TYPES:
            self.exports[target] = target
        elif right.type == "object" and target == "default":
            for prop in right.named_children:
                if prop.type == "shorthand_property_identifier":
                    self.exports[text(prop)] = text(prop)
                elif prop.type == "pair":
                    key = text(prop.child_by_field_name("key")).strip("'\"")
                    val = prop.child_by_field_name("value")
                    if val is not None and val.type == "identifier":
                        self.exports[key] = text(val)
            self._pseudo_var("default", right)
            self.exports["default"] = "default"
        else:
            self._pseudo_var(target, right)
            self.exports[target] = target

    def _link_var_fns(self) -> None:
        spans = {key: span for span, key in self.fn_keys.items()}
        for name, (start, end) in self._var_spans.items():
            fns = [k for k, (s, e) in spans.items() if s >= start and e <= end]
            if fns:
                self.vars[name]["fns"] = sorted(fns, key=lambda k: spans[k])

    def to_json(self) -> JSON:
        out: JSON = {
            "imports": self.imports,
            "reexports": self.reexports,
            "exports": self.exports,
            "vars": self.vars,
            "classes": self.classes,
            "scopes": self.scopes,
        }
        if self.directive:
            out["directive"] = self.directive
        return out


def _param_names(fn: ts.Node) -> list[str]:
    single = fn.child_by_field_name("parameter")
    if single is not None and single.type == "identifier":
        return [text(single)]
    params = fn.child_by_field_name("parameters")
    out = []
    for p in params.named_children if params is not None else []:
        if p.type in ("required_parameter", "optional_parameter"):
            p = p.child_by_field_name("pattern") or p
        if p.type == "assignment_pattern":
            p = p.child_by_field_name("left") or p
        out.append(text(p) if p.type == "identifier" else "")
    return out


def _deco_arg(node: ts.Node) -> JSON:
    n = unwrap(node)
    value = string_value(n)
    if value is not None:
        return {"k": "str", "value": value}
    if n.type == "identifier":
        return {"k": "id", "name": text(n)}
    if n.type == "arrow_function":
        body = n.child_by_field_name("body")
        if body is not None and unwrap(body).type == "identifier":
            return {"k": "id", "name": text(unwrap(body))}
        return {"k": "fn"}
    if n.type == "member_expression":
        c = chain(n)
        return {"k": "member", "chain": c} if c else {"k": "other"}
    if n.type == "object":
        props: JSON = {}
        for pair in n.named_children:
            if pair.type == "pair":
                key = text(pair.child_by_field_name("key")).strip("'\"")
                val = pair.child_by_field_name("value")
                if val is not None:
                    props[key] = _deco_arg(val)
        return {"k": "obj", "props": props}
    if n.type == "array":
        return {"k": "array", "items": [_deco_arg(c) for c in n.named_children]}
    if n.type in ("call_expression", "new_expression"):
        fn = n.child_by_field_name("function") or n.child_by_field_name("constructor")
        args = n.child_by_field_name("arguments")
        return {
            "k": "call",
            "chain": chain(fn),
            "args": [_deco_arg(a) for a in args.named_children] if args is not None else [],
        }
    return {"k": "other"}


def _decorator(node: ts.Node) -> JSON:
    """`@Get(':id')` -> {"name": "Get", "args": [...], "line": n}."""
    expr = next((c for c in node.named_children), None)
    out: JSON = {"name": "", "args": [], "line": line(node)}
    if expr is None:
        return out
    if expr.type == "call_expression":
        c = chain(expr.child_by_field_name("function"))
        args = expr.child_by_field_name("arguments")
        out["name"] = ".".join(c) if c else ""
        out["args"] = [_deco_arg(a) for a in args.named_children] if args is not None else []
    else:
        c = chain(expr)
        out["name"] = ".".join(c) if c else ""
    return out


def _ctor_fields(ctor: ts.Node) -> JSON:
    """Constructor parameter properties: `constructor(private users: UsersService)`."""
    out: JSON = {}
    params = ctor.child_by_field_name("parameters")
    for p in params.named_children if params is not None else []:
        if p.type not in ("required_parameter", "optional_parameter"):
            continue
        if not any(c.type in ("accessibility_modifier", "readonly") for c in p.children):
            continue
        pattern = p.child_by_field_name("pattern")
        if pattern is None or pattern.type != "identifier":
            continue
        field: JSON = {"line": line(p)}
        ptype = p.child_by_field_name("type")
        if ptype is not None:
            field["type"] = text(ptype).lstrip(":").strip()
        decos = [_decorator(d) for d in p.children if d.type == "decorator"]
        if decos:
            field["decorators"] = decos
        out[text(pattern)] = field
    return out


def _first_string_arg(call: ts.Node) -> str | None:
    args = call.child_by_field_name("arguments")
    if args is None or not args.named_children:
        return None
    return string_value(args.named_children[0])


def _require_spec(value: ts.Node) -> str | None:
    v = unwrap(value)
    if v.type == "call_expression" and chain(v.child_by_field_name("function")) == ["require"]:
        return _first_string_arg(v)
    return None


def _is_declared_require(call: ts.Node) -> bool:
    """`const x = require('y')` at module level is recorded as a binding, not twice."""
    p = call.parent
    while p is not None and p.type in ("await_expression", "parenthesized_expression"):
        p = p.parent
    return (
        p is not None
        and p.type == "variable_declarator"
        and p.parent is not None
        and p.parent.parent is not None
        and p.parent.parent.type in ("program", "export_statement")
    )


def _pattern_keys(pattern: ts.Node) -> list[tuple[str, str]]:
    """Object pattern -> [(property, local)]."""
    out = []
    for prop in pattern.named_children:
        if prop.type == "shorthand_property_identifier_pattern":
            out.append((text(prop), text(prop)))
        elif prop.type == "pair_pattern":
            key = text(prop.child_by_field_name("key")).strip("'\"")
            val = prop.child_by_field_name("value")
            if val is not None and val.type == "assignment_pattern":
                val = val.child_by_field_name("left")
            if val is not None and val.type == "identifier":
                out.append((key, text(val)))
        elif prop.type == "object_assignment_pattern":
            left = prop.child_by_field_name("left")
            if left is not None:
                out.append((text(left), text(left)))
        elif prop.type == "identifier":  # array pattern element
            out.append((text(prop), text(prop)))
    return out


def _refs_outside_functions(node: ts.Node) -> set[str]:
    out: set[str] = set()
    stack = [node]
    while stack:
        n = stack.pop()
        if n.type in FUNC_TYPES:
            continue
        if n.type in ("identifier", "shorthand_property_identifier"):
            out.add(text(n))
        stack.extend(n.children)
    return out


def _strings(node: ts.Node) -> list[str]:
    out: list[str] = []
    stack = [node]
    while stack:
        n = stack.pop()
        value = string_value(n)
        if value is not None:
            out.append(value)
            continue
        stack.extend(reversed(n.children))
    return out


def summarise(tree: ts.Tree) -> tuple[JSON, FnKeys]:
    s = _Summary(tree.root_node)
    s.run()
    return s.to_json(), s.fn_keys
