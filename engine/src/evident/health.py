"""Deterministic health checks over a finished graph."""

from __future__ import annotations

from collections import defaultdict

from evident.models import Finding, Graph
from evident.query import TRACE_EDGES, GraphIndex, walk


def run_health(graph: Graph) -> list[Finding]:
    idx = GraphIndex(graph)
    findings = [*_unguarded_writes(idx), *_unused_models(idx), *_undocumented_env(idx)]
    findings += _import_cycles(idx)
    # shortcut: unvalidated-body needs body-validation facts from route extractors; add with them.
    return sorted(findings, key=lambda f: f.id)


def _unguarded_writes(idx: GraphIndex) -> list[Finding]:
    out = []
    for route in idx.of_type("route"):
        if any(e.type == "guards" for e in idx.incoming[route.id]):
            continue
        hops = walk(idx, [route.id], forward=True, depth=8, edge_types=TRACE_EDGES)
        writes = [h.edge for h in hops if h.edge is not None and h.edge.type == "writes"]
        for edge in writes:
            model = idx.nodes[edge.dst]
            out.append(
                Finding(
                    id=f"unguarded-write:{route.id}->{model.id}",
                    rule="unguarded-write",
                    severity="warning",
                    message=f"{route.label} writes to {model.label} with no auth middleware.",
                    node_ids=[route.id, model.id],
                    evidence=edge.evidence,
                )
            )
    return out


def _unused_models(idx: GraphIndex) -> list[Finding]:
    return [
        Finding(
            id=f"unused-model:{m.label}",
            rule="unused-model",
            severity="info",
            message=f"{m.label} is never read or written.",
            node_ids=[m.id],
            evidence=m.evidence,
        )
        for m in idx.of_type("model")
        if not any(e.type in ("reads", "writes") for e in idx.incoming[m.id])
    ]


def _undocumented_env(idx: GraphIndex) -> list[Finding]:
    return [
        Finding(
            id=f"undocumented-env:{n.label}",
            rule="undocumented-env",
            severity="info",
            message=f"{n.label} is read but not listed in .env.example.",
            node_ids=[n.id],
            evidence=n.evidence,
        )
        for n in idx.of_type("envVar")
        if n.attrs.get("documented") is False
    ]


def _import_cycles(idx: GraphIndex) -> list[Finding]:
    adj: dict[str, list[str]] = defaultdict(list)
    for e in idx.graph.edges:
        if e.type == "imports":
            adj[e.src].append(e.dst)
    out = []
    for scc in _strongly_connected(adj):
        if len(scc) < 2 and scc[0] not in adj[scc[0]]:
            continue
        members = sorted(scc)
        evidence = [ev for m in members for ev in idx.nodes[m].evidence][:5]
        out.append(
            Finding(
                id=f"circular-import:{members[0]}",
                rule="circular-import",
                severity="warning",
                message="Import cycle: " + " -> ".join(idx.nodes[m].label for m in members),
                node_ids=members,
                evidence=evidence,
            )
        )
    return out


def _strongly_connected(adj: dict[str, list[str]]) -> list[list[str]]:
    """Iterative Tarjan, so deep import chains can't hit the recursion limit."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    result: list[list[str]] = []
    counter = 0
    for start in list(adj):
        if start in index:
            continue
        work = [(start, 0)]
        while work:
            v, i = work.pop()
            if i == 0:
                index[v] = low[v] = counter
                counter += 1
                stack.append(v)
                on_stack.add(v)
            children = adj.get(v, [])
            if i < len(children):
                work.append((v, i + 1))
                w = children[i]
                if w not in index:
                    work.append((w, 0))
                elif w in on_stack:
                    low[v] = min(low[v], index[w])
                continue
            if low[v] == index[v]:
                scc = []
                while True:
                    w = stack.pop()
                    on_stack.discard(w)
                    scc.append(w)
                    if w == v:
                        break
                result.append(scc)
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[v])
    return result
