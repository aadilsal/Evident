# Threat model

Evident clones and analyses repositories **it did not write and must not trust**, then republishes facts about them on a public site. This page lists what we protect, what can go wrong, and the rules that prevent it.

## Assets

| Asset | Why it matters |
| --- | --- |
| The VM and its network | Compromise exposes everything, including the home network if self-hosted |
| LLM API key, GitHub token | Direct cost and abuse |
| Service availability | A dead recruiter link is the main business risk |
| Integrity of published maps | The product's whole claim is "every edge is proven" |
| LLM spend | Unbounded cost on a public demo |

## Trust boundaries

1. **Internet → Caddy/API:** untrusted users submit URLs.
2. **Worker → cloned repo:** file contents are hostile input (paths, sizes, encodings, text crafted for prompt injection).
3. **Worker → LLM:** responses are untrusted output.
4. **API → browser:** graph strings (labels, paths, snippets) originate in untrusted repos.

## Threats and controls

| # | Threat | Control |
| --- | --- | --- |
| T1 | **Code execution** via repo scripts, git hooks, postinstall, build configs | **Never execute repo code.** No `npm`/`npx`/`node`, no builds, no `import()` of repo files. Clone with `-c core.hooksPath=/dev/null`, `--no-recurse-submodules`, `GIT_LFS_SKIP_SMUDGE=1`. Parse with tree-sitter only. |
| T2 | **SSRF / arbitrary fetch** via crafted URLs | Accept only `https://github.com/<owner>/<repo>`, validated by regex, and rebuild the clone URL ourselves (never pass user input to git). Use the `protocol.allow=never` default, with only `https` allowed. Worker egress is limited to GitHub and the LLM API. |
| T3 | **Resource exhaustion**: huge repos, millions of files, giant or minified files, deep nesting | Shallow clone with a blob size filter. Check size via the GitHub API before cloning; cap at 200 MB / 10k files, 1 MB per parsed file. 120 s job timeout. Container CPU, memory and PID limits. One job per worker process. |
| T4 | **Path traversal / symlink escape** out of the temp dir | Don't follow symlinks; resolve every path and assert it stays under the job's temp root. Evidence paths are repo-relative POSIX, and the schema rejects `..`, absolute paths and backslashes. |
| T5 | **Leftover data** between jobs | Each job gets a fresh `mkdtemp` dir, removed in a `finally` block, plus a periodic sweeper for orphaned dirs older than 10 min. Use tmpfs where RAM allows. |
| T6 | **Prompt injection** from repo text (comments, names, README) steering the LLM | Send the LLM only node IDs, types, short labels and paths, never file contents. Validate the output strictly: unknown IDs are dropped, lengths capped, and the schema is enforced. LLM text is always shown as `inferred`. |
| T7 | **XSS** via labels, paths, snippets or LLM summaries | Render everything as text; no `dangerouslySetInnerHTML`. Shiki output only from escaped source. Strict CSP. |
| T8 | **Publishing secrets** found in repos | Env var **names** only; values are never read or stored. Snippets come from public repos, but a takedown path exists ([SECURITY.md](../SECURITY.md)) along with a per-repo delete. |
| T9 | **Abuse / cost blow-up**: scripted submissions, LLM spend | Per-IP rate limit in Redis, global concurrent-job cap, cache by commit SHA, cheap model for grouping, monthly spend cap with hard stop, gallery precomputed. |
| T10 | **Secret leakage** from our own infra | Keys only in the worker's env, never in graphs, logs or the frontend bundle. `.env` git-ignored, gitleaks in pre-commit, least-privilege fine-grained GitHub token (public read only). |
| T11 | **Container escape / lateral movement** | Worker runs as non-root with a read-only root filesystem, `no-new-privileges` and all capabilities dropped, on its own network. Postgres and Redis are not exposed outside the Compose network. |
| T12 | **Supply chain** in our own dependencies | Lockfiles committed, Dependabot, CI on pinned action SHAs, minimal dependencies. |

## Rules (the short version)

1. Never execute repo code.
2. Only `https://github.com/owner/repo`; we build the clone URL.
3. Size, file-count, per-file and time limits on every job.
4. Fresh temp dir per job, wiped in `finally`; sweeper as backup.
5. LLM sees IDs and labels only, and its output is validated against existing IDs.
6. Everything from a repo is rendered as text.
7. Env var names, never values.
8. Rate limits per IP and a hard LLM spend cap.

## Out of scope (v1)

Private repos and OAuth tokens, multi-tenant accounts, and malicious tree-sitter grammar bugs (we track upstream releases).
