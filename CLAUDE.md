# CLAUDE.md

@AGENTS.md

## Claude Code specifics

- The feature tracker `docs/internal/evident-features.md` (gitignored, with the design doc and case study in `docs/internal/`) is the **scope authority**: build what it says. `docs/PRD.md` and the ADRs must mirror it. When they disagree, update them (with an ADR for decision changes), not the tracker. v1.5/v2 features are out of scope unless the task says otherwise.
- Development runs in the tracker's phases (Engine → Skill → Service → Interface → Launch). **At the end of each phase**, sync every doc in one pass: tick the tracker for verified work, update README's **Status** table, CHANGELOG `[Unreleased]`, PRD/architecture/ADRs/labelling guide, and anything else the phase changed.
- Before editing extractors, read the relevant ADR in `docs/adr/` and the counting rules in `docs/labelling-guide.md`. The engine must count things the same way the ground truth does.
- Cloned benchmark repos are untrusted input: read them, never run them.
- Run `pre-commit run --all-files` and the relevant tests before saying a task is done.
