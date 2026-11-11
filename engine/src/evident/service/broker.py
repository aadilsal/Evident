"""Queue, progress pub/sub and rate limits over Redis (architecture §3), plus an in-memory twin."""

from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Any, Protocol

JSON = dict[str, Any]
SNAPSHOT_TTL_S = 24 * 3600
RATE_WINDOW_S = 3600


class Broker(Protocol):
    async def enqueue(self, job_id: str) -> None: ...
    async def publish(self, job_id: str, event: JSON) -> None: ...
    async def snapshot(self, job_id: str) -> JSON | None: ...
    def subscribe(self, job_id: str) -> AsyncIterator[JSON]: ...
    async def allow(self, client: str, limit: int) -> bool: ...
    async def ping(self) -> bool: ...


def _terminal(event: JSON) -> bool:
    return event.get("stage") in ("done", "failed")


class RedisBroker:
    def __init__(self, url: str) -> None:
        import redis.asyncio as aioredis

        self.url = url
        self.redis = aioredis.from_url(url, decode_responses=True)  # type: ignore[no-untyped-call]
        self._arq: Any = None

    async def enqueue(self, job_id: str) -> None:
        from arq import create_pool
        from arq.connections import RedisSettings

        if self._arq is None:
            self._arq = await create_pool(RedisSettings.from_dsn(self.url))
        await self._arq.enqueue_job("analyze_job", job_id, _job_id=job_id)  # arq dedupes by id

    async def publish(self, job_id: str, event: JSON) -> None:
        data = json.dumps(event)
        await self.redis.set(f"evident:job:{job_id}", data, ex=SNAPSHOT_TTL_S)
        await self.redis.publish(f"evident:events:{job_id}", data)

    async def snapshot(self, job_id: str) -> JSON | None:
        data = await self.redis.get(f"evident:job:{job_id}")
        return dict(json.loads(data)) if data else None

    async def subscribe(self, job_id: str) -> AsyncIterator[JSON]:
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(f"evident:events:{job_id}")
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                event = dict(json.loads(message["data"]))
                yield event
                if _terminal(event):
                    return
        finally:
            await pubsub.unsubscribe()
            await pubsub.aclose()

    async def allow(self, client: str, limit: int) -> bool:
        key = f"evident:rate:{client}:{int(time.time()) // RATE_WINDOW_S}"
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, RATE_WINDOW_S)
        return int(count) <= limit

    async def ping(self) -> bool:
        try:
            return bool(await self.redis.ping())
        except Exception:
            return False


class MemoryBroker:
    """Same behaviour in one process: tests, and `evident serve` without Redis."""

    def __init__(self) -> None:
        self.queue: list[str] = []
        self.snapshots: dict[str, JSON] = {}
        self.hits: dict[str, int] = defaultdict(int)
        self._subs: dict[str, list[asyncio.Queue[JSON]]] = defaultdict(list)

    async def enqueue(self, job_id: str) -> None:
        if job_id not in self.queue:
            self.queue.append(job_id)

    async def publish(self, job_id: str, event: JSON) -> None:
        self.snapshots[job_id] = event
        for q in self._subs[job_id]:
            q.put_nowait(event)

    async def snapshot(self, job_id: str) -> JSON | None:
        return self.snapshots.get(job_id)

    async def subscribe(self, job_id: str) -> AsyncIterator[JSON]:
        q: asyncio.Queue[JSON] = asyncio.Queue()
        self._subs[job_id].append(q)
        try:
            while True:
                event = await q.get()
                yield event
                if _terminal(event):
                    return
        finally:
            self._subs[job_id].remove(q)

    async def allow(self, client: str, limit: int) -> bool:
        key = f"{client}:{int(time.time()) // RATE_WINDOW_S}"
        self.hits[key] += 1
        return self.hits[key] <= limit

    async def ping(self) -> bool:
        return True
