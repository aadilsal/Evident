"""Typed graph and CLI result models. JSON shapes match schema/*.schema.json."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Literal

from evident import CLI_SCHEMA_VERSION, ENGINE_VERSION, GRAPH_SCHEMA_VERSION, __version__

JSON = dict[str, Any]
Source = Literal["extracted", "inferred"]
Host = Literal["github.com", "local"]


class UsageError(Exception):
    """Bad arguments or an unresolvable query target (exit 2)."""


class AnalysisError(Exception):
    """The repo could not be analysed (exit 3)."""


@dataclass(frozen=True)
class Evidence:
    file: str
    start_line: int
    end_line: int
    sha: str

    @property
    def ref(self) -> str:
        if self.end_line == self.start_line:
            return f"{self.file}:{self.start_line}"
        return f"{self.file}:{self.start_line}-{self.end_line}"

    def to_dict(self) -> JSON:
        return {
            "file": self.file,
            "startLine": self.start_line,
            "endLine": self.end_line,
            "sha": self.sha,
        }

    @classmethod
    def from_dict(cls, d: JSON) -> Evidence:
        return cls(d["file"], d["startLine"], d["endLine"], d["sha"])


def _restamp(evidence: list[Evidence], sha: str) -> list[Evidence]:
    return [replace(e, sha=sha) for e in evidence]


@dataclass
class Node:
    id: str
    type: str
    label: str
    evidence: list[Evidence]
    attrs: JSON = field(default_factory=dict)
    source: Source = "extracted"
    confidence: float = 1.0

    def to_dict(self) -> JSON:
        return {
            "id": self.id,
            "type": self.type,
            "label": self.label,
            "source": self.source,
            "confidence": self.confidence,
            "evidence": [e.to_dict() for e in self.evidence],
            "attrs": self.attrs,
        }

    @classmethod
    def from_dict(cls, d: JSON) -> Node:
        return cls(
            d["id"],
            d["type"],
            d["label"],
            [Evidence.from_dict(e) for e in d["evidence"]],
            d.get("attrs", {}),
            d["source"],
            d["confidence"],
        )

    def restamped(self, sha: str) -> Node:
        return replace(self, evidence=_restamp(self.evidence, sha))


@dataclass
class Edge:
    id: str
    type: str
    src: str
    dst: str
    evidence: list[Evidence]
    attrs: JSON = field(default_factory=dict)
    source: Source = "extracted"
    confidence: float = 1.0

    def to_dict(self) -> JSON:
        d: JSON = {
            "id": self.id,
            "type": self.type,
            "from": self.src,
            "to": self.dst,
            "source": self.source,
            "confidence": self.confidence,
            "evidence": [e.to_dict() for e in self.evidence],
        }
        if self.attrs:
            d["attrs"] = self.attrs
        return d

    @classmethod
    def from_dict(cls, d: JSON) -> Edge:
        return cls(
            d["id"],
            d["type"],
            d["from"],
            d["to"],
            [Evidence.from_dict(e) for e in d["evidence"]],
            d.get("attrs", {}),
            d["source"],
            d["confidence"],
        )

    def restamped(self, sha: str) -> Edge:
        return replace(self, evidence=_restamp(self.evidence, sha))


@dataclass
class Group:
    id: str
    label: str
    summary: str
    members: list[str]
    confidence: float

    def to_dict(self) -> JSON:
        return {
            "id": self.id,
            "label": self.label,
            "summary": self.summary,
            "members": self.members,
            "source": "inferred",
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, d: JSON) -> Group:
        return cls(d["id"], d["label"], d["summary"], d["members"], d["confidence"])


@dataclass
class Finding:
    id: str
    rule: str
    severity: Literal["info", "warning", "error"]
    message: str
    node_ids: list[str]
    evidence: list[Evidence]

    def to_dict(self) -> JSON:
        return {
            "id": self.id,
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
            "nodeIds": self.node_ids,
            "evidence": [e.to_dict() for e in self.evidence],
        }

    @classmethod
    def from_dict(cls, d: JSON) -> Finding:
        return cls(
            d["id"],
            d["rule"],
            d["severity"],
            d["message"],
            d["nodeIds"],
            [Evidence.from_dict(e) for e in d["evidence"]],
        )


@dataclass
class RepoInfo:
    host: Host
    name: str
    sha: str
    analyzed_at: str
    owner: str | None = None
    ref: str | None = None
    dirty: bool | None = None
    worktree_hash: str | None = None

    def to_dict(self) -> JSON:
        d: JSON = {"host": self.host, "name": self.name, "sha": self.sha}
        optional = {
            "owner": self.owner,
            "ref": self.ref,
            "dirty": self.dirty,
            "worktreeHash": self.worktree_hash,
        }
        d.update({k: v for k, v in optional.items() if v is not None})
        d["analyzedAt"] = self.analyzed_at
        return d

    @classmethod
    def from_dict(cls, d: JSON) -> RepoInfo:
        return cls(
            d["host"],
            d["name"],
            d["sha"],
            d["analyzedAt"],
            d.get("owner"),
            d.get("ref"),
            d.get("dirty"),
            d.get("worktreeHash"),
        )


@dataclass
class Graph:
    repo: RepoInfo
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    groups: list[Group] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    engine_version: str = ENGINE_VERSION
    schema_version: str = GRAPH_SCHEMA_VERSION
    stack: JSON | None = None

    def to_dict(self) -> JSON:
        d: JSON = {
            "schemaVersion": self.schema_version,
            "engineVersion": self.engine_version,
            "repo": self.repo.to_dict(),
        }
        if self.stack is not None:
            d["stack"] = self.stack
        d.update(
            nodes=[n.to_dict() for n in self.nodes],
            edges=[e.to_dict() for e in self.edges],
            groups=[g.to_dict() for g in self.groups],
            findings=[f.to_dict() for f in self.findings],
        )
        return d

    @classmethod
    def from_dict(cls, d: JSON) -> Graph:
        return cls(
            RepoInfo.from_dict(d["repo"]),
            [Node.from_dict(n) for n in d["nodes"]],
            [Edge.from_dict(e) for e in d["edges"]],
            [Group.from_dict(g) for g in d.get("groups", [])],
            [Finding.from_dict(f) for f in d.get("findings", [])],
            d["engineVersion"],
            d["schemaVersion"],
            d.get("stack"),
        )

    def check_integrity(self) -> list[str]:
        """Rules the JSON Schema can't express. Returns problems; empty means valid."""
        ids = [n.id for n in self.nodes]
        known = set(ids)
        problems = [f"duplicate node id {i}" for i in sorted(known) if ids.count(i) > 1]
        for e in self.edges:
            problems += [f"edge {e.id} -> missing {x}" for x in (e.src, e.dst) if x not in known]
        for g in self.groups:
            problems += [f"group {g.id} -> missing {m}" for m in g.members if m not in known]
        for f in self.findings:
            problems += [f"finding {f.id} -> missing {n}" for n in f.node_ids if n not in known]
        all_evidence = [ev for x in self.nodes for ev in x.evidence]
        all_evidence += [ev for x in self.edges for ev in x.evidence]
        all_evidence += [ev for x in self.findings for ev in x.evidence]
        problems += [
            f"bad line range {ev.ref}" for ev in all_evidence if ev.end_line < ev.start_line
        ]
        return problems


