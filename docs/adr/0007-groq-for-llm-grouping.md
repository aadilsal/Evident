# 0007. Use Groq (free tier) for LLM grouping, behind a provider-agnostic interface

- **Status:** Accepted
- **Date:** 2026-11-10

## Context

The grouping stage ([0003](0003-llm-labels-existing-node-ids.md)) makes one small LLM call per uncached commit: node IDs, types, labels and paths in, groups out. It's a public demo with no revenue, so the PRD's open question was which provider to use and what the monthly spend cap should be.

## Decision

Use **Groq on its free tier** as the first provider, called through a small provider-agnostic interface (`complete(prompt) -> text`), so the provider can change without touching the validator. The API key lives only in the worker's environment as `GROQ_API_KEY`. Only the name is ever logged or stored.

When the call fails, is rate-limited or over quota, the engine **falls back automatically to `--no-llm`** (deterministic directory-based groups) and reports `llm: unavailable`. A grouping failure never fails an analysis.

## Consequences

- Hosting cost stays at zero. The "monthly spend cap" becomes "stay within free-tier limits".
- Free-tier rate and token limits become the real constraint. Caching by commit SHA, the precomputed gallery and per-IP rate limits keep usage small.
- Groq's model list changes over time, so the model ID is configuration, not code.
- **Cost:** free tiers can change or throttle without notice, so graceful fallback is required, not a nice-to-have. Large graphs may need the node list trimmed or chunked to fit token limits.

## Alternatives considered

- **Paid frontier API:** better labels, but recurring cost on a public demo.
- **Local model only:** private and free, but the hosted VM may lack the RAM or GPU. It stays an option for the local CLI (v2).
- **No LLM:** serviceable, but poor group names on flat repos ([0003](0003-llm-labels-existing-node-ids.md)).
