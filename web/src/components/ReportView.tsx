"use client";

import { Printer } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  attrs,
  countsByType,
  GraphIndex,
  routeReach,
  type Evidence,
  type Graph,
} from "@/lib/graph";
import type { EnvVarAttrs, ModelAttrs, RouteAttrs, ServiceAttrs } from "@/lib/schema";
import { evidenceLink, loadGraph, SourceError } from "@/lib/source";
import { parseSource, sourceParams } from "@/lib/url";
import { Button, ButtonLink, Mono } from "./ui";

function Ref({ graph, ev }: { graph: Graph; ev: Evidence }) {
  const text = `${ev.file}:${ev.startLine}${ev.endLine !== ev.startLine ? `-${ev.endLine}` : ""}`;
  const href = evidenceLink(graph, ev);
  return href ? (
    <a href={href} className="font-mono text-code-sm underline-offset-2 hover:underline">
      {text}
    </a>
  ) : (
    <Mono className="text-code-sm">{text}</Mono>
  );
}

const TH = "py-xs pr-md text-left font-condensed text-label-sm uppercase";
const TD = "py-xs pr-md align-top";

/** Architecture report: routes, data model, services, env vars and findings with file:line (tracker §7). */
export function ReportView() {
  const params = useSearchParams();
  const source = useMemo(() => parseSource(new URLSearchParams(params.toString())), [params]);
  const [graph, setGraph] = useState<Graph | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!source) return;
    loadGraph(source)
      .then(setGraph)
      .catch((e: unknown) =>
        setError(e instanceof SourceError ? e.message : "Couldn't load the graph."),
      );
    // The source is derived from the URL; the key keeps the effect stable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source ? JSON.stringify(source) : ""]);

  if (!source) return <p className="p-xl">This report link doesn&apos;t point at a map.</p>;
  if (error)
    return (
      <p role="alert" className="p-xl">
        {error}
      </p>
    );
  if (!graph) return <p className="p-xl text-on-surface-muted">Loading…</p>;

  const idx = new GraphIndex(graph);
  const counts = countsByType(graph);
  const repo = graph.repo.owner ? `${graph.repo.owner}/${graph.repo.name}` : graph.repo.name;
  const mapHref = `/map/?${new URLSearchParams(sourceParams(source)).toString()}`;
  const routes = idx.ofType("route").sort((a, b) => a.label.localeCompare(b.label));
  const models = idx.ofType("model").sort((a, b) => a.label.localeCompare(b.label));

  return (
    <div data-theme="light" className="min-h-dvh bg-surface text-on-surface">
      <div className="no-print mx-auto flex max-w-[960px] gap-sm px-xl pt-lg">
        <ButtonLink href={mapHref}>Back to the map</ButtonLink>
        <Button variant="primary" onClick={() => window.print()}>
          <Printer size={16} strokeWidth={1.5} /> Print or save as PDF
        </Button>
      </div>
      <article className="mx-auto max-w-[960px] px-xl py-xl text-body-sm">
        <header className="border-b border-outline pb-lg">
          <p className="font-condensed text-label-sm uppercase text-on-surface-muted">
            Architecture report · Evident
          </p>
          <h1 className="mt-xs text-headline-lg">{repo}</h1>
          <p className="mt-sm font-mono text-code-sm text-on-surface-muted">
            commit {graph.repo.sha} · analysed {graph.repo.analyzedAt.slice(0, 10)} · engine{" "}
            {graph.engineVersion} · schema {graph.schemaVersion}
          </p>
          <p className="mt-sm font-mono text-code-md tabular">
            {counts.route} routes · {counts.model} models · {counts.service} services ·{" "}
            {counts.envVar} env vars · {graph.findings.length} findings
          </p>
          {graph.stack && (
            <p className="mt-xs text-on-surface-muted">
              Stack: {graph.stack.adapters.join(", ") || "none detected"}
            </p>
          )}
        </header>

        {graph.findings.length > 0 && (
          <section className="mt-xl break-inside-avoid">
            <h2 className="text-headline-md">Findings</h2>
            <table className="mt-sm w-full">
              <thead>
                <tr className="border-b border-outline">
                  <th className={TH}>Severity</th>
                  <th className={TH}>Finding</th>
                  <th className={TH}>Evidence</th>
                </tr>
              </thead>
              <tbody>
                {graph.findings.map((f) => (
                  <tr key={f.id} className="border-b border-outline">
                    <td className={TD}>
                      <span className="font-condensed text-label-sm uppercase">{f.severity}</span>
                    </td>
                    <td className={TD}>{f.message}</td>
                    <td className={TD}>
                      <Ref graph={graph} ev={f.evidence[0]} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}

        <section className="mt-xl">
          <h2 className="text-headline-md">Routes</h2>
          <table className="mt-sm w-full">
            <thead>
              <tr className="border-b border-outline">
                <th className={TH}>Route</th>
                <th className={TH}>Reads / writes</th>
                <th className={TH}>Defined at</th>
              </tr>
            </thead>
            <tbody>
              {routes.map((r) => {
                const a = attrs<RouteAttrs>(r);
                const reach = routeReach(idx, r.id).filter((x) => x.type !== "uses");
                return (
                  <tr key={r.id} className="border-b border-outline">
                    <td className={TD}>
                      <Mono className="text-code-sm">{r.label}</Mono>
                      {a.dynamic && <span className="ml-xs text-on-surface-muted">(dynamic)</span>}
                    </td>
                    <td className={TD}>
                      {reach.length
                        ? reach
                            .map(
                              (x) =>
                                `${x.type === "writes" ? "writes" : "reads"} ${idx.nodes.get(x.targetId)?.label}`,
                            )
                            .join(", ")
                        : "–"}
                    </td>
                    <td className={TD}>
                      <Ref graph={graph} ev={r.evidence[0]} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>

        {models.length > 0 && (
          <section className="mt-xl">
            <h2 className="text-headline-md">Data model</h2>
            <div className="mt-sm grid gap-lg sm:grid-cols-2">
              {models.map((m) => {
                const a = attrs<ModelAttrs>(m);
                return (
                  <div key={m.id} className="break-inside-avoid border-t border-outline pt-sm">
                    <p className="font-medium">
                      {m.label}{" "}
                      <Mono className="text-code-sm text-on-surface-muted">
                        table {a.tableName}
                      </Mono>
                    </p>
                    <p className="font-mono text-code-sm text-on-surface-muted">
                      {(a.fields ?? [])
                        .map(
                          (f) =>
                            `${f.name}: ${f.type}${f.isList ? "[]" : ""}${f.isOptional ? "?" : ""}`,
                        )
                        .join(" · ")}
                    </p>
                    <Ref graph={graph} ev={m.evidence[0]} />
                  </div>
                );
              })}
            </div>
          </section>
        )}

        <section className="mt-xl grid gap-xl sm:grid-cols-2">
          <div>
            <h2 className="text-headline-md">External services</h2>
            <ul className="mt-sm">
              {idx.ofType("service").map((s) => (
                <li key={s.id} className="border-b border-outline py-xs">
                  {s.label}{" "}
                  <Mono className="text-code-sm text-on-surface-muted">
                    {attrs<ServiceAttrs>(s).packages?.join(", ")}
                  </Mono>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h2 className="text-headline-md">Env vars (names only)</h2>
            <ul className="mt-sm">
              {idx.ofType("envVar").map((e) => (
                <li key={e.id} className="border-b border-outline py-xs">
                  <Mono className="text-code-sm">{e.label}</Mono>{" "}
                  <span className="text-on-surface-muted">
                    {attrs<EnvVarAttrs>(e).documented ? "documented" : "not in .env.example"}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <footer className="mt-2xl border-t border-outline pt-md text-on-surface-muted">
          Every item was extracted from code at the commit above; groups and summaries are not
          included because they are inferred. Evidence references point at that exact commit.
        </footer>
      </article>
    </div>
  );
}
