"""Link stage: per-file facts -> graph (adapters, then the universal layer)."""

from __future__ import annotations

from evident.adapters import ADAPTERS, detect_stack
from evident.extract import FileFacts
from evident.link import LinkContext, Project
from evident.models import Graph, RepoInfo
from evident.universal.build import build


def link(facts: dict[str, FileFacts], repo: RepoInfo) -> Graph:
    project = Project({path: f.raw for path, f in facts.items()})
    ctx = LinkContext(project, repo.sha)
    for adapter in ADAPTERS:
        adapter.link(ctx)
    build(ctx)
    edges = ctx.finish()
    graph = Graph(repo, sorted(ctx.nodes.values(), key=lambda n: n.id), edges)
    graph.stack = detect_stack(project, ctx.adapters)
    return graph
