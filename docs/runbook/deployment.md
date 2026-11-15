# Deployment runbook

How the hosted Evident runs, and how to deploy, roll back, restore and recover it. Tested end to end on 2026-11-15. Account IDs, IPs and secrets live in the owner's private notes, not here.

## Overview

| Piece | Where |
| --- | --- |
| Site (`web/`, static export) | Vercel project `evident`, root directory `web`, builds on every push to `main` ([ADR-0008](../adr/0008-static-web-on-vercel-api-on-one-server.md)) |
| API, worker, Postgres, Redis, Caddy | One AWS EC2 `t4g.small` (Amazon Linux 2023, arm64) running `deploy/docker-compose.yml` + `deploy/docker-compose.prod.yml` |
| HTTPS for the API | Caddy, automatic Let's Encrypt for every name in `API_DOMAIN` |
| Secrets | SSM Parameter Store, `/evident/*` (SecureString for keys and passwords), copied into a root-only `/opt/evident/.env` at deploy time |
| Backups | `pg_dump` nightly at 03:15 UTC (systemd timer `evident-backup`) to a private, versioned S3 bucket; 30-day expiry |
| Access | AWS Systems Manager Session Manager and Run Command; no SSH port, no key pair |
| Monitoring | `.github/workflows/uptime.yml` every 15 min (failed runs email the owner); CloudWatch alarm that recovers the instance on a host failure; AWS budget alert |

**Settings in Parameter Store** (names only):
- **Secrets:** `GROQ_API_KEY`, `POSTGRES_PASSWORD`, `EVIDENT_IP_SALT`, optional `GITHUB_TOKEN`.
- **Plain settings:** `API_DOMAIN`, `EVIDENT_CORS_ORIGINS`, `EVIDENT_PUBLIC_URL`.

**Vercel:** `NEXT_PUBLIC_API_URL` (not a secret).

## Deploy

Every update is the same command, run as root on the server:

```bash
bash /opt/evident/deploy/deploy.sh main      # or a tag: deploy.sh v0.3.0
```

From a workstation without logging in, through Run Command:

```bash
aws ssm send-command --instance-ids <instance-id> --document-name AWS-RunShellScript \
  --parameters 'commands=["bash /opt/evident/deploy/deploy.sh main 2>&1 | tail -20"]'
```

`deploy.sh` does the following:
1. fetches and checks out the ref;
2. rebuilds `.env` from Parameter Store, readable by root only;
3. runs `docker compose … up -d --build`;
4. prunes old images;
5. reinstalls the backup timer.

The database schema only grows (`create … if not exists`), so there are no migration steps.

**Smoke test** from any machine:

```bash
cd engine && uv run python scripts/smoke_service.py https://<api-host>
```

It checks health, submits a pinned repo, follows the progress stream to `done`, and verifies the route count.

**Web:** push to `main`. If you change `NEXT_PUBLIC_API_URL`, redeploy, because the value is built into the site. From `web/`, run `vercel redeploy <latest-production-url> --target production`.

## Roll back

1. API: `deploy.sh <previous-tag-or-commit>`, then the smoke test.
2. Web: Vercel → Deployments → the previous production deployment → **Promote to Production**.

## Change a setting or secret

```bash
aws ssm put-parameter --name /evident/<NAME> --type SecureString --value file://<file> --overwrite
```

Then run `deploy.sh` again. Use `--type String` for non-secrets. Never put a value on the command line or in the repo. Rotating `POSTGRES_PASSWORD` also needs the database user's password changed, so leave it alone unless it has leaked.

## Backups and restore

- **Manual backup now:** `systemctl start evident-backup.service`. Check it with `aws s3 ls s3://<bucket>/pg/`.
- **Restore drill:** do it quarterly, and record the date below.
  1. Download a dump with your own credentials: `aws s3 cp s3://<bucket>/pg/<date>.dump .`. The server can write backups but can't read them.
  2. Restore it into a scratch Postgres: `docker run -d --name drill -e POSTGRES_USER=evident -e POSTGRES_PASSWORD=x postgres:16-alpine`, then `docker exec -i drill pg_restore -U evident -d evident --no-owner < <date>.dump`.
  3. Compare row counts of `graphs` and `jobs` with production.
- **Real restore:** copy the dump to the server, then `docker compose … exec -T postgres pg_restore -U evident -d evident --clean --if-exists < <date>.dump`, then the smoke test.
- **What losing the database costs:** only cached analyses, job history, shares and reports. Graphs can be rebuilt from GitHub, and the gallery and benchmarks are static files in the site.

| Drill | Date | Result |
| --- | --- | --- |
| Backup ran on the server, dump uploaded to S3 (25 KB) | 2026-11-15 | ✅ |
| Local restore of that dump | _pending_ | |

## Rebuild the server from scratch

1. Launch the same instance type with the IAM role `evident-ec2`, the `evident-web` security group (80/443 only), IMDSv2 required, and the first-boot script. The script installs Docker, verified Compose and buildx, and swap.
2. Re-associate the Elastic IP, so DNS doesn't change.
3. Parameter Store still holds every setting. Run `deploy.sh main`.
4. Restore the latest dump (above), then the smoke test.

The full step-by-step with commands is in the owner's private guide (`docs/internal/aws-deployment.md`).

## Monitoring and alerts

- **Uptime:** the GitHub Actions workflow checks the API health and three site URLs every 15 minutes. A failure emails the owner.
- **Host failure:** a CloudWatch `StatusCheckFailed_System` alarm recovers the instance automatically.
- **Spend:** an AWS budget emails at 80% of the monthly budget, and again when the forecast goes over it. On the Free plan, also watch the credit balance in AWS Settings > Billing.
- **CPU:** the instance uses `standard` credits, so heavy analysis is throttled, never billed. If `CPUCreditBalance` sits near zero, move to a larger size.

## Incidents

| Symptom | First checks |
| --- | --- |
| API down | `docker compose … ps`; `docker compose … logs --since 30m caddy api`; instance status in EC2 |
| HTTPS errors on a new name | DNS points at the Elastic IP, and port 80 is reachable (Let's Encrypt HTTP challenge); `logs caddy` |
| Jobs stuck in `queued` | `logs worker`; Redis healthy; a job over the timeout is killed and marked failed by design |
| Site loads but can't analyse | `NEXT_PUBLIC_API_URL` built into the site; `EVIDENT_CORS_ORIGINS` lists the exact site origin |
| LLM groups missing | `GROQ_API_KEY` set; Groq 429s fall back to directory groups by design |
