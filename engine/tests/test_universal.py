"""Universal layer: module summaries, manifests, Prisma schema parsing, stack fallback."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from evident.adapters.prisma import parse_schema
from evident.syntax import parse
from evident.universal import manifests
from evident.universal.js import summarise
from tests.graph_helpers import analyse_fixture, node_ids


def _summary(rel: str, src: str) -> dict[str, Any]:
    tree = parse(rel, src)
    assert tree is not None
    return summarise(tree)[0]


def test_esm_imports_exports_and_scopes() -> None:
    s = _summary(
        "a.ts",
        "import d, { x as y } from './m';\n"
        "import * as ns from 'pkg';\n"
        "import type { T } from './types';\n"
        "export { y as z };\n"
        "export * from './more';\n"
        "export default function Page() { return ns.go(); }\n"
        "export const handler = withAuth(async () => d());\n",
    )
    assert [
        (i["spec"], i.get("default"), i.get("namespace"), i["names"]) for i in s["imports"]
    ] == [
        ("./m", "d", None, [["x", "y"]]),
        ("pkg", None, "ns", []),
    ]
    assert s["exports"] == {"z": "y", "default": "Page", "handler": "handler"}
    assert s["reexports"] == [{"spec": "./more", "line": 5, "names": [], "star": True}]
    scopes = s["scopes"]
    assert set(scopes) == {"<module>", "Page", "L7"}
    assert s["vars"]["handler"]["callee"] == ["withAuth"]
    assert s["vars"]["handler"]["fns"] == ["L7"]


def test_commonjs_and_env_reads() -> None:
    s = _summary(
        "a.js",
        "const db = require('./db');\n"
        "const { a, b: c } = require('./x');\n"
        "const { SECRET } = process.env;\n"
        "function f() { return process.env.TOKEN + process.env['OTHER']; }\n"
        "module.exports = { f };\n",
    )
    imports = {i["spec"]: i for i in s["imports"]}
    assert imports["./db"]["default"] == "db" and imports["./db"]["cjs"] is True
    assert imports["./x"]["names"] == [["a", "a"], ["b", "c"]]
    assert s["exports"] == {"f": "f", "default": "default"}
    assert s["scopes"]["f"]["env"] == [["TOKEN", 4], ["OTHER", 4]]
    assert s["scopes"]["<module>"]["env"] == [["SECRET", 3]]


def test_manifests_ignore_scripts_and_values() -> None:
    pkg = manifests.package_json(
        '{"name": "a", "scripts": {"postinstall": "rm -rf /"}, "dependencies": {"next": "1"}}'
    )
    assert pkg == {"deps": ["next"], "name": "a"}
    assert manifests.tsconfig('{ // c\n "compilerOptions": {"paths": {"@/*": ["./src/*"]},},}') == {
        "paths": {"@/*": ["./src/*"]}
    }
    assert manifests.env_names("A=secret\n# B=x\nexport C=\n") == ["A", "C"]
    assert manifests.python_deps("requirements.txt", "Django>=4\n# x\nfastapi[all]\n-e .\n") == [
        "django",
        "fastapi",
    ]
    assert manifests.pnpm_workspace("packages:\n  - 'apps/*'\n  - packages/*\n") == [
        "apps/*",
        "packages/*",
    ]


def test_prisma_schema_parser() -> None:
    parsed = parse_schema(
        'datasource db {\n  url = env("DATABASE_URL")\n}\n'
        "model Post {\n"
        "  id     Int     @id\n"
        "  tags   Tag[]\n"
        "  author User?   @relation(fields: [aid], references: [id])\n"
        '  @@map("posts")\n'
        "}\n"
        "enum Role { A B }\n"
    )
    assert parsed["env"] == [["DATABASE_URL", 2]]
    (post,) = parsed["models"]
    assert (post["name"], post["line"], post["end"], post["map"]) == ("Post", 4, 9, "posts")
    assert post["fields"] == [
        {"name": "id", "type": "Int", "line": 5, "id": True},
        {"name": "tags", "type": "Tag", "line": 6, "list": True},
        {"name": "author", "type": "User", "line": 7, "optional": True, "relation": True},
    ]


def test_unsupported_stack_falls_back_to_universal_map(
    copy_fixture: Callable[[str], Path], graph_validator: Draft202012Validator
) -> None:
    g = analyse_fixture(copy_fixture("nest-only"), graph_validator)
    assert g.stack is not None
    assert g.stack["unsupported"] == ["NestJS"]
    assert g.stack["message"].startswith("Routes and models aren't supported for NestJS yet")
    assert node_ids(g, "route") == set()
    assert node_ids(g, "service") == {"service:stripe"}
    assert node_ids(g, "module") == {"module:src/main.ts"}
