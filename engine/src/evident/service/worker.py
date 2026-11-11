"""arq worker. Run: `arq evident.service.worker.WorkerSettings`.

One job at a time per worker process (security.md T3); scale with more containers, not threads.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, ClassVar

from arq import cron
from arq.connections import RedisSettings

from evident.service.broker import RedisBroker
from evident.service.config import Settings
from evident.service.jobs import run_job
from evident.service.store import MemoryStore, PostgresStore

ORPHAN_AGE_S = 600


async def startup(ctx: dict[str, Any]) -> None:
    settings = Settings.from_env()
    store = PostgresStore(settings.database_url) if settings.database_url else MemoryStore()
    store.setup()
    ctx.update(settings=settings, store=store, broker=RedisBroker(settings.redis_url))


async def analyze_job(ctx: dict[str, Any], job_id: str) -> str:
    return await run_job(job_id, ctx["store"], ctx["broker"], ctx["settings"])


async def sweep_tmp(ctx: dict[str, Any]) -> int:
    """Backstop for T5: remove job temp dirs a crashed worker left behind."""
    del ctx
    removed = 0
    root = Path(tempfile.gettempdir())
    for d in root.glob("evident-*"):
        try:
            if d.is_dir() and time.time() - d.stat().st_mtime > ORPHAN_AGE_S:
                shutil.rmtree(d, ignore_errors=True)
                removed += 1
        except OSError:
            continue
    return removed


class WorkerSettings:
    functions: ClassVar[list[Any]] = [analyze_job]
    cron_jobs: ClassVar[list[Any]] = [cron(sweep_tmp, minute=set(range(0, 60, 5)))]
    on_startup = startup
    max_jobs = 1
    job_timeout = Settings.from_env().job_timeout_s + 30
    redis_settings = RedisSettings.from_dsn(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
