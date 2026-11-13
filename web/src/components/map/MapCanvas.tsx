"use client";

import {
  Background,
  BaseEdge,
  Controls,
  EdgeLabelRenderer,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  ReactFlowProvider,
  getSmoothStepPath,
  useReactFlow,
  type Edge as FlowEdge,
  type EdgeProps,
  type Node as FlowNode,
  type NodeProps,
} from "@xyflow/react";
import { animate, stagger } from "animejs";
import { AlertTriangle, Layers } from "lucide-react";
import { memo, useEffect, useMemo, useRef, useState } from "react";
import { labelPoint, layout, roundedPath, type Laid, type Point } from "@/lib/layout";
import type { VEdge, VNode, ViewModel } from "@/lib/views";
import { LAYER_BG, LAYER_STROKE, LAYER_TEXT, cx } from "../ui";

type NodeData = VNode & { dimmed: boolean; selected: boolean; onTrace: boolean } & Record<
    string,
    unknown
  >;
type EdgeData = VEdge & {
  dimmed: boolean;
  selected: boolean;
  onTrace: boolean;
  points?: Point[];
} & Record<string, unknown>;

const TRACE_HOP_MS = 160;
const TRACE_STAGGER_MS = 90;

function reducedMotion(): boolean {
  return (
    typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

const EvNode = memo(function EvNode({ data }: NodeProps<FlowNode<NodeData>>) {
  const group = data.kind === "group";
  return (
    <div
      data-trace-step={data.step}
      className={cx(
        "relative h-full overflow-hidden rounded-md bg-surface-raised text-on-surface transition-[opacity,border-color] duration-[var(--ev-motion-feedback)] ease-standard",
        data.inferred ? "border border-dashed border-outline-strong" : "border border-outline",
        data.selected ? "!border-2 !border-on-surface" : "hover:border-outline-strong",
        data.onTrace && "!border-primary",
        data.dimmed && "opacity-35",
        group && "shadow-[3px_3px_0_-1px_var(--color-surface),3px_3px_0_0_var(--color-outline)]",
      )}
      title={data.label}
    >
      <span aria-hidden className={cx("absolute inset-y-0 left-0 w-[3px]", LAYER_BG[data.layer])} />
      <Handle type="target" position={Position.Left} isConnectable={false} />
      <div className="flex h-10 items-center gap-sm pl-md pr-md">
        {group && (
          <Layers aria-hidden size={14} strokeWidth={1.5} className={LAYER_TEXT[data.layer]} />
        )}
        <span className="min-w-0 flex-1 truncate font-condensed text-label-md">{data.label}</span>
        {data.severity && data.severity !== "info" && (
          <AlertTriangle
            size={13}
            strokeWidth={1.75}
            className={data.severity === "error" ? "text-error" : "text-warning"}
            aria-label={`${data.severity} finding`}
          />
        )}
        {data.count && (
          <span className="shrink-0 font-mono text-code-sm tabular text-on-surface-muted">
            {data.count}
          </span>
        )}
      </div>
      {data.fields && data.fields.length > 0 && (
        <ul className="border-t border-outline px-md py-xs">
          {data.fields.slice(0, 14).map((f) => (
            <li
              key={f.name}
              className="flex h-5 items-center justify-between gap-md font-mono text-code-sm"
            >
              <span
                className={cx("truncate", f.isId ? "text-on-surface" : "text-on-surface-muted")}
              >
                {f.name}
                {f.isOptional ? "?" : ""}
              </span>
              <span
                className={cx(
                  "truncate",
                  f.isRelation ? LAYER_TEXT.model : "text-on-surface-muted",
                )}
              >
                {f.type}
                {f.isList ? "[]" : ""}
              </span>
            </li>
          ))}
          {data.fields.length > 14 && (
            <li className="h-5 font-mono text-code-sm text-on-surface-muted">
              +{data.fields.length - 14} more
            </li>
          )}
        </ul>
      )}
      <Handle type="source" position={Position.Right} isConnectable={false} />
    </div>
  );
});

const EvEdge = memo(function EvEdge(props: EdgeProps<FlowEdge<EdgeData>>) {
  const { sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data } = props;
  if (!data) return null;
  let path: string;
  let labelX: number;
  let labelY: number;
  if (data.points && data.points.length > 1) {
    path = roundedPath(data.points);
    ({ x: labelX, y: labelY } = labelPoint(data.points));
  } else {
    [path, labelX, labelY] = getSmoothStepPath({
      sourceX,
      sourceY,
      targetX,
      targetY,
      sourcePosition,
      targetPosition,
      borderRadius: 6,
    });
  }
  const stroke = data.onTrace ? "var(--color-primary)" : LAYER_STROKE[data.layer];
  const width = data.onTrace || data.selected ? 3 : data.count > 3 ? 2 : 1.5;
  return (
    <>
      <g
        className="ev-edge"
        data-trace-edge={data.step}
        style={{ opacity: data.dimmed ? 0.35 : 1 }}
      >
        <BaseEdge
          path={path}
          className="ev-edge-line"
          style={{
            stroke,
            strokeWidth: width,
            strokeDasharray: data.inferred ? "6 4" : undefined,
          }}
          interactionWidth={14}
        />
      </g>
      {data.count > 1 && !data.dimmed && (
        <EdgeLabelRenderer>
          <span
            className="pointer-events-none absolute rounded-sm bg-surface px-xs font-mono text-code-sm tabular text-on-surface-muted"
            style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
          >
            {data.count}
          </span>
        </EdgeLabelRenderer>
      )}
    </>
  );
});

const nodeTypes = { ev: EvNode };
const edgeTypes = { ev: EvEdge };

export interface CanvasProps {
  view: ViewModel;
  selectedNode?: string;
  selectedEdge?: string;
  /** Node ids to keep at full opacity; everything else dims to 35%. */
  emphasis?: ReadonlySet<string> | null;
  /** Frame these nodes when they change (findings, search). */
  frame?: readonly string[];
  onSelectNode: (id: string, vnode: VNode) => void;
  onSelectEdge: (id: string, vedge: VEdge) => void;
  onClear: () => void;
  onLaidOut?: (laid: Laid) => void;
  interactive?: boolean;
}

function Canvas(props: CanvasProps) {
  const { view, selectedNode, selectedEdge, emphasis, frame, interactive = true } = props;
  const [result, setResult] = useState<{ view: ViewModel; laid: Laid } | null>(null);
  // A layout for a previous view is stale; treat it as not laid out yet.
  const laid = result?.view === view ? result.laid : null;
  const placed = laid?.nodes ?? null;
  const [error, setError] = useState<string | null>(null);
  const flow = useReactFlow();
  const wrapper = useRef<HTMLDivElement>(null);
  const onLaidOut = props.onLaidOut;

  useEffect(() => {
    let live = true;
    layout(view)
      .then((p) => {
        if (!live) return;
        setResult({ view, laid: p });
        onLaidOut?.(p);
      })
      .catch(() => live && setError("Couldn't lay out this view."));
    return () => {
      live = false;
    };
  }, [view, onLaidOut]);

  const traced = view.kind === "trace" || view.kind === "impact";
  const traceIds = useMemo(
    () => (traced ? new Set(view.nodes.map((n) => n.id)) : null),
    [traced, view.nodes],
  );

  const nodes: FlowNode<NodeData>[] = useMemo(() => {
    if (!placed) return [];
    return view.nodes.map((n) => {
      const p = placed.get(n.id) ?? { x: 0, y: 0, width: 160, height: 40 };
      return {
        id: n.id,
        type: "ev",
        position: { x: p.x, y: p.y },
        width: p.width,
        height: p.height,
        draggable: false,
        selectable: interactive,
        data: {
          ...n,
          selected: n.id === selectedNode,
          dimmed: Boolean(emphasis && !emphasis.has(n.id)),
          onTrace: view.kind === "trace" && Boolean(traceIds?.has(n.id)) && n.id !== view.rootId,
        },
      };
    });
  }, [placed, view, selectedNode, emphasis, traceIds, interactive]);

  const edges: FlowEdge<EdgeData>[] = useMemo(
    () =>
      view.edges.map((e) => ({
        id: e.id,
        source: e.from,
        target: e.to,
        type: "ev",
        selectable: interactive,
        data: {
          ...e,
          selected: e.id === selectedEdge,
          dimmed: Boolean(emphasis && !(emphasis.has(e.from) && emphasis.has(e.to))),
          onTrace: view.kind === "trace",
          points: laid?.routes.get(e.id),
        },
      })),
    [view, selectedEdge, emphasis, interactive, laid],
  );

  // Frame the whole view on layout; camera eases over 300ms and cuts under reduced motion.
  useEffect(() => {
    if (!placed) return;
    const id = requestAnimationFrame(() =>
      flow.fitView({ padding: 0.15, duration: reducedMotion() ? 0 : 300, maxZoom: 1.2 }),
    );
    return () => cancelAnimationFrame(id);
  }, [placed, flow]);

  useEffect(() => {
    if (!placed || !frame?.length) return;
    const ids = frame.filter((id) => placed.has(id)).map((id) => ({ id }));
    if (ids.length)
      flow.fitView({ nodes: ids, padding: 0.4, duration: reducedMotion() ? 0 : 300, maxZoom: 1.4 });
  }, [frame, placed, flow]);

  // The trace draws hop by hop: each edge over 160ms, staggered 90ms; nodes light as edges arrive.
  useEffect(() => {
    if (!placed || !traced || reducedMotion()) return;
    const root = wrapper.current;
    if (!root) return;
    const frameId = requestAnimationFrame(() => {
      const lines = [
        ...root.querySelectorAll<SVGPathElement>("[data-trace-edge] path.ev-edge-line"),
      ];
      const stations = [...root.querySelectorAll<HTMLElement>("[data-trace-step]")].filter(
        (el) => el.dataset.traceStep !== "0",
      );
      lines.sort(
        (a, b) => step(a.closest("[data-trace-edge]")) - step(b.closest("[data-trace-edge]")),
      );
      stations.sort((a, b) => Number(a.dataset.traceStep) - Number(b.dataset.traceStep));
      for (const l of lines) {
        l.setAttribute("pathLength", "1");
        l.style.strokeDasharray = "1";
        l.style.strokeDashoffset = "1";
      }
      for (const s of stations) s.style.opacity = "0.35";
      animate(lines, {
        strokeDashoffset: [1, 0],
        duration: TRACE_HOP_MS,
        delay: stagger(TRACE_STAGGER_MS),
        ease: "cubicBezier(0.4, 0, 0.2, 1)",
        onComplete: () => {
          for (const l of lines) {
            l.style.strokeDasharray = "";
            l.removeAttribute("pathLength");
          }
        },
      });
      animate(stations, {
        opacity: [0.35, 1],
        duration: TRACE_HOP_MS,
        delay: stagger(TRACE_STAGGER_MS, { start: TRACE_HOP_MS }),
        ease: "cubicBezier(0.2, 0, 0, 1)",
      });
    });
    return () => cancelAnimationFrame(frameId);
  }, [placed, traced, view.rootId]);

  if (error) return <CanvasMessage>{error}</CanvasMessage>;
  if (view.note && !view.nodes.length) return <CanvasMessage>{view.note}</CanvasMessage>;
  if (!view.nodes.length)
    return <CanvasMessage>Nothing to show with the current filters.</CanvasMessage>;

  return (
    <div ref={wrapper} className="drafting-grid h-full w-full" data-testid="map-canvas">
      {!placed && <CanvasMessage>Laying out {view.nodes.length} nodes…</CanvasMessage>}
      <ReactFlow<FlowNode<NodeData>, FlowEdge<EdgeData>>
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={interactive}
        zoomOnScroll={interactive}
        panOnDrag={interactive}
        zoomOnDoubleClick={false}
        minZoom={0.1}
        maxZoom={2}
        onNodeClick={(_, n) => props.onSelectNode(n.id, n.data)}
        onEdgeClick={(_, e) => e.data && props.onSelectEdge(e.id, e.data)}
        onPaneClick={props.onClear}
        proOptions={{ hideAttribution: true }}
        aria-label="Architecture map"
      >
        <Background gap={24} size={0} color="transparent" />
        {interactive && <Controls showInteractive={false} position="bottom-left" />}
        {interactive && view.nodes.length > 40 && (
          <MiniMap
            pannable
            zoomable
            position="bottom-right"
            nodeColor={(n) => LAYER_STROKE[n.data.layer as VNode["layer"]]}
            maskColor="color-mix(in srgb, var(--color-surface) 70%, transparent)"
          />
        )}
      </ReactFlow>
    </div>
  );
}

function step(el: Element | null): number {
  return Number(el?.getAttribute("data-trace-edge") ?? 0);
}

export function CanvasMessage({ children }: { children: React.ReactNode }) {
  return (
    <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center p-xl text-center text-body-md text-on-surface-muted">
      {children}
    </div>
  );
}

export function MapCanvas(props: CanvasProps) {
  return (
    <ReactFlowProvider>
      <div className="relative h-full w-full">
        <Canvas {...props} />
      </div>
    </ReactFlowProvider>
  );
}
