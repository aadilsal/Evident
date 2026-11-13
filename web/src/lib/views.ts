// Turns a graph into the nodes and edges one view draws. Pure functions, so they're unit-tested.
import {
  attrs,
  GraphIndex,
  impact,
  routeReach,
  trace,
  type Edge,
  type EdgeType,
  type Hop,
  type Node,
  type NodeType,
} from "./graph";
import type { ModelAttrs, RouteAttrs } from "./schema";

export const LAYERS = ["route", "middleware", "handler", "model", "service", "env"] as const;
export type Layer = (typeof LAYERS)[number];

export const LAYER_LABEL: Record<Layer, string> = {
  route: "Routes",
  middleware: "Middleware",
  handler: "Handlers",
  model: "Models",
  service: "Services",
  env: "Env vars",
};

export function layerOf(type: NodeType): Layer {
  switch (type) {
    case "route":
      return "route";
    case "middleware":
      return "middleware";
    case "model":
      return "model";
    case "service":
    case "container":
      return "service";
    case "envVar":
      return "env";
    default:
      return "handler";
  }
}

export const TYPE_TAG: Record<NodeType, string> = {
  route: "ROUTE",
  handler: "HANDLER",
  function: "FUNCTION",
  middleware: "MIDDLEWARE",
  model: "MODEL",
  service: "SERVICE",
  module: "MODULE",
  envVar: "ENV",
  container: "CONTAINER",
};

export const VIEWS = ["overview", "routes", "data", "trace", "impact", "focus"] as const;
export type ViewKind = (typeof VIEWS)[number];

export interface VNode {
  id: string;
  kind: "node" | "group";
  layer: Layer;
  label: string;
  tag: string;
  count?: string;
  nodeId?: string;
  groupId?: string;
  members?: string[];
  inferred: boolean;
  severity?: "error" | "warning" | "info";
  fields?: ModelAttrs["fields"];
  step?: number;
}

export interface VEdge {
  id: string;
  from: string;
  to: string;
  type: EdgeType;
  layer: Layer;
  edgeIds: string[];
  count: number;
  inferred: boolean;
  derived: boolean;
  step?: number;
}

export interface ViewModel {
  kind: ViewKind;
  nodes: VNode[];
  edges: VEdge[];
  /** Hop order for trace/impact animation and the numbered hop list. */
  hops?: Hop[];
  rootId?: string;
  note?: string;
}

export interface ViewOptions {
  hidden?: ReadonlySet<Layer>;
  expanded?: ReadonlySet<string>;
  root?: string;
  focus?: readonly string[];
}

const OVERVIEW_EDGES: ReadonlySet<EdgeType> = new Set([
  "writes",
  "reads",
  "uses",
  "guards",
  "handles",
]);
const STRENGTH: Record<EdgeType, number> = {
  writes: 0,
  reads: 1,
  uses: 2,
  guards: 3,
  handles: 4,
  calls: 5,
  relates: 6,
  imports: 7,
};

const GROUPABLE: ReadonlySet<NodeType> = new Set(["route", "handler", "function", "middleware"]);
const UNGROUPED = "group:_other";

function worstSeverity(idx: GraphIndex): Map<string, "error" | "warning" | "info"> {
  const rank = { error: 0, warning: 1, info: 2 } as const;
  const out = new Map<string, "error" | "warning" | "info">();
  for (const f of idx.graph.findings) {
    for (const id of f.nodeIds) {
      const prev = out.get(id);
      if (!prev || rank[f.severity] < rank[prev]) out.set(id, f.severity);
    }
  }
  return out;
}

function nodeCount(idx: GraphIndex, n: Node): string | undefined {
  switch (n.type) {
    case "model": {
      const writes = idx.in(n.id).filter((e) => e.type === "writes").length;
      const reads = idx.in(n.id).filter((e) => e.type === "reads").length;
      return writes ? `${writes} writes` : reads ? `${reads} reads` : undefined;
    }
    case "service":
    case "envVar": {
      const users = idx.in(n.id).length;
      return users ? `${users} uses` : undefined;
    }
    case "middleware": {
      const guarded = idx.out(n.id).filter((e) => e.type === "guards").length;
      return guarded ? `${guarded} routes` : undefined;
    }
    default:
      return undefined;
  }
}

function vnode(idx: GraphIndex, n: Node, sev: Map<string, "error" | "warning" | "info">): VNode {
  const v: VNode = {
    id: n.id,
    kind: "node",
    layer: layerOf(n.type),
    label: n.label,
    tag: TYPE_TAG[n.type],
    count: nodeCount(idx, n),
    nodeId: n.id,
    inferred: n.source === "inferred",
    severity: sev.get(n.id),
  };
  if (n.type === "route" && attrs<RouteAttrs>(n).dynamic) v.inferred = true;
  return v;
}

