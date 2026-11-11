"""Run one analysis job (architecture §4). Shared by the arq worker and the tests.

The pipeline runs in a child process: a timeout can kill it outright (a thread can't be killed),
and a crash or memory blow-up in parsing can't take the worker down (security.md T3).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import multiprocessing as mp
import queue
import shutil
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evident.service.broker import Broker
from evident.service.config import Settings
from evident.service.store import Store

JSON = dict[str, Any]
POLL_S = 0.2


def _child(target: str, out: str, events: Any, use_llm: bool) -> None:
    """In the child process: analyse, stream progress, write the graph to `out`."""
    from evident.analyze import analyze
    from evident.models import AnalysisError

    def progress(stage: str, counts: dict[str, int]) -> None:
        events.put({"stage": stage, "counts": counts})

    try:
        res = analyze(target, use_llm=use_llm, cache_root=Path(out).parent, progress=progress)
        payload = {"graph": res.graph.to_dict(), "llm": res.llm, "durationMs": res.duration_ms}
        Path(out).write_text(json.dumps(payload), encoding="utf-8")
    except AnalysisError as exc:
        events.put({"stage": "failed", "error": str(exc)[:300]})
    except Exception as exc:
        events.put({"stage": "failed", "error": f"internal error ({type(exc).__name__})"})


async def run_job(
    job_id: str,
    store: Store,
    broker: Broker,
    settings: Settings,
    *,
    target: str | None = None,
) -> str:
    """Returns the final status. `target` overrides the GitHub URL (tests use a local fixture)."""
    job = store.get_job(job_id)
    if job is None:
        return "failed"
    started = datetime.now(UTC)
    store.update_job(job_id, status="running", started_at=started)
    await broker.publish(job_id, {"stage": "fetch", "counts": {}})
    tmp = Path(tempfile.mkdtemp(prefix="evident-job-"))
    out = tmp / "result.json"
    ctx = mp.get_context("spawn")
    events: Any = ctx.Queue()
    child = ctx.Process(
        target=_child, args=(target or job.url, str(out), events, settings.use_llm), daemon=True
    )
    error: str | None = None
    try:
        child.start()
        deadline = time.monotonic() + settings.job_timeout_s
        while True:
            error = await _relay(job_id, events, store, broker) or error
            if not child.is_alive():
                break
            if time.monotonic() > deadline:
                child.kill()
                child.join(5)
                error = f"analysis timed out after {settings.job_timeout_s}s"
                break
            await asyncio.sleep(POLL_S)
        error = await _relay(job_id, events, store, broker) or error
        if error is None and out.is_file():
            result = json.loads(out.read_text(encoding="utf-8"))
            store.save_graph(result["graph"])
            store.update_job(
                job_id,
                status="done",
                stage="done",
                llm=result["llm"],
                duration_ms=result["durationMs"],
                finished_at=datetime.now(UTC),
            )
            await broker.publish(job_id, {"stage": "done", "graphUrl": job.graph_url, "counts": {}})
            return "done"
        error = error or "analysis failed"
        store.update_job(
            job_id, status="failed", stage="failed", error=error, finished_at=datetime.now(UTC)
        )
        await broker.publish(job_id, {"stage": "failed", "error": error, "counts": {}})
        return "failed"
    finally:
        if child.is_alive():
            child.kill()
        with contextlib.suppress(Exception):
            events.close()
        shutil.rmtree(tmp, ignore_errors=True)


async def _relay(job_id: str, events: Any, store: Store, broker: Broker) -> str | None:
    """Forward queued child events; returns an error message if the child reported one."""
    error = None
    while True:
        try:
            event: JSON = events.get_nowait()
        except queue.Empty:
            return error
        except (EOFError, OSError):
            return error
        if event["stage"] == "failed":
            error = str(event.get("error") or "analysis failed")
            continue
        if event["stage"] == "done":
            continue  # the parent announces done after the graph is stored
        store.update_job(job_id, stage=event["stage"], counts=event.get("counts", {}))
        await broker.publish(job_id, event)
