# Deployment runbook

> **Skeleton.** Fill this in during Phase 4 (launch) and test every section once before relying on it.

## Overview

- **Host:** _VM provider, size, region / home + Cloudflare Tunnel_
- **Stack:** Docker Compose: Caddy, web, api, worker, Redis, Postgres
- **Domain / DNS:** _…_
- **Secrets:** `.env` on the VM only (never committed). Keys: _list names, not values_

## Deploy

1. _Tag a release (`vX.Y.Z`) and update CHANGELOG.md_
2. _On the VM: pull, build or pull images, `docker compose up -d`_
3. _Run DB migrations_
4. _Smoke test: `/api/health`, landing page, one gallery map, one fresh analysis_

## Roll back

1. _Redeploy the previous tag_
2. _DB migrations: forward-only? down-migration steps?_
3. _Confirm with the smoke test_

## Backup and restore

- **Postgres:** _nightly `pg_dump` → where? retention?_
- **Restore drill:** _steps, last tested on YYYY-MM-DD_
- **Gallery JSON:** _rebuilt from the repo, no backup needed_

## Rebuild the VM from scratch

_Provision → install Docker → clone → restore `.env` → restore DB → deploy → DNS / tunnel_

## Monitoring and alerts

- _Uptime monitor on `/api/health` and `/`_
- _Disk, memory, LLM spend alerts_

## Incidents

| Symptom | First checks |
| --- | --- |
| Site down | _Caddy / tunnel status, `docker compose ps`_ |
| Jobs stuck | _worker logs, Redis queue length, temp dir sweeper_ |
| LLM spend spike | _rate-limit logs, cap status; switch to `--no-llm` grouping fallback_ |
