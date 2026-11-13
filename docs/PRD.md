# Evident: Product Requirements (v1)

| | |
| --- | --- |
| Owner | Aadil Salman Butt |
| Status | Phases 1 (Engine, Gate A 2026-11-10), 2 (Skill), 3 (Service) (2026-11-11) and 4 (Interface, 2026-11-13) complete; Phase 5 (Launch) next |
| Scope reference | This PRD plus the [ADRs](adr/). Scope follows the internal feature tracker; update all three when a decision changes. |
| Last updated | 2026-11-10 |

## 1. Problem

Developers who land in an unfamiliar codebase, whether onboarding, evaluating an open-source project or reviewing a PR, spend hours answering *what talks to what*. Coding agents have the same problem and fill the gaps by guessing. Existing AI diagram tools (GitDiagram, DeepWiki, CodeBoarding) produce folder- or module-level Mermaid diagrams, largely inferred by an LLM, with no way to verify a box or an arrow. Users report hallucinated components. A diagram that can't be checked can't be trusted.

## 2. Product

An evidence-backed architecture map for web apps. Point it at a repo (a public GitHub URL, or a local folder through the CLI) and get routes, handlers, middleware, models/tables, external services, env vars and containers, plus the edges between them. Every element links to the file and line range that proves it. Static analysis produces the facts; an LLM only groups and labels them.

It's **CLI-first** ([ADR-0005](adr/0005-cli-first-three-front-ends.md)). One pip package (`evident-map`) powers three front-ends:
- the `evident` CLI
- a Claude skill for coding agents
- the hosted web app (and later an MCP server)

Extraction runs through **per-framework adapters on a universal layer** ([ADR-0006](adr/0006-adapter-architecture.md)).

## 3. Users

| Persona | Job to be done | What success looks like |
| --- | --- | --- |
| **New joiner** | Understand a codebase in their first week | Finds where a feature's data is written in under 5 minutes |
| **OSS evaluator** | Decide whether to adopt or contribute | Sees the system's shape and risks before cloning |
| **Reviewer** | Judge a PR's architectural impact | Sees blast radius of a changed model or file |
| **Coding agent (via the Claude skill)** | Change code without breaking callers it can't see | Runs `impact` before editing a model; cites `file:line` for every claimed dependency |
| **Developer on a private repo** | Same map, without uploading code | `evident analyze .` works offline; nothing leaves the machine unless they run `share` |
| **Recruiter / hiring manager** *(portfolio audience)* | Judge the author's engineering | Opens a gallery map in 10 seconds, sees the benchmark score |

## 4. Goals and non-goals

**Goals (v1)**
1. Extract routes, models, DB read/write edges and external services with **≥ 90% precision and ≥ 85% recall** on the benchmark, reported per category **and per adapter**.
2. Every node and edge carries line-level evidence; no surface (CLI, skill, UI) shows an element without a receipt.
3. Demo works in 10 seconds with no waiting (featured gallery).
4. Publish accuracy openly (`/benchmarks`), with a GitDiagram baseline.
5. A Claude skill that measurably improves agent tasks (with vs without the skill).
6. Unsupported stacks degrade gracefully to the universal map, never a blank screen.

**Non-goals (v1)**
- Hosted analysis of private repos, authentication, user accounts (local CLI covers private code; hosted private repos are a v2 Pro tier)
- Post-launch ecosystems before launch: Spring Boot, Laravel, Rails, ASP.NET Core, Go
- Next.js Pages Router, Remix
- Executing, installing or building any analysed code
- Free-form AI chat (Ask the map is v1.5 and grounded)

## 5. Functional requirements (v1)

### 5.1 Analyse a repo
- **FR-1** Accept a local path (CLI) or `github.com/owner/repo` (optionally `/tree/<ref>`); resolve to a commit SHA, or a worktree hash for a folder without git.
- **FR-2** If a graph exists for `repo@sha + engineVersion`, return it from cache. Locally, the `.evident/` cache re-runs only changed files (target 1–2 s).
- **FR-3** Hosted: enqueue one job per commit; duplicate submissions attach to the running job.
- **FR-4** Hosted: stream progress over SSE by stage: fetch → parse → extract → link → analyse → group, with live counts.
- **FR-5** Reject with a clear message: non-GitHub hosts, private or missing repos, repos over size limits (default 200 MB / 10k files). An unsupported stack is **not** rejected; see FR-12.

