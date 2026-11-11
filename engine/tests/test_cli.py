from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from evident.cli import build_parser, main

COMMANDS = ["analyze", "trace", "impact", "find", "health", "show", "export"]
QUERIES = [
    ["trace", "POST /api/users"],
    ["impact", "User.email"],
    ["find", "--writes", "Invoice"],
    ["health"],
    ["show", "model:User"],
    ["export", "--format", "md"],
]


def run_json(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, dict[str, Any]]:
    code = main([*argv, "--json"])
    out: dict[str, Any] = json.loads(capsys.readouterr().out)
    return code, out


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file() and ".evident" not in p.parts
    }


def test_help_lists_every_command(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert all(c in out for c in COMMANDS)


@pytest.mark.parametrize("argv", [["analyze"], *QUERIES])
def test_every_command_emits_schema_valid_json(
    argv: list[str],
    fixture_repo: Path,
    capsys: pytest.CaptureFixture[str],
    cli_validator: Draft202012Validator,
) -> None:
    repo_args = [str(fixture_repo)] if argv == ["analyze"] else ["--repo", str(fixture_repo)]
    code, out = run_json(capsys, *argv, *repo_args)
    errors = [e.message for e in cli_validator.iter_errors(out)]
    assert not errors, errors
    assert out["command"] == argv[0]
    assert out["exitCode"] == code
    assert code == (1 if argv == ["health"] else 0)  # health exits 1 when it has findings
    assert out["repo"]["host"] == "local"


def test_analyze_writes_valid_graph_and_nothing_else(
    fixture_repo: Path, capsys: pytest.CaptureFixture[str], graph_validator: Draft202012Validator
) -> None:
    before = snapshot(fixture_repo)
    code, out = run_json(capsys, "analyze", str(fixture_repo))
    assert code == 0
    assert snapshot(fixture_repo) == before, "analysis must be read-only outside .evident/"
    graph = json.loads((fixture_repo / ".evident" / "graph.json").read_text(encoding="utf-8"))
    assert not [e.message for e in graph_validator.iter_errors(graph)]
    assert (fixture_repo / ".evident" / ".gitignore").read_text() == "*\n"
    assert out["stats"]["files"] == 9


def test_incremental_cache(fixture_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _, first = run_json(capsys, "analyze", str(fixture_repo))
    _, second = run_json(capsys, "analyze", str(fixture_repo))
    assert first["stats"]["cache"] == "miss"
    assert second["stats"]["cache"] == "hit"
    assert second["stats"]["parsed"] == 0

    users = fixture_repo / "src" / "routes" / "users.ts"
    users.write_text(users.read_text(encoding="utf-8") + "\n// changed\n", encoding="utf-8")
    _, third = run_json(capsys, "analyze", str(fixture_repo))
    assert third["stats"]["cache"] == "partial"
    assert third["stats"]["parsed"] == 1
    assert third["repo"]["worktreeHash"] != second["repo"]["worktreeHash"]


def test_missing_path_is_analysis_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], cli_validator: Draft202012Validator
) -> None:
    code, out = run_json(capsys, "analyze", str(tmp_path / "nope"))
    assert code == 3
    assert "error" in out
    assert not list(cli_validator.iter_errors(out))


def test_non_github_url_rejected(capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run_json(capsys, "analyze", "https://gitlab.com/a/b")
    assert code == 3
    assert "github.com" in out["error"]


def test_bad_trace_query_is_usage_error(
    fixture_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out = run_json(capsys, "trace", "users", "--repo", str(fixture_repo))
    assert code == 2
    assert out["exitCode"] == 2


def test_argparse_usage_error_exits_2() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["find", "--reads", "A", "--writes", "B"])
    assert exc.value.code == 2


def test_human_output_is_summary_first(
    fixture_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["analyze", str(fixture_repo), "--no-llm"]) == 0
    first_line = capsys.readouterr().out.splitlines()[0]
    assert first_line.startswith("Analysed 9 files")


def test_analyze_is_summary_first(fixture_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _, out = run_json(capsys, "analyze", str(fixture_repo), "--limit", "3")
    types = [r.get("type") or r.get("rule") for r in out["results"]]
    assert types[:3] == ["route", "route", "route"]
    assert "unguarded-write" in types and "model" in types and "service" in types
    assert out["truncated"] is True
    assert all(r["evidence"] for r in out["results"])


def test_export_markdown_cites_code_and_writes_only_where_asked(
    fixture_repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "out" / "architecture.md"
    before = snapshot(fixture_repo)
    code = main(["export", "--repo", str(fixture_repo), "--format", "md", "--out", str(target)])
    assert code == 0
    assert snapshot(fixture_repo) == before
    md = target.read_text(encoding="utf-8")
    for section in ("# Architecture:", "## Routes", "## Data model", "## Health findings"):
        assert section in md
    assert "| `POST /api/users` | api | users.ts:17 handler | - | User (write) |" in md
    assert "`src/routes/users.ts:17-20`" in md
    assert "Wrote md export" in capsys.readouterr().out


def test_export_json_is_the_graph(
    fixture_repo: Path, capsys: pytest.CaptureFixture[str], graph_validator: Draft202012Validator
) -> None:
    assert main(["export", "--repo", str(fixture_repo), "--format", "json"]) == 0
    graph = json.loads(capsys.readouterr().out)
    assert not [e.message for e in graph_validator.iter_errors(graph)]
