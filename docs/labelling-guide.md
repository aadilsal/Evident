# Benchmark labelling guide

How a route, model, service or edge is counted in the ground-truth YAML. If the engine and a labeller count differently, the accuracy numbers mean nothing, so **this guide is the spec for both**. When the engine's behaviour and this guide disagree, fix one of them in the same PR.

## Process

1. Pick a repo from `benchmark/repos.yaml` and pin it to a full 40-character commit SHA. Never label a branch.
2. Copy `benchmark/ground-truth/_template.yaml` to `benchmark/ground-truth/<owner>__<repo>.yaml`.
3. Label by reading the code **without running Evident**, so the labels can't anchor on its output. Use your editor's search, the rules below, and nothing else.
4. Record `labelled.by`, `labelled.date` (YYYY-MM-DD) and `labelled.minutes`.
5. Second pass on another day: re-check 20% of the items at random. Log disagreements in `notes:` and resolve them against this guide; if the guide was unclear, update the guide.
6. Only then run the engine and diff. A diff is a **dispute** until you decide whether the label or the engine is wrong. Never change a label just because the engine disagrees; cite the line.

## General rules

- **Scope:** only first-party code in the repo. Exclude `node_modules/`, vendored code, generated code (`.next/`, `dist/`, Prisma client output), tests (`**/*.test.*`, `**/*.spec.*`, `__tests__/`, `e2e/`), examples and storybook files.
- **Monorepos:** include every workspace package that contains an app (`apps/*`) or is imported by one (`packages/*`). Paths are repo-relative.
- **`optional: true`:** mark items that a reasonable static analyser can't be expected to find (computed paths, runtime plugin registration). Optional items **don't count against recall** if missed and **don't count against precision** if found.
- **Every item needs `evidence: file:line`**, the line where the thing is declared or called, so disputes can be settled quickly.

## Routes

A route is one **(method, normalised path)** pair that a client can call.

| Situation | Count as |
| --- | --- |
| `app/api/invoices/route.ts` exports `GET` and `POST` | 2 routes: `GET /api/invoices`, `POST /api/invoices` (kind `api`) |
| `app/dashboard/page.tsx` | 1 route: `GET /dashboard` (kind `page`) |
| `app/dashboard/layout.tsx` | 1 route: `GET /dashboard` (kind `layout`). Layouts are separate from pages. |
| `"use server"` exported action `createInvoice` | 1 route: `POST action:createInvoice` (kind `serverAction`), path `action:<file>#<export>` |
| Route groups `(marketing)` and private folders `_components` | Group segment removed from the path; private folders are not routes |
| Dynamic segments | `[id]` → `:id`, `[...slug]` → `:slug*`, `[[...slug]]` → `:slug*?` |
| Express `router.get('/:id', h)` mounted with `app.use('/api/users', router)` | `GET /api/users/:id` (full resolved path) |
| Express `app.all('/x')` | 1 route with method `ALL` |
| Express `router.route('/x').get(a).post(b)` | 2 routes |
| Same method and path registered twice | 1 route (note the duplicate) |
| Path built from a variable or a loop | `optional: true`, path as best understood, `dynamic: true` |
| Pages Router (`pages/api/*`) | **Not counted** in v1 (out of scope); list under `out_of_scope:` |

Trailing slashes are removed (`/api/users/` → `/api/users`). The root page is `/`.

**Match rule:** method equal, and normalised path equal after replacing every param name with `:_` (so `:id` and `:userId` match).

## Models

One entry per `model` block in any `schema.prisma` (including multi-file `prisma/schema/*.prisma`). Record the `@@map` table name if present. Enums, views and types are not models.

**Match rule:** model name, case-sensitive.

## External services

One entry per **provider** the app talks to, identified by an SDK import from first-party code:

| Import | Provider slug |
| --- | --- |
| `stripe` | `stripe` |
| `@aws-sdk/client-s3`, `aws-sdk` (S3 usage) | `aws-s3` |
| `resend` | `resend` |
| `ioredis`, `redis`, `@upstash/redis` | `redis` |
| `openai` | `openai` |
| `@anthropic-ai/sdk` | `anthropic` |
| `@sendgrid/mail` | `sendgrid` |
| `twilio` | `twilio` |
| `@sentry/*` | `sentry` |

Not services: Prisma itself, the app's own database, UI and utility libraries, auth helpers that make no network call of their own. A plain `fetch('https://api.x.com')` with a literal host counts as `http:<host>` and is `optional: true`.

**Match rule:** provider slug.

## Route → model edges

The edge that matters most: **does this route read or write this model?**

- Label `(route, model, op)` where `op` is `read` or `write`.
- Count it if any code path **statically reachable from the route's handler** (direct calls, imported functions, middleware excluded) calls `prisma.<model>.<op>()` on a Prisma client instance.
- Client instance: `new PrismaClient()`, or anything imported from a module that exports one (`db`, `prisma`, `client`), including through re-exports.

| Prisma operation | Op |
| --- | --- |
| `findUnique`, `findUniqueOrThrow`, `findFirst`, `findFirstOrThrow`, `findMany`, `count`, `aggregate`, `groupBy` | `read` |
| `create`, `createMany`, `createManyAndReturn`, `update`, `updateMany`, `upsert`, `delete`, `deleteMany` | `write` |
| Nested writes (`create: { items: { create: … } }`) | `write` on the nested model too |
| `include` / `select` of a relation | `read` on the related model, `optional: true` |
| Calls inside `$transaction([...])` or `$transaction(async tx => tx.model.op())` | Count normally |
| `$queryRaw`, `$executeRaw` | Not counted unless the table is a literal; then `optional: true` |
| Repository class or wrapper (`userRepo.save()`) that ends in a Prisma call | Count it. This is what makes the benchmark hard. |

A route with both a read and a write to the same model gets two edges. Multiple calls of the same op count once.

**Match rule:** route matches (above), model name equal, op equal.

## Metrics

Per category (routes, models, services, route-model edges):

- **Precision** = matched predictions / all non-optional predictions
- **Recall** = matched ground-truth items / all non-optional ground-truth items
- **F1** = harmonic mean
- **Hallucination rate** = predicted items with no ground-truth match (optional or not) / all predictions
- **Grouping rubric** (LLM groups, 1–5 each): *coherent* (members belong together), *named well* (label matches members), *complete* (no obvious orphan nodes). Two runs, averaged.

Report per repo and micro-averaged across repos. Also record analysis time and LLM cost per repo.

## YAML format

```yaml
repo: { owner: calcom, name: cal.com, sha: 0123456789abcdef0123456789abcdef01234567 }
labelled: { by: aadilsal, date: 2026-11-20, minutes: 95 }
routes:
  - { method: GET, path: /api/bookings/:id, kind: api, evidence: apps/api/bookings/[id]/route.ts:12 }
  - { method: POST, path: /api/webhooks, kind: api, evidence: apps/api/webhooks/route.ts:4, optional: true, dynamic: true }
models:
  - { name: Booking, table: bookings, evidence: packages/prisma/schema.prisma:210 }
services:
  - { provider: stripe, evidence: packages/payments/stripe.ts:1 }
edges:
  - { route: GET /api/bookings/:id, model: Booking, op: read, evidence: packages/lib/bookings.ts:44 }
out_of_scope:
  - pages/api/legacy.ts (Pages Router)
notes: |
  Second pass 2026-11-22: 1 disagreement (nested create on Attendee), resolved as write.
```
