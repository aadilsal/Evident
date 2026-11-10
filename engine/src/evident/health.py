"""Deterministic health checks over a finished graph."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace

from evident.link import AUTH_RE
from evident.models import Finding, Graph, Node
from evident.query import TRACE_EDGES, GraphIndex, walk
from evident.universal.build import VALIDATE_RE

BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})


def run_health(graph: Graph) -> list[Finding]:
    idx = GraphIndex(graph)
    findings = [*_unguarded_writes(idx), *_unused_models(idx), *_undocumented_env(idx)]
    findings += _import_cycles(idx)
    findings += _unvalidated_bodies(idx)
    return sorted(findings, key=lambda f: f.id)


def _unguarded_writes(idx: GraphIndex) -> list[Finding]:
    out = []
    for route in idx.of_type("route"):
        if _is_guarded(idx, route.id):
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


def _is_guarded(idx: GraphIndex, route_id: str) -> bool:
    """An auth-like middleware guards the route, or its handler checks auth itself."""
    for e in idx.incoming[route_id]:
        mw = idx.nodes.get(e.src)
        if e.type != "guards" or mw is None:
            continue
        if mw.attrs.get("checksAuth") or AUTH_RE.search(f"{mw.label} {mw.attrs.get('name') or ''}"):
            return True
    for e in idx.outgoing[route_id]:
        handler = idx.nodes.get(e.dst)
        if e.type == "handles" and handler is not None and handler.attrs.get("checksAuth"):
            return True
    return False


def _handler(idx: GraphIndex, route_id: str) -> Node | None:
    for e in idx.outgoing[route_id]:
        if e.type == "handles" and e.dst in idx.nodes:
            return idx.nodes[e.dst]
    return None


def _unvalidated_bodies(idx: GraphIndex) -> list[Finding]:
    """POST/PUT/PATCH handlers that read the body with no validator on the request path."""
    out = []
    for route in idx.of_type("route"):
        attrs = route.attrs
        if attrs.get("method") not in BODY_METHODS or attrs.get("kind") != "api":
            continue
        if attrs.get("framework") == "nestjs":
            continue  # bodies arrive as DTOs, validated by pipes we don't model yet
        handler = _handler(idx, route.id)
        if handler is None or not handler.attrs.get("bodyLine"):
            continue
        guards = [idx.nodes[e.src] for e in idx.incoming[route.id] if e.type == "guards"]
        reached = walk(idx, [handler.id], forward=True, depth=3, edge_types=frozenset({"calls"}))
        if (
            handler.attrs.get("validatesBody")
            or any(VALIDATE_RE.search(f"{g.label} {g.attrs.get('name') or ''}") for g in guards)
            or any(idx.nodes[h.node_id].attrs.get("validatesBody") for h in reached)
        ):
            continue
        at = int(handler.attrs["bodyLine"])
        evidence = [replace(handler.evidence[0], start_line=at, end_line=at)]
        out.append(
            Finding(
                id=f"unvalidated-body:{route.id}",
                rule="unvalidated-body",
                severity="warning",
                message=f"{route.label} reads the request body without validating it.",
                node_ids=[route.id, handler.id],
                evidence=evidence,
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
