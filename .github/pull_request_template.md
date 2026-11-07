## What and why

<!-- One or two sentences. Link the issue: Closes #123 -->

## Type

- [ ] feat
- [ ] fix
- [ ] refactor / perf
- [ ] docs / ADR
- [ ] build / ci / chore

## Checklist

- [ ] PR title follows Conventional Commits (`feat(engine): …`)
- [ ] Tests added or updated (fixture test for any extractor change or map bug)
- [ ] `pre-commit run --all-files`, mypy and tests pass locally
- [ ] Graph schema changed? `schemaVersion` bumped, examples and both sides updated
- [ ] Engine changed? Benchmark delta noted below
- [ ] UI changed? Follows `DESIGN.md`; screenshot attached
- [ ] Decision changed? New ADR added

## Benchmark delta (engine changes)

<!-- Paste the CI benchmark summary, or "n/a". Explain any intentional trade-off. -->
