"""Express + Prisma adapters on the ESM and CommonJS fixtures: exact nodes, edges and evidence."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from jsonschema import Draft202012Validator

from evident.health import run_health
from tests.graph_helpers import analyse_fixture, edges, node, node_ids

USERS = "src/routes/users.ts"
INVOICES = "src/routes/invoices.ts"
AUTH = "middleware:src/middleware/auth.ts#requireAuth"


def test_esm_routes_and_mount_prefixes(
    fixture_repo: Path, graph_validator: Draft202012Validator
) -> None:
    g = analyse_fixture(fixture_repo, graph_validator)
    assert node_ids(g, "route") == {
        "route:GET /health",
        "route:GET /api/users",
        "route:GET /api/users/:id",
        "route:POST /api/users",
        "route:GET /api/invoices",
        "route:POST /api/invoices",
    }
    assert edges(g, "handles") == {
        "handles:route:GET /health->handler:src/app.ts#L9": ["src/app.ts:9"],
        f"handles:route:GET /api/users->handler:{USERS}#L6": [f"{USERS}:6"],
        f"handles:route:GET /api/users/:id->handler:{USERS}#L11": [f"{USERS}:11"],
        f"handles:route:POST /api/users->handler:{USERS}#L17": [f"{USERS}:17"],
        f"handles:route:GET /api/invoices->handler:{INVOICES}#L10": [f"{INVOICES}:10"],
        f"handles:route:POST /api/invoices->handler:{INVOICES}#L14": [f"{INVOICES}:14"],
    }
    route = node(g, "route:POST /api/users")
    assert route["attrs"] == {
        "method": "POST",
        "path": "/api/users",
        "framework": "express",
        "kind": "api",
        "handlerRef": f"handler:{USERS}#L17",
    }
    assert route["evidence"][0]["startLine"] == 17  # type: ignore[index]
    assert route["evidence"][0]["endLine"] == 20  # type: ignore[index]


def test_mount_middleware_guards_only_its_router(
    fixture_repo: Path, graph_validator: Draft202012Validator
) -> None:
    g = analyse_fixture(fixture_repo, graph_validator)
    assert edges(g, "guards") == {
        f"guards:{AUTH}->route:GET /api/invoices": ["src/app.ts:11"],
        f"guards:{AUTH}->route:POST /api/invoices": ["src/app.ts:11"],
    }


def test_prisma_reads_and_writes_through_reexported_client(
    fixture_repo: Path, graph_validator: Draft202012Validator
) -> None:
    g = analyse_fixture(fixture_repo, graph_validator)
    assert edges(g, "reads", "writes") == {
        f"reads:handler:{USERS}#L6->model:User": [f"{USERS}:7"],
        f"reads:handler:{USERS}#L11->model:User": [f"{USERS}:12"],
        f"writes:handler:{USERS}#L17->model:User": [f"{USERS}:18"],
        f"reads:handler:{INVOICES}#L10->model:Invoice": [f"{INVOICES}:11"],
        f"writes:handler:{INVOICES}#L14->model:Invoice": [f"{INVOICES}:16"],
        f"reads:{AUTH}->envVar:API_TOKEN": ["src/middleware/auth.ts:4"],
    }
    writes = next(e for e in g.edges if e.id == f"writes:handler:{USERS}#L17->model:User")
    assert (writes.attrs, writes.source, writes.confidence) == (
        {"operation": "create"},
        "extracted",
        1.0,
    )


def test_calls_services_models_and_env(
    fixture_repo: Path, graph_validator: Draft202012Validator
) -> None:
    g = analyse_fixture(fixture_repo, graph_validator)
    charge = "function:src/lib/billing.ts#chargeCustomer"
    assert edges(g, "calls") == {
        f"calls:handler:{INVOICES}#L14->{charge}": [f"{INVOICES}:17"],
    }
    assert edges(g, "uses") == {
        f"uses:{charge}->service:stripe": ["src/lib/billing.ts:6"],
        "uses:module:src/lib/billing.ts->service:stripe": ["src/lib/billing.ts:1"],
    }
    assert edges(g, "relates") == {
        "relates:model:Invoice->model:User": ["prisma/schema.prisma:20"],
        "relates:model:User->model:Invoice": ["prisma/schema.prisma:14"],
    }
    assert node(g, "model:Invoice")["attrs"]["tableName"] == "invoices"  # type: ignore[index]
    documented = {n.label: n.attrs["documented"] for n in g.nodes if n.type == "envVar"}
    assert documented == {"API_TOKEN": True, "DATABASE_URL": True, "STRIPE_SECRET_KEY": False}
    assert "imports:module:src/app.ts->module:src/routes/users.ts" in edges(g, "imports")


def test_health_findings(fixture_repo: Path, graph_validator: Draft202012Validator) -> None:
    g = analyse_fixture(fixture_repo, graph_validator)
    assert sorted(f.id for f in run_health(g)) == [
        "undocumented-env:STRIPE_SECRET_KEY",
        "unguarded-write:route:POST /api/users->model:User",
        "unused-model:AuditLog",
        "unvalidated-body:route:POST /api/users",
    ]
    body = next(f for f in run_health(g) if f.rule == "unvalidated-body")
    assert [e.ref for e in body.evidence] == [f"{USERS}:18"]


def test_commonjs_routes_wrappers_and_use_order(
    copy_fixture: Callable[[str], Path], graph_validator: Draft202012Validator
) -> None:
    g = analyse_fixture(copy_fixture("express-cjs"), graph_validator)
    ctrl = "src/controllers/items.js"
    assert edges(g, "handles") == {
        f"handles:route:GET /v1/items->handler:{ctrl}#listItems": ["src/routes/index.js:7"],
        f"handles:route:POST /v1/items->handler:{ctrl}#createItem": ["src/routes/index.js:7"],
        "handles:route:GET /v1/items/:id->handler:src/routes/index.js#L8": [
            "src/routes/index.js:8"
        ],
        f"handles:route:DELETE /admin/items/:id->handler:{ctrl}#removeItem": [
            "src/routes/admin.js:6"
        ],
    }
    # app.use(requireUser) comes after the /v1 mount, so it only guards /admin.
    assert edges(g, "guards") == {
        "guards:middleware:src/auth.js#requireUser->route:DELETE /admin/items/:id": [
            "src/server.js:8"
        ],
    }
    assert edges(g, "reads", "writes") == {
        f"reads:handler:{ctrl}#listItems->model:Item": [f"{ctrl}:4"],
        f"writes:handler:{ctrl}#createItem->model:Item": [f"{ctrl}:8"],
        f"writes:handler:{ctrl}#removeItem->model:Item": [f"{ctrl}:12"],
    }
    assert [f.id for f in run_health(g) if f.rule == "unguarded-write"] == [
        "unguarded-write:route:POST /v1/items->model:Item"
    ]


def test_router_factories_local_services_and_esm_js_specifiers(
    copy_fixture: Callable[[str], Path], graph_validator: Draft202012Validator
) -> None:
    """Regression: routers built inside factories were missed (TournamentMatchMaker, 0 routes)."""
    g = analyse_fixture(copy_fixture("express-factory"), graph_validator)
    handler = "handler:src/users.routes.ts#L9"
    create = "function:src/users.service.ts#UsersService.create"
    assert node_ids(g, "route") == {"route:POST /api/v1/users"}
    assert edges(g, "handles") == {
        f"handles:route:POST /api/v1/users->{handler}": ["src/users.routes.ts:9"]
    }
    assert edges(g, "guards") == {
        "guards:middleware:src/auth.ts#authenticate->route:POST /api/v1/users": [
            "src/users.routes.ts:9"
        ]
    }
    assert edges(g, "calls") == {f"calls:{handler}->{create}": ["src/users.routes.ts:10"]}
    assert edges(g, "writes") == {f"writes:{create}->model:User": ["src/users.service.ts:5"]}
    assert [f for f in run_health(g) if f.rule == "unguarded-write"] == []
