# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **Phase 4 (Interface) complete:** `web/`, a Next.js static export (ADR-0008) that runs on Vercel and inside the pip package:
  - map UI with five views (system overview with collapsible LLM groups, route map, data model, request tracer, blast radius) plus a focus view for findings;
  - ELK orthogonal layout in a Web Worker, drawn along ELK's routes;
  - evidence panel with Shiki-highlighted snippets at the pinned commit and GitHub permalinks;
  - hop-by-hop trace animation (anime.js), layer filters, ⌘K search, commit-pinned permalinks, light and dark themes, a mobile layout and an unsupported-stack screen;
  - exports: PNG/SVG of the current view (stamped with repo, SHA and date), graph JSON, and a printable architecture report (PDF);
  - "report a wrong node/edge"
- Site pages:
  - a landing page with a live, clickable gallery map;
  - a gallery of 5 pre-analysed repos (static JSON, LLM-grouped);
  - `/benchmarks` with per-category tables and an F1 history chart;
  - supported stacks with per-adapter scores;
  - live analysis progress over SSE (a six-stop transit line);
  - privacy and terms
- Design tokens generated from DESIGN.md and TS types generated from the schema, with a CI check; Vitest checks trace and impact against goldens produced by the engine
- `evident open`: serves the bundled UI on `127.0.0.1`. It serves only files the graph cites, refuses symlinks and foreign `Host` headers, and sends a CSP
- `evident share`: an opt-in, metadata-only upload with an expiring link; `--delete` removes it with the saved token
- API:
  - `POST/GET/DELETE /api/shares`, validated against the packaged schema, size-capped and rate-limited;
  - `POST /api/reports`;
  - CORS for the site's exact origins (`EVIDENT_CORS_ORIGINS`), and `EVIDENT_PUBLIC_URL` for share links
