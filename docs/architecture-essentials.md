# Architecture essentials

The one page to read before touching the code. Details: [architecture.md](architecture.md).

## The shape

```
Browser → Caddy → Next.js (web)
                → FastAPI (api) → Redis queue → Worker → Postgres
                                                  ├→ GitHub (shallow clone)
                                                  └→ LLM (node IDs only)
```

The worker runs six stages: **Fetch → Parse → Extract → Link → Analyse → Group.** Only *Group* touches an LLM.

## The seven invariants

Break one of these and the product's core claim breaks with it.

1. **Facts come from code, never from the LLM.** Nodes and edges are produced only by deterministic extractors. The LLM returns groups and labels over existing node IDs, and the validator drops any ID it doesn't recognise. ([ADR-0003](adr/0003-llm-labels-existing-node-ids.md))
2. **No receipt, no element.** Every node and edge has at least one `{file, startLine, endLine, sha}`. The schema enforces `minItems: 1`.
3. **Never execute analysed code.** Read files as text and parse with tree-sitter. No installs, builds, scripts, hooks or `import()` of repo files. ([threat-model.md](threat-model.md))
4. **One contract.** `schema/graph.schema.json` is the only interface between engine and web. Changing it means bumping `schemaVersion` and updating both sides in one PR.
5. **Deterministic and cached.** The same `repo@sha + engineVersion` always produces the same facts. Graphs are immutable and cached by that key.
6. **Honest uncertainty.** If a link can't be proven (a wrapper, a dynamic path), emit it as `inferred` with lower `confidence`, or don't emit it. Never upgrade inferred to extracted.
7. **Measured, not claimed.** Engine changes run the benchmark in CI, and a drop of more than 2 points in any category fails the build.

## Where things go

| If you're adding… | Put it in… |
| --- | --- |
| A new framework pattern (e.g. Express `Router.route()`) | an extractor in `engine/src/evident/extract/` + a fixture test |
| A new SDK/service | the service catalogue (data, not code) + a fixture |
| A health check | `engine/src/evident/analyse/` with an evidence-bearing finding |
| A new node/edge type or field | `schema/graph.schema.json` first, then engine, then web |
| A UI view | `web/`, as a pure selector over the graph, styled per [DESIGN.md](../DESIGN.md) |
| A decision that changes any of the above | a new ADR in `docs/adr/` |

## Limits (defaults)

| Limit | Value |
| --- | --- |
| Repo size | 200 MB |
| File count | 10,000 |
| Single file parsed | 1 MB |
| Job timeout | 120 s |
| Submissions per IP | 10 / hour *(proposed)* |
