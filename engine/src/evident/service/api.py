"""FastAPI app (architecture §6). Run: `uvicorn evident.service.api:app`."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from evident import ENGINE_VERSION, GRAPH_SCHEMA_VERSION
from evident.models import AnalysisError
from evident.repo import GitHubRepo, check_size, parse_github, remote_head
from evident.service.broker import Broker, RedisBroker
from evident.service.config import Settings
from evident.service.store import Job, MemoryStore, PostgresStore, Store

JSON = dict[str, Any]
Resolver = Callable[[GitHubRepo], str]
_OWNER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}$")
_REPO = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
_SHA = re.compile(r"^[0-9a-f]{40}$")
HEARTBEAT_S = 15.0
IMMUTABLE = {"Cache-Control": "public, max-age=31536000, immutable"}


class AnalysisRequest(BaseModel):
    url: str = Field(
        description="https://github.com/<owner>/<repo>, optionally /tree/<ref>", max_length=300
    )


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
