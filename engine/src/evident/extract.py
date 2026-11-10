"""Per-file extraction. Pure: text in, cacheable facts out. No I/O, no execution."""

from __future__ import annotations

from dataclasses import dataclass, field

from evident.models import JSON, Edge, Node

PARSED_SUFFIXES = (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs", ".prisma")
PARSED_NAMES = (
    "package.json",
    "tsconfig.json",
    "jsconfig.json",
    ".env.example",
    ".env.sample",
    ".env.template",
    "pnpm-workspace.yaml",
    "requirements.txt",
    "pyproject.toml",
)
ENV_DOCS = (".env.example", ".env.sample", ".env.template")


@dataclass
class FileFacts:
    """`raw` holds the per-file summary; the linker turns all of them into nodes and edges."""

    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    raw: JSON = field(default_factory=dict)

    def to_dict(self) -> JSON:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "raw": self.raw,
        }

    @classmethod
    def from_dict(cls, d: JSON) -> FileFacts:
        return cls(
            [Node.from_dict(n) for n in d.get("nodes", [])],
            [Edge.from_dict(e) for e in d.get("edges", [])],
            d.get("raw", {}),
        )

    def restamped(self, sha: str) -> FileFacts:
        return FileFacts(
            [n.restamped(sha) for n in self.nodes],
            [e.restamped(sha) for e in self.edges],
            self.raw,
        )


def is_parsed(rel_path: str) -> bool:
    name = rel_path.rsplit("/", 1)[-1]
    if name.endswith(".d.ts"):
        return False
    return name.endswith(PARSED_SUFFIXES) or name in PARSED_NAMES


def extract_file(rel_path: str, text: str, sha: str) -> FileFacts:
    """Run the universal summariser and every adapter's extractor that applies to this file."""
    del sha  # evidence is stamped at link time, so cached facts survive new commits
    # Imported here so `evident.extract` stays importable from the adapter modules.
    from evident.adapters import ADAPTERS
    from evident.adapters.prisma import parse_schema
    from evident.syntax import parse
    from evident.universal import manifests
    from evident.universal.js import summarise

    name = rel_path.rsplit("/", 1)[-1]
    raw: JSON = {}
    try:
        if name.endswith(".prisma"):
            raw["prisma"] = parse_schema(text)
        elif name == "package.json":
            raw["package"] = manifests.package_json(text)
        elif name in ("tsconfig.json", "jsconfig.json"):
            raw["tsconfig"] = manifests.tsconfig(text)
        elif name in ENV_DOCS:
            raw["envDoc"] = manifests.env_names(text)
        elif name == "pnpm-workspace.yaml":
            raw["pnpmWorkspaces"] = manifests.pnpm_workspace(text)
        elif name in ("requirements.txt", "pyproject.toml"):
            raw["pyDeps"] = manifests.python_deps(name, text)
        else:
            tree = parse(rel_path, text)
            if tree is None:
                return FileFacts()
            summary, fn_keys = summarise(tree)
            raw["js"] = summary
            for adapter in ADAPTERS:
                if adapter.extract is not None:
                    part = adapter.extract(rel_path, tree, fn_keys)
                    if part:
                        raw[adapter.name] = part
    except (ValueError, RecursionError) as exc:
        raw = {"error": f"{type(exc).__name__}: {exc}"[:200]}
    return FileFacts(raw=raw)
