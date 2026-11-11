"""Run skill-tasks/tasks.yaml with and without the Evident skill and grade the answers.

Each run copies a fixture to a fresh temp dir, optionally installs the skill under
`.claude/skills/evident`, and calls `claude -p` isolated from user settings, plugins and MCP
servers. Tools are limited to `evident`, read-only shell commands and file reads, so fixture
code is never executed.

    uv run --project engine python skill-tasks/run.py [--model haiku] [--task ID] [--repeat N]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "engine" / "tests" / "fixtures"
SKILL = ROOT / "skills" / "evident"
OUT = ROOT / "skill-tasks" / "results"
TOOLS = [
    "Bash(evident:*)",
    "Bash(ls:*)",
    "Bash(cat:*)",
    "Bash(grep:*)",
    "Bash(find:*)",
    "Read",
    "Grep",
    "Glob",
]
CONDITIONS = ("with-skill", "without-skill")


def _bin_dir() -> Path:
    venv = ROOT / "engine" / ".venv"
    return venv / ("Scripts" if os.name == "nt" else "bin")


def grade(answer: str, task: dict[str, Any]) -> dict[str, Any]:
    def hit(pattern: str) -> bool:
        if pattern.startswith("re:"):
            return re.search(pattern[3:], answer, re.I | re.S) is not None
        return pattern.lower() in answer.lower()

    expected = task.get("expect", [])
    missing = [p for p in expected if not hit(p)]
    forbidden = [p for p in task.get("forbid", []) if hit(p)]
    score = (len(expected) - len(missing)) / len(expected) if expected else 1.0
    return {
        "score": round(score, 3),
        "pass": not missing and not forbidden,
        "missing": missing,
        "forbidden": forbidden,
    }


def run_one(task: dict[str, Any], condition: str, model: str, suffix: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="evident-task-") as tmp:
        repo = Path(tmp) / task["fixture"]
        shutil.copytree(FIXTURES / task["fixture"], repo)
        if condition == "with-skill":
            shutil.copytree(SKILL, repo / ".claude" / "skills" / "evident")
        mcp = Path(tmp) / "mcp.json"
        mcp.write_text('{"mcpServers": {}}', encoding="utf-8")
        env = {**os.environ, "PATH": f"{_bin_dir()}{os.pathsep}{os.environ.get('PATH', '')}"}
        cmd = [
            shutil.which("claude") or "claude",
            "-p",
            f"{task['prompt']} {suffix}",
            "--model",
            model,
            "--setting-sources",
            "project",
            "--strict-mcp-config",
            "--mcp-config",
            str(mcp),
            "--output-format",
            "stream-json",
            "--verbose",
            "--no-session-persistence",
            "--allowedTools",
            *TOOLS,
        ]
        started = time.perf_counter()
        try:
            proc = subprocess.run(  # noqa: S603 - fixed argv, our own CLI
                cmd, cwd=repo, env=env, capture_output=True, text=True, timeout=420,
                encoding="utf-8", errors="replace",
            )
            data, calls = _parse_stream(proc.stdout)
        except subprocess.TimeoutExpired:
            data, calls = {"result": "", "error": "timeout"}, []
        seconds = time.perf_counter() - started
    answer = str(data.get("result") or "")
    return {
        "task": task["id"],
        "condition": condition,
        "seconds": round(seconds, 1),
        "turns": data.get("num_turns"),
        "costUsd": round(float(data.get("total_cost_usd") or 0), 4),
        "toolCalls": len(calls),
        "usedEvident": any(c.startswith("evident") for c in calls),
        "commands": calls,
        **grade(answer, task),
        "answer": answer,
    }


def _parse_stream(stdout: str) -> tuple[dict[str, Any], list[str]]:
    """Final result event plus the Bash commands / tool names the agent used."""
    result: dict[str, Any] = {}
    calls: list[str] = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "result":
            result = event
        elif event.get("type") == "assistant":
            for block in event.get("message", {}).get("content", []):
                if block.get("type") == "tool_use":
                    command = block.get("input", {}).get("command")
                    calls.append(str(command).strip() if command else str(block.get("name")))
    return result, calls


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for cond in CONDITIONS:
        sub = [r for r in rows if r["condition"] == cond]
        if not sub:
            continue
        out[cond] = {
            "runs": len(sub),
            "passed": sum(r["pass"] for r in sub),
            "meanScore": round(sum(r["score"] for r in sub) / len(sub), 3),
            "meanTurns": round(sum(r["turns"] or 0 for r in sub) / len(sub), 1),
            "meanToolCalls": round(sum(r["toolCalls"] for r in sub) / len(sub), 1),
            "usedEvident": sum(r["usedEvident"] for r in sub),
            "meanSeconds": round(sum(r["seconds"] for r in sub) / len(sub), 1),
            "totalCostUsd": round(sum(r["costUsd"] for r in sub), 4),
        }
    return out


def markdown(meta: dict[str, Any], summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Skill-task evals",
        "",
        f"Model `{meta['model']}`, {meta['date']}, {meta['repeat']} run(s) per task and condition. "
        "Graded by `skill-tasks/run.py` against `skill-tasks/tasks.yaml`.",
        "",
        "| Condition | Passed | Mean score | Mean tool calls | Used evident | Mean seconds | Cost (USD) |",
        "| --- | --: | --: | --: | --: | --: | --: |",
    ]
    for cond, s in summary.items():
        lines.append(
            f"| {cond} | {s['passed']}/{s['runs']} | {s['meanScore']:.0%} | {s['meanToolCalls']} | "
            f"{s['usedEvident']}/{s['runs']} | {s['meanSeconds']} | {s['totalCostUsd']:.2f} |"
        )
    lines += ["", "| Task | With skill | Without skill |", "| --- | --- | --- |"]
    for task in dict.fromkeys(r["task"] for r in rows):
        cells = []
        for cond in CONDITIONS:
            sub = [r for r in rows if r["task"] == task and r["condition"] == cond]
            if not sub:
                cells.append("-")
                continue
            passed = sum(r["pass"] for r in sub)
            missing = sorted({m for r in sub for m in r["missing"]})
            note = f" (missing {', '.join(f'`{m}`' for m in missing)})" if missing else ""
            cells.append(f"{passed}/{len(sub)}{note}")
        lines.append(f"| {task} | {cells[0]} | {cells[1]} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="haiku")
    ap.add_argument("--task", action="append", help="only this task id (repeatable)")
    ap.add_argument("--repeat", type=int, default=1)
    args = ap.parse_args()
    spec = yaml.safe_load((ROOT / "skill-tasks" / "tasks.yaml").read_text(encoding="utf-8"))
    tasks = [t for t in spec["tasks"] if not args.task or t["id"] in args.task]
    rows = []
    for task in tasks:
        for _ in range(args.repeat):
            for cond in CONDITIONS:
                row = run_one(task, cond, args.model, spec.get("suffix", ""))
                rows.append(row)
                status = "PASS" if row["pass"] else f"FAIL missing={row['missing']}"
                print(f"{task['id']:<24} {cond:<14} {status} tools={row['toolCalls']} "
                      f"evident={row['usedEvident']} "
                      f"${row['costUsd']}", file=sys.stderr, flush=True)
    meta = {
        "model": args.model,
        "date": datetime.now(UTC).strftime("%Y-%m-%d"),
        "repeat": args.repeat,
    }
    summary = summarise(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "latest.json").write_text(
        json.dumps({"meta": meta, "summary": summary, "runs": rows}, indent=1) + "\n",
        encoding="utf-8",
    )
    (OUT / "latest.md").write_text(markdown(meta, summary, rows), encoding="utf-8")
    print(markdown(meta, summary, rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
