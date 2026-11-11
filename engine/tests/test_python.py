"""Python adapters: FastAPI, Flask, Django (+DRF), Django ORM, SQLAlchemy. Exact graphs."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from evident.adapters._py import fastapi_path, flask_path
from evident.health import run_health
from evident.link import Ns, Project, Sym
from evident.syntax import parse
from evident.universal.py import summarise
from tests.graph_helpers import analyse_fixture, edges, node, node_ids

Copy = Callable[[str], Path]


def _summary(src: str) -> dict[str, Any]:
    tree = parse("m.py", src)
    assert tree is not None
    return summarise(tree)[0]


def test_summary_imports_self_calls_and_env() -> None:
    s = _summary(
        "import os\n"
        "from .models import User as U\n"
        "from . import crud\n"
        "class Svc:\n"
        "    def run(self):\n"
        "        self.helper(os.environ['A'], os.getenv('B'))\n"
        "    def helper(self, *a):\n"
        "        return U.query.all()\n"
    )
    assert [(i["spec"], i["names"]) for i in s["imports"]][1:] == [
        (".models", [["User", "U"]]),
        (".", [["crud", "crud"]]),
    ]
    run = s["scopes"]["Svc.run"]
    assert run["calls"][0]["c"] == ["this", "helper"]
    assert run["env"] == [["A", 6], ["B", 6]]
    assert "Svc.helper" in s["scopes"]


def test_module_var_with_unresolvable_callee_has_no_callee() -> None:
    """Regression: `x = make()()` stored callee=None and crashed the build (SpotterTruckLogging)."""
    s = _summary("x = make()()\ny = factory(1)\n")
    assert "callee" not in s["vars"]["x"]
    assert s["vars"]["y"]["callee"] == ["factory"]


def test_python_module_resolution_relative_absolute_and_submodule() -> None:
    files = {
        "app/__init__.py": "",
        "app/models.py": "class User: pass\n",
        "app/routers/__init__.py": "",
        "app/routers/users.py": (
            "from ..models import User\nfrom app import models\nfrom . import items\n"
        ),
        "app/routers/items.py": "x = 1\n",
    }
    raw = {}
    for path, src in files.items():
        tree = parse(path, src)
        assert tree is not None
        raw[path] = {"py": summarise(tree)[0]}
    p = Project(raw)
    users = "app/routers/users.py"
    assert p.resolve(users, "User") == Sym("app/models.py", "User")
    assert p.resolve(users, "models") == Ns("app/models.py")
    assert p.resolve(users, "items") == Ns("app/routers/items.py")


def test_path_converters() -> None:
    assert fastapi_path("/files/{file_path:path}/v/{id}") == "/files/:file_path*/v/:id"
    assert flask_path("/u/<int:user_id>/<slug>") == "/u/:user_id/:slug"


def test_fastapi_prefixes_auth_dependencies_and_sqlalchemy(
    copy_fixture: Copy, graph_validator: Draft202012Validator
) -> None:
    g = analyse_fixture(copy_fixture("fastapi-sqlalchemy"), graph_validator)
    users, items = "app/routers/users.py", "app/routers/items.py"
    assert node_ids(g, "route") == {
        "route:GET /health",
        "route:GET /api/users",
        "route:POST /api/users",
        "route:GET /api/users/:user_id",
        "route:POST /api/items",
        "route:DELETE /api/items/:item_id",
    }
    assert set(edges(g, "guards")) == {
        "guards:middleware:app/deps.py#get_current_user->route:POST /api/items",
        "guards:middleware:app/deps.py#get_current_user->route:DELETE /api/items/:item_id",
    }
    assert edges(g, "reads", "writes") == {
        f"reads:handler:{users}#list_users->model:User": [f"{users}:16"],
        f"writes:handler:{users}#create_user->model:User": [f"{users}:22"],
        f"reads:handler:{users}#get_user->model:User": [f"{users}:29"],
        f"writes:handler:{items}#create_item->model:Item": [f"{items}:14"],
        f"writes:handler:{items}#delete_item->model:Item": [f"{items}:20"],
        "reads:middleware:app/deps.py#get_current_user->envVar:API_TOKEN": ["app/deps.py:15"],
    }
    assert edges(g, "calls") == {
        f"calls:handler:{items}#create_item->function:app/billing.py#charge": [f"{items}:15"]
    }
    assert "uses:function:app/billing.py#charge->service:stripe" in edges(g, "uses")
    assert node(g, "model:Item")["attrs"]["tableName"] == "items"  # type: ignore[index]
    assert set(edges(g, "relates")) == {"relates:model:Item->model:User"}
    assert sorted(f.id for f in run_health(g) if f.rule != "undocumented-env") == [
        "unguarded-write:route:POST /api/users->model:User",
        "unvalidated-body:route:POST /api/items",
    ]


def test_flask_blueprints_decorator_guards_and_flask_sqlalchemy(
    copy_fixture: Copy, graph_validator: Draft202012Validator
) -> None:
    g = analyse_fixture(copy_fixture("flask-app"), graph_validator)
    p = "app/posts.py"
    assert node_ids(g, "route") == {
        "route:POST /auth/login",
        "route:GET /posts",
        "route:POST /posts",
        "route:DELETE /posts/:post_id",
    }
    assert set(edges(g, "guards")) == {
        f"guards:middleware:{p}#login_required->route:POST /posts",
        f"guards:middleware:{p}#login_required->route:DELETE /posts/:post_id",
    }
    assert edges(g, "reads", "writes") == {
        f"reads:handler:{p}#list_posts->model:Post": [f"{p}:12"],
        f"writes:handler:{p}#create_post->model:Post": [f"{p}:19"],
        f"reads:handler:{p}#delete_post->model:Post": [f"{p}:27"],
        f"writes:handler:{p}#delete_post->model:Post": [f"{p}:28"],
    }
    assert [f.id for f in run_health(g) if f.rule == "unguarded-write"] == []


def test_django_urlconf_views_drf_router_and_orm(
    copy_fixture: Copy, graph_validator: Draft202012Validator
) -> None:
    g = analyse_fixture(copy_fixture("django-app"), graph_validator)
    v = "blog/views.py"
    assert node_ids(g, "route") == {
        "route:ALL /blog",
        "route:POST /blog/new",
        "route:GET /blog/list",
        "route:GET /blog/:pk",
        "route:DELETE /blog/:pk",
        "route:GET /api/authors",
        "route:POST /api/authors",
        "route:GET /api/authors/:pk",
        "route:PUT /api/authors/:pk",
        "route:PATCH /api/authors/:pk",
        "route:DELETE /api/authors/:pk",
        "route:POST /api/authors/:pk/publish",
    }
    assert edges(g, "handles")[
        "handles:route:DELETE /blog/:pk->handler:blog/views.py#PostDetail.delete"
    ] == ["blog/urls.py:9"]
    assert edges(g, "reads", "writes") == {
        f"reads:handler:{v}#index->model:Post": [f"{v}:11"],
        f"writes:handler:{v}#create->model:Post": [f"{v}:17"],
        f"reads:handler:{v}#PostDetail.get->model:Post": [f"{v}:26"],
        f"reads:handler:{v}#PostDetail.delete->model:Post": [f"{v}:29"],
        f"writes:handler:{v}#PostDetail.delete->model:Post": [f"{v}:30"],
        "reads:handler:api/views.py#AuthorViewSet.publish->model:Author": ["api/views.py:13"],
        "writes:handler:api/views.py#AuthorViewSet.publish->model:Author": ["api/views.py:14"],
    }
    guards = set(edges(g, "guards"))
    assert "guards:middleware:blog/views.py#login_required->route:POST /blog/new" in guards
    assert len([x for x in guards if "IsAuthenticated" in x]) == 7
    assert node(g, "model:Post")["attrs"]["tableName"] == "blog_posts"  # type: ignore[index]
    assert node(g, "model:Author")["attrs"]["tableName"] == "blog_author"  # type: ignore[index]
    assert set(edges(g, "relates")) == {"relates:model:Post->model:Author"}
    assert g.stack is not None and "unsupported" not in g.stack
