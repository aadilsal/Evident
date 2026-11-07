from __future__ import annotations

import pytest

from evident.repo import GitHubRepo, parse_github


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
