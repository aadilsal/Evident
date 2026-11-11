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

## Adapters covered

The rules below cover every v1 adapter ([ADR-0006](adr/0006-adapter-architecture.md)): **Next.js, Express, NestJS, Fastify, Prisma, Drizzle, TypeORM, Mongoose** (JS/TS) and **FastAPI, Flask, Django, Django ORM, SQLAlchemy** (Python). A new adapter gets its counting rules here **in the same PR as the adapter**. Until it has them, its benchmark items aren't scored. Record which adapters a repo uses under `adapters:` in `benchmark/repos.yaml`, and tag each route with `framework:` and each model and edge with `orm:`, so metrics can be reported per adapter.

## Routes

A route is one **(method, normalised path)** pair that a client can call.

| Situation | Count as |
| --- | --- |
| `app/api/invoices/route.ts` exports `GET` and `POST` | 2 routes: `GET /api/invoices`, `POST /api/invoices` (kind `api`) |
| `app/dashboard/page.tsx` | 1 route: `GET /dashboard` (kind `page`) |
| `app/dashboard/layout.tsx` | 1 route: `GET /dashboard` (kind `layout`). Layouts are separate from pages. |
| `"use server"` exported action `createInvoice` | 1 route: `POST action:createInvoice` (kind `serverAction`), path `action:<file>#<export>` |
| Route groups `(marketing)` and private folders `_components` | Group segment removed from the path; private folders are not routes |
| Dynamic segments | `[id]` → `:id`, `[...slug]` → `:slug*`, `[[...slug]]` → `:slug*?`. Names can contain hyphens (`[[...sign-in]]` → `:sign-in*?`). |
| Several layouts resolve to the same path (`app/layout.tsx`, `app/(shop)/layout.tsx`) | 1 route |
| `loading`, `error`, `not-found`, `template`, `robots`, `sitemap` files | Not routes |
| Express `router.get('/:id', h)` mounted with `app.use('/api/users', router)` | `GET /api/users/:id` (full resolved path) |
| Express `app.all('/x')` | 1 route with method `ALL` |
| Express `router.route('/x').get(a).post(b)` | 2 routes |
| Same method and path registered twice | 1 route (note the duplicate) |
| Path built from a variable or a loop | `optional: true`, path as best understood, `dynamic: true` |
| Pages Router (`pages/api/*`) | **Not counted** in v1 (out of scope); list under `out_of_scope:` |

Trailing slashes are removed (`/api/users/` → `/api/users`). The root page is `/`.

**Match rule:** method equal, and normalised path equal after replacing every param name with `:_` (so `:id` and `:userId` match). A layout keeps its own key, so a page and a layout at the same path are two routes.

### NestJS

| Situation | Count as |
| --- | --- |
| `@Controller('users')` + `@Get(':id')` with `app.setGlobalPrefix('api')` | `GET /api/users/:id` |
| `@Controller()` / `@Get()` with no path | The prefix + controller path alone |
| `@Get(['a', 'b'])` | The first path; the rest are `optional: true` |
| URI versioning with `VERSION_NEUTRAL` in `defaultVersion` | The unversioned path; `/v1/...` aliases are `optional: true` |
| Controller methods without an HTTP-method decorator | Not routes |

### Fastify

| Situation | Count as |
| --- | --- |
| `app.get('/x', [opts], handler)` | 1 route |
| `app.route({ method: ['GET', 'PUT'], url: '/x', handler })` | 1 route per method |
| `app.register(plugin, { prefix: '/api' })` | Routes inside the plugin get the prefix, nested registrations stack |
| A plugin that is never registered | Its local paths, `optional: true` |

### FastAPI

| Situation | Count as |
| --- | --- |
| `@router.get("/{id}")` on `APIRouter(prefix="/users")`, included with `include_router(router, prefix="/api")` | `GET /api/users/:id` (prefixes stack) |
| `@app.api_route("/x", methods=["GET", "POST"])` | 1 route per method |
| `{file_path:path}` | `:file_path*` |
| `app.mount("/", StaticFiles(...))` | Not a route |

### Flask

| Situation | Count as |
| --- | --- |
| `@app.route("/x")` with no `methods` | `GET /x` |
| `@bp.route("/x", methods=["GET", "POST"])` / `@bp.post("/x")` | 1 route per method |
| `Blueprint(..., url_prefix="/a")` registered with `register_blueprint(bp, url_prefix="/b")` | Blueprint prefix and registration prefix stack |
| `<int:id>` / `<path:p>` | `:id` / `:p*` |
| `app.add_url_rule("/x", view_func=f, methods=[...])` | 1 route per method |

### Django (and Django REST Framework)

