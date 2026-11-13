"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { exportImage, downloadJson } from "@/lib/exporting";
import { GraphIndex, countsByType, type Graph } from "@/lib/graph";
import type { Finding } from "@/lib/schema";
import { loadGraph, sourceTitle, SourceError } from "@/lib/source";
import { mapHref, parseState, sourceParams, type MapState } from "@/lib/url";
import {
  buildView,
  LAYERS,
  layerOf,
  type Layer,
  type VEdge,
  type VNode,
  type ViewKind,
} from "@/lib/views";
import { ButtonLink, shortSha } from "../ui";
import { CommandPalette } from "./CommandPalette";
import { EvidencePanel } from "./EvidencePanel";
import { MapCanvas } from "./MapCanvas";
import { MobileMap } from "./MobileMap";
import { NodePicker } from "./NodePicker";
import { Rail } from "./Rail";
import { TopBar } from "./TopBar";
import { Unsupported } from "./Unsupported";

const VIEW_LABEL: Record<ViewKind, string> = {
  overview: "System overview",
  routes: "Route map",
  data: "Data model",
  trace: "Request trace",
  impact: "Blast radius",
  focus: "Focus",
};

type Load = { key: string } & (
  { status: "error"; message: string } | { status: "ok"; graph: Graph }
);

function useIsMobile(): boolean {
  const [mobile, setMobile] = useState(false);
  useEffect(() => {
    const q = window.matchMedia("(max-width: 767px)");
    const update = () => setMobile(q.matches);
    update();
    q.addEventListener("change", update);
    return () => q.removeEventListener("change", update);
  }, []);
  return mobile;
}

