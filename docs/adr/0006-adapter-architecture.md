# 0006. Extract through per-framework adapters on a universal layer

- **Status:** Accepted. Widens the v1 scope in [PRD](../PRD.md) §4 and extends [0001](0001-python-tree-sitter-engine.md) beyond JS/TS.
- **Date:** 2026-11-10

## Context

The PRD scoped v1 to Next.js App Router, Express and Prisma, and listed other frameworks and languages as non-goals. The project's feature tracker sets a wider v1: more JS/TS frameworks and ORMs (NestJS, Fastify, Drizzle, TypeORM, Mongoose) and Python (Django, FastAPI, Flask, Django ORM, SQLAlchemy), with Java, PHP, Ruby, C# and Go after launch. Hard-coding each framework into one extractor module won't scale to that list, and an unsupported stack must never produce a blank screen.

## Decision

Split extraction into two layers:

1. **Universal layer:** runs on any language tree-sitter parses. It extracts the module/import graph, external services (from manifests and SDK imports), env vars (and whether they're documented in `.env.example`) and containers from `docker-compose.yml`.
2. **Adapters:** one per framework or ORM, found through a registry. An adapter is **tree-sitter `.scm` queries plus a small Python mapper** that turns captures into nodes and edges with evidence. Adapters live in `engine/src/evident/adapters/<name>/`.

**Stack detection** reads manifests (`package.json`, `pyproject.toml`/`requirements.txt`, `pom.xml`/Gradle, `go.mod`, `composer.json`, `Gemfile`, `.csproj`) and turns on every matching adapter. In a monorepo, several adapters run at once across workspaces.

**Graceful fallback:** if no adapter matches, the engine still returns the universal map plus a message: "Routes and models aren't supported for <framework> yet. Here's the module and service map we found."

**Every adapter must have** a fixture repo, snapshot tests, benchmark cases, counting rules in the [labelling guide](../labelling-guide.md), and a row on the "Supported stacks" page with its own precision and recall.

**v1 adapters:** Next.js, Express, NestJS, Fastify, Prisma, Drizzle, TypeORM, Mongoose, Django, FastAPI, Flask, Django ORM, SQLAlchemy. **After launch**, one ecosystem every 1–2 weeks: Spring Boot + JPA → Laravel + Eloquent → Rails + ActiveRecord → ASP.NET Core + EF Core → Go (Gin/Echo/Chi/net/http + GORM).

## Consequences

- New frameworks become data plus a small mapper, not engine surgery. Contributors get a clear template (`docs/writing-an-adapter.md`).
- Benchmark metrics are reported per adapter as well as per category, so a weak adapter can't hide behind a strong one.
- The graph schema's `framework` and node-type enums grow as adapters land (a minor bump each time, e.g. adding `container` nodes).
- **Cost:** much more v1 surface. Thirteen adapters each need fixtures and labelled benchmark repos. The positioning moves from "one stack, in depth" to "depth per supported stack", and each stack has to earn its row.
- [0001](0001-python-tree-sitter-engine.md) still holds: Python and tree-sitter, never executing code. Its "no type checker" cost now applies to every language.

## Alternatives considered

- **Keep v1 to Next.js/Express/Prisma:** less risk, but a narrower audience and not what the tracker commits to.
- **LSP per language:** type-aware, but needs installed dependencies and heavier sandboxing. Rejected in 0001 for the same reasons.
- **One monolithic extractor per language:** fast to start, but framework rules get tangled together and per-framework metrics are lost.
