"use client";

import Link from "next/link";
import { useState } from "react";
import { countsByType, type Graph, type GraphIndex } from "@/lib/graph";
import type { GraphSource } from "@/lib/url";
import { layerOf, TYPE_TAG, type ViewModel } from "@/lib/views";
import { LayerTag, Mono, Severity, cx, shortSha } from "../ui";
import { EvidencePanel, type PanelActions } from "./EvidencePanel";

type Tab = "routes" | "models" | "findings";

/** Phones get the summary and lists; the full canvas needs a bigger screen (tracker §8). */
export function MobileMap({
  graph,
  idx,
  source,
  view,
  nodeId,
  actions,
}: {
  graph: Graph;
  idx: GraphIndex;
  source: GraphSource;
  view: ViewModel;
  nodeId?: string;
  actions: PanelActions;
}) {
  const [tab, setTab] = useState<Tab>("routes");
  const counts = countsByType(graph);
  const repo = graph.repo.owner ? `${graph.repo.owner}/${graph.repo.name}` : graph.repo.name;

  if (nodeId || view.hops?.length) {
    return (
      <div className="fixed inset-0 flex flex-col bg-surface-raised">
        <EvidencePanel
          graph={graph}
          idx={idx}
          source={source}
          view={view}
          nodeId={nodeId}
          actions={actions}
        />
      </div>
    );
  }

  const items =
    tab === "routes"
      ? idx.ofType("route")
      : tab === "models"
        ? [...idx.ofType("model"), ...idx.ofType("service")]
        : [];

  return (
    <main className="flex min-h-dvh flex-col">
      <header className="border-b border-outline px-lg py-md">
        <Link href="/" className="font-condensed text-label-lg tracking-wide">
          EVIDENT
        </Link>
        <p className="mt-sm break-all font-mono text-code-md">
          {repo} <span className="text-on-surface-muted">@ {shortSha(graph.repo.sha)}</span>
        </p>
        <p className="mt-xs font-mono text-code-sm tabular text-on-surface-muted">
          {counts.route} routes · {counts.model} models · {counts.service} services ·{" "}
          {graph.findings.length} findings
        </p>
        <p className="mt-sm text-body-sm text-on-surface-muted">
          Open on a larger screen for the interactive map.
        </p>
      </header>
      <div role="tablist" className="flex border-b border-outline px-sm">
        {(["routes", "models", "findings"] as const).map((t) => (
          <button
            key={t}
            role="tab"
            type="button"
            aria-selected={tab === t}
            onClick={() => setTab(t)}
            className={cx(
              "flex-1 py-md text-label-lg capitalize",
              tab === t ? "border-b-2 border-on-surface text-on-surface" : "text-on-surface-muted",
            )}
          >
            {t === "models" ? "Models & services" : t}
          </button>
        ))}
      </div>
      <ul className="flex-1 px-sm py-sm">
        {tab === "findings"
          ? graph.findings.map((f) => (
              <li key={f.id}>
                <button
                  type="button"
                  onClick={() => actions.selectNode(f.nodeIds[0])}
                  className="flex w-full flex-col gap-xs rounded-sm px-sm py-md text-left"
                >
                  <Severity severity={f.severity} />
                  <span className="text-body-md">{f.message}</span>
                </button>
              </li>
            ))
          : items.map((n) => (
              <li key={n.id}>
                <button
                  type="button"
                  onClick={() => actions.selectNode(n.id)}
                  className="flex w-full items-center gap-sm rounded-sm px-sm py-md text-left"
                >
                  <LayerTag layer={layerOf(n.type)} tag={TYPE_TAG[n.type]} />
                  <span className="min-w-0 flex-1 break-all font-condensed text-label-md">
                    {n.label}
                  </span>
                </button>
              </li>
            ))}
        {tab === "findings" && graph.findings.length === 0 && (
          <li className="p-md text-on-surface-muted">No findings.</li>
        )}
      </ul>
      <footer className="border-t border-outline px-lg py-md">
        <Mono className="text-code-sm text-on-surface-muted">engine {graph.engineVersion}</Mono>
      </footer>
    </main>
  );
}
