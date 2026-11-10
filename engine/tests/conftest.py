from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schema"
FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))
    return data


@pytest.fixture(scope="session")
def graph_validator() -> Draft202012Validator:
    return Draft202012Validator(_load("graph.schema.json"), format_checker=FormatChecker())


@pytest.fixture(scope="session")
def cli_validator() -> Draft202012Validator:
    graph, cli = _load("graph.schema.json"), _load("cli-output.schema.json")
    registry = Registry().with_resources(
        [(s["$id"], Resource.from_contents(s)) for s in (graph, cli)]
    )
    return Draft202012Validator(cli, registry=registry, format_checker=FormatChecker())


@pytest.fixture(scope="session")
def example_graph() -> dict[str, Any]:
    return _load("examples/minimal.graph.json")


@pytest.fixture
def fixture_repo(tmp_path: Path) -> Path:
    """A private copy, so .evident/ never lands in the source tree."""
    dest = tmp_path / "express-prisma"
    shutil.copytree(FIXTURES / "express-prisma", dest)
    return dest


@pytest.fixture
def copy_fixture(tmp_path: Path) -> Callable[[str], Path]:
    def copy(name: str) -> Path:
        dest = tmp_path / name
        shutil.copytree(FIXTURES / name, dest)
        return dest

    return copy
