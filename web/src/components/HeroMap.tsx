"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { GraphIndex, type Graph } from "@/lib/graph";
import { checkGraph } from "@/lib/source";
import { buildView, type ViewKind } from "@/lib/views";
import { MapCanvas } from "./map/MapCanvas";
import { ButtonLink, Mono, cx, shortSha } from "./ui";

interface Tab {
  id: "trace" | "impact" | "overview";
  label: string;
  caption: string;
}

/**
 * A real, pre-analysed map: the product is the hero image (DESIGN.md Do's).
 * It opens on one request, not the whole system, so the first look is readable.
 */
export function HeroMap({
  slug,
  traceRoot,
  impactRoot,
  traceLabel,
  impactLabel,
}: {
  slug: string;
  traceRoot: string;
  impactRoot: string;
  traceLabel: string;
  impactLabel: string;
}) {
  const router = useRouter();
  const [graph, setGraph] = useState<Graph | null>(null);
  const [failed, setFailed] = useState(false);
  const [tab, setTab] = useState<Tab["id"]>("trace");

  useEffect(() => {
    fetch(`/data/gallery/${slug}.json`)
      .then((r) => r.json())
      .then((d) => setGraph(checkGraph(d)))
      .catch(() => setFailed(true));
  }, [slug]);

  const tabs: Tab[] = [
    {
      id: "trace",
      label: "One request",
      caption: `What ${traceLabel} touches, hop by hop. Click a box for the line of code behind it.`,
    },
    {
      id: "impact",
      label: "Blast radius",
      caption: `Everything that depends on ${impactLabel}: change it, and these break.`,
    },
    {
      id: "overview",
      label: "Whole system",
      caption: "Every feature group and the tables and services it uses. Groups expand on the map.",
    },
  ];
  const active = tabs.find((t) => t.id === tab)!;

  const idx = useMemo(() => (graph ? new GraphIndex(graph) : null), [graph]);
  const view = useMemo(() => {
    if (!idx) return null;
    const kind: ViewKind = tab;
    const root = tab === "trace" ? traceRoot : tab === "impact" ? impactRoot : undefined;
    return buildView(idx, kind, { root, hidden: new Set(["env"]) });
  }, [idx, tab, traceRoot, impactRoot]);

  const mapQuery =
    tab === "overview"
      ? `gallery=${slug}`
      : `gallery=${slug}&view=${tab}&root=${encodeURIComponent(tab === "trace" ? traceRoot : impactRoot)}`;
  const open = (extra = "") => router.push(`/map/?${mapQuery}${extra}`);

  return (
    <div className="overflow-hidden rounded-lg border border-outline bg-surface">
      <div className="flex flex-wrap items-center gap-x-lg gap-y-sm border-b border-outline px-lg py-sm">
        <div role="tablist" aria-label="Sample views" className="flex gap-xs">
          {tabs.map((t) => (
            <button
              key={t.id}
              role="tab"
              type="button"
              aria-selected={tab === t.id}
              onClick={() => setTab(t.id)}
              className={cx(
                "h-8 rounded-md px-md text-label-md transition-colors duration-[var(--ev-motion-feedback)]",
                tab === t.id
                  ? "bg-surface-raised text-on-surface"
                  : "text-on-surface-muted hover:text-on-surface",
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
        <Mono className="ml-auto truncate text-code-sm text-on-surface-muted">
          {graph ? `${graph.repo.owner}/${graph.repo.name} @ ${shortSha(graph.repo.sha)}` : slug}
        </Mono>
        <ButtonLink href={`/map/?${mapQuery}`} variant="ghost" className="!h-8">
          Open full map
        </ButtonLink>
      </div>
      <p className="border-b border-outline px-lg py-sm text-body-sm text-on-surface-muted">
        {active.caption}
      </p>
      <div className="relative h-[400px]">
        {failed && <p className="p-xl text-on-surface-muted">The sample map couldn&apos;t load.</p>}
        {view && (
          <MapCanvas
            view={view}
            controls={false}
            onSelectNode={(id) => open(`&node=${encodeURIComponent(id)}`)}
            onSelectEdge={(id) => open(`&edge=${encodeURIComponent(id)}`)}
            onClear={() => undefined}
          />
        )}
      </div>
    </div>
  );
}
