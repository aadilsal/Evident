# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Project documentation: PRD, architecture, threat model, ADRs 0001–0004, benchmark labelling guide, DESIGN.md
- Graph JSON Schema `1.0.0` with a validated example; CLI output schema `1.0.0`; `local` host for folders
- `evident-map` package (imports as `evident`): `analyze`, `trace`, `impact`, `find`, `health`, `show` with `--json`, exit codes 0–3, an incremental `.evident/` cache, a safe GitHub shallow clone and four health rules. Extractors are stubs; graphs are empty until adapters land
- Repo standards: ruff and mypy config, Prettier, EditorConfig, Conventional Commits, issue and PR templates
- ADR 0005 (CLI-first, three front-ends), ADR 0006 (adapter architecture, wider v1 scope), ADR 0007 (Groq for grouping)
- `benchmark/repos.yaml` with pinned candidate repos and a ground-truth template; share-data and local-mode rules in `docs/security.md`

### Changed

- PRD, architecture, README and labelling guide now match the feature tracker's v1 scope: JS/TS + Python adapters, CLI, Claude skill

### Not yet added

- `.pre-commit-config.yaml`, ESLint config and the CI workflow (listed in AGENTS.md, still to do)
