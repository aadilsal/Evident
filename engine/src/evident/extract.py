"""Per-file extractors. Pure: text in, facts out. No I/O, no execution."""

from __future__ import annotations

from dataclasses import dataclass, field

from evident.models import JSON, Edge, Node

PARSED_SUFFIXES = (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs", ".prisma")
PARSED_NAMES = ("package.json", "tsconfig.json", ".env.example", ".env.sample")


@dataclass
class FileFacts:
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)

    def to_dict(self) -> JSON:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
        }

    @classmethod
    def from_dict(cls, d: JSON) -> FileFacts:
        return cls(
            [Node.from_dict(n) for n in d.get("nodes", [])],
            [Edge.from_dict(e) for e in d.get("edges", [])],
        )

    def restamped(self, sha: str) -> FileFacts:
        return FileFacts(
            [n.restamped(sha) for n in self.nodes], [e.restamped(sha) for e in self.edges]
        )


def is_parsed(rel_path: str) -> bool:
    name = rel_path.rsplit("/", 1)[-1]
    return name.endswith(PARSED_SUFFIXES) or name in PARSED_NAMES


def extract_file(rel_path: str, text: str, sha: str) -> FileFacts:
    """Run every extractor that applies to this file.

    shortcut: returns no facts until the tree-sitter extractors land (Phase 1); cache,
    linking, health checks and queries already run on whatever this returns.
    """
    del rel_path, text, sha
    return FileFacts()
