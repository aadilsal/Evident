# 0005. Build a CLI-first engine that powers three front-ends

- **Status:** Accepted
- **Date:** 2026-11-10

## Context

The original plan treated the engine as an internal stage of a hosted web service. But the people who most need "what talks to what" answers are often coding agents working inside a repo, and developers on private code that can't be sent to a public site. A hosted-only design serves neither. The engine also needs a way to run on a laptop for fixture work and the benchmark.

## Decision

The engine ships as a standalone pip package, `evident-map` (imports as `evident`, provides the `evident` command). It's a library plus a CLI, and it runs fully offline and read-only, writing only to `.evident/`. Every other surface is a thin client over the same package and the same graph JSON:

1. **CLI:** `analyze`, `trace`, `impact`, `find`, `health`, `show`, `export`, `open`, `share`. Each has `--json` output (the [CLI output schema](../../schema/cli-output.schema.json)), `file:line` evidence, exit codes 0/1/2/3, and `--limit`/`--depth`. Output is summary-first and token-efficient.
2. **Claude skill** (`skills/evident/`): runs `analyze --no-llm` once per session, runs `impact` before edits to models or shared code, and always cites the evidence the tool returned.
3. **Web app:** the hosted service (API, worker and map UI) calls the same library. The map UI has a data-source switch: API mode or local-file mode. It's also bundled as a static export inside the pip package, so `evident open` needs no Node.

The MCP server (v2) becomes a fourth thin client.

## Consequences

- One extraction code path. The benchmark, the CLI, the skill and the web app can't disagree about facts.
- Local mode gives a privacy story for private repos without building accounts or OAuth.
- The skill can ship around week 4, before the hosted service, and be measured with `skill-tasks/` evals (with vs without the skill).
- **Cost:** the CLI's JSON envelope is a second public contract to version alongside the graph schema. The static map export adds a build step to packaging.
- `evident share` must upload graph metadata only (never source), opt-in and expiring. See [security.md](../security.md).

## Alternatives considered

- **Web-only service:** simpler packaging, but no agent or private-repo story, and the engine is harder to test outside the worker.
- **Separate CLI and service engines:** duplicated extraction logic would drift and break the benchmark's meaning.
