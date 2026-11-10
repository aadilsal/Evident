"""Parse manifests and config as data. Never runs scripts; env files yield names only."""

from __future__ import annotations

import json
import re
from typing import Any

JSON = dict[str, Any]
_ENV_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")
_PY_REQ = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def _strip_jsonc(text: str) -> str:
    """Drop // and /* */ comments and trailing commas, leaving strings intact."""
    out, i, n, in_str = [], 0, len(text), False
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
            out.append(ch)
        elif text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
            continue
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end == -1 else end + 2
            continue
        else:
            out.append(ch)
        i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def _load(text: str, jsonc: bool = False) -> Any:
    try:
        return json.loads(_strip_jsonc(text) if jsonc else text)
    except ValueError:
        return None


def package_json(text: str) -> JSON:
    """Name, dependency names and workspace globs. Scripts are deliberately ignored."""
    data = _load(text)
    if not isinstance(data, dict):
        return {"error": "unparseable package.json"}
    deps: set[str] = set()
    for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        section = data.get(key)
        if isinstance(section, dict):
            deps.update(str(k) for k in section)
    ws = data.get("workspaces")
    if isinstance(ws, dict):
        ws = ws.get("packages")
    out: JSON = {"deps": sorted(deps)}
    if isinstance(data.get("name"), str):
        out["name"] = data["name"]
    if isinstance(ws, list):
        out["workspaces"] = [w for w in ws if isinstance(w, str)]
    for key in ("main", "module", "types"):
        if isinstance(data.get(key), str):
            out[key] = data[key]
    return out


def tsconfig(text: str) -> JSON:
    data = _load(text, jsonc=True)
    if not isinstance(data, dict):
        return {"error": "unparseable tsconfig"}
    raw_opts = data.get("compilerOptions")
    opts: JSON = raw_opts if isinstance(raw_opts, dict) else {}
    out: JSON = {}
    if isinstance(opts.get("baseUrl"), str):
        out["baseUrl"] = opts["baseUrl"]
    paths = opts.get("paths")
    if isinstance(paths, dict):
        out["paths"] = {
            str(k): [t for t in v if isinstance(t, str)]
            for k, v in paths.items()
            if isinstance(v, list)
        }
    if isinstance(data.get("extends"), str):
        out["extends"] = data["extends"]
    return out


def env_names(text: str) -> list[str]:
    """Names declared in an example env file. Values are never kept."""
    return sorted({m.group(1) for ln in text.splitlines() if (m := _ENV_LINE.match(ln))})


def pnpm_workspace(text: str) -> list[str]:
    """`packages:` globs from pnpm-workspace.yaml (a tiny, safe subset of YAML)."""
    out, in_packages = [], False
    for raw in text.splitlines():
        ln = raw.split("#", 1)[0].rstrip()
        if not ln.strip():
            continue
        if not raw.startswith((" ", "\t", "-")):
            in_packages = ln.strip() == "packages:"
            continue
        item = ln.strip()
        if in_packages and item.startswith("-"):
            out.append(item[1:].strip().strip("'\""))
    return out


def python_deps(name: str, text: str) -> list[str]:
    """Distribution names from requirements*.txt or pyproject.toml, lower-cased."""
    names: set[str] = set()
    if name.endswith(".txt"):
        for ln in text.splitlines():
            ln = ln.split("#", 1)[0].strip()
            if ln and not ln.startswith("-") and (m := _PY_REQ.match(ln)):
                names.add(m.group(1).lower())
    else:
        for m in re.finditer(
            r"[\"']([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*[<>=~!;\"']", text
        ):
            names.add(m.group(1).lower())
        for m in re.finditer(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*=", text, re.M):
            names.add(m.group(1).lower())
    return sorted(names)
