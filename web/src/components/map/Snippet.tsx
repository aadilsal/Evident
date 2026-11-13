"use client";

import { useEffect, useState } from "react";
import type { Evidence, Graph } from "@/lib/graph";
import { highlightLines, type Line } from "@/lib/highlight";
import { loadFile } from "@/lib/source";
import type { GraphSource } from "@/lib/url";
import { cx } from "../ui";

const CONTEXT = 3;
const MAX_LINES = 40;

type State = { key: string } & ({ status: "none" } | { status: "ok"; lines: Line[] });

/** Code around one evidence item; the proving lines carry the highlighter strip. */
export function Snippet({
  source,
  graph,
  ev,
}: {
  source: GraphSource;
  graph: Graph;
  ev: Evidence;
}) {
  const key = `${graph.repo.sha}:${ev.file}:${ev.startLine}:${ev.endLine}`;
  const [loaded, setLoaded] = useState<State | null>(null);
  // Anything loaded for a different receipt counts as still loading.
  const state = loaded?.key === key ? loaded : null;

  useEffect(() => {
    let live = true;
    loadFile(source, graph, ev.file).then(async (text) => {
      if (!live) return;
      if (text === null) return setLoaded({ key, status: "none" });
      const from = Math.max(1, ev.startLine - CONTEXT);
      const to = Math.min(ev.endLine + CONTEXT, from + MAX_LINES - 1);
      const lines = await highlightLines(ev.file, text, from, to);
      if (live) setLoaded({ key, status: "ok", lines });
    });
    return () => {
      live = false;
    };
  }, [key, source, graph, ev.file, ev.startLine, ev.endLine]);

  if (!state) {
    return <div className="h-16 rounded-md bg-surface-sunken" aria-label="Loading code" />;
  }
  if (state.status === "none") {
    return (
      <p className="rounded-md bg-surface-sunken p-md text-body-sm text-on-surface-muted">
        Snippet unavailable.{" "}
        {source.kind === "share"
          ? "Shared maps carry no source code."
          : "The file couldn't be loaded."}
      </p>
    );
  }
  return (
    <pre className="overflow-x-auto rounded-md bg-surface-sunken py-md font-mono text-code-md">
      <code>
        {state.lines.map((line) => {
          const proving = line.number >= ev.startLine && line.number <= ev.endLine;
          return (
            <div key={line.number} className={cx("flex pr-md", proving && "bg-highlight")}>
              <span className="w-12 shrink-0 select-none pr-md text-right text-on-surface-muted tabular">
                {line.number}
              </span>
              <span className="whitespace-pre">
                {line.tokens.map((t, i) => (
                  <span key={i} style={t.color ? { color: t.color } : undefined}>
                    {t.content}
                  </span>
                ))}
                {line.tokens.length === 0 && " "}
              </span>
            </div>
          );
        })}
      </code>
    </pre>
  );
}
