"""Service: API contract, dedupe, rate limits, the job runner (child process + timeout), SSE."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from evident import ENGINE_VERSION
from evident.models import AnalysisError
from evident.repo import GitHubRepo
from evident.service.api import create_app
from evident.service.broker import MemoryBroker
from evident.service.config import Settings
from evident.service.jobs import run_job
from evident.service.store import MemoryStore

SHA = "a" * 40
SETTINGS = Settings(
    database_url=None,
    redis_url="redis://unused",
    job_timeout_s=120,
    rate_limit_per_hour=5,
    max_queued_jobs=10,
    ip_salt="test",
    trust_proxy=False,
    use_llm=False,
    gallery_path=None,
    benchmark_path=None,
)


def _resolve(repo: GitHubRepo) -> str:
    if repo.name == "missing":
        raise AnalysisError("aadilsal/missing not found or private")
    return SHA


@pytest.fixture
def svc() -> tuple[TestClient, MemoryStore, MemoryBroker]:
    store, broker = MemoryStore(), MemoryBroker()
    app = create_app(store, broker, SETTINGS, resolve=_resolve)
    return TestClient(app), store, broker


def _submit(
    client: TestClient, url: str = "https://github.com/acme/shop"
) -> tuple[int, dict[str, object]]:
    resp = client.post("/api/analyses", json={"url": url})
    return resp.status_code, resp.json()


def test_rejects_non_github_urls_and_missing_repos(
    svc: tuple[TestClient, MemoryStore, MemoryBroker],
) -> None:
    client, _, _ = svc
    assert _submit(client, "https://gitlab.com/a/b")[0] == 400
    assert _submit(client, "file:///etc/passwd")[0] == 400
    code, body = _submit(client, "https://github.com/acme/missing")
    assert code == 422 and "not found" in str(body["detail"])


def test_queues_once_per_commit_and_dedupes(
    svc: tuple[TestClient, MemoryStore, MemoryBroker],
) -> None:
    client, store, broker = svc
    code, first = _submit(client)
    assert code == 202 and first["status"] == "queued" and first["sha"] == SHA
    code, again = _submit(client, "https://github.com/acme/shop/tree/main")
    assert code == 202 and again["jobId"] == first["jobId"]
    assert broker.queue == [first["jobId"]]
    job = store.get_job(str(first["jobId"]))
    assert job is not None and job.ip_hash and "127.0.0.1" not in job.ip_hash
    public = client.get(f"/api/analyses/{first['jobId']}").json()
    assert "ip_hash" not in public and public["status"] == "queued"


def test_rate_limit_per_client(svc: tuple[TestClient, MemoryStore, MemoryBroker]) -> None:
    client, _, _ = svc
    codes = [_submit(client, f"https://github.com/acme/r{i}")[0] for i in range(7)]
    assert codes == [202] * 5 + [429, 429]


def test_job_runs_in_a_child_process_and_serves_an_immutable_graph(
    svc: tuple[TestClient, MemoryStore, MemoryBroker],
    fixture_repo: Path,
    graph_validator: Draft202012Validator,
) -> None:
    client, store, broker = svc
    _, body = _submit(client)
    job_id = str(body["jobId"])
    assert asyncio.run(run_job(job_id, store, broker, SETTINGS, target=str(fixture_repo))) == "done"
    status = client.get(f"/api/analyses/{job_id}").json()
    assert status["status"] == "done" and status["graphUrl"] == f"/api/graphs/acme/shop/{SHA}"
    # The local fixture graph is stored under its own repo key; serve it by that key.
    graph = next(iter(store.graphs.values()))
    assert not [e.message for e in graph_validator.iter_errors(graph)]
    assert graph["engineVersion"] == ENGINE_VERSION and graph["groups"]
    stages = [s for s in ("fetch", "parse", "extract", "link", "analyse", "group")]
    assert broker.snapshots[job_id]["stage"] == "done" and stages
    events = client.get(f"/api/analyses/{job_id}/events")
    assert events.headers["content-type"].startswith("text/event-stream")
    assert '"stage": "done"' in events.text


def test_cached_commit_short_circuits(svc: tuple[TestClient, MemoryStore, MemoryBroker]) -> None:
    client, store, _ = svc
    store.graphs[("acme", "shop", SHA, ENGINE_VERSION)] = {"repo": {"name": "shop"}, "nodes": []}
    code, body = _submit(client)
    assert code == 200 and body == {
        "status": "done",
        "sha": SHA,
        "graphUrl": f"/api/graphs/acme/shop/{SHA}",
    }
    resp = client.get(f"/api/graphs/acme/shop/{SHA}")
    assert resp.status_code == 200 and "immutable" in resp.headers["cache-control"]
    assert client.get("/api/graphs/acme/shop/not-a-sha").status_code == 400
    assert client.get(f"/api/graphs/acme/other/{SHA}").status_code == 404


def test_timeout_kills_the_child_and_fails_the_job(
    svc: tuple[TestClient, MemoryStore, MemoryBroker], fixture_repo: Path
) -> None:
    client, store, broker = svc
    job_id = str(_submit(client)[1]["jobId"])
    quick = replace(SETTINGS, job_timeout_s=0)
    assert asyncio.run(run_job(job_id, store, broker, quick, target=str(fixture_repo))) == "failed"
    job = store.get_job(job_id)
    assert job is not None and job.error == "analysis timed out after 0s"
    assert broker.snapshots[job_id] == {"stage": "failed", "error": job.error, "counts": {}}


def test_analysis_errors_are_reported_not_raised(
    svc: tuple[TestClient, MemoryStore, MemoryBroker], tmp_path: Path
) -> None:
    client, store, broker = svc
    job_id = str(_submit(client)[1]["jobId"])
    missing = str(tmp_path / "nope")
    assert asyncio.run(run_job(job_id, store, broker, SETTINGS, target=missing)) == "failed"
    job = store.get_job(job_id)
    assert job is not None and job.error is not None and "not a directory" in job.error


def test_health_gallery_and_openapi(
    svc: tuple[TestClient, MemoryStore, MemoryBroker], tmp_path: Path
) -> None:
    client, _, _ = svc
    health = client.get("/api/health").json()
    assert health["ok"] is True and health["engineVersion"] == ENGINE_VERSION
    assert client.get("/api/gallery").json() == {"repos": []}
    assert client.get("/api/benchmarks").status_code == 404
    spec = client.get("/api/openapi.json").json()
    assert {"/api/analyses", "/api/graphs/{owner}/{repo}/{sha}"} <= set(spec["paths"])
    bench = tmp_path / "b.json"
    bench.write_text(json.dumps({"categories": {}}), encoding="utf-8")
    app = create_app(
        MemoryStore(), MemoryBroker(), replace(SETTINGS, benchmark_path=bench), resolve=_resolve
    )
    assert TestClient(app).get("/api/benchmarks").json() == {"categories": {}}


# --- shares and reports (Interface phase) -------------------------------------------------------

EXAMPLE = Path(__file__).resolve().parents[2] / "schema" / "examples" / "minimal.graph.json"


def _example() -> dict[str, object]:
    data: dict[str, object] = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    return data


def test_share_round_trip_and_delete_with_token(
    svc: tuple[TestClient, MemoryStore, MemoryBroker],
) -> None:
    client, store, _ = svc
    resp = client.post("/api/shares", json=_example())
    assert resp.status_code == 201
    body = resp.json()
    assert body["url"] is None  # no EVIDENT_PUBLIC_URL configured
    share_id, token = body["id"], body["deleteToken"]
    assert token not in json.dumps([vars(s) for s in store.shares.values()], default=str)
    got = client.get(f"/api/shares/{share_id}")
    assert got.status_code == 200 and got.json()["nodes"] == _example()["nodes"]
    assert (
        client.delete(f"/api/shares/{share_id}", headers={"X-Delete-Token": "nope"}).status_code
        == 404
    )
    assert (
        client.delete(f"/api/shares/{share_id}", headers={"X-Delete-Token": token}).status_code
        == 204
    )
    assert client.get(f"/api/shares/{share_id}").status_code == 404


def test_share_rejects_code_smuggled_into_attrs_and_bad_graphs(
    svc: tuple[TestClient, MemoryStore, MemoryBroker],
) -> None:
    client, _, _ = svc
    smuggled = _example()
    nodes = smuggled["nodes"]
    assert isinstance(nodes, list)
    nodes[1]["attrs"]["source"] = "export async function POST() { ... }"
    resp = client.post("/api/shares", json=smuggled)
    assert resp.status_code == 422 and "Not a valid" in json.dumps(resp.json())
    dangling = _example()
    edges = dangling["edges"]
    assert isinstance(edges, list)
    edges[0]["to"] = "handler:nowhere.ts#X"
    assert client.post("/api/shares", json=dangling).status_code == 422
    assert client.post("/api/shares", content=b"not json").status_code == 400


def test_share_size_cap_expiry_and_rate_limit(tmp_path: Path) -> None:
    store, broker = MemoryStore(), MemoryBroker()
    settings = replace(SETTINGS, share_max_bytes=100, share_limit_per_hour=2)
    client = TestClient(create_app(store, broker, settings, resolve=_resolve))
    assert client.post("/api/shares", json=_example()).status_code == 413
    settings = replace(SETTINGS, share_limit_per_hour=2, public_url="https://evident.example")
    client = TestClient(create_app(store, broker, settings, resolve=_resolve))
    first = client.post("/api/shares?ttlDays=1", json=_example()).json()
    assert first["url"] == f"https://evident.example/map/?share={first['id']}"
    share = store.shares[first["id"]]
    share.expires_at = share.created_at  # expired
    assert client.get(f"/api/shares/{first['id']}").status_code == 404
    client.post("/api/shares", json=_example())
    assert client.post("/api/shares", json=_example()).status_code == 429
    assert client.post("/api/shares?ttlDays=99", json=_example()).status_code in (422, 429)


def test_reports_are_validated_and_stored(
    svc: tuple[TestClient, MemoryStore, MemoryBroker],
) -> None:
    client, store, _ = svc
    report = {
        "owner": "acme",
        "repo": "shop",
        "sha": SHA,
        "engineVersion": ENGINE_VERSION,
        "elementId": "writes:handler:a.ts#POST->model:User",
        "kind": "edge",
        "note": "phantom edge",
    }
    assert client.post("/api/reports", json=report).status_code == 202
    assert store.reports[0].element_id == report["elementId"] and store.reports[0].ip_hash
    assert client.post("/api/reports", json={**report, "sha": "main"}).status_code == 422
    assert client.post("/api/reports", json={**report, "kind": "group"}).status_code == 422


def test_cors_allows_only_configured_origins() -> None:
    settings = replace(SETTINGS, cors_origins=("https://evident.example",))
    client = TestClient(create_app(MemoryStore(), MemoryBroker(), settings, resolve=_resolve))
    ok = client.get("/api/gallery", headers={"Origin": "https://evident.example"})
    assert ok.headers.get("access-control-allow-origin") == "https://evident.example"
    other = client.get("/api/gallery", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in other.headers
