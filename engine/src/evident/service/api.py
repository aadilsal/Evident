"""FastAPI app (architecture §6). Run: `uvicorn evident.service.api:app`."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import secrets
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from evident import ENGINE_VERSION, GRAPH_SCHEMA_VERSION
from evident.contract import schema_errors
from evident.models import AnalysisError, Graph
from evident.repo import GitHubRepo, check_size, parse_github, remote_head
from evident.service.broker import Broker, RedisBroker
from evident.service.config import Settings
from evident.service.store import Job, MemoryStore, PostgresStore, Report, Share, Store

JSON = dict[str, Any]
Resolver = Callable[[GitHubRepo], str]
_OWNER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}$")
_REPO = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_SHARE_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
MAX_SHARE_TTL_DAYS = 30
HEARTBEAT_S = 15.0
IMMUTABLE = {"Cache-Control": "public, max-age=31536000, immutable"}


class AnalysisRequest(BaseModel):
    url: str = Field(
        description="https://github.com/<owner>/<repo>, optionally /tree/<ref>", max_length=300
    )


class ReportRequest(BaseModel):
    owner: str = Field(pattern=_OWNER.pattern)
    repo: str = Field(pattern=_REPO.pattern)
    sha: str = Field(pattern=_SHA.pattern)
    engineVersion: str = Field(max_length=40)  # noqa: N815 (wire format is camelCase)
    elementId: str = Field(min_length=3, max_length=300)  # noqa: N815
    kind: Literal["node", "edge"]
    note: str = Field(default="", max_length=500)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def resolve_github(repo: GitHubRepo) -> str:
    """ref -> commit SHA, rejecting missing, private or oversized repos before any clone."""
    sha = remote_head(repo)
    check_size(repo)
    return sha


def create_app(
    store: Store | None = None,
    broker: Broker | None = None,
    settings: Settings | None = None,
    resolve: Resolver = resolve_github,
) -> FastAPI:
    settings = settings or Settings.from_env()
    store = store or (
        PostgresStore(settings.database_url) if settings.database_url else MemoryStore()
    )
    broker = broker or RedisBroker(settings.redis_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        store.setup()
        yield

    app = FastAPI(
        title="Evident API",
        description="Evidence-backed architecture maps. Every node and edge cites file:line.",
        version=ENGINE_VERSION,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
        lifespan=lifespan,
    )
    if settings.cors_origins:
        # The frontend is a separate origin (Vercel, ADR-0008). No cookies, so no credentials.
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["Content-Type", "X-Delete-Token"],
            max_age=600,
        )

    def client_id(request: Request) -> str:
        ip = request.client.host if request.client else "unknown"
        if settings.trust_proxy:
            ip = request.headers.get("x-forwarded-for", ip).split(",")[0].strip()
        return hashlib.sha256(f"{settings.ip_salt}:{ip}".encode()).hexdigest()[:32]

    @app.post("/api/analyses", summary="Submit a GitHub repo; returns the cached graph or a job")
    async def submit(body: AnalysisRequest, request: Request) -> JSONResponse:
        gh = parse_github(body.url)
        if gh is None:
            raise HTTPException(400, "Only https://github.com/<owner>/<repo> URLs are supported.")
        client = client_id(request)
        if not await broker.allow(client, settings.rate_limit_per_hour):
            raise HTTPException(
                429, "Too many analyses from this address; try again within the hour."
            )
        try:
            sha = await asyncio.to_thread(resolve, gh)
        except AnalysisError as exc:
            raise HTTPException(422, str(exc)) from exc
        if store.get_graph(gh.owner, gh.name, sha, ENGINE_VERSION) is not None:
            url = f"/api/graphs/{gh.owner}/{gh.name}/{sha}"
            return JSONResponse({"status": "done", "sha": sha, "graphUrl": url})
        active = store.active_job(gh.owner, gh.name, sha, ENGINE_VERSION)
        if active is not None:
            return JSONResponse(
                {"status": active.status, "sha": sha, "jobId": active.id}, status_code=202
            )
        if store.count_active() >= settings.max_queued_jobs:
            raise HTTPException(503, "The analysis queue is full; try again in a few minutes.")
        job = store.create_job(Job(gh.owner, gh.name, sha, ENGINE_VERSION, gh.ref, client))
        await broker.publish(job.id, {"stage": "queued", "counts": {}})
        await broker.enqueue(job.id)
        return JSONResponse({"status": "queued", "sha": sha, "jobId": job.id}, status_code=202)

    @app.get("/api/analyses/{job_id}", summary="Job status snapshot")
    async def status(job_id: str) -> JSON:
        job = store.get_job(job_id)
        if job is None:
            raise HTTPException(404, "No such job.")
        return job.public()

    @app.get("/api/analyses/{job_id}/events", summary="Server-sent progress events until done")
    async def events(job_id: str) -> StreamingResponse:
        if store.get_job(job_id) is None:
            raise HTTPException(404, "No such job.")

        async def stream() -> AsyncIterator[str]:
            stream_events = broker.subscribe(job_id)
            first = await broker.snapshot(job_id)
            if first is not None:
                yield f"event: progress\ndata: {json.dumps(first)}\n\n"
                if first.get("stage") in ("done", "failed"):
                    return
            iterator = stream_events.__aiter__()
            while True:
                try:
                    event = await asyncio.wait_for(iterator.__anext__(), HEARTBEAT_S)
                except TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                except StopAsyncIteration:
                    return
                yield f"event: progress\ndata: {json.dumps(event)}\n\n"
                if event.get("stage") in ("done", "failed"):
                    return

        headers = {"Cache-Control": "no-store", "X-Accel-Buffering": "no"}
        return StreamingResponse(stream(), media_type="text/event-stream", headers=headers)

    @app.get("/api/graphs/{owner}/{repo}/{sha}", summary="Graph JSON for one commit (immutable)")
    async def graph(owner: str, repo: str, sha: str) -> JSONResponse:
        if not (_OWNER.match(owner) and _REPO.match(repo) and _SHA.match(sha)):
            raise HTTPException(400, "Bad owner, repo or sha.")
        data = store.get_graph(owner, repo, sha, ENGINE_VERSION) or store.latest_graph(
            owner, repo, sha
        )
        if data is None:
            raise HTTPException(404, "Not analysed yet.")
        return JSONResponse(data, headers=IMMUTABLE)

    def _file(path: Any, fallback: JSON) -> JSON:
        if path is None or not path.is_file():
            return fallback
        loaded: JSON = json.loads(path.read_text(encoding="utf-8"))
        return loaded

    @app.get("/api/gallery", summary="Featured, pre-analysed repos")
    async def gallery() -> JSON:
        return _file(settings.gallery_path, {"repos": []})

    @app.get("/api/benchmarks", summary="Latest benchmark results")
    async def benchmarks() -> JSON:
        data = _file(settings.benchmark_path, {})
        if not data:
            raise HTTPException(404, "No benchmark results published.")
        return data

    @app.post(
        "/api/shares",
        status_code=201,
        summary="Share a graph (metadata only, schema-validated, expiring)",
    )
    async def create_share(
        request: Request,
        ttl_days: int = Query(default=0, alias="ttlDays", ge=0, le=MAX_SHARE_TTL_DAYS),
    ) -> JSONResponse:
        client = client_id(request)
        if not await broker.allow(f"share:{client}", settings.share_limit_per_hour):
            raise HTTPException(
                429, "Too many shares from this address; try again within the hour."
            )
        raw = await request.body()
        if len(raw) > settings.share_max_bytes:
            raise HTTPException(
                413, f"Graphs over {settings.share_max_bytes} bytes can't be shared."
            )
        try:
            data = json.loads(raw)
        except ValueError as exc:
            raise HTTPException(400, "Body must be graph JSON.") from exc
        errors = await asyncio.to_thread(schema_errors, data)
        if errors:
            raise HTTPException(422, {"message": "Not a valid Evident graph.", "errors": errors})
        graph = Graph.from_dict(data)
        problems = graph.check_integrity()
        if problems:
            detail = {"message": "Graph failed integrity checks.", "errors": problems[:5]}
            raise HTTPException(422, detail)
        store.purge_shares()
        share_id, token = secrets.token_urlsafe(12), secrets.token_urlsafe(24)
        days = ttl_days or settings.share_ttl_days
        expires = datetime.now(UTC) + timedelta(days=min(days, MAX_SHARE_TTL_DAYS))
        # Re-serialised from the parsed graph: only schema fields are stored, never raw input.
        store.create_share(Share(share_id, graph.to_dict(), _token_hash(token), expires, client))
        url = f"{settings.public_url}/map/?share={share_id}" if settings.public_url else None
        body = {"id": share_id, "url": url, "expiresAt": expires.isoformat(), "deleteToken": token}
        return JSONResponse(body, status_code=201)

    @app.get("/api/shares/{share_id}", summary="A shared graph, until it expires")
    async def get_share(share_id: str) -> JSONResponse:
        share = store.get_share(share_id) if _SHARE_ID.match(share_id) else None
        if share is None:
            raise HTTPException(404, "This share link has expired or never existed.")
        return JSONResponse(share.graph, headers={"Cache-Control": "private, max-age=300"})

    @app.delete("/api/shares/{share_id}", status_code=204, summary="Delete a share early")
    async def delete_share(
        share_id: str, x_delete_token: str = Header(default="", max_length=100)
    ) -> Response:
        if not (_SHARE_ID.match(share_id) and x_delete_token):
            raise HTTPException(404, "No such share.")
        if not store.delete_share(share_id, _token_hash(x_delete_token)):
            raise HTTPException(404, "No such share, or the token doesn't match.")
        return Response(status_code=204)

    @app.post("/api/reports", status_code=202, summary="Flag a wrong node or edge")
    async def report(body: ReportRequest, request: Request) -> JSONResponse:
        client = client_id(request)
        if not await broker.allow(f"report:{client}", settings.report_limit_per_hour):
            raise HTTPException(429, "Too many reports from this address; try again later.")
        store.add_report(
            Report(
                body.owner,
                body.repo,
                body.sha,
                body.engineVersion,
                body.elementId,
                body.kind,
                body.note,
                client,
            )
        )
        return JSONResponse({"ok": True}, status_code=202)

    @app.get("/api/health", summary="Liveness for the uptime monitor")
    async def health() -> JSONResponse:
        db, redis = store.ping(), await broker.ping()
        body = {
            "ok": db and redis,
            "db": db,
            "redis": redis,
            "engineVersion": ENGINE_VERSION,
            "schemaVersion": GRAPH_SCHEMA_VERSION,
        }
        return JSONResponse(body, status_code=200 if db and redis else 503)

    return app


def __getattr__(name: str) -> Any:
    """`uvicorn evident.service.api:app` builds the app lazily, so imports stay cheap in tests."""
    if name == "app":
        return create_app()
    raise AttributeError(name)
