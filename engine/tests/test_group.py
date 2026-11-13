"""LLM grouping: only existing node IDs survive, nothing but IDs/labels/paths is sent."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from jsonschema import Draft202012Validator

from evident.analyze import analyze
from evident.group import (
    GroqClient,
    LLMError,
    assign_groups,
    client_from_env,
    deterministic_groups,
    validate_groups,
)
from tests.graph_helpers import analyse_fixture


@dataclass
class FakeLLM:
    reply: str = ""
    error: bool = False
    prompts: list[str] = field(default_factory=list)

    def complete(self, system: str, user: str) -> str:
        self.prompts.append(user)
        if self.error:
            raise LLMError("HTTP 429")
        return self.reply


def test_validator_drops_unknown_ids_and_empty_groups(
    fixture_repo: Path, graph_validator: Draft202012Validator
) -> None:
    g = analyse_fixture(fixture_repo, graph_validator)
    reply = json.dumps(
        {
            "groups": [
                {
                    "label": "Billing",
                    "summary": "Invoices",
                    "members": ["model:Invoice", "model:Ghost"],
                },
                {"label": "Phantom", "members": ["route:GET /nope"]},
                {"label": "", "members": ["model:User"]},
                {
                    "label": "Users" * 20,
                    "summary": "x" * 999,
                    "members": ["model:User", "model:User"],
                },
                "not a group",
            ]
        }
    )
    groups = validate_groups(reply, g)
    assert [(x.id, x.members) for x in groups] == [
        ("group:billing", ["model:Invoice"]),
        ("group:" + "users" * 9 + "use", ["model:User"]),
    ]
    assert len(groups[1].label) == 60 and len(groups[1].summary) == 400
    assert validate_groups("not json", g) == [] and validate_groups("[]", g) == []


def test_prompt_holds_ids_labels_and_paths_only(
    fixture_repo: Path, graph_validator: Draft202012Validator
) -> None:
    g = analyse_fixture(fixture_repo, graph_validator)
    fake = FakeLLM(json.dumps({"groups": [{"label": "Users", "members": ["model:User"]}]}))
    assert assign_groups(g, fake, use_llm=True) == "used"
    lines = fake.prompts[0].splitlines()
    assert lines and all(len(ln.split("|")) == 4 for ln in lines)  # key|type|label|path only
    assert "findMany" not in fake.prompts[0], "source code must never reach the LLM"
    assert g.groups[0].id == "group:users"
    # Nodes from the same file as a member join its group (here: the schema file).
    assert "model:Invoice" in g.groups[0].members


def test_failures_fall_back_to_directory_groups(
    fixture_repo: Path, graph_validator: Draft202012Validator
) -> None:
    g = analyse_fixture(fixture_repo, graph_validator)
    assert assign_groups(g, FakeLLM(error=True), use_llm=True) == "unavailable"
    assert g.groups == deterministic_groups(g)
    assert assign_groups(g, FakeLLM("{}"), use_llm=True) == "unavailable"
    assert assign_groups(g, None, use_llm=True) == "unavailable"
    assert assign_groups(g, FakeLLM(error=True), use_llm=False) == "skipped"
    labels = {x.label for x in g.groups}
    assert {"Data model", "External services", "Configuration", "routes"} <= labels


def test_short_prompt_keys_map_back_to_ids(
    fixture_repo: Path, graph_validator: Draft202012Validator
) -> None:
    g = analyse_fixture(fixture_repo, graph_validator)
    groups = validate_groups(
        '{"groups": [{"label": "Data", "members": ["n1", "nX"]}]}', g, {"n1": "model:User"}
    )
    assert [x.members for x in groups] == [["model:User"]]


def test_analyze_records_groups_and_progress(fixture_repo: Path) -> None:
    fake = FakeLLM(
        json.dumps(
            {
                "groups": [
                    {"label": "Auth", "members": ["middleware:src/middleware/auth.ts#requireAuth"]}
                ]
            }
        )
    )
    stages: list[str] = []
    res = analyze(str(fixture_repo), llm=fake, progress=lambda s, _c: stages.append(s))
    assert res.llm == "used" and res.graph.groups[0].label == "Auth"
    members = [m for g in res.graph.groups for m in g.members]
    assert sorted(members) == sorted(n.id for n in res.graph.nodes), "every node, exactly once"
    assert stages == ["parse", "extract", "link", "analyse", "group", "done"]
    assert res.graph.check_integrity() == []


def test_client_reads_key_name_from_env_only() -> None:
    assert client_from_env({}) is None
    client = client_from_env({"GROQ_API_KEY": "k", "EVIDENT_LLM_MODEL": "qwen/x"})
    assert isinstance(client, GroqClient) and client.model == "qwen/x"


def test_cache_hit_regroups_with_the_llm_when_cache_has_directory_groups(
    fixture_repo: Path,
) -> None:
    """Regression: a --no-llm run cached directory groups, and a later LLM run reused them."""
    first = analyze(str(fixture_repo), use_llm=False)
    assert first.llm == "skipped"
    fake = FakeLLM(
        json.dumps(
            {
                "groups": [
                    {"label": "Auth", "members": ["middleware:src/middleware/auth.ts#requireAuth"]}
                ]
            }
        )
    )
    second = analyze(str(fixture_repo), llm=fake)
    assert second.cache_state == "hit" and second.parsed == 0
    assert second.llm == "used" and second.graph.groups[0].label == "Auth"
    # The LLM groups are cached too: the next run neither re-parses nor calls the LLM again.
    third = analyze(str(fixture_repo), llm=FakeLLM(error=True))
    assert third.graph.groups[0].label == "Auth" and third.llm == "skipped"
