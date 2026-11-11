# Schemas

The contracts every Evident front-end (web app, CLI and agent skill, future MCP server) shares.

| File | What it describes |
| --- | --- |
| [graph.schema.json](graph.schema.json) | The full architecture graph for one analysed commit: nodes, edges, groups, findings, each with evidence |
| [cli-output.schema.json](cli-output.schema.json) | The envelope printed by every `evident <command> --json` |
| [examples/](examples/) | Valid documents, checked in pre-commit and CI |

## Versioning

Both schemas carry a semver `schemaVersion`.

- **Minor** (`1.0 → 1.1`): additive only (new optional fields, new enum values the reader can ignore). Old readers keep working.
- **Major** (`1.x → 2.0`): breaking. Engine, web and skill must update in the same PR.

**CLI 1.2.0** (additive): the `export` command.

**1.1.0** (additive): `container` nodes (`containerAttrs`), a top-level `stack` object, `action:<file>#<export>` paths for server actions, `nestjs`/`fastify` frameworks, model `orm`, function `checksAuth`/`bodyLine`/`validatesBody`, middleware `checksAuth`; CLI `stats.stack`.

The engine's `ENGINE_VERSION` is separate. It bumps whenever extraction output can change, and it's part of the cache key.

## What the schema doesn't check

The engine validator enforces these:
- Every edge endpoint, group member and finding `nodeId` exists in `nodes`
- `endLine >= startLine`
- Node IDs are unique
