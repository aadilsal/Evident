---
name: evident
description: Answers questions about a JS/TS or Python web app's routes and endpoints, request flow, middleware and auth, database models and tables, env vars and external services, with file:line evidence from the read-only `evident` CLI (Next.js, Express, NestJS, Fastify, FastAPI, Flask, Django; Prisma, Drizzle, TypeORM, Mongoose, Django ORM, SQLAlchemy). Use when the user asks which routes read or write a table, whether an endpoint is behind auth or validated, what a request does end to end, where an env var or SDK is used, what the full path of an endpoint is, or what breaks if a model, file or env var changes. Also use BEFORE editing a database model, shared module, middleware or route, to check the blast radius.
---

# Evident: architecture map with receipts

`evident` reads the repo with static analysis (it never runs the code) and answers questions from a graph in which every route, model, service and edge points to the line that proves it. Your job: ask the graph, then answer **only** with what it returned, citing `file:line`.

## Once per session

1. Check the CLI: `evident --version`. If it's missing, tell the user and ask before running `scripts/ensure_installed.sh` (macOS/Linux) or `scripts/ensure_installed.ps1` (Windows) from this skill's folder.
2. Build the map offline: `evident analyze . --no-llm`. It's incremental (cached in `.evident/`, which ignores itself), so later commands stay fast.
3. Lead with a short summary from that output: stack, counts, the main routes, models and services, and the top findings with `file:line`. Five or six lines, not a dump.
4. Offer once: "Want the interactive map? `evident open` serves it on localhost; nothing is uploaded." Don't offer again, and run it only if the user says yes (it keeps running until stopped).

## Before you edit

- **Model, shared module, middleware or env var:** run `evident impact <target>` first, e.g. `evident impact User`, `evident impact src/lib/db.ts`, `evident impact STRIPE_SECRET_KEY`. Tell the user which routes are affected before changing anything.
- **New or changed route:** after the change, run `evident health --file <path>` and report any `unguarded-write` or `unvalidated-body` finding.

## Answering questions

| Question | Command |
| --- | --- |
| How does a request flow? | `evident trace "POST /api/users"` |
| Who writes or reads a table? | `evident find --writes Invoice` / `evident find --reads Invoice` |
| What depends on X? | `evident impact <model, file or env var>` |
| What is this node? | `evident show <id or name>` (e.g. `model:User`, `User`) |
| Risks? | `evident health --severity warning` |
| Architecture doc | `evident export --format md --out docs/architecture.md` (only when the user asks for the file) |

Use human output by default (it's summary-first and short). Add `--json` only when you need to parse results. Use `--limit` and `--depth` to stay concise, and say when output was truncated.

## Rules

- **Cite evidence.** Every claim about a route, model, call or dependency carries the `file:line` the tool printed.
- **Never invent a dependency.** If the tool didn't return it, don't claim it. If you then confirm something by reading code yourself, say it came from reading, not from the map.
- **Flag doubt.** Results marked `~inferred` (or `"source": "inferred"` in JSON) or with low confidence: say so ("probably", plus the confidence).
- **Respect the scope note.** If `analyze` prints `note: … isn't supported yet`, say those routes or models are missing from the map instead of reporting "none".
- **Exit codes:** `0` ok, `1` no match or findings (not an error), `2` bad usage (fix the arguments), `3` analysis failed (report the message).
- **Never run `evident share`** unless the user explicitly asks. It uploads graph metadata.
- **Read-only.** Evident writes only inside `.evident/`, plus `export --out` when the user asked for it.
