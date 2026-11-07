# Evident: Product Requirements (v1)

| | |
| --- | --- |
| Owner | Aadil Salman Butt |
| Status | Draft, pre-development |
| Source of truth | [design-doc.md](design-doc.md). If this PRD and the design doc disagree, the design doc wins; fix the PRD. |
| Last updated | 2026-11-07 |

## 1. Problem

Developers who land in an unfamiliar codebase, whether onboarding, evaluating an open-source project or reviewing a PR, spend hours answering *what talks to what*. Existing AI diagram tools (GitDiagram, DeepWiki, CodeBoarding) produce folder- or module-level Mermaid diagrams, largely inferred by an LLM, with no way to verify a box or an arrow. Users report hallucinated components. A diagram that can't be checked can't be trusted.

## 2. Product

An evidence-backed, interactive architecture map for JS/TS full-stack apps (Next.js, Express, Prisma). Paste a public GitHub URL and get routes, handlers, middleware, database tables, external services and env vars, plus the edges between them. Every element links to the file and line range that proves it. Static analysis produces the facts; an LLM only groups and labels them.

## 3. Users

| Persona | Job to be done | What success looks like |
| --- | --- | --- |
| **New joiner** | Understand a codebase in their first week | Finds where a feature's data is written in under 5 minutes |
| **OSS evaluator** | Decide whether to adopt or contribute | Sees the system's shape and risks before cloning |
| **Reviewer** | Judge a PR's architectural impact | Sees blast radius of a changed model or file |
| **Recruiter / hiring manager** *(portfolio audience)* | Judge the author's engineering | Opens a gallery map in 10 seconds, sees the benchmark score |

## 4. Goals and non-goals

**Goals (v1)**
1. Extract routes, models, DB read/write edges and external services with **≥ 90% precision and ≥ 85% recall** on the benchmark.
2. Every node and edge carries line-level evidence; the UI never shows an element without a receipt.
3. Demo works in 10 seconds with no waiting (featured gallery).
4. Publish accuracy openly (`/benchmarks`), with a GitDiagram baseline.

**Non-goals (v1)**
- Private repos, authentication, user accounts
- Frameworks beyond Next.js App Router / Express / Prisma (no NestJS, Remix, Drizzle, Pages Router)
- Languages beyond JS/TS
- Executing, installing or building any analysed code
- Free-form AI chat (Ask the map is v1.5 and grounded)

## 5. Functional requirements (v1)

### 5.1 Analyse a repo
- **FR-1** User pastes `github.com/owner/repo` (optionally `/tree/<ref>`); the system resolves it to a commit SHA.
- **FR-2** If a graph exists for `owner/repo@sha + engineVersion`, return it immediately from cache.
- **FR-3** Otherwise enqueue one job per commit; duplicate submissions attach to the running job.
- **FR-4** Stream progress over SSE by stage: fetch → parse → extract → link → analyse → group, with live counts.
- **FR-5** Reject with a clear message: non-GitHub hosts, private or missing repos, repos over size limits (default 200 MB / 10k files), unsupported stacks (no Next.js/Express/Prisma detected).

### 5.2 Extraction
- **FR-6** Next.js App Router: `app/**/route.{ts,js}` exported methods, pages, layouts, `"use server"` actions, `middleware.ts` + `config.matcher`.
- **FR-7** Express: `app|router.METHOD(path, ...handlers)`, `app.use(prefix, router)` mounts with prefix resolution, middleware chains.
- **FR-8** Prisma: models, fields, relations, `@@map` from `schema.prisma`; `prisma.<model>.<op>()` calls classified read/write, including through re-exported client instances.
- **FR-9** External services from SDK imports via a maintained catalogue (Stripe, AWS S3, Resend, Redis, OpenAI, …).
- **FR-10** `process.env.X` reads (names only), and whether each is documented in `.env.example`.
- **FR-11** Module graph with `tsconfig` `paths`/`baseUrl` aliases and npm/pnpm/yarn workspaces.

