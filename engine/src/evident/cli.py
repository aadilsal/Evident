"""`evident` command line. Summary-first output for humans and agents; --json for machines."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from evident import __version__
from evident.analyze import analyze
from evident.models import AnalysisError, CommandResult, Graph, ResultItem, UsageError
from evident.query import (
    TRACE_EDGES,
    GraphIndex,
    filter_findings,
    find_access,
    find_route,
    finding_item,
    hop_item,
    neighbours,
    resolve_targets,
    walk,
)
from evident.report import render_markdown

EXIT_OK, EXIT_MATCH, EXIT_USAGE, EXIT_ERROR = 0, 1, 2, 3
DEFAULT_LIMIT = 20


def _positive(value: str) -> int:
    n = int(value)
    if n < 0:
        raise argparse.ArgumentTypeError("must be >= 0")
    return n


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="print the versioned JSON envelope")
    common.add_argument(
        "--limit", type=_positive, default=DEFAULT_LIMIT, help="max results (default 20)"
    )
    common.add_argument("--depth", type=_positive, default=None, help="max hops from the target")
    common.add_argument("--no-llm", action="store_true", help="skip LLM grouping (fully offline)")
    common.add_argument(
        "--repo", default=".", metavar="PATH|URL", help="repo to query (default: current folder)"
    )

    p = argparse.ArgumentParser(
        prog="evident",
        description="Evidence-backed architecture maps for Next.js, Express and Prisma apps. "
        "Static and read-only: never runs repo code; writes only inside .evident/.",
        epilog="Exit codes: 0 ok, 1 findings or no match, 2 usage error, 3 analysis error.",
    )
    p.add_argument("--version", action="version", version=f"evident {__version__}")
    sub = p.add_subparsers(dest="command", required=True, metavar="<command>")

    a = sub.add_parser("analyze", parents=[common], help="build or refresh the graph")
    a.add_argument("target", nargs="?", default=None, metavar="PATH|URL")

    t = sub.add_parser(
        "trace", parents=[common], help="route -> middleware -> handler -> model -> table"
    )
    t.add_argument("route", metavar='"METHOD /path"')

    i = sub.add_parser("impact", parents=[common], help="blast radius of a model, file or env var")
    i.add_argument(
        "node", metavar="NODE", help="node id, name (User, User.email, STRIPE_KEY) or file"
    )

    f = sub.add_parser("find", parents=[common], help="who reads or writes a model")
    mode = f.add_mutually_exclusive_group(required=True)
    mode.add_argument("--reads", metavar="MODEL")
    mode.add_argument("--writes", metavar="MODEL")

    h = sub.add_parser("health", parents=[common], help="architecture findings")
    h.add_argument("--rule", action="append", help="only this rule (repeatable)")
    h.add_argument("--file", action="append", help="only findings with evidence in this file")
    h.add_argument(
        "--severity", choices=["info", "warning", "error"], default="info", help="minimum"
    )

    s = sub.add_parser("show", parents=[common], help="one node with its evidence and edges")
    s.add_argument("node_id", metavar="NODE")

    e = sub.add_parser("export", parents=[common], help="architecture report (md) or graph (json)")
    e.add_argument("--format", choices=["md", "json"], default="md", dest="fmt")
    e.add_argument(
        "--out",
        metavar="FILE",
        help="write here (the only write outside .evident/, and only when asked); default stdout",
    )
    return p


def _cap(items: list[ResultItem], limit: int) -> tuple[list[ResultItem], int, bool]:
    return items[:limit], len(items), len(items) > limit


SUMMARY_TYPES = ("route", "model", "service")
SUMMARY_FINDINGS = 5


def _analyze_cmd(args: argparse.Namespace, graph: Graph | None) -> CommandResult:
    """Summary-first: counts, then the top routes, models, services and findings with file:line."""
    res = analyze(args.target or args.repo, use_llm=not args.no_llm)
    g, st = res.graph, res.stats()
    counts = ", ".join(f"{v} {k}s" for k, v in sorted(st["byType"].items())) or "no nodes yet"
    summary = (
        f"Analysed {st['files']} files ({st['parsed']} parsed, {st['reused']} cached): "
        f"{counts}, {st['findings']} findings in {st['durationMs']} ms."
    )
    if g.stack and g.stack.get("adapters"):
        summary += "\n  stack: " + ", ".join(g.stack["adapters"])
    if g.stack and g.stack.get("message"):
        summary += "\n  note: " + str(g.stack["message"])
    items: list[ResultItem] = []
    per_type = max(1, min(args.limit, 10))
    for node_type in SUMMARY_TYPES:
        nodes = sorted((n for n in g.nodes if n.type == node_type), key=lambda n: n.label)
        items += [ResultItem.from_node(n) for n in nodes[:per_type]]
    findings = filter_findings(g, rules=None, files=None, min_severity="info")
    items += [finding_item(f) for f in findings[:SUMMARY_FINDINGS]]
    total = sum(st["byType"].get(t, 0) for t in SUMMARY_TYPES) + len(findings)
    return CommandResult(
        "analyze", EXIT_OK, summary, items, total, len(items) < total, repo=g.repo, stats=st
    )


def _export_cmd(args: argparse.Namespace, graph: Graph | None) -> CommandResult:
    graph = _require(graph)
    if args.fmt == "md":
        content = render_markdown(graph)
    else:
        content = json.dumps(graph.to_dict(), indent=1) + "\n"
    query: dict[str, object] = {"format": args.fmt, "out": args.out}
    if args.out:
        out = Path(args.out)
        if out.suffix == "" or out.is_dir():
            raise UsageError(f"--out must be a file path, got {args.out!r}")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        size = len(content.encode("utf-8"))
        return CommandResult(
            "export", EXIT_OK, f"Wrote {args.fmt} export to {args.out} ({size} bytes).", query=query
        )
    if not args.json:
        print(content, end="")
    return CommandResult("export", EXIT_OK, f"{args.fmt} export printed.", query=query)


def _require(graph: Graph | None) -> Graph:
    if graph is None:
        raise AnalysisError("no graph available")
    return graph


def _trace_cmd(args: argparse.Namespace, graph: Graph | None) -> CommandResult:
    graph = _require(graph)
    idx = GraphIndex(graph)
    route = find_route(idx, args.route)
    depth = 8 if args.depth is None else args.depth
    query = {"route": args.route, "depth": depth, "limit": args.limit}
    if route is None:
        return CommandResult("trace", EXIT_MATCH, f"No route matches {args.route!r}.", query=query)
    items = [
        hop_item(idx, h)
        for h in walk(idx, [route.id], forward=True, depth=depth, edge_types=TRACE_EDGES)
    ]
    shown, total, cut = _cap(items, args.limit)
    summary = f"{route.label}: {total - 1} hops reachable within depth {depth}."
    return CommandResult("trace", EXIT_OK, summary, shown, total, cut, query=query)


def _impact_cmd(args: argparse.Namespace, graph: Graph | None) -> CommandResult:
    graph = _require(graph)
    idx = GraphIndex(graph)
    roots = resolve_targets(idx, args.node)
    depth = 3 if args.depth is None else args.depth
    query = {"target": args.node, "resolved": roots, "depth": depth, "limit": args.limit}
    if not roots:
        return CommandResult(
            "impact", EXIT_MATCH, f"Nothing in the graph matches {args.node!r}.", query=query
        )
    hops = [h for h in walk(idx, roots, forward=False, depth=depth) if h.depth > 0]
    items = [hop_item(idx, h) for h in hops]
    routes = sum(1 for i in items if i.type == "route")
    shown, total, cut = _cap(items, args.limit)
    summary = f"Changing {args.node} affects {total} nodes ({routes} routes) within depth {depth}."
    return CommandResult(
        "impact", EXIT_OK if items else EXIT_MATCH, summary, shown, total, cut, query=query
    )


def _find_cmd(args: argparse.Namespace, graph: Graph | None) -> CommandResult:
    graph = _require(graph)
    op, model = ("reads", args.reads) if args.reads else ("writes", args.writes)
    depth = 6 if args.depth is None else args.depth
    items = find_access(GraphIndex(graph), model, op, depth)
    query = {op: model, "depth": depth, "limit": args.limit}
    shown, total, cut = _cap(items, args.limit)
    routes = sorted({r for i in items for r in i.routes or []})
    summary = f"{total} functions {op} {model}, reached from {len(routes)} routes."
    return CommandResult(
        "find", EXIT_OK if items else EXIT_MATCH, summary, shown, total, cut, query=query
    )


def _health_cmd(args: argparse.Namespace, graph: Graph | None) -> CommandResult:
    graph = _require(graph)
    found = filter_findings(graph, rules=args.rule, files=args.file, min_severity=args.severity)
    items = [finding_item(f) for f in found]
    shown, total, cut = _cap(items, args.limit)
    by_sev = {s: sum(1 for f in found if f.severity == s) for s in ("error", "warning", "info")}
    detail = ", ".join(f"{n} {s}" for s, n in by_sev.items() if n)
    summary = f"{total} findings ({detail})." if total else "No findings."
    query = {"rule": args.rule, "file": args.file, "severity": args.severity, "limit": args.limit}
    return CommandResult(
        "health", EXIT_MATCH if total else EXIT_OK, summary, shown, total, cut, query=query
    )


def _show_cmd(args: argparse.Namespace, graph: Graph | None) -> CommandResult:
    graph = _require(graph)
    idx = GraphIndex(graph)
    ids = resolve_targets(idx, args.node_id)
    query = {"node": args.node_id, "resolved": ids, "limit": args.limit}
    if not ids:
        return CommandResult("show", EXIT_MATCH, f"No node matches {args.node_id!r}.", query=query)
    if len(ids) > 1:
        items = [ResultItem.from_node(idx.nodes[i]) for i in ids]
        shown, total, cut = _cap(items, args.limit)
        return CommandResult(
            "show",
            EXIT_OK,
            f"{total} nodes match; pass an exact id.",
            shown,
            total,
            cut,
            query=query,
        )
    node = idx.nodes[ids[0]]
    edges = neighbours(idx, node.id)
    items = [ResultItem.from_node(node, attrs=node.attrs), *edges]
    shown, total, cut = _cap(items, args.limit + 1)
    conf = f"confidence {node.confidence:g}"
    summary = f"{node.type} {node.label}: {len(edges)} edges, {node.source}, {conf}."
    return CommandResult("show", EXIT_OK, summary, shown, total, cut, query=query)


COMMANDS: dict[str, Callable[[argparse.Namespace, Graph | None], CommandResult]] = {
    "analyze": _analyze_cmd,
    "trace": _trace_cmd,
    "impact": _impact_cmd,
    "find": _find_cmd,
    "health": _health_cmd,
    "show": _show_cmd,
    "export": _export_cmd,
}


def render(result: CommandResult) -> str:
    lines = [result.summary]
    for r in result.results:
        indent = "  " * (1 + (r.depth or 0))
        head = r.severity or r.type or ""
        text = r.message or r.label or r.id or ""
        via = (
            f" [{r.direction + ' ' if r.direction else ''}{r.via}{' ' + r.op if r.op else ''}]"
            if r.via
            else ""
        )
        doubt = (
            f" ~inferred {r.confidence:.2f}"
            if r.source == "inferred" and r.confidence is not None
            else ""
        )
        where = f"  {', '.join(r.evidence[:3])}" if r.evidence else ""
        routes = f"  <- {', '.join(r.routes)}" if r.routes else ""
        lines.append(f"{indent}{head:<10} {text}{via}{doubt}{where}{routes}")
    if result.truncated:
        lines.append(f"  ... {result.total - len(result.results)} more (raise --limit)")
    if st := result.stats:
        lines.append(f"  graph: {st['graphPath']} (cache {st['cache']}, llm {st['llm']})")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(
                encoding="utf-8", errors="replace"
            )  # Windows consoles default to cp1252
    args = build_parser().parse_args(argv)
    try:
        graph = None
        if args.command != "analyze":
            # Queries refresh incrementally first, so answers never come from a stale graph.
            graph = analyze(args.repo, use_llm=not args.no_llm).graph
        result = COMMANDS[args.command](args, graph)
        if graph is not None:
            result.repo = graph.repo
    except UsageError as exc:
        result = CommandResult(args.command, EXIT_USAGE, f"Usage error: {exc}", error=str(exc))
    except AnalysisError as exc:
        result = CommandResult(args.command, EXIT_ERROR, f"Analysis failed: {exc}", error=str(exc))
    if args.json:
        print(json.dumps(result.to_dict(), separators=(",", ":")))
    elif args.command == "export" and not result.error and not args.out:
        pass  # the export itself went to stdout; keep it clean for piping
    else:
        print(render(result), file=sys.stderr if result.error else sys.stdout)
    return result.exit_code


def run() -> None:
    sys.exit(main())
