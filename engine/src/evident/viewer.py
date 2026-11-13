"""`evident open`: the bundled map UI on localhost. Read-only; serves only the graph's own files.

The web app is a static export (web/, `npm run build:bundle`) shipped inside the package as
evident/webui. Two endpoints feed it: /local/graph.json and /local/file?path= for snippets.
"""

from __future__ import annotations

import json
import mimetypes
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from evident.models import Graph

MAX_FILE_BYTES = 1_000_000
# The UI loads only its own assets and this server; GitHub serves snippets for remote graphs.
CSP = (
    "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; font-src 'self' data:; worker-src 'self' blob:; "
    "connect-src 'self' https://raw.githubusercontent.com; frame-ancestors 'none'; base-uri 'none'"
)


def bundle() -> Traversable | None:
    ui = resources.files("evident").joinpath("webui")
    return ui if ui.joinpath("index.html").is_file() else None


def evidence_files(graph: Graph) -> set[str]:
    files = {ev.file for n in graph.nodes for ev in n.evidence}
    files |= {ev.file for e in graph.edges for ev in e.evidence}
    files |= {ev.file for f in graph.findings for ev in f.evidence}
    return files


def read_repo_file(root: Path | None, allowed: set[str], rel: str) -> bytes | None:
    """File bytes only if the graph cites the file and it resolves inside the repo (no symlinks)."""
    if root is None or rel not in allowed or rel.startswith("/") or "\\" in rel:
        return None
    path = root / rel
    try:
        if path.is_symlink() or any(p.is_symlink() for p in path.parents if p != root.parent):
            return None
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
            return None
        if resolved.stat().st_size > MAX_FILE_BYTES:
            return None
        return resolved.read_bytes()
    except OSError:
        return None


def _asset(ui: Traversable, url_path: str) -> tuple[bytes, str] | None:
    parts = [p for p in unquote(url_path).split("/") if p]
    if any(p in ("..", ".") or "\\" in p for p in parts):
        return None
    node = ui
    for p in parts:
        node = node.joinpath(p)
    if not node.is_file():
        node = node.joinpath("index.html")
        if not node.is_file():
            return None
    ctype = mimetypes.guess_type(node.name)[0] or "application/octet-stream"
    if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
        ctype += "; charset=utf-8"
    return node.read_bytes(), ctype


class Viewer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port: int, graph: Graph, root: Path | None, ui: Traversable) -> None:
        super().__init__(("127.0.0.1", port), _Handler)
        self.graph_json = json.dumps(graph.to_dict()).encode("utf-8")
        self.root = root
        self.allowed = evidence_files(graph)
        self.ui = ui
        self.hosts = {f"127.0.0.1:{self.port}", f"localhost:{self.port}"}

    @property
    def port(self) -> int:
        return int(self.server_address[1])

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/map/?local=1"


class _Handler(BaseHTTPRequestHandler):
    server: Viewer
    server_version = "evident"
    sys_version = ""

    def log_message(self, format: str, *args: object) -> None:
        del format, args  # quiet: the terminal shows only the URL

    def _send(self, status: HTTPStatus, body: bytes, ctype: str, cache: str = "no-store") -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", CSP)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _not_found(self) -> None:
        self._send(HTTPStatus.NOT_FOUND, b"not found", "text/plain; charset=utf-8")

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        # DNS rebinding: a hostile page can't reach us under its own hostname.
        if self.headers.get("Host", "") not in self.server.hosts:
            self._send(HTTPStatus.FORBIDDEN, b"forbidden", "text/plain; charset=utf-8")
            return
        url = urlsplit(self.path)
        if url.path == "/local/graph.json":
            self._send(HTTPStatus.OK, self.server.graph_json, "application/json; charset=utf-8")
            return
        if url.path == "/local/file":
            rel = parse_qs(url.query).get("path", [""])[0]
            data = read_repo_file(self.server.root, self.server.allowed, rel)
            if data is None:
                self._not_found()
                return
            self._send(HTTPStatus.OK, data, "text/plain; charset=utf-8")
            return
        found = _asset(self.server.ui, url.path)
        if found is None:
            self._not_found()
            return
        body, ctype = found
        immutable = "/_next/static/" in url.path
        self._send(
            HTTPStatus.OK,
            body,
            ctype,
            "public, max-age=31536000, immutable" if immutable else "no-cache",
        )


def start(graph: Graph, root: Path | None, port: int = 0) -> Viewer:
    """Bind and serve in a background thread; the caller owns shutdown."""
    ui = bundle()
    if ui is None:
        raise FileNotFoundError("map UI not bundled")
    server = Viewer(port, graph, root, ui)
    threading.Thread(target=server.serve_forever, name="evident-open", daemon=True).start()
    return server