export function MapApp() {
  const params = useSearchParams();
  const router = useRouter();
  const state = useMemo(() => parseState(new URLSearchParams(params.toString())), [params]);
  const sourceKey = state.source ? JSON.stringify(state.source) : "";
  const [loaded, setLoad] = useState<Load | null>(null);
  const load = loaded?.key === sourceKey ? loaded : null;

  useEffect(() => {
    if (!state.source) return;
    let live = true;
    loadGraph(state.source)
      .then((graph) => live && setLoad({ key: sourceKey, status: "ok", graph }))
      .catch(
        (e: unknown) =>
          live &&
          setLoad({
            key: sourceKey,
            status: "error",
            message:
              e instanceof SourceError ? e.message : "Something went wrong loading this map.",
          }),
      );
    return () => {
      live = false;
    };
    // sourceKey captures the source; the object itself is recreated on every URL change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceKey]);

  if (!state.source) {
    return (
      <Centered>
        <p>This link doesn&apos;t point at a map.</p>
        <ButtonLink href="/gallery/">Open the gallery</ButtonLink>
      </Centered>
    );
  }
  if (!load) {
    return <Centered>Loading the map for {sourceTitle(state.source)}…</Centered>;
  }
  if (load.status === "error") {
    return (
      <Centered>
        <p role="alert" className="max-w-[28rem] text-center">
          {load.message}
        </p>
        <ButtonLink href="/">Back to start</ButtonLink>
      </Centered>
    );
  }
  return (
    <LoadedMap
      graph={load.graph}
      state={state}
      navigate={(s, push) => {
        const href = mapHref(s);
        if (push) router.push(href, { scroll: false });
        else router.replace(href, { scroll: false });
      }}
    />
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-lg p-xl text-on-surface-muted">
      {children}
    </main>
  );
}

function LoadedMap({
  graph,
  state,
  navigate,
}: {
  graph: Graph;
  state: MapState;
  navigate: (s: MapState, push?: boolean) => void;
}) {
  const idx = useMemo(() => new GraphIndex(graph), [graph]);
  const mobile = useIsMobile();
  const [palette, setPalette] = useState(false);
  const canvasRef = useRef<HTMLDivElement>(null);
  const counts = useMemo(() => countsByType(graph), [graph]);

  const layerCounts = useMemo(() => {
    const out = Object.fromEntries(LAYERS.map((l) => [l, 0])) as Record<Layer, number>;
    for (const n of graph.nodes) if (n.type !== "module") out[layerOf(n.type)] += 1;
    return out;
  }, [graph]);

  // Keyed by content so selecting a node (a URL change) doesn't rebuild the view and re-run layout.
  const hiddenKey = [...state.hidden].sort().join(",");
  const expandedKey = [...state.expanded].sort().join(",");
  const focusKey = state.focus.join(",");
  const view = useMemo(
    () =>
      buildView(idx, state.view, {
        hidden: new Set(hiddenKey.split(",").filter(Boolean) as Layer[]),
        expanded: new Set(expandedKey.split(",").filter(Boolean)),
        root: state.root,
        focus: focusKey.split(",").filter(Boolean),
      }),
    [idx, state.view, state.root, hiddenKey, expandedKey, focusKey],
  );

  const set = useCallback(
    (patch: Partial<MapState>, push = false) => navigate({ ...state, ...patch }, push),
    [navigate, state],
  );

  const inView = useCallback((id: string) => view.nodes.some((n) => n.id === id), [view.nodes]);

  const selectNode = useCallback(
    (id: string) => {
      if (inView(id) || graph.groups.some((g) => g.id === id)) set({ node: id, edge: undefined });
      else set({ view: "focus", focus: [id], node: id, edge: undefined, root: undefined }, true);
    },
    [inView, graph.groups, set],
  );

  const actions = useMemo(
    () => ({
      selectNode,
      trace: (id: string) =>
        set({ view: "trace", root: id, node: undefined, edge: undefined }, true),
      impact: (id: string) =>
        set({ view: "impact", root: id, node: undefined, edge: undefined }, true),
      expand: (gid: string) =>
        set(
          { view: "overview", expanded: new Set([...state.expanded, gid]), node: undefined },
          true,
        ),
      close: () => set({ node: undefined, edge: undefined }),
    }),
    [selectNode, set, state.expanded],
  );

  const onFinding = useCallback(
    (f: Finding) =>
      set(
        { view: "focus", focus: f.nodeIds, node: f.nodeIds[0], edge: undefined, root: undefined },
        true,
      ),
    [set],
  );

  const selectedEdge: VEdge | undefined = state.edge
    ? view.edges.find((e) => e.id === state.edge)
    : undefined;
  const activeFinding =
    state.view === "focus"
      ? graph.findings.find((f) => f.nodeIds.join() === state.focus.join())?.id
      : undefined;
  const frame = useMemo(() => (state.node ? [state.node] : undefined), [state.node]);

  const reportHref = `/report/?${new URLSearchParams(sourceParams(state.source!)).toString()}`;
  const unsupported =
    (graph.stack?.unsupported?.length ?? 0) > 0 && counts.route === 0 && counts.model === 0;

  async function onExport(format: "png" | "svg" | "json") {
    if (format === "json") return downloadJson(graph);
    if (canvasRef.current)
      await exportImage(canvasRef.current, graph, VIEW_LABEL[view.kind], format);
  }

  if (unsupported) return <Unsupported graph={graph} />;

  if (mobile) {
    return (
      <MobileMap
        graph={graph}
        idx={idx}
        source={state.source!}
        view={view}
        nodeId={state.node}
        actions={actions}
      />
    );
  }

  const showPanel = Boolean(state.node || selectedEdge || view.hops?.length);
  const needsRoot = (state.view === "trace" || state.view === "impact") && !state.root;

  return (
    <div className="flex h-dvh flex-col">
      <TopBar
        graph={graph}
        reportHref={reportHref}
        onSearch={() => setPalette(true)}
        onExport={onExport}
      />
      <div className="flex min-h-0 flex-1">
        <Rail
          idx={idx}
          view={state.view}
          hidden={state.hidden}
          layerCounts={layerCounts}
          onView={(v) =>
            set(
              {
                view: v,
                node: undefined,
                edge: undefined,
                root: v === state.view ? state.root : undefined,
              },
              true,
            )
          }
          onToggleLayer={(l) => {
            const hidden = new Set(state.hidden);
            if (hidden.has(l)) hidden.delete(l);
            else hidden.add(l);
            set({ hidden });
          }}
          onFinding={onFinding}
          activeFinding={activeFinding}
        />
        <main className="relative min-w-0 flex-1" aria-label={VIEW_LABEL[view.kind]}>
          <div ref={canvasRef} className="relative h-full w-full bg-surface">
            <p className="pointer-events-none absolute left-lg top-md z-10 font-mono text-code-sm text-on-surface-muted">
              {graph.repo.owner ? `${graph.repo.owner}/` : ""}
              {graph.repo.name} @ {shortSha(graph.repo.sha)} · {VIEW_LABEL[view.kind]}
              <span className="export-only"> · {new Date().toISOString().slice(0, 10)}</span>
            </p>
            {needsRoot ? (
              <NodePicker
                idx={idx}
                kind={state.view as "trace" | "impact"}
                onPick={(id) => set({ root: id }, true)}
              />
            ) : (
              <MapCanvas
                view={view}
                selectedNode={state.node}
                selectedEdge={state.edge}
                frame={frame}
                onSelectNode={(id: string, v: VNode) =>
                  v.kind === "group" && !state.expanded.has(id)
                    ? set({ node: id, edge: undefined })
                    : selectNode(id)
                }
                onSelectEdge={(id) => set({ edge: id, node: undefined })}
                onClear={() => set({ node: undefined, edge: undefined })}
              />
            )}
          </div>
          <Legend counts={counts} findings={graph.findings.length} />
        </main>
        {showPanel && (
          <EvidencePanel
            graph={graph}
            idx={idx}
            source={state.source!}
            view={view}
            nodeId={state.node}
            edge={selectedEdge}
            actions={actions}
          />
        )}
      </div>
      <CommandPalette graph={graph} open={palette} onOpenChange={setPalette} onPick={selectNode} />
    </div>
  );
}

function Legend({ counts, findings }: { counts: Record<string, number>; findings: number }) {
  return (
    <p className="pointer-events-none absolute right-lg top-md z-10 font-mono text-code-sm tabular text-on-surface-muted">
      {counts.route} routes · {counts.model} models · {counts.service} services · {findings}{" "}
      findings
    </p>
  );
}