function edgeLayer(idx: GraphIndex, e: { type: EdgeType; to: string; from: string }): Layer {
  // Colour an edge by the line it runs into: guards are middleware, everything else its target.
  if (e.type === "guards") return "middleware";
  const target = idx.nodes.get(e.to);
  return target ? layerOf(target.type) : "handler";
}

function visible(hidden: ReadonlySet<Layer> | undefined, layer: Layer): boolean {
  return !hidden?.has(layer);
}

function dropHidden(model: ViewModel, hidden?: ReadonlySet<Layer>): ViewModel {
  if (!hidden?.size) return model;
  const keep = new Set(model.nodes.filter((n) => visible(hidden, n.layer)).map((n) => n.id));
  return {
    ...model,
    nodes: model.nodes.filter((n) => keep.has(n.id)),
    edges: model.edges.filter((e) => keep.has(e.from) && keep.has(e.to)),
  };
}

export function buildView(idx: GraphIndex, kind: ViewKind, opts: ViewOptions = {}): ViewModel {
  switch (kind) {
    case "overview":
      return dropHidden(overview(idx, opts.expanded ?? new Set()), opts.hidden);
    case "routes":
      return dropHidden(routes(idx), opts.hidden);
    case "data":
      return dropHidden(dataModel(idx), opts.hidden);
    case "trace":
      return hopView(idx, "trace", opts.root);
    case "impact":
      return hopView(idx, "impact", opts.root);
    case "focus":
      return focus(idx, opts.focus ?? []);
  }
}

/** Groups collapsed into one box each; models, services and env vars drawn individually. */
function overview(idx: GraphIndex, expanded: ReadonlySet<string>): ViewModel {
  const sev = worstSeverity(idx);
  const box = new Map<string, string>();
  const groupMembers = new Map<string, string[]>();
  const groupLabel = new Map<string, string>([[UNGROUPED, "Other"]]);
  const groupInferred = new Map<string, boolean>();
  for (const g of idx.graph.groups) {
    groupLabel.set(g.id, g.label);
    groupInferred.set(g.id, true);
    for (const m of g.members) {
      const n = idx.nodes.get(m);
      if (!n || !GROUPABLE.has(n.type) || box.has(m)) continue;
      box.set(m, g.id);
      groupMembers.set(g.id, [...(groupMembers.get(g.id) ?? []), m]);
    }
  }
  for (const n of idx.graph.nodes) {
    if (GROUPABLE.has(n.type) && !box.has(n.id)) {
      box.set(n.id, UNGROUPED);
      groupMembers.set(UNGROUPED, [...(groupMembers.get(UNGROUPED) ?? []), n.id]);
    }
  }

  const nodes: VNode[] = [];
  const at = new Map<string, string>();
  for (const [gid, members] of groupMembers) {
    if (expanded.has(gid)) {
      for (const m of members) {
        const n = idx.nodes.get(m)!;
        nodes.push({ ...vnode(idx, n, sev), groupId: gid });
        at.set(m, m);
      }
      continue;
    }
    const routes = members.filter((m) => idx.nodes.get(m)?.type === "route").length;
    const worst =
      members.map((m) => sev.get(m)).find((s) => s === "error") ??
      members.map((m) => sev.get(m)).find((s) => s === "warning");
    nodes.push({
      id: gid,
      kind: "group",
      layer: routes ? "route" : "handler",
      label: groupLabel.get(gid) ?? gid,
      tag: "GROUP",
      count: routes ? `${routes} routes` : `${members.length} nodes`,
      groupId: gid,
      members,
      inferred: groupInferred.get(gid) ?? false,
      severity: worst,
    });
    for (const m of members) at.set(m, gid);
  }
  for (const n of idx.graph.nodes) {
    if (GROUPABLE.has(n.type) || n.type === "module") continue;
    // Unconnected nodes (often env vars read at module level) add a row of noise; search still finds them.
    const linked = [...idx.out(n.id), ...idx.in(n.id)].some((e) => e.type !== "imports");
    if (!linked) continue;
    nodes.push(vnode(idx, n, sev));
    at.set(n.id, n.id);
  }

  // What talks to what: one line per pair, the strongest type wins. Calls and model relations
  // loop back across the map; they live in the trace and the data model views.
  const agg = new Map<string, VEdge>();
  for (const e of idx.graph.edges) {
    if (!OVERVIEW_EDGES.has(e.type)) continue;
    const from = at.get(e.from);
    const to = at.get(e.to);
    if (!from || !to || from === to) continue;
    const key = `${from}|${to}`;
    const prev = agg.get(key);
    if (prev) {
      prev.edgeIds.push(e.id);
      prev.count += 1;
      prev.inferred = prev.inferred && e.source === "inferred";
      if (STRENGTH[e.type] < STRENGTH[prev.type]) {
        prev.type = e.type;
        prev.layer = edgeLayer(idx, e);
      }
    } else {
      agg.set(key, {
        id: key,
        from,
        to,
        type: e.type,
        layer: edgeLayer(idx, e),
        edgeIds: [e.id],
        count: 1,
        inferred: e.source === "inferred",
        derived: from !== e.from || to !== e.to,
      });
    }
  }
  return { kind: "overview", nodes, edges: [...agg.values()] };
}

