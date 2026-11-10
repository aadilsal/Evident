# 0001. Use Python + tree-sitter for the analysis engine

- **Status:** Accepted. Language scope extended beyond JS/TS by [0006](0006-adapter-architecture.md).
- **Date:** 2026-11-07

## Context

The engine must extract routes, Prisma calls, SDK imports and env reads from JS/TS repos it must never execute. It also hosts the API, the worker, the LLM step and the benchmark/eval harness. Python is the strongest ecosystem for evals and data work, and is the author's portfolio focus alongside TypeScript.

## Decision

Write the engine in Python and parse JS/TS/TSX with tree-sitter (via `tree-sitter` Python bindings and the official grammars). Parse `schema.prisma` with a small dedicated parser. Build our own import resolver for `tsconfig` paths and workspaces.

## Consequences

- Fast, error-tolerant parsing of partial or broken files, with exact byte and line ranges for evidence.
- Pure syntax: no code runs, which supports the "never execute" rule.
- **Cost:** no TypeScript type checker. Dynamic route registration, computed paths and type-driven re-exports can be missed. We mitigate with confidence scores, `inferred` edges and benchmark-measured recall.
- One language for API, worker, engine and evals keeps deployment simple.

## Alternatives considered

- **TypeScript compiler API / ts-morph (Node):** full type info, but heavyweight per repo, slower, and needs a project setup that often expects installed dependencies. It also splits the backend across two languages.
- **LSP (as CodeBoarding does):** needs language servers and often `node_modules` to be useful; heavier sandboxing.
- **Regex/grep:** too fragile for nested routers, aliases and multi-line calls.
