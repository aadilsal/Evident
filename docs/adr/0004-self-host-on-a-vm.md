# 0004. Self-host everything on one VM with Docker Compose

- **Status:** Accepted. The frontend part is superseded by [ADR-0008](0008-static-web-on-vercel-api-on-one-server.md): the web app is a static export on Vercel; this ADR still governs the backend stack.
- **Date:** 2026-11-07

## Context

This is a portfolio project with a public demo. The only unavoidable paid cost should be LLM usage. Analysis jobs need long-running workers, git, CPU for parsing and a writable temp disk, which suits serverless poorly. Showing real infra skills (sandboxing, deploys, backups) is part of the point.

## Decision

Run Caddy, Next.js, FastAPI, the arq worker, Redis and Postgres as one Docker Compose stack on a single VM. Expose it via Caddy (automatic HTTPS), or through Cloudflare Tunnel if the VM sits behind NAT at home. Precompute the featured gallery as static JSON so it works even if the worker is down.

## Consequences

- Near-zero hosting cost, with full control over sandboxing (container limits, egress rules, tmpfs).
- One-command local dev matches production.
- **Cost:** a single point of failure, so we need an uptime monitor, documented restore from Postgres backups, and a static gallery fallback. Scaling is vertical only, with job concurrency capped.
- We own patching and backups ([runbook](../runbook/deployment.md)).

## Alternatives considered

- **Vercel + serverless workers:** cheap frontend, but function time limits and no git/disk sandbox make analysis awkward.
- **Managed containers (Fly, Railway, Cloud Run):** good option later. Recurring cost and less infra to show today.
- **Kubernetes:** far too much for one VM.
