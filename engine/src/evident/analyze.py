"""Build or incrementally refresh the graph for a local folder or a GitHub repo."""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from evident import cache
from evident.extract import FileFacts, extract_file, is_parsed
from evident.health import run_health
from evident.models import AnalysisError, Edge, Graph, Node, RepoInfo
from evident.repo import (
    MAX_FILE_BYTES,
    MAX_FILES,
    MAX_REPO_BYTES,
    GitHubRepo,
    check_size,
    local_dirty,
    local_head,
    looks_like_url,
    parse_github,
    remote_head,
    shallow_clone,
)

SKIP_DIRS = frozenset(
    {"node_modules", "dist", "build", "out", "coverage", "vendor", "__pycache__", "generated"}
)
CacheState = Literal["hit", "partial", "miss"]


@dataclass
class AnalyzeResult:
    graph: Graph
    cache_dir: Path
    files: int
    parsed: int
    reused: int
    cache_state: CacheState
    llm: Literal["used", "skipped", "unavailable"]
    duration_ms: int

    def stats(self) -> dict[str, Any]:
        by_type: dict[str, int] = {}
        for n in self.graph.nodes:
            by_type[n.type] = by_type.get(n.type, 0) + 1
        try:
            graph_path = os.path.relpath(self.cache_dir / "graph.json")
        except ValueError:  # different drive on Windows
            graph_path = str(self.cache_dir / "graph.json")
        return {
            "files": self.files,
            "parsed": self.parsed,
            "reused": self.reused,
            "nodes": len(self.graph.nodes),
            "edges": len(self.graph.edges),
            "findings": len(self.graph.findings),
            "byType": by_type,
            "durationMs": self.duration_ms,
            "cache": self.cache_state,
            "llm": self.llm,
            "graphPath": graph_path.replace("\\", "/"),
        }


def _sha1(data: bytes) -> str:
    return hashlib.sha1(data, usedforsecurity=False).hexdigest()


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def discover(root: Path) -> list[tuple[str, Path, os.stat_result]]:
    """Analysable files under root. Never follows symlinks; skips dot-dirs and build output."""
    found = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") and d not in SKIP_DIRS)
        for name in sorted(filenames):
            path = Path(dirpath) / name
            rel = path.relative_to(root).as_posix()
            if path.is_symlink() or not is_parsed(rel):
                continue
            found.append((rel, path, path.stat()))
            if len(found) > MAX_FILES:
                raise AnalysisError(f"more than {MAX_FILES} analysable files; limit exceeded")
    return found


def analyze(
    target: str = ".", *, use_llm: bool = True, cache_root: Path | None = None
) -> AnalyzeResult:
    """Analyse a local folder (cache in <folder>/.evident) or a GitHub URL (cache in ./.evident)."""
    started = time.perf_counter()
    gh = parse_github(target)
    if gh is not None:
        result = _analyze_github(gh, use_llm=use_llm, cache_root=cache_root or Path.cwd())
    elif looks_like_url(target):
        raise AnalysisError(f"only https://github.com/<owner>/<repo> URLs are supported: {target}")
    else:
        root = Path(target).resolve()
        if not root.is_dir():
            raise AnalysisError(f"not a directory: {target}")
        result = _analyze_dir(
            root,
            cache_dir=root / cache.CACHE_DIR,
            repo_name=root.name,
            sha=local_head(root),
            host="local",
            dirty=local_dirty(root),
            use_llm=use_llm,
        )
    result.duration_ms = int((time.perf_counter() - started) * 1000)
    return result