| Situation | Count as |
| --- | --- |
| `path("users/<int:pk>/", view)` reached from `ROOT_URLCONF` through `include("app.urls")` | `/users/:pk` (prefixes join; trailing slash removed) |
| Function view with no method decorator | Method `ALL` |
| `@require_http_methods(["GET", "POST"])`, `@require_GET`, `@api_view(["POST"])` | Those methods |
| Class view (`as_view()`) | 1 route per HTTP method it defines, plus the methods its generic base implies (`ListView`/`RetrieveAPIView` = GET, `CreateAPIView` = POST, `RetrieveUpdateAPIView` = GET/PUT/PATCH, `RetrieveUpdateDestroyAPIView` = GET/PUT/PATCH/DELETE, ...) |
| A view class from a library (simplejwt `TokenObtainPairView`) | `optional: true` (its methods aren't in the repo) |
| DRF `router.register("trips", TripViewSet)` | `ModelViewSet`: `GET /trips`, `POST /trips`, `GET`/`PUT`/`PATCH`/`DELETE /trips/:pk`; mixins and defined actions likewise |
| `@action(detail=True, methods=["get"], url_path="logs/pdf")` | `GET /trips/:pk/logs/pdf`; regex groups in `url_path` become params |
| `DefaultRouter`'s API root, `admin.site.urls` | Optional / out of scope |
| `re_path` with a pattern beyond named groups | `optional: true`, `dynamic: true` |

When the engine can't know a class view's methods it emits `ALL` with `dynamic: true`; it is scored like an optional item.

## Models

One entry per model the app defines, by ORM:

| ORM | One model per… | Name |
| --- | --- | --- |
| Prisma | `model` block in any `*.prisma` file (enums, views, types are not models); record `@@map` | Model name |
| Drizzle | `pgTable` / `mysqlTable` / `sqliteTable` call | The exported **variable** (`export const users = pgTable('users', …)` → `users`) |
| TypeORM | `@Entity()` class | Class name; table from `@Entity('name')` |
| Mongoose | `model('Name', schema)` call | The string name |
| Django ORM | Concrete `models.Model` subclass (not `abstract = True`); table from `Meta.db_table` or `<app>_<model>` | Class name |
| SQLAlchemy | Declarative class with `__tablename__` (or SQLModel with `table=True`, Flask-SQLAlchemy `db.Model`) | Class name |

Models from libraries (Django's `User`) are not counted.

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
| `@aws-sdk/client-ses` | `aws-ses` |
| `@stripe/*` (e.g. `@stripe/stripe-js` in a web client) | `stripe` |
| `groq-sdk` | `groq` |
| `@google/generative-ai`, `@google/genai` | `google-gemini` |
| `cloudinary` | `cloudinary` |
| `@supabase/*` | `supabase` |
| `convex`, `@convex-dev/*` | `convex` |
| `@clerk/*` | `clerk` |
| `@arcjet/*` | `arcjet` |
| `@sfpy/node-core` | `safepay` |
| Python: `stripe`, `openai`, `anthropic`, `redis`, `resend`, `twilio`, `groq`, `supabase`, `cloudinary`, `sendgrid` | Same slugs |
| Python: `sentry_sdk` / `boto3` / `google.generativeai`, `google.genai` | `sentry` / `aws-s3` / `google-gemini` |

Hosted backends (Supabase, Convex) count as services even when they hold the app's data: the app reaches them over the network through a vendor SDK. A package declared in `package.json` but never imported is not a service. A dynamic `import('stripe')` counts.

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
| A server component (page/layout) that calls a server action or function directly | Count the callee's edges for that page. JSX children (`<Header />`) are not calls. |
| Work enqueued on a job queue (`queue.add(...)`) | Not counted: the worker isn't statically reachable from the route |
| Framework-invoked hooks (DRF `get_queryset`, `get_object`, `perform_create`; class-level `queryset = ...`) | Not counted: no first-party handler calls them |
| A write behind a runtime flag (`if self.persist: event.save()`) | Counted: it's statically reachable |

The same reachability rule applies to the other ORMs; only the call shapes differ:

| ORM | `read` | `write` |
| --- | --- | --- |
| Drizzle | `select().from(t)`, joins on `t`, `db.query.t.findMany/findFirst` | `insert(t)`, `update(t)`, `delete(t)` |
| TypeORM (repository from `getRepository(E)`, `@InjectRepository(E)` or a `Repository<E>` field) | `find*`, `count*`, `exist*`, `sum`/`average`/`minimum`/`maximum` | `save`, `insert`, `update`, `upsert`, `delete`, `remove`, `softDelete`, `softRemove`, `restore`, `increment`, `decrement`, `clear` |
| Django ORM | `Model.objects.<all/filter/get/exclude/first/last/count/exists/aggregate/annotate/values/...>`, `get_object_or_404(Model)` | `Model.objects.<create/bulk_create/update/delete/get_or_create/update_or_create/bulk_update>`, `.save()`/`.delete()` on an instance built as `Model(...)` or loaded with `Model.objects.get(...)` |
| SQLAlchemy | `session.query(M)`, `select(M)`, `session.get(M, id)`, Flask-SQLAlchemy `M.query.<op>()` | `insert(M)`, `update(M)`, `delete(M)`, `session.add/merge/delete(x)` where `x = M(...)` or `x = M.query.<op>()` |
| Mongoose (model binding, or `@InjectModel` field typed `Model<E>`) | `find*`, `countDocuments`, `estimatedDocumentCount`, `exists`, `aggregate`, `distinct` | `create`, `insertMany`, `update*`, `delete*`, `replaceOne`, `bulkWrite`, `findOneAnd*`/`findByIdAnd*`, `new Model().save()` |

A route with both a read and a write to the same model gets two edges. Multiple calls of the same op count once.

**Match rule:** route matches (above), model name equal, op equal.

## Metrics

Per category (routes, models, services, route-model edges), and per adapter:

- **Precision** = matched predictions / all non-optional predictions
- **Recall** = matched ground-truth items / all non-optional ground-truth items
- **F1** = harmonic mean
- **Hallucination rate** = predicted items with no ground-truth match (optional or not) / all predictions
- **Engine-marked dynamic predictions** (`dynamic: true`, a computed path) are scored like optional items: they don't count against precision, but an unmatched one still counts in the hallucination rate.
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
