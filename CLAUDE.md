# CLAUDE.md

@AGENTS.md

## Claude Code specifics

- Treat `docs/design-doc.md` as the source of truth for scope. v1.5/v2 features are out of scope unless the task says otherwise.
- Before editing extractors, read the relevant ADR in `docs/adr/` and the counting rules in `docs/labelling-guide.md`. The engine must count things the same way the ground truth does.
- Cloned benchmark repos are untrusted input: read them, never run them.
- Run `pre-commit run --all-files` and the relevant tests before saying a task is done.
