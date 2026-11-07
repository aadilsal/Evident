"""Resolve a target and fetch GitHub repos safely. Never runs repo code."""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from evident.models import AnalysisError

MAX_REPO_BYTES = 200 * 1024 * 1024
MAX_FILES = 10_000
MAX_FILE_BYTES = 1024 * 1024
CLONE_TIMEOUT_S = 120
GIT_TIMEOUT_S = 30

_GITHUB = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com/"
    r"(?P<owner>[A-Za-z0-9][A-Za-z0-9-]{0,38})/(?P<name>[A-Za-z0-9._-]{1,100}?)"
    r"(?:\.git)?(?:/tree/(?P<ref>[A-Za-z0-9._/-]{1,200}))?/?$"
)
# Ignore any hostile local git config: no hooks, no fsmonitor command, https only.
_SAFE_GIT = [
    "git",
    "-c", "core.hooksPath=/dev/null",
    "-c", "core.fsmonitor=false",
    "-c", "core.symlinks=false",
    "-c", "protocol.allow=never",
    "-c", "protocol.https.allow=always",
]  # fmt: skip
_GIT_ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_LFS_SKIP_SMUDGE": "1"}


@dataclass(frozen=True)
class GitHubRepo:
    owner: str
    name: str
    ref: str | None = None

    @property
    def clone_url(self) -> str:
        # Built from validated parts only; user input never reaches git directly.
        return f"https://github.com/{self.owner}/{self.name}.git"


def parse_github(target: str) -> GitHubRepo | None:
    m = _GITHUB.match(target.strip())
    if not m or ".." in (m["ref"] or ""):
        return None
    return GitHubRepo(m["owner"], m["name"], m["ref"])


def looks_like_url(target: str) -> bool:
    return "://" in target or target.startswith(("github.com/", "www."))


def _git(args: list[str], *, cwd: Path | None = None, timeout: int = GIT_TIMEOUT_S) -> str:
    try:
        proc = subprocess.run(
            [*_SAFE_GIT, *args],
            cwd=cwd,
            env=_GIT_ENV,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
        )
    except FileNotFoundError as exc:
        raise AnalysisError("git is not installed") from exc
    except subprocess.TimeoutExpired as exc:
        raise AnalysisError(f"git {args[0]} timed out after {timeout}s") from exc
    except subprocess.CalledProcessError as exc:
        raise AnalysisError(f"git {args[0]} failed: {exc.stderr.strip()[:300]}") from exc
    return proc.stdout


def local_head(root: Path) -> str | None:
    try:
        return _git(["rev-parse", "HEAD"], cwd=root).strip() or None
    except AnalysisError:
        return None


def local_dirty(root: Path) -> bool | None:
    try:
        out = _git(["status", "--porcelain", "--", ".", ":(exclude).evident"], cwd=root)
    except AnalysisError:
        return None
    return bool(out.strip())


def remote_head(repo: GitHubRepo) -> str:
    out = _git(["ls-remote", repo.clone_url, repo.ref or "HEAD"])
    for line in out.splitlines():
        sha, _, name = line.partition("\t")
        if repo.ref is None or name in (f"refs/heads/{repo.ref}", f"refs/tags/{repo.ref}"):
            return sha
    if repo.ref and re.fullmatch(r"[0-9a-f]{40}", repo.ref):
        return repo.ref
    raise AnalysisError(f"ref {repo.ref!r} not found in {repo.owner}/{repo.name}")


def check_size(repo: GitHubRepo) -> None:
    """Reject oversized or missing repos before cloning. Network errors are not fatal."""
    url = f"https://api.github.com/repos/{repo.owner}/{repo.name}"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            size_kb = int(json.load(resp).get("size", 0))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise AnalysisError(f"{repo.owner}/{repo.name} not found or private") from exc
        return
    except (urllib.error.URLError, TimeoutError, ValueError):
        return
    if size_kb * 1024 > MAX_REPO_BYTES:
        raise AnalysisError(f"repo is {size_kb // 1024} MB; limit is {MAX_REPO_BYTES >> 20} MB")


def shallow_clone(repo: GitHubRepo, dest: Path) -> None:
    args = ["clone", "--depth", "1", "--no-tags", "--single-branch"]
    if repo.ref and not re.fullmatch(r"[0-9a-f]{40}", repo.ref):
        args += ["--branch", repo.ref]
    _git([*args, "--", repo.clone_url, str(dest)], timeout=CLONE_TIMEOUT_S)
