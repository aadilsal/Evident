"""End-to-end smoke test of a running Evident service (API + worker + Postgres + Redis).

    python scripts/smoke_service.py http://localhost:8000

Submits a pinned benchmark repo, follows the SSE stream to completion, fetches the graph and
checks it matches the labelled route count. Used by CI and by the deployment runbook.
"""

from __future__ import annotations

import json
import sys
import time

import httpx

REPO = "https://github.com/aadilsal/MotorAi/tree/c10fa5d77f0daa0d40a26ab681e795d5fc589a55"
EXPECTED_ROUTES = 39  # benchmark/ground-truth/aadilsal__MotorAi.yaml
TIMEOUT_S = 300


def main(base: str) -> int:
    with httpx.Client(base_url=base, timeout=30) as client:
        health = client.get("/api/health").json()
        print("health", health)
        if not health.get("ok"):
            return 1
        resp = client.post("/api/analyses", json={"url": REPO})
        body = resp.json()
        print("submit", resp.status_code, body)
        if resp.status_code == 202:
            stages = []
            with client.stream(
                "GET", f"/api/analyses/{body['jobId']}/events", timeout=TIMEOUT_S
            ) as sse:
                for line in sse.iter_lines():
                    if line.startswith("data: "):
                        event = json.loads(line[6:])
                        stages.append(event["stage"])
                        print("event", event)
                        if event["stage"] in ("done", "failed"):
                            break
            if stages[-1:] != ["done"]:
                return 1
            graph_url = f"/api/graphs/aadilsal/MotorAi/{body['sha']}"
        elif resp.status_code == 200:
            graph_url = body["graphUrl"]
        else:
            return 1
        started = time.time()
        graph = client.get(graph_url)
        print(
            "graph",
            graph.status_code,
            graph.headers.get("cache-control"),
            f"{time.time() - started:.2f}s",
        )
        routes = [n for n in graph.json()["nodes"] if n["type"] == "route"]
        print("routes", len(routes), "groups", len(graph.json()["groups"]))
        return 0 if len(routes) == EXPECTED_ROUTES else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"))
