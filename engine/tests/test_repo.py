from __future__ import annotations

from pathlib import Path

import pytest

from evident.repo import GitHubRepo, local_dirty, local_head, parse_github


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://github.com/calcom/cal.com", GitHubRepo("calcom", "cal.com")),
        ("github.com/vercel/next.js.git", GitHubRepo("vercel", "next.js")),
        ("https://github.com/a/b/tree/feat/x", GitHubRepo("a", "b", "feat/x")),
        ("https://www.github.com/a/b/", GitHubRepo("a", "b")),
    ],
)
def test_parse_github_accepts(url: str, expected: GitHubRepo) -> None:
    assert parse_github(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://gitlab.com/a/b",
        "https://github.com/a",
        "https://github.com/a/b/tree/../../etc",
        "https://github.com/a/b;rm -rf /",
        "ssh://git@github.com/a/b",
        "file:///etc/passwd",
        "https://github.com.evil.com/a/b",
    ],
)
def test_parse_github_rejects(url: str) -> None:
    assert parse_github(url) is None


def test_clone_url_is_rebuilt_from_parts() -> None:
    repo = parse_github("github.com/a-b/c.d")
    assert repo is not None
    assert repo.clone_url == "https://github.com/a-b/c.d.git"


def test_local_head_and_dirty_handle_a_missing_folder(tmp_path: Path) -> None:
    """Regression: a missing clone folder raised NotADirectoryError on Windows (bench crash)."""
    missing = tmp_path / "not-cloned-yet"
    assert local_head(missing) is None
    assert local_dirty(missing) is None
    a_file = tmp_path / "file.txt"
    a_file.write_text("x", encoding="utf-8")
    assert local_head(a_file) is None
