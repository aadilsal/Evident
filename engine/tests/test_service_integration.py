"""PostgresStore and RedisBroker against real services (CI provides them; skipped locally)."""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest

DB = os.environ.get("EVIDENT_TEST_DATABASE_URL")
REDIS = os.environ.get("EVIDENT_TEST_REDIS_URL")
pytestmark = pytest.mark.skipif(
    not (DB and REDIS), reason="needs EVIDENT_TEST_DATABASE_URL and _REDIS_URL"
)


def test_postgres_store_round_trip() -> None:
    from evident.service.store import Job, PostgresStore

    assert DB is not None
    store = PostgresStore(DB)
    store.setup()
    store.setup()  # idempotent
    repo = f"r{uuid.uuid4().hex[:8]}"
    job = store.create_job(Job("acme", repo, "b" * 40, "0.0.0", None, "hash"))
    assert store.active_job("acme", repo, "b" * 40, "0.0.0") is not None
    store.update_job(job.id, status="done", stage="done", counts={"routes": 3}, llm="skipped")
    got = store.get_job(job.id)
    assert got is not None and got.status == "done" and got.counts == {"routes": 3}
    assert store.active_job("acme", repo, "b" * 40, "0.0.0") is None
    graph = {
        "repo": {"owner": "acme", "name": repo, "sha": "b" * 40},
        "engineVersion": "0.0.0",
        "nodes": [],
        "edges": [],
        "findings": [{"id": "f1", "rule": "unused-model", "severity": "info", "message": "m"}],
    }
    store.save_graph(graph)
    store.save_graph(graph)  # conflict-safe
    assert store.get_graph("acme", repo, "b" * 40, "0.0.0") == graph
    assert store.ping()


def test_redis_broker_snapshot_pubsub_and_rate_limit() -> None:
    from evident.service.broker import RedisBroker

    assert REDIS is not None

    async def scenario() -> list[str]:
        broker = RedisBroker(REDIS)
        job = uuid.uuid4().hex
        seen: list[str] = []

        async def listen() -> None:
            async for event in broker.subscribe(job):
                seen.append(str(event["stage"]))

        task = asyncio.create_task(listen())
        await asyncio.sleep(0.2)
        for stage in ("parse", "link", "done"):
            await broker.publish(job, {"stage": stage})
        await asyncio.wait_for(task, 5)
        assert (await broker.snapshot(job)) == {"stage": "done"}
        client = uuid.uuid4().hex
        assert [await broker.allow(client, 2) for _ in range(3)] == [True, True, False]
        assert await broker.ping()
        return seen

    assert asyncio.run(scenario()) == ["parse", "link", "done"]


def test_postgres_shares_and_reports() -> None:
    from datetime import UTC, datetime, timedelta

    from evident.service.store import PostgresStore, Report, Share

    assert DB
    store = PostgresStore(DB)
    store.setup()
    sid = uuid.uuid4().hex[:16]
    graph = {"schemaVersion": "1.2.0", "nodes": [], "edges": []}
    store.create_share(Share(sid, graph, "hash", datetime.now(UTC) + timedelta(days=1), "ip"))
    got = store.get_share(sid)
    assert got is not None and got.graph == graph
    assert not store.delete_share(sid, "wrong")
    assert store.delete_share(sid, "hash") and store.get_share(sid) is None
    old = uuid.uuid4().hex[:16]
    store.create_share(Share(old, graph, "h", datetime.now(UTC) - timedelta(seconds=1)))
    assert store.get_share(old) is None and store.purge_shares() >= 1
    store.add_report(Report("acme", "shop", "a" * 40, "0.3.0", "model:User", "node", "note"))
