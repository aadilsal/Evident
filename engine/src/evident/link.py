"""Cross-file linking. Per-file summaries in, one graph out.

Resolves module specifiers (relative, tsconfig paths, workspaces), symbols through imports and
re-exports, and which bindings come from which npm package. Adapters and the universal layer
then build nodes and edges through `LinkContext`.
"""

from __future__ import annotations

import posixpath
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any

from evident.models import Edge, Evidence, Node

JSON = dict[str, Any]
CODE_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts")
MAX_EVIDENCE = 10
MAX_DEPTH = 16
# Names that signal an authentication or authorisation step (middleware, wrappers, calls).
AUTH_RE = re.compile(
    r"(?i)(auth|session|jwt|token|protect|guard|login|logged|permission|currentuser|"
    r"requireuser|clerk|passport|acl|rbac|role)"
)


@dataclass(frozen=True)
class Sym:
    """A name defined at module level in a first-party file."""

    file: str
    name: str


@dataclass(frozen=True)
class Pkg:
    """A binding imported from an npm package (or an unresolvable specifier)."""

    package: str
    imported: str


@dataclass(frozen=True)
class Ns:
    """A namespace / CommonJS module object for a first-party file."""

    file: str


Target = Sym | Pkg | Ns
FnKey = tuple[str, str]  # (file, scope key)


def package_name(spec: str) -> str:
    spec = spec.removeprefix("node:")
    parts = spec.split("/")
    return "/".join(parts[:2]) if spec.startswith("@") and len(parts) > 1 else parts[0]


def _norm(path: str) -> str | None:
    p = posixpath.normpath(path)
    if p.startswith("../") or p == ".." or p.startswith("/"):
        return None
    return "" if p == "." else p