### 5.3 Views
- **FR-12** System overview: LLM-grouped clusters of nodes, collapsible.
- **FR-13** Route map: all routes by path, filterable by method/framework/kind.
- **FR-14** Data model (ERD) from Prisma models and relations.
- **FR-15** Request tracer: select a route and highlight route → middleware → handler → functions → models/services, with code per hop.
- **FR-16** Health findings: `unguarded-write`, `unvalidated-body`, `circular-import`, `unused-model`, `undocumented-env`, each with evidence and linked nodes.
- **FR-17** Blast radius: select a model, file or env var and highlight all transitive dependents.
- **FR-18** Evidence panel on every node/edge: file, line range, highlighted snippet, `extracted`/`inferred` badge, confidence, GitHub permalink at the SHA.
- **FR-19** Commit-pinned permalinks encode selected node, filters and active trace.

### 5.4 Gallery and benchmarks
- **FR-20** Featured gallery of pre-analysed popular repos served as static JSON (works when the worker is down).
- **FR-21** `/benchmarks` page: precision/recall/F1 per category, hallucination rate, GitDiagram baseline, history chart.

## 6. Non-functional requirements

| Area | Requirement | Status |
| --- | --- | --- |
| Correctness | Every element validates against `schema/graph.schema.json`; LLM output references only existing IDs | Fixed |
| Safety | No execution of analysed code; limits per [security.md](security.md) | Fixed |
| Latency | Cached graph < 500 ms; fresh analysis of a ~500-file repo p50 < 60 s | Proposed, confirm after first benchmark |
| Cost | LLM spend under a monthly cap; one grouping call per uncached commit | Cap TBD (open question) |
| Availability | Gallery and landing page stay up if worker/API is down; uptime monitor alerts | Fixed |
| Accessibility | WCAG 2.2 AA; keyboard-navigable graph; colour never the only signal (see [DESIGN.md](../DESIGN.md)) | Fixed |
| Reproducibility | Same commit + engine version → identical graph (except LLM groups, which are cached) | Fixed |

## 7. Success metrics

- **Launch gate:** ≥ 90% precision, ≥ 85% recall on routes, models, DB edges across ≥ 15 repos.
- Hallucination rate (predicted nodes with no ground-truth match) reported and below 5%. *(Proposed.)*
- Gallery map time-to-interactive < 3 s.
- Benchmark runs on every PR; no metric regresses > 2 points.

## 8. Release plan

| Tier | Contents | Starts when |
| --- | --- | --- |
| **v1** | Pillars + request tracer, health checks, gallery, live progress, blast radius, permalinks | Now |
| **v1.5** | Ask the map, commit time machine/diff, exports + README embed, onboarding tour | v1 is live with video and case study |
| **v2** | PR architecture bot, local CLI + MCP server | After v1.5 |

### Milestones

*The design doc's milestone diagram (4 phases, 2 gates) is an embed that didn't export; this is a reconstruction from its text. Confirm it.*

1. **Phase 1: Engine.** Extractors, linker, schema validator, CLI output; label the first 5 benchmark repos.
   **Gate A: accuracy.** Benchmark meets targets on the first 5 repos before any UI work.
2. **Phase 2: Service.** FastAPI, arq worker, SSE progress, Postgres cache, LLM grouping and validator, limits and sandboxing.
3. **Phase 3: Map UI.** Five views, evidence panel, tracer, blast radius, permalinks, gallery.
4. **Phase 4: Launch.** 15–20 benchmark repos, `/benchmarks` page, VM deploy, demo GIF/video, case study.
   **Gate B: launch.** All targets met on the full set; runbook tested (deploy, rollback, restore).

## 9. Risks

See [design-doc.md § Risks](design-doc.md#risks-and-open-questions). The top two: dynamic route registration missed by static analysis (mitigation: confidence + benchmark measures misses), and scope creep (mitigation: v1 rows only).

## 10. Open questions

- [ ] VM specs and location (cloud or home)?
- [ ] LLM provider for grouping and monthly spend cap?
- [ ] Product name and domain (working name: **Evident**)?
- [ ] Which 5 repos to label first?
- [ ] Latency and hallucination-rate targets above: accept or change?
