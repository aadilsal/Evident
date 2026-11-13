"""Pre-analyses the featured gallery into static JSON (web/public/data/gallery/).

Usage: uv run python scripts/build_gallery.py [--llm]

Reuses the pinned benchmark clones in benchmark/.repos/src (run `evident-bench` first). Repos are
parsed as text only, never installed or run. Without --llm, groups come from directories.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from evident.analyze import analyze
from evident.models import AnalysisError

ROOT = Path(__file__).resolve().parents[2]
CLONES = ROOT / "benchmark" / ".repos" / "src"
OUT = ROOT / "web" / "public" / "data" / "gallery"

# Benchmark repos shown in the gallery. Each must stay under the repo's 1 MB file limit.
FEATURED = ("MotorAi", "Munshi", "AjaiConsultancyAssignment", "Insight-OS", "SpotterTruckLogging")


def slug(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--llm", action="store_true", help="group with the LLM (needs GROQ_API_KEY)"
    )
    args = parser.parse_args()
    repos = yaml.safe_load((ROOT / "benchmark" / "repos.yaml").read_text(encoding="utf-8"))
    by_name = {
        r["name"]: r for section in repos.values() if isinstance(section, list) for r in section
    }
    OUT.mkdir(parents=True, exist_ok=True)
    index = []
    for name in FEATURED:
        entry = by_name.get(name)
        src = CLONES / name
        if entry is None or not src.is_dir():
            print(f"skip {name}: no pinned clone (run evident-bench first)", file=sys.stderr)
            continue
        owner = entry["owner"]
        try:
            data = analyze(str(src), use_llm=args.llm).graph.to_dict()
        except AnalysisError as exc:
            print(f"skip {name}: {exc}", file=sys.stderr)
            continue
        # Gallery graphs point at the public GitHub commit so snippets and permalinks resolve.
        data["repo"].update(
            {"host": "github.com", "owner": owner, "name": name, "sha": entry["sha"]}
        )
        for item in (*data["nodes"], *data["edges"], *data["findings"]):
            for ev in item["evidence"]:
                ev["sha"] = entry["sha"]
        data["repo"].pop("dirty", None)
        out = OUT / f"{slug(name)}.json"
        out.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8", newline="\n")
        counts = {t: sum(1 for n in data["nodes"] if n["type"] == t) for t in ("route", "model")}
        index.append(
            {
                "slug": slug(name),
                "repo": f"{owner}/{name}",
                "sha": entry["sha"],
                # Facts only: the description is the stack Evident detected.
                "blurb": " + ".join(data.get("stack", {}).get("adapters", [])) or "No adapters",
                "stack": data.get("stack", {}).get("adapters", []),
                "routes": counts["route"],
                "models": counts["model"],
                "findings": len(data["findings"]),
            }
        )
        print(f"wrote {out.name}: {counts['route']} routes, {counts['model']} models")
    (OUT / "index.json").write_text(
        json.dumps({"repos": index}, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