/** Routes with their middleware, and the models and services each route reaches. */
function routes(idx: GraphIndex): ViewModel {
  const sev = worstSeverity(idx);
  const nodes = new Map<string, VNode>();
  const edges: VEdge[] = [];
  for (const r of idx.ofType("route")) {
    nodes.set(r.id, vnode(idx, r, sev));
    for (const g of idx.in(r.id).filter((e) => e.type === "guards")) {
      const mw = idx.nodes.get(g.from);
      if (!mw) continue;
      nodes.set(mw.id, vnode(idx, mw, sev));
      edges.push(single(idx, g, false));
    }
    for (const reach of routeReach(idx, r.id)) {
      const target = idx.nodes.get(reach.targetId)!;
      if (target.type === "envVar") continue;
      nodes.set(target.id, vnode(idx, target, sev));
      edges.push({
        id: `${reach.type}|${r.id}|${target.id}`,
        from: r.id,
        to: target.id,
        type: reach.type,
        layer: layerOf(target.type),
        edgeIds: [reach.via.id],
        count: 1,
        inferred: reach.via.source === "inferred",
        derived: reach.via.from !== r.id,
      });
    }
  }
  return { kind: "routes", nodes: [...nodes.values()], edges };
}

function single(idx: GraphIndex, e: Edge, derived: boolean): VEdge {
  return {
    id: e.id,
    from: e.from,
    to: e.to,
    type: e.type,
    layer: edgeLayer(idx, e),
    edgeIds: [e.id],
    count: 1,
    inferred: e.source === "inferred",
    derived,
  };
}

function dataModel(idx: GraphIndex): ViewModel {
  const sev = worstSeverity(idx);
  const nodes = idx.ofType("model").map((m) => ({
    ...vnode(idx, m, sev),
    fields: attrs<ModelAttrs>(m).fields ?? [],
    count: `${(attrs<ModelAttrs>(m).fields ?? []).length} fields`,
  }));
  const ids = new Set(nodes.map((n) => n.id));
  const edges = idx.graph.edges
    .filter((e) => e.type === "relates" && ids.has(e.from) && ids.has(e.to))
    .map((e) => single(idx, e, false));
  return { kind: "data", nodes, edges };
}

function hopView(idx: GraphIndex, kind: "trace" | "impact", root?: string): ViewModel {
  if (!root || !idx.nodes.has(root)) {
    return { kind, nodes: [], edges: [], note: "Pick a node to start from." };
  }
  const rootNode = idx.nodes.get(root)!;
  if (kind === "trace" && rootNode.type !== "route") {
    return { kind, nodes: [], edges: [], note: "Request traces start from a route." };
  }
  const hops = kind === "trace" ? trace(idx, root) : impact(idx, root);
  const sev = worstSeverity(idx);
  const nodes = hops.map((h, i) => ({ ...vnode(idx, idx.nodes.get(h.nodeId)!, sev), step: i }));
  const edges = hops
    .filter((h) => h.edge)
    .map((h, i) => ({ ...single(idx, h.edge!, false), step: i + 1 }));
  return { kind, nodes, edges, hops, rootId: root };
}

function focus(idx: GraphIndex, ids: readonly string[]): ViewModel {
  const sev = worstSeverity(idx);
  const set = new Set(ids.filter((id) => idx.nodes.has(id)));
  // Add direct neighbours so a single node isn't drawn alone.
  if (set.size === 1) {
    const [only] = set;
    for (const e of [...idx.out(only), ...idx.in(only)]) {
      if (e.type !== "imports") set.add(e.from === only ? e.to : e.from);
    }
  }
  const nodes = [...set].map((id) => vnode(idx, idx.nodes.get(id)!, sev));
  const edges = idx.graph.edges
    .filter((e) => set.has(e.from) && set.has(e.to))
    .map((e) => single(idx, e, false));
  return { kind: "focus", nodes, edges };
}