# --- CLI output -------------------------------------------------------------

_RENAME = {"node_ids": "nodeIds"}


@dataclass
class ResultItem:
    id: str | None = None
    type: str | None = None
    label: str | None = None
    depth: int | None = None
    via: str | None = None
    direction: Literal["in", "out"] | None = None
    op: str | None = None
    source: Source | None = None
    confidence: float | None = None
    rule: str | None = None
    severity: str | None = None
    message: str | None = None
    node_ids: list[str] | None = None
    routes: list[str] | None = None
    attrs: JSON | None = None
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> JSON:
        out: JSON = {}
        for key, value in vars(self).items():
            if value is None or (key == "evidence" and not value):
                continue
            out[_RENAME.get(key, key)] = value
        return out

    @classmethod
    def from_node(cls, node: Node, **extra: Any) -> ResultItem:
        return cls(
            id=node.id,
            type=node.type,
            label=node.label,
            source=node.source,
            confidence=node.confidence,
            evidence=[e.ref for e in node.evidence],
            **extra,
        )


@dataclass
class CommandResult:
    command: str
    exit_code: int
    summary: str
    results: list[ResultItem] = field(default_factory=list)
    total: int = 0
    truncated: bool = False
    repo: RepoInfo | None = None
    query: JSON | None = None
    stats: JSON | None = None
    error: str | None = None

    def to_dict(self) -> JSON:
        d: JSON = {
            "schemaVersion": CLI_SCHEMA_VERSION,
            "graphSchemaVersion": GRAPH_SCHEMA_VERSION,
            "tool": {"name": "evident", "version": __version__},
            "command": self.command,
            "exitCode": self.exit_code,
            "summary": self.summary,
        }
        if self.repo:
            d["repo"] = self.repo.to_dict()
        if self.query is not None:
            d["query"] = self.query
        d["total"] = self.total
        d["truncated"] = self.truncated
        d["results"] = [r.to_dict() for r in self.results]
        if self.stats is not None:
            d["stats"] = self.stats
        if self.error is not None:
            d["error"] = self.error
        return d
