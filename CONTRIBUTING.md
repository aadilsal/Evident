# Contributing to Evident

Thanks for helping. The most useful contribution is a **"the map is wrong" report**: open an *Incorrect map* issue with the repo URL, commit and what's missing or invented. Each one becomes a test fixture or a benchmark case.

## Before you start

Read [docs/architecture-essentials.md](docs/architecture-essentials.md) (one page). It lists the invariants every change must keep. For UI work, also read [DESIGN.md](DESIGN.md).

## Setup

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 22+, Docker, [pre-commit](https://pre-commit.com/).

```bash
pre-commit install --hook-type pre-commit --hook-type commit-msg
cd engine && uv sync
cd ../web && npm ci
```

## Workflow

1. Branch from `main`: `feat/express-router-mounts`, `fix/prisma-wrapper-calls`.
2. Write a failing fixture test first for any extractor change or map bug (`engine/tests/fixtures/`).
3. Keep PRs small and focused, one concern per PR.
4. Run checks locally:
   ```bash
   pre-commit run --all-files
   cd engine && uv run mypy && uv run pytest
   cd web && npm run lint && npm run typecheck
   ```
5. Open a PR using the template. CI runs lint, types, tests, schema validation and the benchmark.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/), enforced by a commit-msg hook and on PR titles:

```
feat(engine): resolve express router mount prefixes
fix(web): keep trace highlight when collapsing a group
docs(adr): supersede 0002 with canvas renderer decision
```

Types: `feat`, `fix`, `perf`, `refactor`, `test`, `docs`, `build`, `ci`, `chore`. Scopes: `engine`, `api`, `worker`, `web`, `schema`, `bench`, `infra`, `docs`.

## The benchmark rule

If your change touches the engine, CI re-runs the benchmark. **A drop of more than 2 points in any category fails the build.** If a trade-off is intentional (e.g. +5 recall, −1 precision), explain it in the PR.

Adding a benchmark repo? Follow the [labelling guide](docs/labelling-guide.md) exactly. Unlabelled conventions make the numbers meaningless.

## Changing a decision

Decisions live in [docs/adr/](docs/adr/). To change one, add a new ADR that supersedes it (copy `0000-template.md`) and link it from the old one. Update [docs/PRD.md](docs/PRD.md) if scope changes.

## Changing the graph schema

`schema/graph.schema.json` is the contract between engine and web. Bump `schemaVersion` (minor = additive, major = breaking), update `schema/examples/`, and change both sides in the same PR.

## Code of conduct

Be kind, be specific, assume good intent.
