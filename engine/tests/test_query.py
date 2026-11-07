"""Query and health logic, run on the schema's example graph (real nodes and edges)."""

from __future__ import annotations

from typing import Any

import pytest

from evident.health import run_health
from evident.models import Edge, Evidence, Graph, Node, RepoInfo, UsageError
from evident.query import (
    TRACE_EDGES,
    GraphIndex,
    find_access,
    find_route,
    hop_item,
    resolve_targets,
    walk,
)

SHA = "0" * 40


@pytest.fixture
def idx(example_graph: dict[str, Any]) -> GraphIndex:
    return GraphIndex(Graph.from_dict(example_graph))


def test_graph_round_trips(example_graph: dict[str, Any]) -> None:
    assert Graph.from_dict(example_graph).to_dict() == example_graph


def test_trace_follows_request_path(idx: GraphIndex) -> None:
    route = find_route(idx, "POST /api/invoices")
    assert route is not None
    hops = walk(idx, [route.id], forward=True, depth=8, edge_types=TRACE_EDGES)
    reached = {h.node_id: h.depth for h in hops}
    assert reached["handler:app/api/invoices/route.ts#POST"] == 1
    assert reached["model:Invoice"] == 2
    assert reached["service:stripe"] == 2
    assert "model:Customer" not in reached  # relates is not part of a request


def test_trace_marks_inferred_hops(idx: GraphIndex) -> None:
    hops = walk(idx, ["route:POST /api/invoices"], forward=True, depth=8, edge_types=TRACE_EDGES)
    stripe = next(hop_item(idx, h) for h in hops if h.node_id == "service:stripe")
    assert stripe.source == "inferred"
    assert stripe.confidence == pytest.approx(0.7)
    assert stripe.evidence == ["app/api/invoices/route.ts:19"]


def test_route_param_names_dont_matter() -> None:
    ev = [Evidence("a.ts", 1, 1, SHA)]
    route = Node("route:GET /u/:id", "route", "GET /u/:id", ev, {"method": "GET", "path": "/u/:id"})
    g = GraphIndex(Graph(RepoInfo("local", "x", SHA, "2026-01-01T00:00:00Z"), [route]))
    assert find_route(g, "GET /u/:userId") is route
    assert find_route(g, "POST /u/:id") is None
    with pytest.raises(UsageError):
        find_route(g, "/u/1")


def test_impact_walks_dependents(idx: GraphIndex) -> None:
    roots = resolve_targets(idx, "Invoice.amount")
    assert roots == ["model:Invoice"]
    hit = {h.node_id for h in walk(idx, roots, forward=False, depth=3) if h.depth}
    assert hit == {"handler:app/api/invoices/route.ts#POST", "route:POST /api/invoices"}


def test_impact_of_a_file_starts_from_every_node_in_it(idx: GraphIndex) -> None:
    roots = resolve_targets(idx, "lib/stripe.ts")
    assert roots == ["envVar:STRIPE_SECRET_KEY", "service:stripe"]


def test_find_writes_reports_routes(idx: GraphIndex) -> None:
    items = find_access(idx, "Invoice", "writes", depth=6)
    assert [i.id for i in items] == ["handler:app/api/invoices/route.ts#POST"]
    assert items[0].routes == ["route:POST /api/invoices"]
    assert items[0].op == "create"
    assert find_access(idx, "Invoice", "reads", depth=6) == []


def test_health_rules(idx: GraphIndex) -> None:
    rules = sorted(f.rule for f in run_health(idx.graph))
    assert rules == ["undocumented-env", "unguarded-write", "unused-model"]  # Customer unused


def test_guarded_route_is_not_flagged(example_graph: dict[str, Any]) -> None:
    g = Graph.from_dict(example_graph)
    ev = [Evidence("middleware.ts", 1, 3, SHA)]
    g.nodes.append(
        Node(
            "middleware:auth",
            "middleware",
            "auth",
            ev,
            {"file": "middleware.ts", "framework": "express"},
        )
    )
    g.edges.append(Edge("guards:auth", "guards", "middleware:auth", "route:POST /api/invoices", ev))
    assert "unguarded-write" not in {f.rule for f in run_health(g)}


def test_import_cycle_detected() -> None:
    ev = [Evidence("a.ts", 1, 1, SHA)]
    mods = [Node(f"module:{m}", "module", m, ev, {"path": m}) for m in ("a", "b", "c")]
    imports = [
        Edge(f"imports:{a}->{b}", "imports", f"module:{a}", f"module:{b}", ev)
        for a, b in (("a", "b"), ("b", "c"), ("c", "a"))
    ]
    g = Graph(RepoInfo("local", "x", SHA, "2026-01-01T00:00:00Z"), mods, imports)
    cycles = [f for f in run_health(g) if f.rule == "circular-import"]
    assert len(cycles) == 1
    assert cycles[0].node_ids == ["module:a", "module:b", "module:c"]


def test_integrity_check_catches_dangling_edges(example_graph: dict[str, Any]) -> None:
    g = Graph.from_dict(example_graph)
    assert g.check_integrity() == []
    g.edges[0].dst = "handler:missing"
    assert g.check_integrity() == [f"edge {g.edges[0].id} -> missing handler:missing"]
