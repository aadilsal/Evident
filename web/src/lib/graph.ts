// Read-only graph queries. A port of engine/src/evident/query.py so the map and the CLI agree.
import type { Edge, EvidentArchitectureGraph, Evidence, Node } from "./schema";

export type Graph = EvidentArchitectureGraph;
export type { Edge, Evidence, Node };
export type NodeType = Node["type"];
export type EdgeType = Edge["type"];

export const TRACE_EDGES: ReadonlySet<EdgeType> = new Set([
  "handles",
  "guards",
  "calls",
  "reads",
  "writes",
  "uses",
]);
export const TRACE_DEPTH = 8;
export const IMPACT_DEPTH = 3;

export function attrs<T>(node: Node | Edge): T {
  return (node.attrs ?? {}) as T;
}

export class GraphIndex {
  readonly nodes = new Map<string, Node>();
  readonly edges = new Map<string, Edge>();
  readonly outgoing = new Map<string, Edge[]>();
  readonly incoming = new Map<string, Edge[]>();

  constructor(readonly graph: Graph) {
    for (const n of graph.nodes) this.nodes.set(n.id, n);
    for (const e of graph.edges) {
      this.edges.set(e.id, e);
      push(this.outgoing, e.from, e);
      push(this.incoming, e.to, e);
    }
    for (const list of [...this.outgoing.values(), ...this.incoming.values()]) {
      list.sort((a, b) => cmp(a.id, b.id));
    }
  }

  out(id: string): Edge[] {
    return this.outgoing.get(id) ?? [];
  }

  in(id: string): Edge[] {
    return this.incoming.get(id) ?? [];
  }

  ofType(type: NodeType): Node[] {
    return this.graph.nodes.filter((n) => n.type === type);
  }
}

function push<K, V>(map: Map<K, V[]>, key: K, value: V): void {
  const list = map.get(key);
  if (list) list.push(value);
  else map.set(key, [value]);
}

function cmp(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

/** Which end depends on the other. A route depends on its middleware, so guards flips. */
export function dependentAndDependency(edge: Edge): [string, string] {
  return edge.type === "guards" ? [edge.to, edge.from] : [edge.from, edge.to];
}

export interface Hop {
  nodeId: string;
  depth: number;
  edge: Edge | null;
}

/** BFS over dependencies. forward = what X depends on; reverse = what depends on X. */
export function walk(
  idx: GraphIndex,
  roots: Iterable<string>,
  opts: { forward: boolean; depth: number; edgeTypes?: ReadonlySet<EdgeType> },
): Hop[] {
  const seen = new Set(roots);
  const hops: Hop[] = [...seen].sort(cmp).map((r) => ({ nodeId: r, depth: 0, edge: null }));
  const queue = [...hops];
  for (let i = 0; i < queue.length; i++) {
    const hop = queue[i];
    if (hop.depth >= opts.depth) continue;
    const candidates = [...idx.out(hop.nodeId), ...idx.in(hop.nodeId)].sort((a, b) =>
      cmp(a.id, b.id),
    );
    for (const edge of candidates) {
      if (opts.edgeTypes && !opts.edgeTypes.has(edge.type)) continue;
      const [dependent, dependency] = dependentAndDependency(edge);
      const [here, there] = opts.forward ? [dependent, dependency] : [dependency, dependent];
      if (here !== hop.nodeId || seen.has(there) || !idx.nodes.has(there)) continue;
      seen.add(there);
      const next = { nodeId: there, depth: hop.depth + 1, edge };
      hops.push(next);
      queue.push(next);
    }
  }
  return hops;
}

export function trace(idx: GraphIndex, routeId: string, depth = TRACE_DEPTH): Hop[] {
  return walk(idx, [routeId], { forward: true, depth, edgeTypes: TRACE_EDGES });
}

export function impact(idx: GraphIndex, nodeId: string, depth = IMPACT_DEPTH): Hop[] {
  return walk(idx, [nodeId], { forward: false, depth });
}

/** A hop is only as certain as the weaker of its edge and node (query.py hop_item). */
export function hopCertainty(
  idx: GraphIndex,
  hop: Hop,
): { source: Node["source"]; confidence: number } {
  const node = idx.nodes.get(hop.nodeId);
  if (!node) return { source: "inferred", confidence: 0 };
  if (!hop.edge) return { source: node.source, confidence: node.confidence };
  const inferred = hop.edge.source === "inferred" || node.source === "inferred";
  return {
    source: inferred ? "inferred" : "extracted",
    confidence: Math.min(hop.edge.confidence, node.confidence),
  };
}

const METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "ALL"];

export function normalisePath(path: string): string {
  const p = path.replace(/\/+$/, "") || "/";
  return p.replace(/(?<=\/):[A-Za-z0-9_-]+\*?\??/g, ":_");
}

/** "POST /api/users" or an exact node id. */
export function findRoute(idx: GraphIndex, query: string): Node | undefined {
  const exact = idx.nodes.get(query);
  if (exact) return exact;
  const parts = query.trim().split(/\s+/);
  if (parts.length !== 2 || !METHODS.includes(parts[0].toUpperCase())) return undefined;
  const [method, path] = [parts[0].toUpperCase(), normalisePath(parts[1])];
  return idx.ofType("route").find((n) => {
    const a = attrs<{ method?: string; path?: string }>(n);
    return (a.method === method || a.method === "ALL") && normalisePath(a.path ?? "") === path;
  });
}

/** Model reads/writes reachable from a route through handlers and calls. */
export interface Reach {
  routeId: string;
  targetId: string;
  type: "reads" | "writes" | "uses";
  via: Edge;
}

export function routeReach(idx: GraphIndex, routeId: string): Reach[] {
  const out = new Map<string, Reach>();
  for (const hop of trace(idx, routeId)) {
    const edge = hop.edge;
    if (!edge || !["reads", "writes", "uses"].includes(edge.type)) continue;
    const target = idx.nodes.get(hop.nodeId);
    if (!target || !["model", "service", "envVar"].includes(target.type)) continue;
    const type = edge.type as Reach["type"];
    const key = `${type}:${target.id}`;
    if (!out.has(key)) out.set(key, { routeId, targetId: target.id, type, via: edge });
  }
  // A route that both reads and writes a model shows one write edge.
  for (const [key, r] of out) {
    if (r.type === "reads" && out.has(`writes:${r.targetId}`)) out.delete(key);
  }
  return [...out.values()];
}

export function countsByType(graph: Graph): Record<NodeType, number> {
  const counts = {
    route: 0,
    handler: 0,
    function: 0,
    middleware: 0,
    model: 0,
    service: 0,
    module: 0,
    envVar: 0,
    container: 0,
  } as Record<NodeType, number>;
  for (const n of graph.nodes) counts[n.type] += 1;
  return counts;
}

export function searchNodes(graph: Graph, query: string, limit = 30): Node[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const scored: [number, Node][] = [];
  for (const n of graph.nodes) {
    if (n.type === "module") continue;
    const label = n.label.toLowerCase();
    const at = label.indexOf(q);
    if (at >= 0) scored.push([at === 0 ? 0 : 1, n]);
    else if (n.id.toLowerCase().includes(q)) scored.push([2, n]);
  }
  scored.sort((a, b) => a[0] - b[0] || cmp(a[1].label, b[1].label));
  return scored.slice(0, limit).map(([, n]) => n);
}