### 5.2 Engine
- **FR-6** Stack detection from manifests (`package.json`, `pyproject.toml`/`requirements.txt`, `pom.xml`/Gradle, `go.mod`, `composer.json`, `Gemfile`, `.csproj`); every matching adapter runs, including several at once in monorepos.
- **FR-7** Universal layer (any language tree-sitter parses): module/import graph, external services from manifests + SDK imports (maintained catalogue), env var reads (names only) and whether each is documented in `.env.example`, containers from `docker-compose.yml`.
- **FR-8** Module resolution for `tsconfig` `paths`/`baseUrl` aliases and npm/pnpm/yarn workspaces.
- **FR-9** Framework adapters (v1): **Next.js** App Router (route handlers, pages, layouts, `"use server"` actions, `middleware.ts` + `config.matcher`), **Express** (`app|router.METHOD`, `app.use(prefix, router)` mounts with prefix resolution, middleware chains), **NestJS**, **Fastify**, **Django**, **FastAPI**, **Flask**.
- **FR-10** ORM adapters (v1): **Prisma** (models, fields, relations, `@@map`; `prisma.<model>.<op>()` classified read/write, including through re-exported client instances), **Drizzle**, **TypeORM**, **Mongoose**, **Django ORM**, **SQLAlchemy**.
- **FR-11** Each adapter is tree-sitter `.scm` queries plus a small Python mapper, registered in an adapter registry, with a fixture repo, snapshot tests and benchmark cases.
- **FR-12** Graceful fallback: unsupported framework → universal map plus "Routes and models aren't supported for <framework> yet. Here's the module and service map we found."
- **FR-13** Fully offline local mode and `--no-llm` mode. The engine never executes repo code and writes only to `.evident/`.

### 5.3 CLI
All commands support `--json` (schema-valid envelope) and human output, `file:line` evidence, exit codes `0` ok / `1` findings or no match / `2` usage / `3` analysis error, `--limit`/`--depth`, and summary-first output.

- **FR-14** `analyze <path-or-url>`, `trace "<METHOD> <path>"`, `impact <node>`, `find --reads/--writes <Model>`, `health`, `show <node-id>`.
- **FR-15** `export --format …` (PNG/SVG, architecture report Markdown/PDF, graph JSON), stamped with repo, SHA and date, matching the current view and filters.
- **FR-16** `open`: the local map UI in the browser, served from a static export bundled in the package (no Node needed).
- **FR-17** `share`: opt-in upload of graph **metadata only** (no source code), returning an expiring link.

### 5.4 Claude skill (`skills/evident/`)
- **FR-18** `SKILL.md` with a `description` that says when to use it; `scripts/ensure_installed.sh` installs the CLI if missing.
- **FR-19** Runs `analyze --no-llm` once per session and leads with a short summary (routes, models, services, top findings with `file:line`); offers `evident open` once per session.
- **FR-20** Runs `impact` **before** editing models or shared code; uses `trace` to explain flows and `health` on new or changed routes.
- **FR-21** Always cites evidence, never claims a dependency the tool didn't return, and flags inferred or low-confidence edges. Can write `docs/architecture.md` via `export --format md`. Never runs `share` unless the user asks.

### 5.5 Views (web app and local viewer)
- **FR-22** System overview: LLM-grouped clusters of nodes, collapsible.
- **FR-23** Route map: all routes by path, filterable by method/framework/kind.
- **FR-24** Data model (ERD) from ORM models and relations.
- **FR-25** Request tracer: select a route and highlight route → middleware → handler → functions → models/services, with code per hop.
- **FR-26** Health findings: `unguarded-write`, `unvalidated-body`, `circular-import`, `unused-model`, `undocumented-env`, each with evidence and linked nodes.
- **FR-27** Blast radius: select a model, file or env var and highlight all transitive dependents.
- **FR-28** Evidence panel on every node/edge: file, line range, highlighted snippet, `extracted`/`inferred` badge, confidence, GitHub permalink at the SHA.
- **FR-29** Commit-pinned permalinks encode selected node, filters and active trace.
- **FR-30** "Report a wrong edge": one-click flag that becomes a benchmark case.
- **FR-31** Mobile layout (at minimum a summary plus route and model lists) and an unsupported-stack screen.
- **FR-32** The map UI is its own frontend package with a data-source switch: API mode or local-file mode. It is a static export, deployed to Vercel and bundled into the pip package ([ADR-0008](adr/0008-static-web-on-vercel-api-on-one-server.md)).

### 5.6 Gallery, benchmarks and stacks
- **FR-33** Featured gallery of pre-analysed repos served as static JSON (works when the worker is down).
- **FR-34** `/benchmarks` page: precision/recall/F1 per category and per adapter, hallucination rate, GitDiagram baseline, history chart.
- **FR-35** "Supported stacks" page with per-adapter scores.

## 6. Non-functional requirements