class Project:
    def __init__(self, raw: dict[str, JSON]) -> None:
        self.raw = raw
        self.js: dict[str, JSON] = {p: r["js"] for p, r in raw.items() if "js" in r}
        self.packages: dict[str, JSON] = {
            posixpath.dirname(p): r["package"] for p, r in raw.items() if "package" in r
        }
        self.tsconfigs: dict[str, JSON] = {
            p: r["tsconfig"] for p, r in raw.items() if "tsconfig" in r
        }
        self.workspaces = {
            str(pkg["name"]): d
            for d, pkg in self.packages.items()
            if isinstance(pkg.get("name"), str)
        }
        self._imports: dict[str, dict[str, tuple[JSON, str]]] = {}
        self._spec_cache: dict[tuple[str, str], tuple[str, str] | None] = {}
        self._alias_cache: dict[str, list[tuple[str, JSON]]] = {}
        self._resolve_cache: dict[tuple[str, str], Target | None] = {}
        self._export_cache: dict[tuple[str, str], Target | None] = {}
        self._taint_cache: dict[tuple[str, str], frozenset[Pkg]] = {}

    # --- modules -----------------------------------------------------------

    def _file(self, base: str | None) -> str | None:
        if base is None:
            return None
        if base in self.js:
            return base
        for ext in CODE_EXTS:
            if base + ext in self.js:
                return base + ext
        for ext in CODE_EXTS:
            cand = posixpath.join(base, "index" + ext) if base else "index" + ext
            if cand in self.js:
                return cand
        stem, ext = posixpath.splitext(base)
        if ext in (".js", ".jsx", ".mjs", ".cjs"):
            for ts_ext in (".ts", ".tsx", ".mts", ".cts"):
                if stem + ts_ext in self.js:
                    return stem + ts_ext
        return None

    def _alias_configs(self, directory: str) -> list[tuple[str, JSON]]:
        """(config dir, merged compilerOptions) for the nearest tsconfig/jsconfig above a dir."""
        if directory in self._alias_cache:
            return self._alias_cache[directory]
        found: list[tuple[str, JSON]] = []
        d: str | None = directory
        while d is not None:
            for name in ("tsconfig.json", "jsconfig.json"):
                path = posixpath.join(d, name) if d else name
                if path in self.tsconfigs:
                    cfg = self._merged_tsconfig(path, 0)
                    if cfg.get("paths") or cfg.get("baseUrl"):
                        found.append((cfg.pop("_dir", d), cfg))
            if found:
                break
            d = None if d == "" else posixpath.dirname(d)
        self._alias_cache[directory] = found
        return found

    def _merged_tsconfig(self, path: str, depth: int) -> JSON:
        own = dict(self.tsconfigs.get(path, {}))
        own_dir = posixpath.dirname(path)
        merged: JSON = {}
        ext = own.get("extends")
        if isinstance(ext, str) and ext.startswith(".") and depth < 5:
            target = _norm(posixpath.join(own_dir, ext))
            if target is not None:
                if not target.endswith(".json"):
                    target += ".json"
                merged = self._merged_tsconfig(target, depth + 1)
        if "paths" in own or "baseUrl" in own:
            merged = {k: v for k, v in merged.items() if k not in ("paths", "baseUrl", "_dir")}
            merged["_dir"] = own_dir
        merged.update({k: v for k, v in own.items() if k in ("paths", "baseUrl")})
        merged.setdefault("_dir", own_dir)
        return merged

    def resolve_spec(self, from_file: str, spec: str) -> tuple[str, str] | None:
        """("file", path) for first-party modules, ("pkg", name) for packages."""
        key = (from_file, spec)
        if key not in self._spec_cache:
            self._spec_cache[key] = self._resolve_spec(from_file, spec)
        return self._spec_cache[key]

    def _resolve_spec(self, from_file: str, spec: str) -> tuple[str, str] | None:
        directory = posixpath.dirname(from_file)
        if spec.startswith((".", "/")):
            if spec.startswith("/"):
                return None
            hit = self._file(_norm(posixpath.join(directory, spec)))
            return ("file", hit) if hit else None
        for cfg_dir, cfg in self._alias_configs(directory):
            base = _norm(posixpath.join(cfg_dir, cfg.get("baseUrl") or "."))
            if base is None:
                continue
            for pattern, targets in (cfg.get("paths") or {}).items():
                prefix, star, suffix = pattern.partition("*")
                if star and spec.startswith(prefix) and spec.endswith(suffix):
                    middle = spec[len(prefix) : len(spec) - len(suffix) if suffix else None]
                elif not star and spec == pattern:
                    middle = ""
                else:
                    continue
                for t in targets:
                    hit = self._file(_norm(posixpath.join(base, t.replace("*", middle))))
                    if hit:
                        return ("file", hit)
            if cfg.get("baseUrl"):
                hit = self._file(_norm(posixpath.join(base, spec)))
                if hit:
                    return ("file", hit)
        for name in sorted(self.workspaces, key=len, reverse=True):
            if spec != name and not spec.startswith(name + "/"):
                continue
            root = self.workspaces[name]
            rest = spec[len(name) + 1 :]
            pkg = self.packages.get(root, {})
            bases = (
                [rest]
                if rest
                else [pkg.get(k) for k in ("main", "module", "types")] + ["src/index", "index"]
            )
            for b in bases:
                if isinstance(b, str):
                    hit = self._file(_norm(posixpath.join(root, b)))
                    if hit:
                        return ("file", hit)
            if rest:
                hit = self._file(_norm(posixpath.join(root, "src", rest)))
                if hit:
                    return ("file", hit)
        return ("pkg", package_name(spec))

    def module_deps(self, file: str) -> Iterator[tuple[str, int]]:
        """First-party files a module imports or re-exports, with the statement line."""
        s = self.js.get(file, {})
        for entry in [*s.get("imports", []), *s.get("reexports", [])]:
            res = self.resolve_spec(file, entry["spec"])
            if res is not None and res[0] == "file" and res[1] != file:
                yield res[1], entry["line"]

    # --- symbols -----------------------------------------------------------

    def imports_of(self, file: str) -> dict[str, tuple[JSON, str]]:
        if file not in self._imports:
            table: dict[str, tuple[JSON, str]] = {}
            for imp in self.js.get(file, {}).get("imports", []):
                if imp.get("default"):
                    table[imp["default"]] = (imp, "default")
                if imp.get("namespace"):
                    table[imp["namespace"]] = (imp, "*")
                for imported, local in imp.get("names", []):
                    table[local] = (imp, imported)
            self._imports[file] = table
        return self._imports[file]

    def resolve(self, file: str, name: str, depth: int = 0) -> Target | None:
        key = (file, name)
        if key in self._resolve_cache:
            return self._resolve_cache[key]
        self._resolve_cache[key] = None  # cycle guard
        result = self._resolve(file, name, depth)
        self._resolve_cache[key] = result
        return result

    def _resolve(self, file: str, name: str, depth: int) -> Target | None:
        s = self.js.get(file)
        if s is None or depth > MAX_DEPTH:
            return None
        hit = self.imports_of(file).get(name)
        if hit is not None:
            imp, imported = hit
            res = self.resolve_spec(file, imp["spec"])
            if res is None:
                return Pkg(imp["spec"], imported)
            if res[0] == "pkg":
                return Pkg(res[1], imported)
            target = res[1]
            if imported == "*":
                return Ns(target)
            if imp.get("cjs"):
                return self.resolve_export(target, "default", depth + 1) or Ns(target)
            return self.resolve_export(target, imported, depth + 1)
        if name in s["scopes"] or name in s["vars"] or name in s["classes"]:
            return Sym(file, name)
        return None

    def resolve_export(self, file: str, exported: str, depth: int = 0) -> Target | None:
        key = (file, exported)
        if key in self._export_cache:
            return self._export_cache[key]
        self._export_cache[key] = None
        result = self._resolve_export(file, exported, depth)
        self._export_cache[key] = result
        return result

    def _resolve_export(self, file: str, exported: str, depth: int) -> Target | None:
        s = self.js.get(file)
        if s is None or depth > MAX_DEPTH:
            return None
        local = s["exports"].get(exported)
        if local is not None:
            return self.resolve(file, local, depth + 1) or Sym(file, local)
        for re_exp in s["reexports"]:
            res = self.resolve_spec(file, re_exp["spec"])
            for imported, alias in re_exp["names"]:
                if alias != exported:
                    continue
                if res is None or res[0] == "pkg":
                    return Pkg(res[1] if res else re_exp["spec"], imported)
                if imported == "*":
                    return Ns(res[1])
                return self.resolve_export(res[1], imported, depth + 1)
        for re_exp in s["reexports"]:
            if re_exp["star"]:
                res = self.resolve_spec(file, re_exp["spec"])
                if res is not None and res[0] == "file":
                    hit = self.resolve_export(res[1], exported, depth + 1)
                    if hit is not None:
                        return hit
        return None

    def taint(self, file: str, name: str) -> frozenset[Pkg]:
        """Packages a binding derives from (`const db = new PrismaClient()` -> @prisma/client)."""
        key = (file, name)
        if key in self._taint_cache:
            return self._taint_cache[key]
        self._taint_cache[key] = frozenset()
        target = self.resolve(file, name)
        out: set[Pkg] = set()
        if isinstance(target, Pkg):
            out.add(target)
        elif isinstance(target, Sym):
            var = self.js[target.file]["vars"].get(target.name)
            if var is not None:
                for ref in var.get("refs", []):
                    if ref != target.name:
                        out |= self.taint(target.file, ref)
        result = frozenset(out)
        self._taint_cache[key] = result
        return result

    def scope_of(self, target: Target | None, depth: int = 0) -> FnKey | None:
        """The function scope a symbol names, seeing through `const h = wrap(async () => …)`."""
        if not isinstance(target, Sym) or depth > MAX_DEPTH:
            return None
        s = self.js[target.file]
        if target.name in s["scopes"]:
            return (target.file, target.name)
        var = s["vars"].get(target.name)
        if var is None:
            return None
        if var.get("fns"):
            return (target.file, var["fns"][0])
        refs = var.get("refs", [])
        if len(refs) == 1 and "callee" not in var and "new" not in var:
            return self.scope_of(self.resolve(target.file, refs[0]), depth + 1)
        return None

    def member_scope(self, file: str, obj: str, prop: str) -> FnKey | None:
        """`obj.prop` where obj is a namespace import, an object literal or a class instance."""
        target = self.resolve(file, obj)
        if isinstance(target, Ns):
            return self.scope_of(self.resolve_export(target.file, prop))
        if isinstance(target, Sym):
            s = self.js[target.file]
            if f"{target.name}.{prop}" in s["scopes"]:
                return (target.file, f"{target.name}.{prop}")
            if target.name == "default":  # CommonJS `module.exports = { fn, ... }`
                hit = self.scope_of(self.resolve_export(target.file, prop))
                if hit is not None:
                    return hit
            var = s["vars"].get(target.name)
            ctor = (var or {}).get("new")
            if ctor and len(ctor) == 1:
                cls = self.resolve(target.file, ctor[0])
                if isinstance(cls, Sym):
                    key = f"{cls.name}.{prop}"
                    if key in self.js[cls.file]["scopes"]:
                        return (cls.file, key)
        return None


