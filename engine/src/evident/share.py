"""`evident share`: opt-in upload of graph metadata (no code) to the hosted viewer (security.md)."""

from __future__ import annotations

import contextlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from evident.models import AnalysisError, Graph, UsageError

# Set once the hosted API has its domain; until then pass --api or EVIDENT_API_URL.
DEFAULT_API_URL: str | None = None
SHARES_FILE = "shares.json"


@dataclass(frozen=True)
class ShareResult:
    id: str
    url: str | None
    expires_at: str
    api: str


def api_url(flag: str | None) -> str:
    url = (flag or os.environ.get("EVIDENT_API_URL") or DEFAULT_API_URL or "").rstrip("/")
    if not url:
        raise UsageError("no share server configured: pass --api URL or set EVIDENT_API_URL")
    if not url.startswith("https://") and not url.startswith("http://127.0.0.1"):
        raise UsageError("the share server must use https")
    return url


def payload(graph: Graph) -> dict[str, Any]:
    """Exactly the graph: ids, types, labels, paths, line ranges, findings. No file contents."""
    return graph.to_dict()


def upload(graph: Graph, api: str, ttl_days: int | None, cache_dir: Path) -> ShareResult:
    params = {"ttlDays": str(ttl_days)} if ttl_days else {}
    try:
        resp = httpx.post(f"{api}/api/shares", json=payload(graph), params=params, timeout=30)
    except httpx.HTTPError as exc:
        raise AnalysisError(f"couldn't reach {api}: {exc.__class__.__name__}") from exc
    if resp.status_code != 201:
        detail: Any = resp.text[:300]
        with contextlib.suppress(ValueError):
            detail = resp.json().get("detail", detail)
        raise AnalysisError(f"share refused ({resp.status_code}): {detail}")
    body = resp.json()
    _remember(cache_dir, body["id"], body["deleteToken"], body["expiresAt"], api)
    return ShareResult(body["id"], body.get("url"), body["expiresAt"], api)


def delete(share_id: str, cache_dir: Path) -> None:
    known = _load(cache_dir)
    entry = known.get(share_id)
    if entry is None:
        raise UsageError(f"no delete token for {share_id} in {cache_dir / SHARES_FILE}")
    try:
        resp = httpx.delete(
            f"{entry['api']}/api/shares/{share_id}",
            headers={"X-Delete-Token": entry["token"]},
            timeout=30,
        )
    except httpx.HTTPError as exc:
        raise AnalysisError(f"couldn't reach {entry['api']}: {exc.__class__.__name__}") from exc
    if resp.status_code not in (204, 404):
        raise AnalysisError(f"delete failed ({resp.status_code})")
    del known[share_id]
    _save(cache_dir, known)


def _load(cache_dir: Path) -> dict[str, dict[str, str]]:
    try:
        data: dict[str, dict[str, str]] = json.loads(
            (cache_dir / SHARES_FILE).read_text(encoding="utf-8")
        )
        return data
    except (OSError, ValueError):
        return {}


def _save(cache_dir: Path, data: dict[str, dict[str, str]]) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / SHARES_FILE).write_text(json.dumps(data, indent=1), encoding="utf-8")


def _remember(cache_dir: Path, share_id: str, token: str, expires: str, api: str) -> None:
    """Delete tokens stay in .evident/ (self-ignored), so `--delete` works later."""
    known = _load(cache_dir)
    known[share_id] = {"token": token, "expiresAt": expires, "api": api}
    _save(cache_dir, known)
