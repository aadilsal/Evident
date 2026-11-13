"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { GraphIndex, type Graph } from "@/lib/graph";
import { checkGraph } from "@/lib/source";
import { buildView } from "@/lib/views";
import { MapCanvas } from "./map/MapCanvas";
import { ButtonLink, Mono, shortSha } from "./ui";

/** A real, pre-analysed map: the product is the hero image (DESIGN.md Do's). */
export function HeroMap({ slug }: { slug: string }) {
  const router = useRouter();
  const [graph, setGraph] = useState<Graph | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    fetch(`/data/gallery/${slug}.json`)
      .then((r) => r.json())
      .then((d) => setGraph(checkGraph(d)))
      .catch(() => setFailed(true));
  }, [slug]);

  const view = useMemo(
    () => (graph ? buildView(new GraphIndex(graph), "routes", { hidden: new Set(["env"]) }) : null),
    [graph],
  );

  const open = (extra = "") => router.push(`/map/?gallery=${slug}&view=routes${extra}`);

  return (
    <div className="overflow-hidden rounded-lg border border-outline bg-surface">
      <div className="flex items-center gap-sm border-b border-outline px-lg py-sm">
        <Mono className="truncate text-code-sm">
          {graph ? `${graph.repo.owner}/${graph.repo.name} @ ${shortSha(graph.repo.sha)}` : slug}
        </Mono>
        <span className="ml-auto hidden text-body-sm text-on-surface-muted sm:inline">
          Click any box for its receipt
        </span>
        <ButtonLink href={`/map/?gallery=${slug}`} variant="ghost" className="!h-8">
          Open full map
        </ButtonLink>
      </div>
      <div className="relative h-[420px]">
        {failed && <p className="p-xl text-on-surface-muted">The sample map couldn&apos;t load.</p>}
        {view && (
          <MapCanvas
            view={view}
            onSelectNode={(id) => open(`&node=${encodeURIComponent(id)}`)}
            onSelectEdge={(id) => open(`&edge=${encodeURIComponent(id)}`)}
            onClear={() => undefined}
          />
        )}
      </div>
    </div>
  );
}
