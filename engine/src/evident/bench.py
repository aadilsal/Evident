"""`evident-bench`: score the engine against hand-labelled ground truth.

Match rules, optional items and metrics follow docs/labelling-guide.md exactly. Repos are cloned
read-only at their pinned SHA (never installed or run). With `--baseline`, exits 1 if any
category's micro-averaged precision or recall drops by more than 2 points.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from evident.analyze import analyze
from evident.models import Graph
from evident.query import GraphIndex, walk

JSON = dict[str, Any]
CATEGORIES = ("routes", "models", "services", "edges")
GATE_POINTS = 2.0
FRAMEWORK_ADAPTER = {"next-app-router": "nextjs"}


def repo_root() -> Path:
    for d in [Path.cwd(), *Path.cwd().parents, *Path(__file__).resolve().parents]:
        if (d / "benchmark" / "repos.yaml").is_file():
            return d
    raise SystemExit("benchmark/repos.yaml not found")


def norm_path(path: str) -> str:
    path = path.rstrip("/") or "/"
    return re.sub(r"(?<=/):[A-Za-z0-9_-]+\*?\??", ":_", path)


def route_key(method: str, path: str, kind: str | None = None) -> str:
    """Labelling-guide match key; layouts are separate routes from pages at the same path."""
    suffix = " (layout)" if kind == "layout" else ""
    return f"{method.upper()} {norm_path(path)}{suffix}"


# --- predictions --------------------------------------------------------------


@dataclass(frozen=True)
class Item:
    category: str
    key: str
    adapter: str | None = None
    dynamic: bool = False  # engine marked it dynamic: scored like an optional item


def predictions(graph: Graph) -> set[Item]:
    idx = GraphIndex(graph)
    out: set[Item] = set()
    for n in graph.nodes:
        if n.type == "route":
            fw = str(n.attrs.get("framework"))
            key = route_key(str(n.attrs["method"]), str(n.attrs["path"]), n.attrs.get("kind"))
            dyn = bool(n.attrs.get("dynamic"))
            out.add(Item("routes", key, FRAMEWORK_ADAPTER.get(fw, fw), dyn))
            fns = [
                h.node_id
                for h in walk(
                    idx, [n.id], forward=True, depth=12, edge_types=frozenset({"handles", "calls"})
                )
                if idx.nodes[h.node_id].type in ("handler", "function")
            ]
            for fn in fns:
                for e in idx.outgoing[fn]:
                    if e.type in ("reads", "writes") and e.dst.startswith("model:"):
                        model = idx.nodes[e.dst]
                        op = "read" if e.type == "reads" else "write"
                        edge_key = f"{key} -> {model.label} {op}"
                        out.add(Item("edges", edge_key, model.attrs.get("orm"), dyn))
        elif n.type == "model":
            out.add(Item("models", n.label, n.attrs.get("orm")))
        elif n.type == "service":
            out.add(Item("services", str(n.attrs["provider"])))
    return out


# --- ground truth -------------------------------------------------------------


def truth_items(gt: JSON) -> tuple[set[Item], set[Item]]:
    """(required items, optional items)."""
    required: set[Item] = set()
    optional: set[Item] = set()

    def add(item: Item, entry: JSON) -> None:
        (optional if entry.get("optional") else required).add(item)

    for r in gt.get("routes") or []:
        add(Item("routes", route_key(r["method"], r["path"], r.get("kind")), r.get("framework")), r)
    for m in gt.get("models") or []:
        add(Item("models", m["name"], m.get("orm")), m)
    for s in gt.get("services") or []:
        add(Item("services", s["provider"]), s)
    for e in gt.get("edges") or []:
        method, _, path = e["route"].partition(" ")
        kind = "layout" if path.endswith(" (layout)") else None
        key = f"{route_key(method, path.removesuffix(' (layout)'), kind)} -> {e['model']} {e['op']}"
        add(Item("edges", key, e.get("orm")), e)
    return required, optional - required


# --- scoring ------------------------------------------------------------------


@dataclass
class Score:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    unmatched: int = 0  # predictions matching nothing, optional or not
    predicted: int = 0
    misses: list[str] = field(default_factory=list)
    extras: list[str] = field(default_factory=list)

    def add(self, other: Score) -> None:
        self.tp += other.tp
        self.fp += other.fp
        self.fn += other.fn
        self.unmatched += other.unmatched
        self.predicted += other.predicted

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 1.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 1.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0

    @property
    def hallucination(self) -> float:
        return self.unmatched / self.predicted if self.predicted else 0.0

    def to_dict(self) -> JSON:
        return {
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "hallucinationRate": round(self.hallucination, 4),
        }


def score(pred: set[Item], required: set[Item], optional: set[Item]) -> dict[str, Score]:
    """Per category; matching ignores the adapter tag."""
    out: dict[str, Score] = {}
    for cat in CATEGORIES:
        p = {i.key for i in pred if i.category == cat}
        strict = {i.key for i in pred if i.category == cat and not i.dynamic}
        req = {i.key for i in required if i.category == cat}
        opt = {i.key for i in optional if i.category == cat}
        s = Score(predicted=len(p))
        s.tp = len(p & req)
        s.fp = len(strict - req - opt)
        s.fn = len(req - p)
        s.unmatched = len(p - req - opt)
        s.misses = sorted(req - p)
        s.extras = sorted(strict - req - opt)
        out[cat] = s
    return out


def score_by_adapter(pred: set[Item], required: set[Item], optional: set[Item]) -> dict[str, JSON]:
    adapters = {i.adapter for i in required | pred if i.adapter}
    out: dict[str, JSON] = {}
    for a in sorted(adapters):
        sub = score(
            {i for i in pred if i.adapter == a},
            {i for i in required if i.adapter == a},
            {i for i in optional if i.adapter == a},
        )
        out[a] = {c: s.to_dict() for c, s in sub.items() if s.tp + s.fp + s.fn}
    return out


# --- runner -------------------------------------------------------------------


def _repos(root: Path) -> list[JSON]:
    data = yaml.safe_load((root / "benchmark" / "repos.yaml").read_text(encoding="utf-8")) or {}
    return [r for section in data.values() if isinstance(section, list) for r in section]


def run_repo(root: Path, repo: JSON) -> JSON | None:
    gt_path = root / "benchmark" / "ground-truth" / f"{repo['owner']}__{repo['name']}.yaml"
    if not gt_path.is_file():
        return None
    gt = yaml.safe_load(gt_path.read_text(encoding="utf-8"))
    url = f"https://github.com/{repo['owner']}/{repo['name']}/tree/{repo['sha']}"
    started = time.perf_counter()
    graph = analyze(url, use_llm=False, cache_root=root / "benchmark" / ".repos").graph
    seconds = time.perf_counter() - started
    required, optional = truth_items(gt)
    pred = predictions(graph)
    scores = score(pred, required, optional)
    return {
        "repo": f"{repo['owner']}/{repo['name']}",
        "sha": repo["sha"],
        "seconds": round(seconds, 2),
        "categories": {c: s.to_dict() for c, s in scores.items()},
        "misses": {c: s.misses for c, s in scores.items() if s.misses},
        "extras": {c: s.extras for c, s in scores.items() if s.extras},
        "byAdapter": score_by_adapter(pred, required, optional),
        "_scores": scores,
        "_items": (pred, required, optional),
    }


def summarise(results: list[JSON]) -> JSON:
    total = {c: Score() for c in CATEGORIES}
    pred_all: set[Item] = set()
    req_all: set[Item] = set()
    opt_all: set[Item] = set()
    for r in results:
        for c, s in r["_scores"].items():
            total[c].add(s)
        pred, req, opt = r["_items"]
        tag = r["repo"] + "::"
        pred_all |= {Item(i.category, tag + i.key, i.adapter, i.dynamic) for i in pred}
        req_all |= {Item(i.category, tag + i.key, i.adapter) for i in req}
        opt_all |= {Item(i.category, tag + i.key, i.adapter) for i in opt}
    return {
        "categories": {c: s.to_dict() for c, s in total.items()},
        "byAdapter": score_by_adapter(pred_all, req_all, opt_all),
        "repos": [{k: v for k, v in r.items() if not k.startswith("_")} for r in results],
    }


def regressions(current: JSON, baseline: JSON) -> list[str]:
    out = []
    for cat, cur in current["categories"].items():
        base = baseline.get("categories", {}).get(cat)
        if not base:
            continue
        for metric in ("precision", "recall"):
            drop = (base[metric] - cur[metric]) * 100
            if drop > GATE_POINTS:
                out.append(f"{cat} {metric}: {base[metric]:.1%} -> {cur[metric]:.1%}")
    return out


def _table(summary: JSON) -> str:
    lines = [
        "| Category | Precision | Recall | F1 | Hallucination | TP/FP/FN |",
        "| --- | --: | --: | --: | --: | --: |",
    ]
    for cat, s in summary["categories"].items():
        lines.append(
            f"| {cat} | {s['precision']:.1%} | {s['recall']:.1%} | {s['f1']:.1%} | "
            f"{s['hallucinationRate']:.1%} | {s['tp']}/{s['fp']}/{s['fn']} |"
        )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="evident-bench", description=__doc__)
    ap.add_argument("--repo", action="append", help="only this repo name (repeatable)")
    ap.add_argument("--baseline", type=Path, help="fail on a >2 point drop against this file")
    ap.add_argument("--write", type=Path, help="write the summary JSON here")
    ap.add_argument("--verbose", action="store_true", help="list misses and extras per repo")
    args = ap.parse_args(argv)
    root = repo_root()
    results = []
    for repo in _repos(root):
        if args.repo and repo["name"] not in args.repo:
            continue
        res = run_repo(root, repo)
        if res is not None:
            results.append(res)
            print(f"scored {res['repo']} in {res['seconds']}s", file=sys.stderr)
    if not results:
        print("no labelled repos found", file=sys.stderr)
        return 2
    summary = summarise(results)
    print(_table(summary))
    if args.verbose:
        for r in summary["repos"]:
            print(f"\n## {r['repo']}")
            for kind in ("misses", "extras"):
                for cat, keys in r[kind].items():
                    for k in keys:
                        print(f"  {kind[:-2] if kind == 'misses' else 'extra'} {cat}: {k}")
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    if args.baseline:
        problems = regressions(summary, json.loads(args.baseline.read_text(encoding="utf-8")))
        for p in problems:
            print(f"REGRESSION {p}", file=sys.stderr)
        return 1 if problems else 0
    return 0


def run() -> None:
    sys.exit(main())
