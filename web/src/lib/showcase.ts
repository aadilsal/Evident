// Real examples for the landing page, computed at build time from a gallery graph (no invented data).
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { GraphIndex, impact, trace, type Evidence, type Graph } from "./graph";
import { checkGraph } from "./source";

export interface ShowHop {
  label: string;
  via: string | null;
  type: string;
  ref: string;
}

export interface Showcase {
  slug: string;
  repo: string;
  sha: string;
  files: number;
  counts: { routes: number; models: number; services: number; findings: number };
  trace: { route: string; hops: ShowHop[] };
  blast: { model: string; routes: string[]; total: number };
  finding: { severity: string; message: string; ref: string } | null;
}

function ref(ev: Evidence): string {
  return ev.startLine === ev.endLine
    ? `${ev.file}:${ev.startLine}`
    : `${ev.file}:${ev.startLine}-${ev.endLine}`;
}

/** Picks the route whose trace reaches the most models and services: the clearest example. */
export function showcase(slug: string): Showcase {
  const raw = JSON.parse(
    readFileSync(join(process.cwd(), "public", "data", "gallery", `${slug}.json`), "utf8"),
  );
  const graph: Graph = checkGraph(raw);
  const idx = new GraphIndex(graph);
  const routes = idx.ofType("route");

  let best = { id: routes[0]?.id ?? "", score: -1 };
  for (const r of routes) {
    const hops = trace(idx, r.id);
    if (hops.length > 12) continue; // long traces don't read at a glance
    const score = hops.filter((h) => {
      const t = idx.nodes.get(h.nodeId)?.type;
      return t === "model" || t === "service";
    }).length;
    if (score > best.score) best = { id: r.id, score };
  }
  const hops = trace(idx, best.id).map((h) => {
    const n = idx.nodes.get(h.nodeId)!;
    return {
      label: n.label,
      via: h.edge?.type ?? null,
      type: n.type,
      ref: ref((h.edge?.evidence ?? n.evidence)[0]),
    };
  });

  // The model with the widest blast radius in routes.
  let blast = { model: "", routes: [] as string[], total: 0 };
  for (const m of idx.ofType("model")) {
    const dependents = impact(idx, m.id).slice(1);
    const rs = dependents
      .map((h) => idx.nodes.get(h.nodeId)!)
      .filter((n) => n.type === "route")
      .map((n) => n.label);
    if (rs.length > blast.routes.length)
      blast = { model: m.label, routes: rs, total: dependents.length };
  }

  const rank = { error: 0, warning: 1, info: 2 } as const;
  const f = [...graph.findings].sort((a, b) => rank[a.severity] - rank[b.severity])[0];

  const files = new Set<string>();
  for (const n of graph.nodes) for (const ev of n.evidence) files.add(ev.file);

  return {
    slug,
    repo: `${graph.repo.owner}/${graph.repo.name}`,
    sha: graph.repo.sha,
    files: files.size,
    counts: {
      routes: idx.ofType("route").length,
      models: idx.ofType("model").length,
      services: idx.ofType("service").length,
      findings: graph.findings.length,
    },
    trace: { route: idx.nodes.get(best.id)?.label ?? "", hops },
    blast,
    finding: f ? { severity: f.severity, message: f.message, ref: ref(f.evidence[0]) } : null,
  };
}
