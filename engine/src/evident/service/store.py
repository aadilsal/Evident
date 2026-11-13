"""Jobs and cached graphs. Postgres in production (architecture §7), in-memory for tests."""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

JSON = dict[str, Any]
Status = Literal["queued", "running", "done", "failed"]
TERMINAL = ("done", "failed")

SCHEMA_SQL = """
create table if not exists jobs (
  id text primary key,
  owner text not null,
  repo text not null,
  sha text not null,
  ref text,
  engine_version text not null,
  status text not null,
  stage text,
  counts jsonb not null default '{}'::jsonb,
  error text,
  ip_hash text,
  llm text,
  duration_ms integer,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz
);
create index if not exists jobs_key on jobs (owner, repo, sha, engine_version, status);
create table if not exists graphs (
  owner text not null,
  repo text not null,
  sha text not null,
  engine_version text not null,
  graph jsonb not null,
  nodes integer not null,
  edges integer not null,
  created_at timestamptz not null default now(),
  primary key (owner, repo, sha, engine_version)
);
create table if not exists findings (
  owner text not null,
  repo text not null,
  sha text not null,
  engine_version text not null,
  finding_id text not null,
  rule text not null,
  severity text not null,
  message text not null,
  primary key (owner, repo, sha, engine_version, finding_id)
);
create table if not exists shares (
  id text primary key,
  graph jsonb not null,
  delete_token_hash text not null,
  ip_hash text,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null
);
create index if not exists shares_expiry on shares (expires_at);
create table if not exists reports (
  id bigserial primary key,
  owner text not null,
  repo text not null,
  sha text not null,
  engine_version text not null,
  element_id text not null,
  kind text not null,
  note text,
  ip_hash text,
  created_at timestamptz not null default now()
);
create table if not exists benchmark_runs (
  id bigserial primary key,
  created_at timestamptz not null default now(),
  evident_sha text,
  summary jsonb not null
);
"""


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Job:
    owner: str
    repo: str
    sha: str
    engine_version: str
    ref: str | None = None
    ip_hash: str | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: Status = "queued"
    stage: str | None = None
    counts: JSON = field(default_factory=dict)
    error: str | None = None
    llm: str | None = None
    duration_ms: int | None = None
    created_at: datetime = field(default_factory=_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @property
    def url(self) -> str:
        return f"https://github.com/{self.owner}/{self.repo}/tree/{self.sha}"

    @property
    def graph_url(self) -> str:
        return f"/api/graphs/{self.owner}/{self.repo}/{self.sha}"

    def public(self) -> JSON:
        """What the API returns: no IP hash."""
        d = asdict(self)
        d.pop("ip_hash")
        for key in ("created_at", "started_at", "finished_at"):
            d[key] = d[key].isoformat() if d[key] else None
        d["graphUrl"] = self.graph_url if self.status == "done" else None
        return d


@dataclass
class Share:
    """An opt-in `evident share` upload: graph metadata only, expiring (security.md)."""

    id: str
    graph: JSON
    delete_token_hash: str
    expires_at: datetime
    ip_hash: str | None = None
    created_at: datetime = field(default_factory=_now)


@dataclass
class Report:
    """A "wrong node/edge" flag from the map; feeds new benchmark cases."""

    owner: str
    repo: str
    sha: str
    engine_version: str
    element_id: str
    kind: Literal["node", "edge"]
    note: str = ""
    ip_hash: str | None = None
    created_at: datetime = field(default_factory=_now)


class Store(Protocol):
    def setup(self) -> None: ...
    def create_job(self, job: Job) -> Job: ...
    def get_job(self, job_id: str) -> Job | None: ...
    def active_job(self, owner: str, repo: str, sha: str, engine_version: str) -> Job | None: ...
    def update_job(self, job_id: str, **fields: Any) -> None: ...
    def count_active(self) -> int: ...
    def get_graph(self, owner: str, repo: str, sha: str, engine_version: str) -> JSON | None: ...
    def latest_graph(self, owner: str, repo: str, sha: str) -> JSON | None: ...
    def save_graph(self, graph: JSON) -> None: ...
    def create_share(self, share: Share) -> None: ...
    def get_share(self, share_id: str) -> Share | None: ...
    def delete_share(self, share_id: str, token_hash: str) -> bool: ...
    def purge_shares(self) -> int: ...
    def add_report(self, report: Report) -> None: ...
    def ping(self) -> bool: ...


class MemoryStore:
    """In-process store for tests and single-user local runs."""

    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self.graphs: dict[tuple[str, str, str, str], JSON] = {}
        self.shares: dict[str, Share] = {}
        self.reports: list[Report] = []
        self._lock = threading.Lock()

    def setup(self) -> None:
        return None

    def create_job(self, job: Job) -> Job:
        with self._lock:
            self.jobs[job.id] = job
        return job

    def get_job(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def active_job(self, owner: str, repo: str, sha: str, engine_version: str) -> Job | None:
        return next(
            (
                j
                for j in self.jobs.values()
                if (j.owner, j.repo, j.sha, j.engine_version) == (owner, repo, sha, engine_version)
                and j.status not in TERMINAL
            ),
            None,
        )

    def update_job(self, job_id: str, **fields: Any) -> None:
        with self._lock:
            job = self.jobs[job_id]
            for k, v in fields.items():
                setattr(job, k, v)

    def count_active(self) -> int:
        return sum(1 for j in self.jobs.values() if j.status not in TERMINAL)

    def get_graph(self, owner: str, repo: str, sha: str, engine_version: str) -> JSON | None:
        return self.graphs.get((owner, repo, sha, engine_version))

    def latest_graph(self, owner: str, repo: str, sha: str) -> JSON | None:
        hits = [g for (o, r, s, _), g in self.graphs.items() if (o, r, s) == (owner, repo, sha)]
        return max(hits, key=lambda g: str(g.get("engineVersion")), default=None)

    def save_graph(self, graph: JSON) -> None:
        repo = graph["repo"]
        key = (repo.get("owner", ""), repo["name"], repo["sha"], graph["engineVersion"])
        self.graphs[key] = graph

    def create_share(self, share: Share) -> None:
        with self._lock:
            self.shares[share.id] = share

    def get_share(self, share_id: str) -> Share | None:
        share = self.shares.get(share_id)
        return share if share and share.expires_at > _now() else None

    def delete_share(self, share_id: str, token_hash: str) -> bool:
        with self._lock:
            share = self.shares.get(share_id)
            if share is None or share.delete_token_hash != token_hash:
                return False
            del self.shares[share_id]
            return True

    def purge_shares(self) -> int:
        with self._lock:
            dead = [k for k, v in self.shares.items() if v.expires_at <= _now()]
            for k in dead:
                del self.shares[k]
            return len(dead)

    def add_report(self, report: Report) -> None:
        with self._lock:
            self.reports.append(report)

    def ping(self) -> bool:
        return True


class PostgresStore:
    """psycopg 3, one short connection per call: low traffic, no pool to babysit."""

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def _conn(self) -> Any:
        import psycopg

        return psycopg.connect(self.dsn, autocommit=True)

    def setup(self) -> None:
        with self._conn() as conn:
            conn.execute(SCHEMA_SQL)

    def create_job(self, job: Job) -> Job:
        with self._conn() as conn:
            conn.execute(
                "insert into jobs (id, owner, repo, sha, ref, engine_version, status, ip_hash,"
                " created_at)"
                " values (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    job.id,
                    job.owner,
                    job.repo,
                    job.sha,
                    job.ref,
                    job.engine_version,
                    job.status,
                    job.ip_hash,
                    job.created_at,
                ),
            )
        return job

    def _job(self, row: Any) -> Job:
        (
            jid,
            owner,
            repo,
            sha,
            ref,
            ev,
            status,
            stage,
            counts,
            error,
            ip_hash,
            llm,
            dur,
            created,
            started,
            finished,
        ) = row
        return Job(
            owner,
            repo,
            sha,
            ev,
            ref,
            ip_hash,
            jid,
            status,
            stage,
            counts or {},
            error,
            llm,
            dur,
            created,
            started,
            finished,
        )

    _COLUMNS = (
        "id, owner, repo, sha, ref, engine_version, status, stage, counts, error, ip_hash,"
        " llm, duration_ms, created_at, started_at, finished_at"
    )

    def get_job(self, job_id: str) -> Job | None:
        with self._conn() as conn:
            # Only the constant column list is interpolated; values are bound parameters.
            sql = f"select {self._COLUMNS} from jobs where id = %s"  # noqa: S608
            row = conn.execute(sql, (job_id,)).fetchone()
        return self._job(row) if row else None

    def active_job(self, owner: str, repo: str, sha: str, engine_version: str) -> Job | None:
        with self._conn() as conn:
            row = conn.execute(
                f"select {self._COLUMNS} from jobs where owner = %s and repo = %s and sha = %s"  # noqa: S608
                " and engine_version = %s and status in ('queued', 'running')"
                " order by created_at desc limit 1",
                (owner, repo, sha, engine_version),
            ).fetchone()
        return self._job(row) if row else None

    def update_job(self, job_id: str, **fields: Any) -> None:
        allowed = {
            "status",
            "stage",
            "counts",
            "error",
            "llm",
            "duration_ms",
            "started_at",
            "finished_at",
        }
        cols = [k for k in fields if k in allowed]
        if not cols:
            return
        values = [json.dumps(fields[k]) if k == "counts" else fields[k] for k in cols]
        sets = ", ".join(f"{k} = %s" for k in cols)  # names come from the allow-list above
        with self._conn() as conn:
            conn.execute(f"update jobs set {sets} where id = %s", (*values, job_id))  # noqa: S608

    def count_active(self) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "select count(*) from jobs where status in ('queued', 'running')"
            ).fetchone()
        return int(row[0]) if row else 0

    def get_graph(self, owner: str, repo: str, sha: str, engine_version: str) -> JSON | None:
        with self._conn() as conn:
            row = conn.execute(
                "select graph from graphs where owner = %s and repo = %s and sha = %s"
                " and engine_version = %s",
                (owner, repo, sha, engine_version),
            ).fetchone()
        return dict(row[0]) if row else None

    def latest_graph(self, owner: str, repo: str, sha: str) -> JSON | None:
        with self._conn() as conn:
            row = conn.execute(
                "select graph from graphs where owner = %s and repo = %s and sha = %s"
                " order by created_at desc limit 1",
                (owner, repo, sha),
            ).fetchone()
        return dict(row[0]) if row else None

    def save_graph(self, graph: JSON) -> None:
        repo = graph["repo"]
        key = (repo.get("owner", ""), repo["name"], repo["sha"], graph["engineVersion"])
        with self._conn() as conn, conn.transaction():
            conn.execute(
                "insert into graphs (owner, repo, sha, engine_version, graph, nodes, edges)"
                " values (%s, %s, %s, %s, %s, %s, %s) on conflict do nothing",
                (*key, json.dumps(graph), len(graph["nodes"]), len(graph["edges"])),
            )
            for f in graph.get("findings", []):
                conn.execute(
                    "insert into findings (owner, repo, sha, engine_version, finding_id, rule,"
                    " severity,"
                    " message) values (%s, %s, %s, %s, %s, %s, %s, %s) on conflict do nothing",
                    (*key, f["id"], f["rule"], f["severity"], f["message"]),
                )

    def create_share(self, share: Share) -> None:
        with self._conn() as conn:
            conn.execute(
                "insert into shares (id, graph, delete_token_hash, ip_hash, created_at, expires_at)"
                " values (%s, %s, %s, %s, %s, %s)",
                (
                    share.id,
                    json.dumps(share.graph),
                    share.delete_token_hash,
                    share.ip_hash,
                    share.created_at,
                    share.expires_at,
                ),
            )

    def get_share(self, share_id: str) -> Share | None:
        with self._conn() as conn:
            row = conn.execute(
                "select id, graph, delete_token_hash, expires_at, ip_hash, created_at from shares"
                " where id = %s and expires_at > now()",
                (share_id,),
            ).fetchone()
        return Share(row[0], dict(row[1]), row[2], row[3], row[4], row[5]) if row else None

    def delete_share(self, share_id: str, token_hash: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                "delete from shares where id = %s and delete_token_hash = %s",
                (share_id, token_hash),
            )
            return bool(cur.rowcount)

    def purge_shares(self) -> int:
        with self._conn() as conn:
            cur = conn.execute("delete from shares where expires_at <= now()")
            return int(cur.rowcount or 0)

    def add_report(self, report: Report) -> None:
        with self._conn() as conn:
            conn.execute(
                "insert into reports (owner, repo, sha, engine_version, element_id, kind, note,"
                " ip_hash, created_at) values (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    report.owner,
                    report.repo,
                    report.sha,
                    report.engine_version,
                    report.element_id,
                    report.kind,
                    report.note,
                    report.ip_hash,
                    report.created_at,
                ),
            )

    def ping(self) -> bool:
        try:
            with self._conn() as conn:
                conn.execute("select 1")
            return True
        except Exception:
            return False
