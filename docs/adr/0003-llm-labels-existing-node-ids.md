# 0003. The LLM only groups and labels existing node IDs

- **Status:** Accepted
- **Date:** 2026-11-07

## Context

Competitors' diagrams are LLM-generated and users report invented components. Our positioning is "every edge has a receipt", and we publish a hallucination rate. An LLM is still useful for naming clusters ("Billing", "Auth") and writing one-line summaries.

## Decision

The LLM receives a compact list of existing nodes (ID, type, label, path) and returns only `groups` (`label`, `summary`, `members`). A validator:

1. Drops any member ID that isn't in the graph
2. Drops groups left empty, caps label and summary lengths
3. Marks every group `source: inferred`
4. Validates the final graph against the JSON Schema

The LLM can never create, delete or modify nodes or edges. If the call fails, the graph falls back to deterministic directory-based groups.

## Consequences

- The hallucination rate for nodes and edges is zero by construction. The only LLM risk is a poor grouping, which is measured by a rubric in the benchmark.
- File contents never reach the LLM, which removes most prompt-injection surface ([threat-model.md](../threat-model.md) T6) and keeps token cost small.
- **Cost:** the LLM can't recover facts static analysis missed. That's intentional: misses show up as recall in the benchmark instead of being papered over.

## Alternatives considered

- **LLM extracts facts from code:** higher recall on dynamic patterns, but unverifiable and expensive.
- **No LLM:** directory grouping is serviceable but produces poor names on flat repos.
