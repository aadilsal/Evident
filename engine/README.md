# evident-map (engine + CLI)

Installed as `evident-map`; imports as `evident` and provides the `evident` command.

The analysis engine behind [Evident](https://github.com/aadilsal/Evident): a static, read-only extractor that turns a Next.js / Express / Prisma repo into an evidence-backed graph. The web app, the agent skill and the future MCP server all sit on top of this package.

```bash
pip install evident-map        # or, from a clone: pip install -e engine
evident analyze .            # build or refresh .evident/graph.json
evident trace "POST /api/users"
evident impact User.email
evident find --writes Invoice
evident health --severity warning
evident show model:User
```

Every command takes `--json` (the [CLI output schema](../schema/cli-output.schema.json)), `--limit`, `--depth`, `--no-llm` and `--repo PATH|URL`.

**Exit codes:** `0` ok · `1` findings or no match · `2` usage error · `3` analysis error.

**Safety:** never executes repo code, never follows symlinks, and writes only inside `.evident/`. See [docs/security.md](../docs/security.md).

## Development

```bash
cd engine
uv sync
uv run pytest && uv run mypy && uv run ruff check . && uv run ruff format --check .
```
