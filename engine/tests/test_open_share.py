"""`evident open` (local viewer) and `evident share` (opt-in, metadata-only upload)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest

from evident import viewer
from evident.analyze import analyze
from evident.cli import main
from evident.models import Graph


@pytest.fixture
def fake_ui(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ui = tmp_path / "webui"
    (ui / "map").mkdir(parents=True)
    (ui / "index.html").write_text("<h1>home</h1>", encoding="utf-8")
    (ui / "map" / "index.html").write_text("<h1>map</h1>", encoding="utf-8")
    monkeypatch.setattr(viewer, "bundle", lambda: ui)
    return ui


@pytest.fixture
def served(fixture_repo: Path, fake_ui: Path) -> Iterator[tuple[viewer.Viewer, Graph]]:
    del fake_ui
    graph = analyze(str(fixture_repo), use_llm=False).graph
    server = viewer.start(graph, fixture_repo, 0)
    yield server, graph
    server.shutdown()
    server.server_close()


def _get(server: viewer.Viewer, path: str, host: str | None = None) -> tuple[int, bytes]:
    req = urllib.request.Request(f"http://127.0.0.1:{server.port}{path}")
    req.add_header("Host", host or f"127.0.0.1:{server.port}")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310 (localhost test server)
            return resp.status, resp.read()
    except urllib.error.HTTPError as err:
        return err.code, b""


def test_open_serves_the_ui_graph_and_cited_files_only(
    served: tuple[viewer.Viewer, Graph], fixture_repo: Path
) -> None:
    server, graph = served
    assert server.url.startswith("http://127.0.0.1:") and server.url.endswith("/map/?local=1")
    assert _get(server, "/map/?local=1") == (200, b"<h1>map</h1>")
    status, body = _get(server, "/local/graph.json")
    assert status == 200 and json.loads(body)["nodes"] == graph.to_dict()["nodes"]
    cited = graph.nodes[0].evidence[0].file
    status, body = _get(server, f"/local/file?path={cited}")
    assert status == 200 and body == (fixture_repo / cited).read_bytes()
    (fixture_repo / "secret.txt").write_text("not cited", encoding="utf-8")
    assert _get(server, "/local/file?path=secret.txt")[0] == 404
    assert _get(server, "/local/file?path=../../etc/passwd")[0] == 404
    assert _get(server, "/..%2f..%2fsecret.txt")[0] == 404


def test_open_rejects_foreign_host_headers(served: tuple[viewer.Viewer, Graph]) -> None:
    server, _ = served
    assert _get(server, "/local/graph.json", host="evil.example")[0] == 403


def test_open_refuses_symlinked_files(served: tuple[viewer.Viewer, Graph], tmp_path: Path) -> None:
    server, graph = served
    cited = graph.nodes[0].evidence[0].file
    target = server.root / cited  # type: ignore[operator]
    outside = tmp_path / "outside.ts"
    outside.write_text("outside", encoding="utf-8")
    target.unlink()
    try:
        target.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks need extra privileges on this OS")
    assert _get(server, f"/local/file?path={cited}")[0] == 404


def test_open_without_a_bundle_says_how_to_build_it(
    fixture_repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(viewer, "bundle", lambda: None)
    code = main(["open", "--repo", str(fixture_repo), "--no-llm", "--no-browser"])
    assert code == 3 and "npm run build:bundle" in capsys.readouterr().err


# --- share ------------------------------------------------------------------------------------


class FakeShareServer:
    """Routes httpx calls into the real FastAPI app, so the CLI and API are tested together."""

    def __init__(self) -> None:
        pytest.importorskip("fastapi")
        from fastapi.testclient import TestClient

        from evident.service.api import create_app
        from evident.service.broker import MemoryBroker
        from evident.service.config import Settings
        from evident.service.store import MemoryStore

        self.store = MemoryStore()
        settings = Settings(
            None, "redis://unused", 120, 5, 10, "salt", False, False, None, None,
            public_url="https://evident.example",
        )  # fmt: skip
        self.client = TestClient(create_app(self.store, MemoryBroker(), settings))

    def post(self, url: str, **kw: Any) -> httpx.Response:
        return self.client.post(url.split("example.test", 1)[1], **kw)  # type: ignore[no-any-return]

    def delete(self, url: str, **kw: Any) -> httpx.Response:
        return self.client.delete(url.split("example.test", 1)[1], **kw)  # type: ignore[no-any-return]


def test_share_needs_explicit_consent_and_a_server(
    fixture_repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("EVIDENT_API_URL", raising=False)
    assert main(["share", "--repo", str(fixture_repo), "--no-llm", "--yes"]) == 2
    assert "EVIDENT_API_URL" in capsys.readouterr().err
    monkeypatch.setenv("EVIDENT_API_URL", "https://example.test")
    assert main(["share", "--repo", str(fixture_repo), "--no-llm", "--json"]) == 2
    assert "--yes" in capsys.readouterr().out
    monkeypatch.setenv("EVIDENT_API_URL", "http://insecure.example")
    assert main(["share", "--repo", str(fixture_repo), "--no-llm", "--yes"]) == 2


def test_share_uploads_metadata_and_deletes_with_the_saved_token(
    fixture_repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeShareServer()
    monkeypatch.setattr(httpx, "post", fake.post)
    monkeypatch.setattr(httpx, "delete", fake.delete)
    monkeypatch.setenv("EVIDENT_API_URL", "https://example.test")
    code = main(["share", "--repo", str(fixture_repo), "--no-llm", "--yes", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0, out
    share_id = out["query"]["id"]
    assert out["query"]["url"] == f"https://evident.example/map/?share={share_id}"
    stored = fake.store.shares[share_id].graph
    # Metadata only: what was stored is exactly the graph, and it carries no file contents.
    source = (fixture_repo / "src" / "routes" / "invoices.ts").read_text(encoding="utf-8")
    assert source.splitlines()[0] not in json.dumps(stored)
    saved = json.loads((fixture_repo / ".evident" / "shares.json").read_text(encoding="utf-8"))
    assert share_id in saved
    assert main(["share", "--repo", str(fixture_repo), "--delete", share_id]) == 0
    assert share_id not in fake.store.shares
