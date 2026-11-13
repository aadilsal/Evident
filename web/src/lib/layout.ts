// ELK layered layout with orthogonal routing (ADR-0002), run in a Web Worker so big maps don't block input.
import type { ElkNode } from "elkjs/lib/elk-api";
import type { VEdge, VNode, ViewModel } from "./views";

export const GRID = 24;
const CHAR_W = 7.2; // Plex Sans Condensed 13px, average advance
const NODE_H = 40;
const FIELD_H = 20;

export interface Placed {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Point {
  x: number;
  y: number;
}

export interface Laid {
  nodes: Map<string, Placed>;
  /** ELK's orthogonal route per edge: start, bends, end. */
  routes: Map<string, Point[]>;
}

export function nodeSize(n: VNode): { width: number; height: number } {
  const text = n.label.length + (n.count ? n.count.length + 3 : 0);
  const width = Math.min(420, Math.max(144, Math.ceil((text * CHAR_W + 40) / GRID) * GRID));
  if (n.fields) {
    const rows = Math.min(n.fields.length, 14);
    return { width: Math.max(width, 216), height: NODE_H + 8 + rows * FIELD_H };
  }
  return { width, height: n.kind === "group" ? NODE_H + 8 : NODE_H };
}

type ElkInstance = { layout: (graph: ElkNode) => Promise<ElkNode> };
let workerElk: Promise<ElkInstance> | null = null;
let mainElk: Promise<ElkInstance> | null = null;
let workerBroken = false;
const WORKER_TIMEOUT_MS = 8000;

function onMainThread(): Promise<ElkInstance> {
  mainElk ??= import("elkjs/lib/elk.bundled.js").then(
    ({ default: ELK }) => new ELK() as unknown as ElkInstance,
  );
  return mainElk;
}

function inWorker(): Promise<ElkInstance> {
  workerElk ??= import("elkjs/lib/elk-api").then(
    ({ default: ELK }) => new ELK({ workerUrl: "/elk-worker.min.js" }) as unknown as ElkInstance,
  );
  return workerElk;
}

/** Worker first (/elk-worker.min.js is copied in at build); main thread if it fails or stalls. */
async function runLayout(graph: ElkNode): Promise<ElkNode> {
  if (typeof Worker !== "undefined" && !workerBroken) {
    try {
      const elk = await inWorker();
      return await Promise.race([
        elk.layout(graph),
        new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error("layout worker timed out")), WORKER_TIMEOUT_MS),
        ),
      ]);
    } catch {
      workerBroken = true;
    }
  }
  return (await onMainThread()).layout(graph);
}

const OPTIONS: Record<string, string> = {
  "elk.algorithm": "layered",
  "elk.direction": "RIGHT",
  "elk.edgeRouting": "ORTHOGONAL",
  "elk.layered.spacing.nodeNodeBetweenLayers": "96",
  "elk.spacing.nodeNode": "24",
  "elk.spacing.edgeNode": "24",
  "elk.layered.nodePlacement.strategy": "NETWORK_SIMPLEX",
  "elk.layered.crossingMinimization.strategy": "LAYER_SWEEP",
  "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
  "elk.separateConnectedComponents": "true",
  "elk.spacing.componentComponent": "48",
};

export async function layout(view: ViewModel): Promise<Laid> {
  const nodes = new Map<string, Placed>();
  const routes = new Map<string, Point[]>();
  if (!view.nodes.length) return { nodes, routes };
  const ids = new Set(view.nodes.map((n) => n.id));
  const graph: ElkNode = {
    id: "root",
    layoutOptions: OPTIONS,
    children: view.nodes.map((n) => ({ id: n.id, ...nodeSize(n) })),
    edges: view.edges
      .filter((e: VEdge) => ids.has(e.from) && ids.has(e.to))
      .map((e) => ({ id: e.id, sources: [e.from], targets: [e.to] })),
  };
  const result = await runLayout(graph);
  // Positions stay unsnapped so ELK's edge routes meet the node sides exactly.
  for (const c of result.children ?? []) {
    nodes.set(c.id, {
      x: c.x ?? 0,
      y: c.y ?? 0,
      width: c.width ?? 160,
      height: c.height ?? NODE_H,
    });
  }
  for (const e of result.edges ?? []) {
    const sec = e.sections?.[0];
    if (!sec) continue;
    routes.set(e.id, [sec.startPoint, ...(sec.bendPoints ?? []), sec.endPoint]);
  }
  return { nodes, routes };
}

/** Orthogonal polyline with rounded corners (DESIGN.md Shapes: 6px radii). */
export function roundedPath(points: Point[], radius = 6): string {
  if (points.length < 2) return "";
  let d = `M ${points[0].x} ${points[0].y}`;
  for (let i = 1; i < points.length - 1; i++) {
    const [a, b, c] = [points[i - 1], points[i], points[i + 1]];
    const r = Math.min(radius, dist(a, b) / 2, dist(b, c) / 2);
    const p1 = toward(b, a, r);
    const p2 = toward(b, c, r);
    d += ` L ${p1.x} ${p1.y} Q ${b.x} ${b.y} ${p2.x} ${p2.y}`;
  }
  const last = points[points.length - 1];
  return `${d} L ${last.x} ${last.y}`;
}

/** Midpoint of the longest segment: where a count label fits. */
export function labelPoint(points: Point[]): Point {
  let best = { x: points[0].x, y: points[0].y };
  let longest = -1;
  for (let i = 1; i < points.length; i++) {
    const len = dist(points[i - 1], points[i]);
    if (len > longest) {
      longest = len;
      best = { x: (points[i - 1].x + points[i].x) / 2, y: (points[i - 1].y + points[i].y) / 2 };
    }
  }
  return best;
}

function dist(a: Point, b: Point): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function toward(from: Point, to: Point, r: number): Point {
  const d = dist(from, to) || 1;
  return { x: from.x + ((to.x - from.x) / d) * r, y: from.y + ((to.y - from.y) / d) * r };
}
