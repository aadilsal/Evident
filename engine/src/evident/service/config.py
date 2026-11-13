"""Service settings from the process environment. Secrets are read by name, never logged."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    database_url: str | None
    redis_url: str
    job_timeout_s: int
    rate_limit_per_hour: int
    max_queued_jobs: int
    ip_salt: str
    trust_proxy: bool
    use_llm: bool
    gallery_path: Path | None
    benchmark_path: Path | None
    cors_origins: tuple[str, ...] = ()
    public_url: str = ""
    share_ttl_days: int = 7
    share_max_bytes: int = 2_000_000
    share_limit_per_hour: int = 20
    report_limit_per_hour: int = 30

    @classmethod
    def from_env(cls) -> Settings:
        def path(name: str) -> Path | None:
            value = os.environ.get(name, "").strip()
            return Path(value) if value else None

        return cls(
            database_url=os.environ.get("DATABASE_URL") or None,
            redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
            job_timeout_s=_int("EVIDENT_JOB_TIMEOUT_S", 120),
            rate_limit_per_hour=_int("EVIDENT_RATE_LIMIT_PER_HOUR", 10),
            max_queued_jobs=_int("EVIDENT_MAX_QUEUED_JOBS", 50),
            # A fresh salt per process if unset: IP hashes still can't be reversed or joined.
            ip_salt=os.environ.get("EVIDENT_IP_SALT") or secrets.token_hex(16),
            trust_proxy=os.environ.get("EVIDENT_TRUST_PROXY", "") == "1",
            use_llm=os.environ.get("EVIDENT_LLM", "on") != "off",
            gallery_path=path("EVIDENT_GALLERY_PATH"),
            benchmark_path=path("EVIDENT_BENCHMARK_PATH"),
            # The Vercel frontend's origin(s); exact matches only, never "*".
            cors_origins=tuple(
                o.strip().rstrip("/")
                for o in os.environ.get("EVIDENT_CORS_ORIGINS", "").split(",")
                if o.strip() and o.strip() != "*"
            ),
            public_url=os.environ.get("EVIDENT_PUBLIC_URL", "").rstrip("/"),
            share_ttl_days=_int("EVIDENT_SHARE_TTL_DAYS", 7),
            share_max_bytes=_int("EVIDENT_SHARE_MAX_BYTES", 2_000_000),
            share_limit_per_hour=_int("EVIDENT_SHARE_LIMIT_PER_HOUR", 20),
            report_limit_per_hour=_int("EVIDENT_REPORT_LIMIT_PER_HOUR", 30),
        )
