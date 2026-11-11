"""The Claude skill must stay in sync with the CLI it drives."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from evident.cli import COMMANDS

SKILL = Path(__file__).resolve().parents[2] / "skills" / "evident"
# Mentioned only conditionally ("if `evident --help` lists `open`", "never run `share`").
NOT_YET = {"open", "share"}


def _skill() -> tuple[dict[str, str], str]:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    _, front, body = text.split("---", 2)
    meta: dict[str, str] = yaml.safe_load(front)
    return meta, body


def test_frontmatter_names_the_skill_and_says_when_to_use_it() -> None:
    meta, _ = _skill()
    assert meta["name"] == "evident"
    assert "Use when" in meta["description"] and "BEFORE editing" in meta["description"]
    assert len(meta["description"]) <= 1024


def test_every_command_the_skill_runs_exists() -> None:
    _, body = _skill()
    used = set(re.findall(r"`evident ([a-z]+)", body))
    assert {"analyze", "impact", "trace", "health", "find", "show", "export"} <= used
    assert used - NOT_YET <= set(COMMANDS), used - NOT_YET - set(COMMANDS)


def test_skill_ships_installers_and_never_shares_unprompted() -> None:
    _, body = _skill()
    assert (SKILL / "scripts" / "ensure_installed.sh").is_file()
    assert (SKILL / "scripts" / "ensure_installed.ps1").is_file()
    assert "Never run `evident share`" in body
    assert "--no-llm" in body