def _analyze_github(gh: GitHubRepo, *, use_llm: bool, cache_root: Path) -> AnalyzeResult:
    cache_dir = cache_root / cache.CACHE_DIR / "github" / gh.owner / gh.name
    sha = remote_head(gh)
    cached = cache.load_graph(cache_dir)
    if cached is not None and cached.repo.sha == sha:
        n = len(cache.load_manifest(cache_dir) or {})
        return AnalyzeResult(cached, cache_dir, n, 0, n, "hit", "skipped", 0)
    check_size(gh)
    tmp = Path(tempfile.mkdtemp(prefix="evident-"))
    try:
        checkout = tmp / "repo"
        shallow_clone(gh, checkout)
        return _analyze_dir(
            checkout,
            cache_dir=cache_dir,
            repo_name=gh.name,
            sha=local_head(checkout) or sha,
            host="github.com",
            owner=gh.owner,
            ref=gh.ref,
            use_llm=use_llm,
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _analyze_dir(
    root: Path,
    *,
    cache_dir: Path,
    repo_name: str,
    sha: str | None,
    host: Literal["github.com", "local"],
    owner: str | None = None,
    ref: str | None = None,
    dirty: bool | None = None,
    use_llm: bool,
) -> AnalyzeResult:
    files = discover(root)
    if sum(st.st_size for _, _, st in files) > MAX_REPO_BYTES:
        raise AnalysisError(f"analysable files exceed {MAX_REPO_BYTES >> 20} MB")
    previous = cache.load_manifest(cache_dir)
    entries: dict[str, cache.FileEntry] = {}
    fresh: set[str] = set()
    for rel, path, st in files:
        if st.st_size > MAX_FILE_BYTES:
            continue  # minified or generated; not worth parsing
        old = (previous or {}).get(rel)
        if old and old.size == st.st_size and old.mtime_ns == st.st_mtime_ns:
            entries[rel] = old
            continue
        data = path.read_bytes()
        digest = _sha1(data)
        if old and old.hash == digest:
            entries[rel] = cache.FileEntry(st.st_size, st.st_mtime_ns, digest, old.facts)
            continue
        fresh.add(rel)
        entries[rel] = cache.FileEntry(st.st_size, st.st_mtime_ns, digest, FileFacts())

    worktree_hash = _sha1("\n".join(f"{p}\0{e.hash}" for p, e in sorted(entries.items())).encode())
    sha = sha or worktree_hash
    unchanged = previous is not None and not fresh and set(previous) == set(entries)
    state: CacheState = "miss" if previous is None else "hit" if unchanged else "partial"

    cached_graph = cache.load_graph(cache_dir) if unchanged else None
    if (
        cached_graph is not None
        and cached_graph.repo.sha == sha
        and cached_graph.repo.worktree_hash == worktree_hash
    ):
        return AnalyzeResult(
            cached_graph, cache_dir, len(entries), 0, len(entries), "hit", "skipped", 0
        )

    for rel in fresh:
        text = (root / rel).read_bytes().decode("utf-8", errors="replace")
        entries[rel].facts = extract_file(rel, text, sha)

    repo = RepoInfo(host, repo_name, sha, _now(), owner, ref, dirty, worktree_hash)
    graph = link([e.facts.restamped(sha) for e in entries.values()], repo)
    graph.findings = run_health(graph)
    # shortcut: LLM grouping isn't built yet; with an LLM requested we report it as unavailable.
    llm: Literal["used", "skipped", "unavailable"] = "unavailable" if use_llm else "skipped"
    problems = graph.check_integrity()
    if problems:
        raise AnalysisError("engine produced an invalid graph: " + "; ".join(problems[:5]))
    cache.save(cache_dir, entries, graph)
    return AnalyzeResult(
        graph, cache_dir, len(entries), len(fresh), len(entries) - len(fresh), state, llm, 0
    )


def link(facts: list[FileFacts], repo: RepoInfo) -> Graph:
    """Merge per-file facts into one graph; first occurrence of an id wins, evidence is merged.

    shortcut: no cross-file resolution yet (imports, route -> handler); lands with extractors.
    """
    nodes: dict[str, Node] = {}
    edges: dict[str, Edge] = {}
    for f in facts:
        for n in f.nodes:
            if n.id in nodes:
                nodes[n.id].evidence = sorted(
                    {*nodes[n.id].evidence, *n.evidence}, key=lambda e: e.ref
                )
            else:
                nodes[n.id] = n
        for e in f.edges:
            edges.setdefault(e.id, e)
    return Graph(
        repo, sorted(nodes.values(), key=lambda n: n.id), sorted(edges.values(), key=lambda e: e.id)
    )
