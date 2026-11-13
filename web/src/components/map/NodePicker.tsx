"use client";

import { useMemo, useState } from "react";
import type { GraphIndex } from "@/lib/graph";
import { layerOf, TYPE_TAG } from "@/lib/views";
import { LayerTag } from "../ui";

/** Where a trace or blast radius starts: routes for a trace; models, services, env vars or routes for impact. */
export function NodePicker({
  idx,
  kind,
  onPick,
}: {
  idx: GraphIndex;
  kind: "trace" | "impact";
  onPick: (id: string) => void;
}) {
  const [q, setQ] = useState("");
  const options = useMemo(() => {
    const types =
      kind === "trace" ? ["route"] : ["model", "service", "envVar", "middleware", "route"];
    const needle = q.trim().toLowerCase();
    return idx.graph.nodes
      .filter((n) => types.includes(n.type))
      .filter((n) => !needle || n.label.toLowerCase().includes(needle))
      .sort(
        (a, b) => types.indexOf(a.type) - types.indexOf(b.type) || a.label.localeCompare(b.label),
      )
      .slice(0, 200);
  }, [idx, kind, q]);

  return (
    <div className="mx-auto flex h-full max-w-[36rem] flex-col px-xl pt-3xl">
      <h2 className="text-headline-md">
        {kind === "trace" ? "Trace a request" : "Find the blast radius"}
      </h2>
      <p className="mt-sm text-on-surface-muted">
        {kind === "trace"
          ? "Pick a route. The path lights up through middleware, handlers and calls to every model and service it touches."
          : "Pick a model, service or env var. Everything that depends on it within 3 hops is shown."}
      </p>
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder={kind === "trace" ? "POST /api/…" : "User, STRIPE_SECRET_KEY…"}
        aria-label="Filter"
        className="mt-lg h-10 rounded-md border border-outline bg-surface-sunken px-md font-mono text-code-md focus:border-outline-strong focus:outline-none"
      />
      <ul className="mt-md min-h-0 flex-1 overflow-y-auto pb-xl">
        {options.map((n) => (
          <li key={n.id}>
            <button
              type="button"
              onClick={() => onPick(n.id)}
              className="flex w-full items-center gap-sm rounded-sm px-sm py-sm text-left hover:bg-surface-raised"
            >
              <LayerTag layer={layerOf(n.type)} tag={TYPE_TAG[n.type]} />
              <span className="min-w-0 flex-1 truncate font-condensed text-label-md">
                {n.label}
              </span>
            </button>
          </li>
        ))}
        {options.length === 0 && <li className="p-sm text-on-surface-muted">No matches.</li>}
      </ul>
    </div>
  );
}
