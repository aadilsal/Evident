"""Adapter registry (ADR-0006). Each adapter: optional per-file extract + a link step.

Per-file extractors run on every file regardless of stack, so the cache never depends on stack
detection; link steps only produce output when they find their framework's patterns.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import tree_sitter as ts

from evident.adapters import drizzle, express, fastify, mongoose, nestjs, nextjs, prisma, typeorm
from evident.link import LinkContext, Project
from evident.universal.js import FnKeys

JSON = dict[str, Any]


@dataclass(frozen=True)
class Adapter:
    name: str
    label: str
    kind: str  # framework | orm
    ecosystem: str
    link: Callable[[LinkContext], None]
    extract: Callable[[str, ts.Tree, FnKeys], JSON | None] | None = None


# Order matters: ORMs first, so call classification knows the models.
ADAPTERS: tuple[Adapter, ...] = (
    Adapter("prisma", "Prisma", "orm", "js", prisma.link, prisma.extract),
    Adapter("drizzle", "Drizzle", "orm", "js", drizzle.link, drizzle.extract),
    Adapter("typeorm", "TypeORM", "orm", "js", typeorm.link, typeorm.extract),
    Adapter("mongoose", "Mongoose", "orm", "js", mongoose.link, mongoose.extract),
    Adapter("express", "Express", "framework", "js", express.link, express.extract),
    Adapter("fastify", "Fastify", "framework", "js", fastify.link),
    Adapter("nestjs", "NestJS", "framework", "js", nestjs.link, nestjs.extract),
    Adapter("nextjs", "Next.js", "framework", "js", nextjs.link),
)

# Detected from manifests, mapped by a future adapter. Until then: universal map + a message.
NOT_YET: dict[str, str] = {
    "koa": "Koa",
    "hono": "Hono",
    "@remix-run/node": "Remix",
    "nuxt": "Nuxt",
    "@sveltejs/kit": "SvelteKit",
}
NOT_YET_PY: dict[str, str] = {
    "django": "Django",
    "fastapi": "FastAPI",
    "flask": "Flask",
    "sqlalchemy": "SQLAlchemy",
}
SUPPORTED_DEPS: dict[str, str] = {
    "next": "Next.js",
    "express": "Express",
    "prisma": "Prisma",
    "@prisma/client": "Prisma",
    "@nestjs/core": "NestJS",
    "fastify": "Fastify",
    "drizzle-orm": "Drizzle",
    "typeorm": "TypeORM",
    "mongoose": "Mongoose",
}


def detect_stack(project: Project, active: list[str]) -> JSON:
    """Frameworks named in manifests, which adapters ran, and the graceful-fallback message."""
    js_deps = {d for pkg in project.packages.values() for d in pkg.get("deps", [])}
    py_deps = {d for raw in project.raw.values() for d in raw.get("pyDeps", [])}
    detected = sorted({v for k, v in SUPPORTED_DEPS.items() if k in js_deps})
    other = {f for raw in project.raw.values() for f in raw.get("otherFrameworks", [])}
    unsupported = sorted(
        {v for k, v in NOT_YET.items() if k in js_deps}
        | {v for k, v in NOT_YET_PY.items() if k in py_deps}
        | other
    )
    labels = {a.name: a.label for a in ADAPTERS}
    ran = [labels[a] for a in active]
    stack: JSON = {"detected": sorted({*detected, *unsupported}), "adapters": ran}
    if unsupported:
        stack["unsupported"] = unsupported
        names = ", ".join(unsupported)
        if any(a.kind == "framework" and a.name in active for a in ADAPTERS):
            stack["message"] = f"{names} isn't supported yet, so its routes and models are missing."
        else:
            stack["message"] = (
                f"Routes and models aren't supported for {names} yet. "
                "Here's the module and service map we found."
            )
    return stack