# --- graph building -----------------------------------------------------------


def fn_ref(key: FnKey) -> str:
    """Placeholder id for a function whose role (handler/middleware/function) isn't final yet."""
    return f"\0fn:{key[0]}#{key[1]}"


ROLE_RANK = {"function": 0, "middleware": 1, "handler": 2}


@dataclass
class _PendingEdge:
    type: str
    src: str
    dst: str
    evidence: list[Evidence]
    attrs: JSON
    source: str
    confidence: float


@dataclass
class LinkContext:
    project: Project
    sha: str
    nodes: dict[str, Node] = field(default_factory=dict)
    pending: dict[tuple[str, str, str], _PendingEdge] = field(default_factory=dict)
    roles: dict[FnKey, str] = field(default_factory=dict)
    entries: set[FnKey] = field(default_factory=set)
    auth_wrapped: set[FnKey] = field(default_factory=set)
    fn_meta: dict[FnKey, JSON] = field(default_factory=dict)  # middleware framework/name
    models: dict[str, str] = field(default_factory=dict)  # client accessor -> model name
    adapters: list[str] = field(default_factory=list)

    def ev(self, file: str, start: int, end: int | None = None) -> Evidence:
        return Evidence(file, start, max(end or start, start), self.sha)

    def node(
        self,
        node_id: str,
        node_type: str,
        label: str,
        evidence: Iterable[Evidence],
        attrs: JSON,
        *,
        source: str = "extracted",
        confidence: float = 1.0,
    ) -> str:
        evidence = list(evidence)
        existing = self.nodes.get(node_id)
        if existing is not None:
            existing.evidence = sorted({*existing.evidence, *evidence}, key=lambda e: e.ref)[
                :MAX_EVIDENCE
            ]
            if source == "extracted":
                existing.source = "extracted"
            existing.confidence = max(existing.confidence, confidence)
            return node_id
        self.nodes[node_id] = Node(
            node_id,
            node_type,
            label,
            sorted(set(evidence), key=lambda e: e.ref)[:MAX_EVIDENCE],
            attrs,
            "extracted" if source == "extracted" else "inferred",
            confidence,
        )
        return node_id

    def edge(
        self,
        edge_type: str,
        src: str,
        dst: str,
        evidence: Iterable[Evidence],
        attrs: JSON | None = None,
        *,
        source: str = "extracted",
        confidence: float = 1.0,
    ) -> None:
        evidence = list(evidence)
        key = (edge_type, src, dst)
        cur = self.pending.get(key)
        if cur is None:
            self.pending[key] = _PendingEdge(
                edge_type, src, dst, evidence, dict(attrs or {}), source, confidence
            )
            return
        cur.evidence = [*cur.evidence, *evidence]
        if source == "extracted":
            cur.source = "extracted"
        cur.confidence = max(cur.confidence, confidence)

    def mark(self, key: FnKey, role: str) -> str:
        if ROLE_RANK[role] > ROLE_RANK[self.roles.get(key, "function")]:
            self.roles[key] = role
        if role != "function":
            self.entries.add(key)
        return fn_ref(key)

    def fn_id(self, key: FnKey) -> str:
        return f"{self.roles.get(key, 'function')}:{key[0]}#{key[1]}"

    def real_id(self, ref: str) -> str:
        if ref.startswith("\0fn:"):
            file, _, scope = ref[4:].partition("#")
            return self.fn_id((file, scope))
        return ref

    def finish(self) -> list[Edge]:
        edges: dict[str, Edge] = {}
        for p in self.pending.values():
            src, dst = self.real_id(p.src), self.real_id(p.dst)
            if src not in self.nodes or dst not in self.nodes or src == dst:
                continue
            edge_id = f"{p.type}:{src}->{dst}"
            evidence = sorted(set(p.evidence), key=lambda e: e.ref)[:MAX_EVIDENCE]
            prev = edges.get(edge_id)
            if prev is not None:
                prev.evidence = sorted({*prev.evidence, *evidence}, key=lambda e: e.ref)[
                    :MAX_EVIDENCE
                ]
                continue
            edges[edge_id] = Edge(
                edge_id,
                p.type,
                src,
                dst,
                evidence,
                p.attrs,
                "extracted" if p.source == "extracted" else "inferred",
                p.confidence,
            )
        for n in self.nodes.values():
            ref = n.attrs.get("handlerRef")
            if isinstance(ref, str):
                n.attrs["handlerRef"] = self.real_id(ref)
        return sorted(edges.values(), key=lambda e: e.id)
