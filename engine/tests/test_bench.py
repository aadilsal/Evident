"""Benchmark scoring follows docs/labelling-guide.md: match keys, optional items, the CI gate."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from evident.bench import Item, norm_path, predictions, regressions, route_key, score, truth_items
from tests.graph_helpers import analyse_fixture


def test_match_keys_ignore_param_names_and_keep_layouts_apart() -> None:
    assert norm_path("/u/:userId/") == "/u/:_"
    assert norm_path("/sign-in/:sign-in*?") == "/sign-in/:_"
    assert norm_path("action:actions/a.js#f") == "action:actions/a.js#f"
    assert route_key("get", "/d", "layout") != route_key("GET", "/d", "page")


def test_scores_express_fixture_against_labels(
    fixture_repo: Path, graph_validator: Draft202012Validator
) -> None:
    g = analyse_fixture(fixture_repo, graph_validator)
    gt = {
        "routes": [
            {"method": "GET", "path": "/health"},
            {"method": "GET", "path": "/api/users"},
            {"method": "GET", "path": "/api/users/:userId"},
            {"method": "POST", "path": "/api/users"},
            {"method": "GET", "path": "/api/invoices"},
            {"method": "POST", "path": "/api/invoices"},
            {"method": "DELETE", "path": "/api/legacy", "optional": True},
        ],
        "models": [{"name": "User"}, {"name": "Invoice"}, {"name": "AuditLog"}],
        "services": [{"provider": "stripe"}],
        "edges": [
            {"route": "POST /api/users", "model": "User", "op": "write"},
            {"route": "GET /api/users", "model": "User", "op": "read"},
            {"route": "GET /api/users/:id", "model": "User", "op": "read"},
            {"route": "GET /api/invoices", "model": "Invoice", "op": "read"},
            {"route": "POST /api/invoices", "model": "Invoice", "op": "write"},
            {"route": "GET /api/invoices", "model": "User", "op": "read", "optional": True},
        ],
    }
    req, opt = truth_items(gt)
    s = score(predictions(g), req, opt)
    assert {c: (v.tp, v.fp, v.fn) for c, v in s.items()} == {
        "routes": (6, 0, 0),
        "models": (3, 0, 0),
        "services": (1, 0, 0),
        "edges": (5, 0, 0),
    }


def test_dynamic_predictions_dont_cost_precision_but_count_as_unmatched() -> None:
    pred = {Item("routes", "PUT /*", dynamic=True), Item("routes", "GET /a")}
    req, opt = truth_items({"routes": [{"method": "GET", "path": "/a"}]})
    s = score(pred, req, opt)["routes"]
    assert (s.tp, s.fp, s.fn, s.precision) == (1, 0, 0, 1.0)
    assert s.hallucination == 0.5


def test_gate_fails_on_more_than_two_points() -> None:
    base = {"categories": {"routes": {"precision": 0.95, "recall": 0.90}}}
    ok = {"categories": {"routes": {"precision": 0.935, "recall": 0.90}}}
    bad = {"categories": {"routes": {"precision": 0.92, "recall": 0.90}}}
    assert regressions(ok, base) == []
    assert regressions(bad, base) == ["routes precision: 95.0% -> 92.0%"]


def test_history_appends_one_point_per_evident_commit(tmp_path: Path) -> None:
    from evident.bench import append_history

    summary = {
        "repos": [{}, {}],
        "categories": {
            "routes": {
                "precision": 1.0,
                "recall": 0.9,
                "f1": 0.947,
                "hallucinationRate": 0.0,
                "tp": 9,
            }
        },
    }
    path = tmp_path / "history.json"
    append_history(path, summary, "a" * 40)
    append_history(path, summary, "a" * 40)  # same commit: replaced, not duplicated
    append_history(path, summary, "b" * 40)
    runs = json.loads(path.read_text(encoding="utf-8"))["runs"]
    assert [r["evidentSha"] for r in runs] == ["a" * 40, "b" * 40]
    assert runs[0]["repos"] == 2 and "tp" not in runs[0]["categories"]["routes"]
