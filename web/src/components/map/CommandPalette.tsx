"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { Command } from "cmdk";
import { useEffect, useMemo, useState } from "react";
import { searchNodes, type Graph } from "@/lib/graph";
import { layerOf, TYPE_TAG } from "@/lib/views";
import { LayerTag } from "../ui";

/** ⌘K: jump to any node by label or id. */
export function CommandPalette({
  graph,
  open,
  onOpenChange,
  onPick,
}: {
  graph: Graph;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onPick: (nodeId: string) => void;
}) {
  const [query, setQuery] = useState("");
  const results = useMemo(() => searchNodes(graph, query), [graph, query]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        onOpenChange(!open);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onOpenChange]);

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-surface-sunken/60" />
        <Dialog.Content
          className="float-shadow fixed left-1/2 top-[15vh] z-50 w-[min(560px,calc(100vw-32px))] -translate-x-1/2 overflow-hidden rounded-lg border border-outline bg-surface-raised"
          aria-describedby={undefined}
        >
          <Dialog.Title className="sr-only">Find a node</Dialog.Title>
          <Command shouldFilter={false} label="Find a node">
            <Command.Input
              value={query}
              onValueChange={setQuery}
              placeholder="Find a route, model, service or env var…"
              className="h-12 w-full border-b border-outline bg-transparent px-lg font-mono text-code-md text-on-surface placeholder:text-on-surface-muted focus:outline-none"
            />
            <Command.List className="max-h-[50vh] overflow-y-auto p-sm">
              {query && (
                <Command.Empty className="p-md text-body-sm text-on-surface-muted">
                  No matches.
                </Command.Empty>
              )}
              {results.map((n) => (
                <Command.Item
                  key={n.id}
                  value={n.id}
                  onSelect={() => {
                    onPick(n.id);
                    onOpenChange(false);
                    setQuery("");
                  }}
                  className="flex cursor-pointer items-center gap-sm rounded-sm px-sm py-sm data-[selected=true]:bg-surface-sunken"
                >
                  <LayerTag layer={layerOf(n.type)} tag={TYPE_TAG[n.type]} />
                  <span className="min-w-0 flex-1 truncate font-condensed text-label-md">
                    {n.label}
                  </span>
                </Command.Item>
              ))}
            </Command.List>
          </Command>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
