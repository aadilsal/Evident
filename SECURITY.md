# Security policy

## Reporting a vulnerability

Please **don't open a public issue** for security problems. Report them privately through GitHub's [private vulnerability reporting](../../security/advisories/new) for this repository.

Include what you found, how to reproduce it, and the impact you expect. You'll get an acknowledgement within 72 hours and a status update within 7 days.

## In scope

- Code execution, sandbox escape or file access outside a job's temp directory in the analysis worker
- SSRF or fetching anything other than a public GitHub repo
- XSS or injection through repo-derived content (labels, paths, snippets, LLM summaries)
- Bypassing rate limits, size limits or the LLM spend cap
- Leaking our API keys or tokens

## Takedown requests

Maps are built from public repositories. If you own a repo and want its map removed, or a snippet shows something sensitive that you committed by mistake, open a private report as above with the repo URL. Removal is handled within 72 hours. (Also rotate the secret: it's already public in your git history.)

## Supported versions

Only the latest deployed version and the `main` branch receive fixes.

## How we design for this

See the [threat model](docs/security.md). The core rule: **Evident never executes the code it analyses.**
