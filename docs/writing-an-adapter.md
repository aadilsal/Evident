# Writing an adapter

An adapter teaches Evident one framework (routes, middleware, handlers) or one ORM (models, reads, writes). This page is the template: what an adapter is, how it plugs in, and the checklist it must pass before it ships. Background: [ADR-0006](adr/0006-adapter-architecture.md); counting rules: [labelling-guide.md](labelling-guide.md).

## How analysis flows

```
every file ──tree-sitter──▶ per-file summary (cached)       engine/src/evident/universal/{js,py}.py
                              + adapter extract() output     adapters/<name>/__init__.py (optional)
all summaries ──link──▶ Project (imports, exports, symbols)  engine/src/evident/link.py
              ──each adapter's link(ctx)──▶ nodes + edges    adapters/<name>/
              ──universal build──▶ call closure, services, env vars, health findings
```

- The **summary** of a file records imports, exports, scopes, calls (with argument descriptions), decorators, classes, env reads and request-body reads. It's computed once per file and cached in `.evident/`, so it must not depend on which adapters are active.
- **`link(ctx)`** runs once per analysis with every summary available. It finds the framework's objects and emits nodes and edges through `ctx`.
- The **universal build** walks calls from each handler and middleware to models and services. An adapter doesn't need to trace calls itself: it marks handlers and lets the build connect them.

## Anatomy

An adapter is a package `engine/src/evident/adapters/<name>/` and one row in the registry:

```python
# engine/src/evident/adapters/__init__.py
Adapter("flask", "Flask", "framework", "python", flask.link)
#        name     label    kind         ecosystem  link  [extract]
```

- **Order matters.** ORMs come first, so the call classifiers they register know the models before frameworks emit routes.
- **`link(ctx: LinkContext) -> None`** is required. It reads `ctx.project.js` (summaries keyed by file, for both JS and Python) and emits through the context.
- **`extract(path, tree, fn_keys) -> JSON | None`** is optional, for facts the shared summary doesn't capture. It runs per file at parse time and lands in the cache. JS adapters usually write it as a tree-sitter query (`routes.scm`, loaded with `adapters/_js.py:load_query`) plus a small mapper. Return `None` for files the adapter doesn't care about.

### The context you emit through

| Call | Use |
| --- | --- |
| `ctx.node(id, type, label, evidence, attrs, source=, confidence=)` | Add a node. IDs are deterministic and prefixed by type (`route:POST /api/x`, `model:User`). |
| `ctx.edge(type, from_id, to_id, evidence)` | Add an edge (`handles`, `guards`, `reads`, `writes`, …). |
| `ctx.ev(file, start, end)` | Evidence for a line range at the analysed commit. **Every node and edge needs one.** |
| `ctx.mark(fn_key, role)` | Turn a function into a `handler` or `middleware` node and return its id; the universal build traces calls from it. |
| `ctx.classifiers.append(fn)` | ORMs: classify a call (`prisma.user.create`) as a read or write of a model. |
| `ctx.access[fn_key]` | ORMs: attach read/write facts the adapter found directly (for example, a repository method). |

Helpers worth reusing:
- `adapters/_py.py`: `from_package` (is this name imported from package X?), `fn_of` and `class_of` (resolve a decorator or argument to a function or class), `emit_route` (route + handler + guard edges in one call), `join` and the path normalisers;
- `adapters/_js.py`: `load_query`, `describe`, `walk_calls`, `callee`, `binding_of`.

### Stack detection

Add the package names to `SUPPORTED_DEPS` (JS) or `SUPPORTED_PY` (Python) in `adapters/__init__.py`, so the manifest scan reports the framework. Remove it from `NOT_YET` if it was there. A detected but unsupported framework produces the fallback message instead of an empty map.

## Rules every adapter follows

1. **Static only.** Read the summary or the tree; never import, require, evaluate or run anything from the analysed repo ([security.md](security.md)).
2. **Receipts.** Point evidence at the line that proves the element: the decorator or registration for a route, the class for a model, the call for a read or write.
3. **Don't guess.** If a path is computed at runtime, emit the route with `dynamic=True` (drawn dashed, confidence 0.4) or not at all. Never invent a path.
4. **Normalise like the labels.** Paths use the labelling guide's rules (`:id`-style params, joined prefixes, no trailing slash) so the benchmark can match them.
5. **Deterministic.** The same commit gives the same ids, labels and order.

## Checklist before it ships

- [ ] **Fixture repo** in `engine/tests/fixtures/<name>/`: tiny, covering registration styles, prefixes, guards and one tricky case.
- [ ] **Tests** with exact expected nodes and edges, evidence lines included, validated against the schema (see `tests/test_python.py` and `tests/test_adapters.py`). Any bug found later gets a regression fixture before the fix.
- [ ] **Schema:** if the `framework` or `orm` enum gains a value, that's a minor bump. Edit `schema/graph.schema.json`, copy it to `engine/src/evident/graph.schema.json`, run `npm run gen:types` in `web/`, and bump `schemaVersion`.
- [ ] **Counting rules** for the framework in [labelling-guide.md](labelling-guide.md): what counts as a route, model or edge, and what's optional.
- [ ] **A labelled benchmark repo** pinned in `benchmark/repos.yaml` with ground truth in `benchmark/ground-truth/`. `uv run evident-bench --repo <name> --verbose` shows misses and extras.
- [ ] **Supported stacks page:** add the adapter to `web/src/data/stacks.json` (`tests/test_web_contract.py` fails until it matches the registry).
- [ ] `pre-commit run --all-files`, `uv run mypy`, `uv run pytest`, and the benchmark gate stays green.
