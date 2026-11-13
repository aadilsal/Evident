# 0008. Static web app on Vercel; API and workers on one server

- **Status:** Accepted. Supersedes the "Next.js on the VM" part of [ADR-0004](0004-self-host-on-a-vm.md).
- **Date:** 2026-11-13

## Context

ADR-0004 put everything, the Next.js frontend included, in one Docker Compose stack on a VM. While building the interface, three facts changed the picture:

- The map UI must also run inside the pip package for `evident open`, with no Node (tracker §8). That pushes it towards a **static export** that talks to a data source over HTTP.
- A static site needs no server of its own. Free static hosting (Vercel) gives a CDN, HTTPS and preview deploys at no cost, and keeps the site up when the analysis server is down.
- The owner has a cheap domain for the site and will host the backend on a single free-tier cloud server (AWS Free plan or Oracle Always Free; see the internal deployment guides).

## Decision

- `web/` is a Next.js **static export** (`output: "export"`). Every view is client-rendered from a graph loaded through one data-source switch: the hosted API, the static gallery, `evident open` (`/local/*`), or a share link.
- The same build is deployed to **Vercel** and bundled into the Python package (`npm run build:bundle` → `evident/webui`).
- The **backend** (FastAPI, arq worker, Postgres, Redis, and Caddy for HTTPS) stays one Docker Compose stack on one server, as ADR-0004 describes, published as `api.<domain>`.
- The API allows the site's exact origins through `EVIDENT_CORS_ORIGINS`. There are no cookies, so no credentialed CORS.
- The gallery and benchmark results ship as static JSON in the site, so they work even when the API is down.

## Consequences

- Hosting cost stays at zero, and the frontend has no server to patch.
- The site degrades gracefully: the gallery, benchmarks and supported-stacks pages never depend on the API.
- One UI codebase serves three modes; `NEXT_PUBLIC_API_URL` decides whether API features appear.
- **Cost:**
  - Routes can't be server-rendered, so permalinks use query strings (`/map/?repo=…&sha=…`) instead of path segments.
  - The API is a separate origin, so CORS must list the site's origins exactly.
  - The site's CSP allows `https:` for `connect-src` until the API domain is fixed.
- ADR-0004's single point of failure now covers only analysis, sharing and reports.

## Alternatives considered

- **Next.js server on the VM (ADR-0004 as written):** one more container to run, and the UI could not be bundled into the pip package without Node.
- **Next.js server on Vercel:** server components would need the API at build time and per request, and the result could not be bundled into the pip package.
- **Backend on Vercel functions:** time limits and no git or disk sandbox; rejected in ADR-0004 for the same reasons.
