"""Shared helpers for fixture-graph tests."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from evident.analyze import analyze
from evident.models import Graph


def analyse_fixture(repo: Path, validator: Draft202012Validator) -> Graph:
    graph = analyze(str(repo), use_llm=False).graph
    data = json.loads((repo / ".evident" / "graph.json").read_text(encoding="utf-8"))
    errors = [f"{list(e.path)}: {e.message}" for e in validator.iter_errors(data)]
    assert not errors, errors
    assert graph.check_integrity() == []
    return graph


def node_ids(graph: Graph, node_type: str) -> set[str]:
    return {n.id for n in graph.nodes if n.type == node_type}


def edges(graph: Graph, *types: str) -> dict[str, list[str]]:
    """Edge id -> evidence refs, for the given edge types."""
    return {e.id: [ev.ref for ev in e.evidence] for e in graph.edges if e.type in types}


def node(graph: Graph, node_id: str) -> dict[str, object]:
    return next(n for n in graph.nodes if n.id == node_id).to_dict()
