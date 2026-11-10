"""Next.js App Router adapter: file routes, aliases, barrels, server actions, middleware."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from evident.adapters.nextjs import app_route, matches
from tests.graph_helpers import analyse_fixture, edges, node, node_ids

API = "src/app/api/invoices/route.ts"
PAGE = "src/app/dashboard/[id]/page.tsx"
MW = "middleware:src/middleware.ts#middleware"


@pytest.mark.parametrize(
    ("rel", "expected"),
    [
        ("app/api/users/route.ts", ("/api/users", "api", "")),
        ("src/app/page.tsx", ("/", "page", "")),
        ("app/(shop)/cart/page.jsx", ("/cart", "page", "")),
        ("app/blog/[...slug]/page.tsx", ("/blog/:slug*", "page", "")),
        ("app/docs/[[...slug]]/page.tsx", ("/docs/:slug*?", "page", "")),
        ("app/sign-in/[[...sign-in]]/page.tsx", ("/sign-in/:sign-in*?", "page", "")),
        ("app/@modal/login/page.tsx", ("/login", "page", "")),
        ("app/_lib/page.tsx", None),
        ("app/(.)photo/page.tsx", None),
        ("app/api/users/handler.ts", None),
        ("apps/web/app/settings/layout.tsx", ("/settings", "layout", "apps/web")),
    ],
)
def test_app_route_paths(rel: str, expected: tuple[str, str, str] | None) -> None:
    assert app_route(rel, ["", "apps/web"]) == expected


@pytest.mark.parametrize(
    ("patterns", "path", "hit"),
    [
        ([], "/anything", True),
        (["/dashboard/:path*"], "/dashboard", True),
        (["/dashboard/:path*"], "/dashboard/:id", True),
        (["/dashboard/:path*"], "/api/invoices", False),
        (["/((?!api|_next/static).*)"], "/api/invoices", False),
        (["/((?!api|_next/static).*)"], "/settings", True),
    ],
)
def test_middleware_matchers(patterns: list[str], path: str, hit: bool) -> None:
    assert matches(patterns, path) is hit


def test_routes_pages_layouts_and_actions(
    copy_fixture: Callable[[str], Path], graph_validator: Draft202012Validator
) -> None:
    g = analyse_fixture(copy_fixture("next-prisma"), graph_validator)
    assert node_ids(g, "route") == {
        "route:GET /api/invoices",
        "route:POST /api/invoices",
        "route:GET /",
        "route:GET /dashboard (layout)",
        "route:GET /dashboard/:id",
        "route:POST action:src/app/actions.ts#deleteInvoice",
    }
    action = node(g, "route:POST action:src/app/actions.ts#deleteInvoice")
    assert action["attrs"]["kind"] == "serverAction"  # type: ignore[index]
    assert edges(g, "handles")[f"handles:route:POST /api/invoices->handler:{API}#POST"] == [
        f"{API}:9-14"
    ]


def test_alias_barrel_and_global_prisma_client(
    copy_fixture: Callable[[str], Path], graph_validator: Draft202012Validator
) -> None:
    g = analyse_fixture(copy_fixture("next-prisma"), graph_validator)
    assert edges(g, "reads", "writes") == {
        f"reads:handler:{API}#GET->model:Invoice": [f"{API}:5"],
        f"writes:handler:{API}#POST->model:Invoice": [f"{API}:11"],
        f"reads:handler:{PAGE}#InvoicePage->model:Invoice": [f"{PAGE}:4"],
        "writes:handler:src/app/actions.ts#deleteInvoice->model:Invoice": ["src/app/actions.ts:6"],
    }
    assert all(e.source == "extracted" for e in g.edges if e.type in ("reads", "writes"))
    assert edges(g, "calls") == {
        f"calls:handler:{API}#POST->function:src/lib/mail.ts#sendReceipt": [f"{API}:12"],
    }
    assert "uses:function:src/lib/mail.ts#sendReceipt->service:resend" in edges(g, "uses")


def test_middleware_matcher_guards_dashboard_only(
    copy_fixture: Callable[[str], Path], graph_validator: Draft202012Validator
) -> None:
    g = analyse_fixture(copy_fixture("next-prisma"), graph_validator)
    assert set(edges(g, "guards")) == {
        f"guards:{MW}->route:GET /dashboard (layout)",
        f"guards:{MW}->route:GET /dashboard/:id",
    }
    assert node(g, MW)["attrs"]["matchers"] == ["/dashboard/:path*"]  # type: ignore[index]
    assert node(g, MW)["attrs"]["checksAuth"] is True  # type: ignore[index]