| Area | Requirement | Status |
| --- | --- | --- |
| Correctness | Every element validates against `schema/graph.schema.json`; LLM output references only existing IDs | Fixed |
| Safety | No execution of analysed code; limits per [security.md](security.md) | Fixed |
| Latency | Cached graph < 500 ms; incremental local re-run 1–2 s; fresh analysis of a ~500-file repo p50 < 60 s | Proposed, confirm after first benchmark |
| Cost | Groq free tier ([ADR-0007](adr/0007-groq-for-llm-grouping.md)); one grouping call per uncached commit; auto-fallback to `--no-llm` | Fixed |
| Availability | Gallery and landing page stay up if worker/API is down; uptime monitor alerts | Fixed |
| Portability | CI on Linux **and Windows** | Fixed |
| Privacy | CLI telemetry opt-in only; privacy-friendly site analytics; `share` sends metadata only | Fixed |
| Accessibility | WCAG 2.2 AA; keyboard-navigable graph; colour never the only signal (see [DESIGN.md](../DESIGN.md)) | Fixed |
| Reproducibility | Same commit + engine version → identical graph (except LLM groups, which are cached) | Fixed |

## 7. Success metrics

- **Launch gate:** ≥ 90% precision, ≥ 85% recall on routes, models, DB edges across 15–20 repos covering every v1 adapter.
- Hallucination rate (predicted nodes with no ground-truth match) reported and below 5%. *(Proposed.)*
- Skill evals: 10–15 agent tasks in `skill-tasks/`, run with and without the skill; the skill must win.
- Gallery map time-to-interactive < 3 s.
- Benchmark runs on every PR; no metric regresses > 2 points.

## 8. Release plan

| Tier | Contents | Starts when |
| --- | --- | --- |
| **v1** | Pillars, engine + v1 adapters, CLI, Claude skill, request tracer, health checks, blast radius, gallery, live progress, permalinks, v1 exports, report a wrong edge | Now |
| **v1.5** | Ask the map, commit time machine/diff, README embed, onboarding tour, Mermaid/C4/CSV/OpenAPI/SARIF exports | v1 is live with video and case study |
| **v2** | PR architecture bot, MCP server, private repos / Pro tier | After v1.5 |
| **Rolling** | Spring Boot → Laravel → Rails → ASP.NET Core → Go adapters, one every 1–2 weeks | After launch |

### Milestones

| Phase | Weeks | Contents | Gate |
| --- | --- | --- | --- |
| 1. Engine | 1–3 | Universal layer, JS/TS adapters, linker, schema validator, CLI; label the first 5 benchmark repos | **Gate A:** baseline F1 measured on 5 repos ✅ *(100% P/R per category)* |
| 2. Skill release | 4 | `skills/evident/`, skill-task evals | Skill usable on fixture repos; evals run ✅ *(24/24 with skill vs 21/24 without)* |
| 3. Service | 4–5 | FastAPI, arq worker, SSE, Postgres cache, validated Groq grouping, Python adapters, limits and sandboxing | ✅ *(8 repos at 100% P/R; CI runs the service end to end)* |
| 4. Interface | 5–7 | Dual-mode map UI, five views, tracer, blast radius, exports, mobile | ✅ *(static export; TS queries match the CLI on goldens; `open`/`share` shipped; Compose stack verified end to end)* |
| 5. Launch | 8–10 | 15–20 benchmark repos, GitDiagram baseline, server + Vercel deploy, demo video, case study | **Gate B:** all targets met; runbook tested (deploy, rollback, restore) |

## 9. Risks

| Risk | Mitigation |
| --- | --- |
| Dynamic route registration missed by static analysis | Confidence scores, `inferred` edges, benchmark measures misses |
| Thirteen v1 adapters stretch the 10-week plan | Adapter template + registry; per-adapter metrics show which ones are ready; an adapter without fixtures and benchmark cases doesn't ship |
| Groq free-tier limits change or throttle | Provider-agnostic interface, cache by SHA, automatic `--no-llm` fallback |
| Scope creep beyond the tracker | Ship v1 rows only; v1.5/v2 wait for the launch gate |

## 10. Open questions

- [x] Frontend hosting: **Vercel**, static export ([ADR-0008](adr/0008-static-web-on-vercel-api-on-one-server.md))
- [ ] Backend server: one free-tier cloud server (AWS Free plan or Oracle Always Free under evaluation); domain to be bought by the owner
- [x] LLM provider: **Groq, free tier** ([ADR-0007](adr/0007-groq-for-llm-grouping.md))
- [x] Product name: **Evident**; PyPI package **`evident-map`** (`evident` is taken). Domain still open.
- [x] First benchmark repos: owner's own repos, pinned in [`benchmark/repos.yaml`](../benchmark/repos.yaml)
- [ ] Latency and hallucination-rate targets above: accept or change?
