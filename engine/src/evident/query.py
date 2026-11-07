"""Read-only queries over a graph: trace, impact, find, health filters, show."""

from __future__ import annotations

import re
from collections import defaultdict, deque
from collections.abc import Iterable
from dataclasses import dataclass

from evident.models import Edge, Finding, Graph, Node, ResultItem, UsageError

HTTP_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "ALL")
TRACE_EDGES = frozenset({"handles", "guards", "calls", "reads", "writes", "uses"})


class GraphIndex:
    def __init__(self, graph: Graph) -> None:
        self.graph = graph
        self.nodes: dict[str, Node] = {n.id: n for n in graph.nodes}
        self.outgoing: dict[str, list[Edge]] = defaultdict(list)
        self.incoming: dict[str, list[Edge]] = defaultdict(list)
        for e in graph.edges:
            self.outgoing[e.src].append(e)
            self.incoming[e.dst].append(e)

    def of_type(self, node_type: str) -> list[Node]:
        return [n for n in self.graph.nodes if n.type == node_type]


def dependent_and_dependency(edge: Edge) -> tuple[str, str]:
    """Which end depends on the other. A route depends on its middleware, so guards flips."""
    return (edge.dst, edge.src) if edge.type == "guards" else (edge.src, edge.dst)


@dataclass(frozen=True)
class Hop:
    node_id: str
    depth: int
    edge: Edge | None


def walk(
    idx: GraphIndex,
    roots: Iterable[str],
    *,
    forward: bool,
    depth: int,
    edge_types: frozenset[str] | None = None,
) -> list[Hop]:
    """BFS over dependencies. forward = what X depends on; reverse = what depends on X."""
    seen = set(roots)
    hops = [Hop(r, 0, None) for r in sorted(seen)]
    queue = deque(hops)
    while queue:
        hop = queue.popleft()
        if hop.depth >= depth:
            continue
        candidates = idx.outgoing[hop.node_id] + idx.incoming[hop.node_id]
        for edge in sorted(candidates, key=lambda e: e.id):
            if edge_types is not None and edge.type not in edge_types:
                continue
            dependent, dependency = dependent_and_dependency(edge)
            here, there = (dependent, dependency) if forward else (dependency, dependent)
            if here != hop.node_id or there in seen or there not in idx.nodes:
                continue
            seen.add(there)
            nxt = Hop(there, hop.depth + 1, edge)
            hops.append(nxt)
            queue.append(nxt)
    return hops


def hop_item(idx: GraphIndex, hop: Hop) -> ResultItem:
    node = idx.nodes[hop.node_id]
    item = ResultItem.from_node(node, depth=hop.depth)
    if node.type == "model" and node.attrs.get("tableName"):
        item.label = f"{node.label} (table {node.attrs['tableName']})"
    if hop.edge is not None:
        item.via = hop.edge.type
        item.op = hop.edge.attrs.get("operation")
        # The edge is the receipt for this hop; fall back to the node's own evidence.
        item.evidence = [e.ref for e in hop.edge.evidence] or item.evidence
        # A hop is only as certain as the weaker of the edge and the node.
        inferred = "inferred" in (hop.edge.source, node.source)
        item.source = "inferred" if inferred else "extracted"
        item.confidence = min(hop.edge.confidence, node.confidence)
    return item


def _normalise_path(path: str) -> str:
    path = path.rstrip("/") or "/"
    return re.sub(r":[A-Za-z0-9_]+\*?\??", ":_", path)


def parse_route_query(query: str) -> tuple[str, str]:
    parts = query.split()
    if len(parts) != 2 or parts[0].upper() not in HTTP_METHODS or not parts[1].startswith("/"):
        raise UsageError(f'expected "<METHOD> <path>", e.g. "POST /api/users"; got {query!r}')
    return parts[0].upper(), parts[1]


def find_route(idx: GraphIndex, query: str) -> Node | None:
    if query in idx.nodes:
        return idx.nodes[query]
    method, path = parse_route_query(query)
    want = _normalise_path(path)
    for node in idx.of_type("route"):
        if (
            node.attrs.get("method") in (method, "ALL")
            and _normalise_path(str(node.attrs.get("path", ""))) == want
        ):
            return node
    return None


def resolve_targets(idx: GraphIndex, target: str) -> list[str]:
    """Exact id, a name (Invoice, Invoice.amount, STRIPE_KEY), or a repo path (every node in it)."""
    if target in idx.nodes:
        return [target]
    name = target.split(".", 1)[0] if "/" not in target else target
    by_name = [
        n.id
        for n in idx.graph.nodes
        if name in (n.label, n.attrs.get("name")) or n.id.split(":", 1)[1] == name
    ]
    if by_name:
        return sorted(by_name)
    path = target.strip("./")
    in_file = [
        n.id
        for n in idx.graph.nodes
        if n.attrs.get("file") == path
        or n.attrs.get("path") == path
        or any(e.file == path for e in n.evidence)
    ]
    return sorted(set(in_file))


def find_access(idx: GraphIndex, model: str, op: str, depth: int) -> list[ResultItem]:
    model_id = model if model.startswith("model:") else f"model:{model.split('.', 1)[0]}"
    items = []
    for edge in sorted(idx.incoming[model_id], key=lambda e: e.id):
        if edge.type != op or edge.src not in idx.nodes:
            continue
        up = walk(idx, [edge.src], forward=False, depth=depth, edge_types=TRACE_EDGES)
        routes = sorted(h.node_id for h in up if idx.nodes[h.node_id].type == "route")
        item = ResultItem.from_node(idx.nodes[edge.src], via=edge.type, routes=routes)
        item.op = edge.attrs.get("operation")
        item.evidence = [e.ref for e in edge.evidence]
        item.source, item.confidence = edge.source, edge.confidence
        items.append(item)
    return items


def finding_item(f: Finding) -> ResultItem:
    return ResultItem(
        id=f.id,
        rule=f.rule,
        severity=f.severity,
        message=f.message,
        node_ids=f.node_ids,
        evidence=[e.ref for e in f.evidence],
    )


SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def filter_findings(
    graph: Graph, *, rules: list[str] | None, files: list[str] | None, min_severity: str
) -> list[Finding]:
    floor = SEVERITY_ORDER[min_severity]
    wanted_files = {f.strip("./") for f in files} if files else None
    out = []
    for f in graph.findings:
        if SEVERITY_ORDER[f.severity] > floor or (rules and f.rule not in rules):
            continue
        if wanted_files is not None and not any(e.file in wanted_files for e in f.evidence):
            continue
        out.append(f)
    return sorted(out, key=lambda f: (SEVERITY_ORDER[f.severity], f.id))


def neighbours(idx: GraphIndex, node_id: str) -> list[ResultItem]:
    items = []
    for direction, edges in (("out", idx.outgoing[node_id]), ("in", idx.incoming[node_id])):
        for e in sorted(edges, key=lambda e: e.id):
            other = e.dst if direction == "out" else e.src
            if other not in idx.nodes:
                continue
            item = ResultItem.from_node(idx.nodes[other], via=e.type, direction=direction)
            item.evidence = [ev.ref for ev in e.evidence]
            item.source, item.confidence = e.source, e.confidence
            items.append(item)
    return items
