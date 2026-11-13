<div align="center">

# Evident

### Architecture maps you can verify.

**Point it at a repo. Get an interactive map of every route, database table and external service in your web app, and how they connect.
Every box and every arrow links to the exact line of code that proves it.**

[![CI](https://github.com/aadilsal/Evident/actions/workflows/ci.yml/badge.svg)](https://github.com/aadilsal/Evident/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Status](https://img.shields.io/badge/status-pre--alpha-orange)
![Stack](https://img.shields.io/badge/stacks-Next.js%20·%20Express%20·%20Prisma%20·%20Django%20·%20FastAPI%20·%20more-black)

[**Status**](#status) · [**CLI**](#use-it-from-the-terminal) · [**Use with Claude**](#use-with-claude) · [**Benchmarks**](#accuracy-measured-not-promised) · [**How it works**](#how-it-works) · [**Docs**](docs/)

<!-- Swap for docs/assets/demo.gif: paste URL → map renders → click a route → request path lights up → evidence panel opens. -->
<img src="docs/assets/demo-placeholder.svg" alt="Evident demo: a request traced from route to database table, with the code for each hop" width="860">

</div>

---

## The problem

You join a new codebase, or you're about to review a pull request in a project you don't know. The first question is always the same: **what talks to what?**

Which routes write to the `User` table? What breaks if I change `Invoice`? Where does Stripe get called? Is this endpoint behind auth?

Today's AI diagram tools answer with a picture of folders, drawn by an LLM guessing from the file tree. It looks convincing until you notice a component that doesn't exist. Coding agents have the same blind spot and fill it by guessing. **A diagram you can't verify is a diagram you can't trust.**

## The approach: facts first, AI second

Evident reads the code the way a compiler would. Static analysis with [tree-sitter](https://tree-sitter.github.io/) extracts the real routes, middleware, models, database calls, SDK imports and environment variables. Only then does an LLM step in, and its only job is to **group and label nodes that already exist**. Its output must reference real node IDs, and a validator rejects anything else.

The result is a map where nothing is made up, and you can check every claim.

<table>
<tr>
<td width="50%" valign="top">

### 🧾 Every edge has a receipt
Click any node or arrow to see the file, the line range and the highlighted snippet. A badge tells you whether it was **extracted** from code or **inferred** by grouping.

</td>
<td width="50%" valign="top">

### 🔦 Request tracer
Click a route and watch the path light up: **route → middleware → handler → service → model → table**, with the code for every hop in a side panel.

</td>
</tr>
<tr>
<td valign="top">

### 🩺 Architecture health checks
Findings with evidence, not lint noise:
*"`POST /api/users` writes to `User` with no auth middleware."* Plus unvalidated request bodies, circular imports, unused models and undocumented env vars.

</td>
<td valign="top">

### 💥 Blast radius
Select a table, file or env var and everything that depends on it is highlighted. It answers the real question: *what breaks if I change this?*

</td>
</tr>
<tr>
<td valign="top">

### 🤖 Built for agents too
One CLI, `evident`, with schema-valid `--json` on every command, plus a Claude skill that runs `impact` before it edits your models and cites `file:line` for every claim.

</td>
<td valign="top">

### 🗺️ A real, explorable graph
Not a static Mermaid image. A zoomable map built with React Flow and ELK auto-layout: filter by layer, collapse groups, follow a request end to end. Hosted, or local with `evident open`.

</td>
</tr>
</table>

## Status

Pre-alpha. **Phases 1 (Engine), 2 (Claude skill), 3 (Service) and 4 (Interface) are complete.** Next up: Phase 5, launch (deploy, more benchmark repos, demo video). This table is updated at the end of every phase.

| Piece | State |
| --- | --- |
| Graph schema `1.2.0` + CLI output schema `1.2.0` | ✅ Done |
| JS/TS adapters: Next.js, Express, NestJS, Fastify, Prisma, Drizzle, TypeORM, Mongoose | ✅ Done, with fixture tests |
| Python adapters: FastAPI, Flask, Django (+ DRF), Django ORM, SQLAlchemy | ✅ Done, with fixture tests |
| Universal layer: module graph, SDK services, env vars, `docker-compose` containers, `tsconfig` aliases, workspaces | ✅ Done (JS/TS and Python) |
| Stack detection + fallback map for unsupported stacks | ✅ Done |
| CLI: `analyze` (summary-first), `trace`, `impact`, `find`, `health`, `show`, `export` (Markdown report, graph JSON), `open`, `share` with `--json` | ✅ Done |
| Health rules: unguarded write, unvalidated body, import cycle, unused model, undocumented env | ✅ Done |
| Benchmark: 8 repos labelled (5 JS/TS, 3 Python), `evident-bench`, CI gate (>2 pt drop fails) | ✅ Done |
| LLM grouping: Groq, validated against node IDs, directory fallback | ✅ Done |
| Service: FastAPI API, arq worker, Postgres cache, SSE progress, rate limits, job timeouts, Docker Compose | ✅ Done (CI runs it end to end) |
| CI: pre-commit, mypy + pytest on Linux and Windows, benchmark gate | ✅ Done |
| Claude skill (`skills/evident/`) + skill-task evals | ✅ Done: 24/24 tasks with the skill vs 21/24 without |
| Web map UI: five views, request tracer, blast radius, evidence panel with snippets, layer filters, ⌘K search, permalinks, light/dark | ✅ Done ([ADR-0008](docs/adr/0008-static-web-on-vercel-api-on-one-server.md): static export) |
| Landing page with a live map, gallery, `/benchmarks` (history chart), supported stacks, live analysis progress, mobile layout, unsupported-stack screen | ✅ Done |
| Exports: PNG/SVG of the current view, graph JSON, printable architecture report (PDF); "report a wrong edge" | ✅ Done |
| `evident open` (UI bundled into the package, localhost only) and `evident share` (opt-in, metadata only, expiring) | ✅ Done |
| Hosting: site on Vercel, API on one server | ⏳ Phase 5 (domain and server pending) |

## Accuracy, measured not promised

"It doesn't hallucinate" is a claim. Evident publishes a number instead.

A hand-labelled benchmark of **15–20 repos**, each pinned to a commit and covering every supported adapter, scores every engine change on precision and recall per category **and per adapter**. It will run in CI on every pull request and fail the build if any metric drops by more than 2 points.

| Category | Target precision | Target recall | Current |
| --- | :-: | :-: | :-: |
| Routes | ≥ 90% | ≥ 85% | **100% / 100%** (460 routes) |
| Models | ≥ 90% | ≥ 85% | **100% / 100%** (26 models) |
| Route → model read/write edges | ≥ 90% | ≥ 85% | **100% / 100%** (168 edges) |
| External services | tracked | tracked | **100% / 100%** (16 services) |

*Current* = precision / recall on 8 labelled repos (Next.js, Express, NestJS, FastAPI, Django with Prisma and Django ORM), hallucination rate 0.4% (2026-11-11). The labels were written from source by an AI assistant and are awaiting the owner's review, and these repos are fairly conventional. Expect the numbers to drop as the set grows to 15–20 repos with public open-source apps. Fastify, Flask, Drizzle, TypeORM, Mongoose and SQLAlchemy have fixture tests but no labelled repos yet. Run it yourself: `cd engine && uv run evident-bench --verbose`.

The same repos are run through GitDiagram as a baseline, so the comparison is honest and reproducible. Method: [benchmark labelling guide](docs/labelling-guide.md). Results: the public `/benchmarks` page *(at launch)*.

## How it is different

| | Evident | GitDiagram | DeepWiki | CodeBoarding |
| --- | :-: | :-: | :-: | :-: |
| Source of truth | Static analysis | LLM over file tree | LLM-written wiki | LSP + LLM agents |
| Level of detail | Routes, handlers, tables, services | Folders and modules | Modules | Modules and components |
| Line-level evidence on every edge | ✅ | — | — | — |
| End-to-end request tracing | ✅ | — | — | — |
| Interactive graph | ✅ React Flow | Mermaid | Mermaid | Mermaid |
| Published accuracy score, per stack | ✅ | — | — | — |
| CLI + agent skill, fully offline | ✅ | — | — | ✅ |
| Language breadth | Per-framework adapters, each benchmarked | Any | Any | Many |

Evident doesn't compete on breadth. Each stack it supports gets a dedicated adapter and its own published score, so a map can be complete and every edge can be proven. Unsupported stacks still get the module and service map.

## Supported stacks

Adapters are tree-sitter queries plus a small mapper ([ADR-0006](docs/adr/0006-adapter-architecture.md)). Each one ships with fixtures, tests and benchmark cases.

| Ecosystem | Frameworks | ORMs | State |
| --- | --- | --- | --- |
| JS / TS | Next.js (App Router, server actions, middleware), Express, NestJS, Fastify | Prisma, Drizzle, TypeORM, Mongoose | ✅ v1 |
| Python | Django (+ Django REST Framework), FastAPI, Flask | Django ORM, SQLAlchemy (incl. SQLModel, Flask-SQLAlchemy) | ✅ v1 |
| Any language | Universal layer: imports, SDK services, env vars, `docker-compose` containers | | ✅ JS/TS and Python |
| Java/Kotlin · PHP · Ruby · C# · Go | Spring Boot, Laravel, Rails, ASP.NET Core, Gin/Echo/Chi | JPA, Eloquent, ActiveRecord, EF Core, GORM | After launch |

Plus `tsconfig` path aliases and npm/pnpm/yarn workspaces.

## Use it from the terminal

The engine is a standalone package (`pip install evident-map`, *not yet published*; for now, install from a clone). It's static and read-only: it never runs your code and writes only inside `.evident/`.

```bash
pip install -e engine          # from a clone, until the PyPI release
evident analyze .              # build or refresh .evident/graph.json
evident trace "POST /api/users"
evident impact User.email
evident find --writes Invoice
evident health --severity warning
evident show model:User
```

`evident export --format md --out docs/architecture.md` writes a commit-stamped architecture report in which every row cites `file:line`; `--format json` prints the graph.

`evident open` serves the interactive map for the repo on `127.0.0.1` (no Node, nothing uploaded). `evident share` uploads the graph's metadata, never code, to the hosted viewer and prints an expiring link; it asks first, and `evident share --delete ID` removes it early.

Every command takes `--json`, `--limit`, `--depth`, `--no-llm` and `--repo PATH|URL`. Exit codes: `0` ok · `1` findings or no match · `2` usage error · `3` analysis error.

`uv run evident-bench` scores the engine against the labelled benchmark repos (cloned read-only at their pinned commits).

## Use with Claude

The Claude skill in [`skills/evident/`](skills/evident/SKILL.md) drives the CLI for you:

- Once per session it runs `evident analyze . --no-llm` (offline) and leads with a short summary.
- Before you edit a model, shared module, middleware or env var, it runs `evident impact` and tells you which routes are affected.
- It explains flows with `trace` and checks new routes with `health`.
- It cites `file:line` for every claim and flags inferred edges. It never claims a dependency the tool didn't return and never runs `share` unless you ask.

**Install** (Claude Code): copy `skills/evident/` into your project's `.claude/skills/` (or `~/.claude/skills/` for every project). If the `evident` CLI is missing, the skill asks before running `scripts/ensure_installed.sh` (or `.ps1` on Windows).

**Does it help?** [`skill-tasks/`](skill-tasks/) runs 12 architecture questions over the fixture repos, twice each, with and without the skill, and grades the answers against expected facts and citations. On Claude Haiku: **24/24 passed with the skill, 21/24 without**, with about 5.0 vs 6.2 tool calls per task ([results](skill-tasks/results/latest.md)). Without the skill, the misses were dropped citations and missed Mongoose routes.

## How it works

```mermaid
flowchart LR
    C[evident CLI<br/>Claude skill] --> L
    U[Browser] -->|GitHub URL| W[Next.js app]
    W -->|submit / SSE progress| A[FastAPI]
    A -->|one job per commit| Q[(Redis queue)]
    Q --> K

    subgraph K[evident engine · six stages]
        direction LR
        S1[1 · Fetch<br/>shallow clone] --> S2[2 · Parse<br/>tree-sitter]
        S2 --> S3[3 · Extract<br/>universal layer<br/>+ adapters]
        S3 --> S4[4 · Link<br/>resolve imports<br/>build graph]
        S4 --> S5[5 · Analyse<br/>health checks]
        S5 --> S6[6 · Group<br/>LLM labels existing IDs<br/>validated, then saved]
    end
    L[local .evident/ cache] --- K

    K -->|versioned graph JSON| P[(Postgres<br/>cache by repo@sha)]
    A --> P
```

Five of the six stages are deterministic. The LLM stage can only label node IDs the engine already found, its output is validated before anything is saved, and `--no-llm` skips it entirely. Every graph conforms to a versioned [JSON Schema](schema/graph.schema.json), the single contract between the engine and every front-end.

**Safe by design:** Evident never runs the code it analyses. There's no `npm install`, no build and no scripts. Clones are shallow and size-capped, every job has a time limit, temp directories are wiped after each job, and every IP is rate limited. See the [threat model](docs/security.md).

## Quick start

The engine CLI runs from a clone:

```bash
git clone https://github.com/aadilsal/Evident.git
cd Evident/engine
uv sync
uv run evident analyze /path/to/your/app     # add GROQ_API_KEY to the environment for LLM group names
```

The service (API, worker, Postgres, Redis) runs with Docker Compose:

```bash
cp .env.example .env                        # GROQ_API_KEY, POSTGRES_PASSWORD, ...
docker compose -f deploy/docker-compose.yml up --build
python engine/scripts/smoke_service.py      # submits a repo, follows the SSE stream, checks the graph
```

API docs: <http://localhost:8000/api/docs>.

The web app (`web/`) is a static Next.js export. Point it at an API with `NEXT_PUBLIC_API_URL`; without one it still serves the gallery, benchmarks and local maps:

```bash
cd web && npm ci
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev   # the API needs EVIDENT_CORS_ORIGINS=http://localhost:3000
npm run build:bundle                                    # build and copy the UI into the package for `evident open`
```

Working on the code instead? See [CONTRIBUTING.md](CONTRIBUTING.md).

## Tech stack

| Layer | Technology |
| --- | --- |
| Analysis engine + CLI | Python 3.12, tree-sitter (per-language grammars), custom import resolver, adapter registry |
| Agent integration | Claude skill (`skills/evident/`); MCP server in v2 |
| API | FastAPI, Server-Sent Events, auto-generated OpenAPI docs |
| Jobs | arq on Redis; each analysis in a child process killed at the job timeout |
| Storage | Postgres (jobs, cached graphs, findings, benchmark history) |
| AI | Groq (free tier, `openai/gpt-oss-20b` by default): one call per uncached commit, IDs and labels only (never code), validated against node IDs, directory-group fallback |
| Frontend | Next.js static export, TypeScript, React Flow, ELK.js (orthogonal routing, Web Worker), anime.js, Shiki, Tailwind v4 with tokens generated from DESIGN.md; the same build is bundled into the pip package for `evident open` |
| Infra | Site on Vercel; API stack in Docker Compose on one server with Caddy (automatic HTTPS) ([ADR-0008](docs/adr/0008-static-web-on-vercel-api-on-one-server.md)) |
| Quality | ruff, mypy, pytest, ESLint, Prettier, Vitest (TS queries checked against the CLI's answers), pre-commit, Conventional Commits, benchmark gate in CI (Linux + Windows) |

## Roadmap

- **v1 (launch):** engine + JS/TS and Python adapters, CLI, Claude skill, five views (system overview, route map, data model, request tracer, health findings), blast radius, live progress, featured gallery, PNG/SVG/Markdown/JSON exports, "report a wrong edge"
- **v1.5:** *Ask the map* (Q&A grounded in the graph, citing node IDs), commit time machine and diff, README embed, onboarding tour, Mermaid/C4/OpenAPI/SARIF exports
- **v2:** PR architecture bot (GitHub Action), MCP server, private repos / Pro tier
- **After launch:** Spring Boot → Laravel → Rails → ASP.NET Core → Go adapters

Full scope and rationale: [PRD](docs/PRD.md) · [Architecture](docs/architecture.md) · [Decision records](docs/adr/)

## Documentation

| Doc | What's in it |
| --- | --- |
| [PRD](docs/PRD.md) | Users, requirements, success metrics, milestones |
| [Architecture](docs/architecture.md) · [Essentials](docs/architecture-essentials.md) | Full system design · the one-page rules |
| [Graph schema](schema/) | The engine ↔ front-end contract |
| [DESIGN.md](DESIGN.md) | Visual design system: tokens, components, motion rules |
| [ADRs](docs/adr/) | Python + tree-sitter, React Flow, ID-only LLM, self-hosting, CLI-first, adapters, Groq |
| [Labelling guide](docs/labelling-guide.md) | How ground truth is counted |
| [Threat model](docs/security.md) · [Security policy](SECURITY.md) | Analysing untrusted repos safely; share-data rules |

## Contributing

Issues and PRs are welcome, and **"the map is wrong" reports are the most valuable kind**. Use the *Incorrect map* issue template with the repo URL and commit, and each one becomes a benchmark case. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
