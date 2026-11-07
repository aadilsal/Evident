"""The .evident/ cache: per-file hashes and facts, plus the last graph. Only place we write."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evident import ENGINE_VERSION
from evident.extract import FileFacts
from evident.models import Graph

CACHE_DIR = ".evident"


@dataclass
class FileEntry:
    size: int
    mtime_ns: int
    hash: str
    facts: FileFacts

    def to_dict(self) -> dict[str, Any]:
        return {
            "size": self.size,
            "mtimeNs": self.mtime_ns,
            "hash": self.hash,
            "facts": self.facts.to_dict(),
        }


def _write_atomic(path: Path, data: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(data, encoding="utf-8")
    tmp.replace(path)


def load_manifest(cache_dir: Path) -> dict[str, FileEntry] | None:
    """None when there is no usable cache (missing, corrupt, or older engine)."""
    try:
        raw = json.loads((cache_dir / "manifest.json").read_text(encoding="utf-8"))
        if raw.get("engineVersion") != ENGINE_VERSION:
            return None
        return {
            path: FileEntry(e["size"], e["mtimeNs"], e["hash"], FileFacts.from_dict(e["facts"]))
            for path, e in raw["files"].items()
        }
    except (OSError, ValueError, KeyError, TypeError):
        return None


def load_graph(cache_dir: Path) -> Graph | None:
    try:
        graph = Graph.from_dict(json.loads((cache_dir / "graph.json").read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return graph if graph.engine_version == ENGINE_VERSION else None


def save(cache_dir: Path, entries: dict[str, FileEntry], graph: Graph) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    # Self-ignoring cache dir, so it never shows up in git status even without a .gitignore rule.
    (cache_dir / ".gitignore").write_text("*\n", encoding="utf-8")
    manifest = {
        "engineVersion": ENGINE_VERSION,
        "files": {p: e.to_dict() for p, e in sorted(entries.items())},
    }
    _write_atomic(cache_dir / "manifest.json", json.dumps(manifest, separators=(",", ":")))
    _write_atomic(cache_dir / "graph.json", json.dumps(graph.to_dict(), indent=1))
