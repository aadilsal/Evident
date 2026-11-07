# AGENTS.md

Instructions for AI coding agents (Claude Code, Codex, Cursor, Copilot) working in this repo. Humans should read [CONTRIBUTING.md](CONTRIBUTING.md) instead; the rules are the same.

## What this project is

Evident turns a public GitHub repo (Next.js / Express / Prisma) into an evidence-backed architecture graph. A Python engine extracts facts with tree-sitter, an LLM only groups and labels them, and a Next.js frontend renders the graph with React Flow. Read [docs/architecture-essentials.md](docs/architecture-essentials.md) before changing anything.

## Repo map

| Path | What lives there |
| --- | --- |
| `engine/` | Python package: FastAPI API, arq worker, extractors, linker, health checks, LLM grouping, benchmark runner |
| `web/` | Next.js + TypeScript frontend (map UI, gallery, benchmarks page) |
| `schema/graph.schema.json` | **The contract** between engine and web. Versioned. |
| `benchmark/ground-truth/` | Hand-labelled YAML per benchmark repo |
| `DESIGN.md` | Visual design system (tokens + rules). Read before writing any UI. |
| `docs/` | Design doc (source of truth), PRD, architecture, ADRs, threat model, labelling guide, runbook |
| `deploy/` | Docker Compose, Caddyfile *(added with infra work)* |

## Non-negotiable rules

1. **Never execute analysed repo code.** No `npm install`, `npx`, builds, `eval`, `require()`/`import()` of cloned files, or git hooks. Parse with tree-sitter and read files as text only. See [docs/security.md](docs/security.md).
2. **Every node and edge needs evidence** (`file`, `startLine`, `endLine`, `sha`). If you can't point to a line, don't emit the element.
3. **The LLM never creates nodes or edges.** It may only return groups and labels that reference existing node IDs; the validator drops anything else. Don't loosen the validator to make a test pass.
4. **Schema changes are contract changes.** Edit `schema/graph.schema.json`, bump `schemaVersion` (minor = additive, major = breaking), update `schema/examples/`, and update both engine and web in the same PR.
5. **Never read or store env var values**, only names.
6. **Don't regress the benchmark.** CI fails if precision or recall drops more than 2 points in any category. If a change trades one metric for another, say so in the PR.
7. **Decisions go in ADRs.** If you change a decision recorded in `docs/adr/` or `docs/design-doc.md`, write a new ADR that supersedes it. Don't silently diverge.

## Commands

```bash
# setup
pre-commit install --hook-type pre-commit --hook-type commit-msg
cd engine && uv sync          # Python deps
cd web && npm ci              # Node deps

# check before every commit
pre-commit run --all-files    # ruff, prettier, schema validation, secret scan
cd engine && uv run mypy && uv run pytest
cd web && npm run lint && npm run typecheck

# benchmark (needs network to clone pinned repos)
cd engine && uv run evident-bench
```

## Code style

- Python: ruff (lint + format) and mypy `strict`. Type every public function. Prefer plain functions and dataclasses over class hierarchies.
- TypeScript: ESLint + Prettier, `strict` tsconfig. Graph types are generated from or checked against the JSON Schema. Don't hand-write a divergent copy.
- UI: follow `DESIGN.md` exactly: tokens only (no raw hex), anime.js for in-app motion, Aceternity UI only from its allowlist and only on marketing pages.
- Comments: one line, saying why. History goes in commit messages.
- Commits: [Conventional Commits](https://www.conventionalcommits.org/) (`feat(engine): extract express router mounts`). Scopes: `engine`, `api`, `worker`, `web`, `schema`, `bench`, `infra`, `docs`.

## Testing expectations

- Each extractor gets fixture-based tests: a tiny TS/JS snippet in `engine/tests/fixtures/` and the exact nodes and edges expected, evidence lines included.
- Any bug in the map ("missed route", "phantom edge") gets a regression fixture before the fix.
- Engine output in tests is validated against `schema/graph.schema.json`.

## When unsure

Check `docs/design-doc.md` and `docs/adr/` first. If they don't answer it, ask rather than guess, especially about scope (v1 vs v1.5 vs v2).
