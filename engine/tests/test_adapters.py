"""NestJS, Fastify, TypeORM, Drizzle, Mongoose, workspaces and containers: exact graphs."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from jsonschema import Draft202012Validator

from evident.health import run_health
from tests.graph_helpers import analyse_fixture, edges, node, node_ids

Copy = Callable[[str], Path]


def test_nestjs_controllers_guards_and_injected_typeorm_repository(
    copy_fixture: Copy, graph_validator: Draft202012Validator
) -> None:
    g = analyse_fixture(copy_fixture("nest-typeorm"), graph_validator)
    ctrl = "handler:src/users/users.controller.ts#UsersController"
    svc = "function:src/users/users.service.ts#UsersService"
    assert node_ids(g, "route") == {
        "route:GET /api/users",
        "route:GET /api/users/:id",
        "route:POST /api/users",
    }
    assert edges(g, "handles") == {
        f"handles:route:GET /api/users->{ctrl}.findAll": ["src/users/users.controller.ts:9"],
        f"handles:route:GET /api/users/:id->{ctrl}.findOne": ["src/users/users.controller.ts:14"],
        f"handles:route:POST /api/users->{ctrl}.create": ["src/users/users.controller.ts:19"],
    }
    assert edges(g, "guards") == {
        "guards:middleware:src/users/jwt.guard.ts#JwtAuthGuard->route:POST /api/users": [
            "src/users/users.controller.ts:20"
        ]
    }
    assert edges(g, "calls")[f"calls:{ctrl}.create->{svc}.create"] == [
        "src/users/users.controller.ts:22"
    ]
    assert edges(g, "reads", "writes") == {
        f"reads:{svc}.findAll->model:User": ["src/users/users.service.ts:11"],
        f"reads:{svc}.findOne->model:User": ["src/users/users.service.ts:15"],
        f"writes:{svc}.create->model:User": ["src/users/users.service.ts:19"],
        "writes:function:src/seed.ts#seed->model:Post": ["src/seed.ts:7"],
    }
    user = node(g, "model:User")["attrs"]
    assert user["tableName"] == "users" and user["orm"] == "typeorm"  # type: ignore[index]
    assert set(edges(g, "relates")) == {
        "relates:model:Post->model:User",
        "relates:model:User->model:Post",
    }
    assert [f.rule for f in run_health(g) if f.rule == "unguarded-write"] == []


def test_fastify_plugins_prefixes_hooks_and_drizzle(
    copy_fixture: Copy, graph_validator: Draft202012Validator
) -> None:
    g = analyse_fixture(copy_fixture("fastify-drizzle"), graph_validator)
    f = "src/routes/users.ts"
    assert node_ids(g, "route") == {
        "route:GET /users",
        "route:POST /users",
        "route:PUT /users/:id",
        "route:GET /users/:id/posts",
    }
    assert edges(g, "reads", "writes") == {
        f"reads:handler:{f}#L11->model:users": [f"{f}:11"],
        f"writes:handler:{f}#L13->model:users": [f"{f}:14"],
        f"writes:handler:{f}#updateUser->model:users": [f"{f}:7"],
        f"reads:handler:{f}#L19->model:posts": [f"{f}:19"],
    }
    assert edges(g, "guards") == {
        f"guards:middleware:{f}#fastify.authenticate->route:POST /users": [f"{f}:13"]
    }
    assert edges(g, "relates") == {"relates:model:posts->model:users": ["src/db/schema.ts:10"]}
    assert node(g, "model:users")["attrs"]["tableName"] == "users"  # type: ignore[index]
    rules = sorted(x.id for x in run_health(g) if x.rule != "undocumented-env")
    assert rules == [
        "unguarded-write:route:PUT /users/:id->model:users",
        "unvalidated-body:route:POST /users",
        "unvalidated-body:route:PUT /users/:id",
    ]


def test_mongoose_models_statics_instances_and_refs(
    copy_fixture: Copy, graph_validator: Draft202012Validator
) -> None:
    g = analyse_fixture(copy_fixture("express-mongoose"), graph_validator)
    assert edges(g, "reads", "writes") == {
        "reads:handler:app.js#L7->model:User": ["app.js:8"],
        "writes:handler:app.js#L11->model:User": ["app.js:13"],
        "writes:handler:app.js#L17->model:Post": ["app.js:18"],
    }
    assert edges(g, "relates") == {
        "relates:model:Post->model:User": ["models/Post.js:5"],
        "relates:model:User->model:Post": ["models/User.js:5"],
    }
    user = node(g, "model:User")["attrs"]
    assert user["orm"] == "mongoose"  # type: ignore[index]
    assert {"name": "posts", "type": "Post", "isList": True, "isRelation": True} in user["fields"]  # type: ignore[index]


def test_workspace_imports_and_compose_containers(
    copy_fixture: Copy, graph_validator: Draft202012Validator
) -> None:
    g = analyse_fixture(copy_fixture("monorepo"), graph_validator)
    write = "writes:handler:apps/api/src/index.ts#L6->model:Order"
    nested = "writes:handler:apps/api/src/index.ts#L6->model:OrderItem"
    assert edges(g, "writes") == {
        write: ["apps/api/src/index.ts:7"],
        nested: ["apps/api/src/index.ts:7"],
    }
    assert next(e for e in g.edges if e.id == nested).attrs == {"operation": "nested create"}
    assert next(e for e in g.edges if e.id == write).source == "extracted"
    assert "imports:module:apps/api/src/index.ts->module:packages/db/src/index.ts" in edges(
        g, "imports"
    )
    assert node(g, "module:apps/api/src/index.ts")["attrs"]["workspace"] == "@acme/api"  # type: ignore[index]
    api = node(g, "container:api")
    assert api["attrs"] == {
        "file": "docker-compose.yml",
        "name": "api",
        "build": "./apps/api",
        "ports": ["4000:4000"],
        "dependsOn": ["db"],
    }
    assert "never-read" not in str(g.to_dict()), "compose environment values must never be read"