- `evident-bench --history` appends a point per Evident commit (`benchmark/results/history.json`)
- `engine/scripts/build_gallery.py`; CI job for `web/` (generated-file check, Prettier, ESLint, typecheck, tests, build); `web/vercel.json` security headers
- ADR-0008: the static web app runs on Vercel, and the API and workers run on one server
- **Phase 3 (Service) complete:** `evident.service` (`pip install evident-map[service]`): FastAPI API (`POST /api/analyses`, status, SSE events, immutable graphs, gallery, benchmarks, health, OpenAPI at `/api/docs`), arq worker running each analysis in a child process with a hard timeout, Postgres store (jobs, graphs, findings, benchmark runs), Redis broker (queue, progress pub/sub, per-IP-hash rate limits), job dedupe per commit, temp-dir sweeper; `engine/Dockerfile`, hardened `deploy/docker-compose.yml`, `scripts/smoke_service.py`, and a CI job that runs it end to end against Postgres and Redis
- LLM grouping (ADR-0003/0007): Groq client behind a provider interface, compact `key|type|label|path` prompt under a size budget, strict validator (existing IDs only, one group per node), same-file and same-directory propagation, 429 retry, directory-group fallback; `analyze` progress hooks per stage
- Python support: tree-sitter Python summaries, module resolution (relative, dotted, packages, submodules), Python SDK catalogue, env reads (`os.environ`, `os.getenv`), request-body reads; adapters for FastAPI, Flask, Django (URLconf, class views, DRF routers and actions), Django ORM and SQLAlchemy (incl. SQLModel and Flask-SQLAlchemy)
- Benchmark: Insight-OS, SpotterTruckLogging and JobFinder labelled (8 repos, 100% P/R per category); the runner retries a failed fetch, reuses verified local clones, and refuses to trust a partial run
- Graph schema `1.2.0` (`fastapi`/`flask`/`django` frameworks, `django-orm`/`sqlalchemy` ORMs); `GITHUB_TOKEN` for GitHub metadata calls
- **Phase 2 (Claude skill) complete:** `skills/evident/` with `SKILL.md` and `ensure_installed.sh`/`.ps1` (installs from the official repo until PyPI). Skill-task evals: 24/24 with the skill vs 21/24 without (Claude Haiku, 12 tasks x 2 runs)
- `skill-tasks/`: 12 graded agent tasks and an isolated `claude -p` runner (project settings only, no MCP, tools limited to `evident` and read-only commands)
- `evident export --format md|json [--out FILE]`: commit-stamped architecture report with GitHub permalinks, or the graph JSON
- `analyze` is summary-first: top routes, models, services and findings with `file:line` (also as `--json` results)
- CLI output schema `1.2.0` (`export` command); package version `0.2.0`; CLI streams are UTF-8 on Windows
- **Phase 1 (Engine) complete, Gate A met:** 100% precision and recall on routes, models, services and route→model edges across the first 5 labelled repos
- tree-sitter parsing (TS/TSX/JS) and a cacheable per-file summary: imports, exports, CommonJS, scopes, calls, locals, decorators, env reads, request-body reads
- Linker: relative, `tsconfig`/`jsconfig` path and workspace module resolution; symbol resolution through re-exports and `export *`; package taint tracking (Prisma client, SDK bindings); NestJS-style `this.field.method()` resolution
- Adapters (ADR-0006 registry): Next.js App Router (routes, pages, layouts, server actions, `middleware.ts` matchers), Express (mount prefixes, factory routers, `use` ordering, `route()` chains, wrappers), NestJS (controllers, global prefix, guards), Fastify (plugins, prefixes, hooks, `route()`), Prisma (models, relations, nested writes), Drizzle, TypeORM, Mongoose
- Universal layer: module graph, SDK service catalogue, env vars with `.env.example` documentation, `docker-compose` containers (values never read), stack detection for JS, Python, Java, Go, PHP, Ruby and .NET manifests, plus a fallback message for unsupported stacks
- Health rule `unvalidated-body`; auth detection for middleware and handlers
- `evident-bench`: labelling-guide scoring per category and per adapter, hallucination rate, `--baseline` gate (>2 points fails); ground truth for 5 repos and a committed baseline
- `.pre-commit-config.yaml` (ruff, prettier, schema validation, gitleaks, Conventional Commits) and a CI workflow (pre-commit; mypy + pytest on Linux and Windows; benchmark gate)
- `.env.example` (`GROQ_API_KEY`)
- Project documentation: PRD, architecture, threat model, ADRs 0001–0004, benchmark labelling guide, DESIGN.md
- Graph JSON Schema `1.1.0` (`container` nodes, `stack`, `action:` paths, `orm`, `checksAuth`, `bodyLine`, `validatesBody`) with a validated example; CLI output schema `1.1.0` (`stats.stack`); `local` host for folders
- `evident-map` package (imports as `evident`): `analyze`, `trace`, `impact`, `find`, `health`, `show` with `--json`, exit codes 0–3, an incremental `.evident/` cache, a safe GitHub clone (shallow, or an exact pinned commit) and five health rules
- Repo standards: ruff and mypy config, Prettier, EditorConfig, Conventional Commits, issue and PR templates
- ADR 0005 (CLI-first, three front-ends), ADR 0006 (adapter architecture, wider v1 scope), ADR 0007 (Groq for grouping)
- `benchmark/repos.yaml` with pinned candidate repos and a ground-truth template; share-data and local-mode rules in `docs/security.md`

### Changed

- PRD, architecture, README and labelling guide now match the feature tracker's v1 scope: JS/TS + Python adapters, CLI, Claude skill
- Docker images build from the repo root (`docker build -f engine/Dockerfile .`). The package ships a copy of the graph schema, and a test keeps it identical to `schema/graph.schema.json`
- The skill offers `evident open` and covers the Python stacks; the CLI and package descriptions no longer say JS/TS only
- Compose services restart unless stopped

### Fixed

- A cache hit returned directory groups from an earlier `--no-llm` run even when LLM grouping was requested. It now regroups without re-parsing

### Not yet added

- Hosting (domain, API server, Vercel project), Caddyfile, PyPI release with the bundled UI, terminal GIF and demo video: Phase 5
