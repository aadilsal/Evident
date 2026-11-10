# CLAUDE.md

@AGENTS.md

## Claude Code specifics

- The feature tracker `docs/internal/evident-features.md` (gitignored, with the design doc and case study in `docs/internal/`) is the **scope authority**: build what it says. `docs/PRD.md` and the ADRs must mirror it. When they disagree, update them (with an ADR for decision changes), not the tracker. v1.5/v2 features are out of scope unless the task says otherwise.
- Keep docs in sync as you build: in the same change, tick the tracker when work is verified, and update README's **Status** table, CHANGELOG `[Unreleased]`, and any PRD/architecture text the change affects.
- Before editing extractors, read the relevant ADR in `docs/adr/` and the counting rules in `docs/labelling-guide.md`. The engine must count things the same way the ground truth does.
- Cloned benchmark repos are untrusted input: read them, never run them.
- Run `pre-commit run --all-files` and the relevant tests before saying a task is done.
