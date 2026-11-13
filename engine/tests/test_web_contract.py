"""The web app re-implements trace/impact in TypeScript; these goldens keep both answers identical.

Regenerate after an intended engine change:
  EVIDENT_UPDATE_GOLDEN=1 uv run pytest tests/test_web_contract.py
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from evident.adapters import ADAPTERS, NOT_YET
from evident.analyze import analyze
from evident.models import Graph
from evident.query import TRACE_EDGES, GraphIndex, walk

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN = ROOT / "web" / "src" / "lib" / "__fixtures__" / "express-prisma.parity.json"
STACKS = ROOT / "web" / "src" / "data" / "stacks.json"


def _walks(graph_dict: dict[str, Any]) -> dict[str, Any]:
    graph = Graph.from_dict(graph_dict)
    idx = GraphIndex(graph)
    trace = {
        n.id: [h.node_id for h in walk(idx, [n.id], forward=True, depth=8, edge_types=TRACE_EDGES)]
        for n in graph.nodes
        if n.type == "route"
    }
    impact = {
        n.id: [h.node_id for h in walk(idx, [n.id], forward=False, depth=3)]
        for n in graph.nodes
        if n.type in ("model", "service", "envVar", "middleware")
    }
    return {"trace": trace, "impact": impact}


def test_trace_and_impact_goldens_match_the_engine(tmp_path: Path) -> None:
    repo = tmp_path / "express-prisma"
    shutil.copytree(FIXTURES / "express-prisma", repo)
    graph = analyze(str(repo), use_llm=False).graph.to_dict()
    # Volatile fields would make the golden churn on every run.
    graph["repo"]["analyzedAt"] = "2026-01-01T00:00:00Z"
    expected: dict[str, Any] = {"graph": graph, **_walks(graph)}
    if os.environ.get("EVIDENT_UPDATE_GOLDEN") == "1":
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(json.dumps(expected, indent=1) + "\n", encoding="utf-8", newline="\n")
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert golden["trace"] == expected["trace"], "regenerate the web golden (see module docstring)"
    assert golden["impact"] == expected["impact"], (
        "regenerate the web golden (see module docstring)"
    )
    assert golden["graph"]["nodes"] == expected["graph"]["nodes"]
    assert golden["graph"]["edges"] == expected["graph"]["edges"]


def test_web_stack_list_matches_the_adapter_registry() -> None:
    data = json.loads(STACKS.read_text(encoding="utf-8"))
    assert data["adapters"] == [
        {"name": a.name, "label": a.label, "kind": a.kind, "ecosystem": a.ecosystem}
        for a in ADAPTERS
    ]
    assert data["notYet"] == sorted(set(NOT_YET.values()))


def test_packaged_schema_copy_matches_the_contract() -> None:
    packaged = Path(__file__).resolve().parents[1] / "src" / "evident" / "graph.schema.json"
    source = ROOT / "schema" / "graph.schema.json"
    assert packaged.read_bytes() == source.read_bytes(), (
        "copy schema/graph.schema.json to engine/src/evident/graph.schema.json"
    )
