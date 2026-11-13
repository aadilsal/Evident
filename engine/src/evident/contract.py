"""The graph JSON Schema: the contract between engine and web.

schema/graph.schema.json is the source of truth. The package carries a byte-identical copy
(evident/graph.schema.json) so wheels and containers can validate shares offline;
tests/test_web_contract.py fails if the two ever differ.
"""

from __future__ import annotations

import json
from functools import cache
from importlib import resources
from typing import Any

SCHEMA_FILE = "graph.schema.json"


@cache
def graph_schema() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        resources.files("evident").joinpath(SCHEMA_FILE).read_text(encoding="utf-8")
    )
    return data


def schema_errors(data: Any, limit: int = 5) -> list[str]:
    """Up to `limit` validation errors, as 'path: message'. Needs the [service] extra."""
    from jsonschema import Draft202012Validator

    validator = Draft202012Validator(graph_schema())
    errors = []
    for err in validator.iter_errors(data):
        errors.append(f"{'/'.join(str(p) for p in err.path) or '(root)'}: {err.message[:200]}")
        if len(errors) >= limit:
            break
    return errors
