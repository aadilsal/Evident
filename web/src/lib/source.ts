// Where a graph and its code come from: the hosted API, the static gallery, `evident open`, or a share link.
import type { Evidence, Graph } from "./graph";
import { SUPPORTED_SCHEMA_MAJOR } from "./schema";
import type { GraphSource } from "./url";

/** Empty in the local bundle: API features (analyse, share, report) are hidden there. */
export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/+$/, "");
export const REPO_URL = "https://github.com/aadilsal/Evident";

export class SourceError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
  }
}

async function getJson(url: string): Promise<unknown> {
  let res: Response;
  try {
    res = await fetch(url, { headers: { Accept: "application/json" } });
  } catch {
    throw new SourceError("Couldn't reach the server. Check your connection and try again.");
  }
  if (!res.ok) {
    let detail = "";
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* not JSON */
    }
    throw new SourceError(detail || `Request failed (${res.status}).`, res.status);
  }
  return res.json();
}

export function graphUrl(source: GraphSource): string {
  switch (source.kind) {
    case "local":
      return "/local/graph.json";
    case "gallery":
      return `/data/gallery/${source.slug}.json`;
    case "share":
      return `${API_URL}/api/shares/${source.id}`;
    case "github":
      return `${API_URL}/api/graphs/${source.owner}/${source.repo}/${source.sha}`;
  }
}

/** Untrusted input (shares, the API): check the shape we rely on before rendering. */
export function checkGraph(data: unknown): Graph {
  const g = data as Partial<Graph> | null;
  if (!g || typeof g !== "object") throw new SourceError("That isn't an Evident graph.");
  const major = Number(String(g.schemaVersion ?? "").split(".")[0]);
  if (major !== SUPPORTED_SCHEMA_MAJOR) {
    throw new SourceError(
      `This graph uses schema ${String(g.schemaVersion)}; this viewer reads ${SUPPORTED_SCHEMA_MAJOR}.x.`,
    );
  }
  if (!Array.isArray(g.nodes) || !Array.isArray(g.edges) || !g.repo) {
    throw new SourceError("The graph is missing nodes, edges or repo details.");
  }
  return {
    ...g,
    groups: Array.isArray(g.groups) ? g.groups : [],
    findings: Array.isArray(g.findings) ? g.findings : [],
  } as Graph;
}

export async function loadGraph(source: GraphSource): Promise<Graph> {
  if ((source.kind === "github" || source.kind === "share") && !API_URL) {
    throw new SourceError("This build has no API configured, so it can only open local graphs.");
  }
  return checkGraph(await getJson(graphUrl(source)));
}

export function hasGithubCode(graph: Graph): boolean {
  return graph.repo.host === "github.com" && Boolean(graph.repo.owner);
}

/** Exact GitHub permalink for an evidence item, pinned to the commit. */
export function evidenceLink(graph: Graph, ev: Evidence): string | null {
  if (!hasGithubCode(graph)) return null;
  const path = ev.file.split("/").map(encodeURIComponent).join("/");
  const lines =
    ev.startLine === ev.endLine ? `L${ev.startLine}` : `L${ev.startLine}-L${ev.endLine}`;
  return `https://github.com/${graph.repo.owner}/${graph.repo.name}/blob/${ev.sha}/${path}#${lines}`;
}

const fileCache = new Map<string, Promise<string | null>>();

/** File text for snippets. Shared local graphs carry no code by design (security.md). */
export function loadFile(source: GraphSource, graph: Graph, file: string): Promise<string | null> {
  let url: string | null = null;
  // GitHub graphs read from the pinned commit (also under `evident open`, which keeps no clone).
  if (hasGithubCode(graph)) {
    const path = file.split("/").map(encodeURIComponent).join("/");
    url = `https://raw.githubusercontent.com/${graph.repo.owner}/${graph.repo.name}/${graph.repo.sha}/${path}`;
  } else if (source.kind === "local") url = `/local/file?path=${encodeURIComponent(file)}`;
  if (!url) return Promise.resolve(null);
  const cached = fileCache.get(url);
  if (cached) return cached;
  const p = fetch(url)
    .then((r) => (r.ok ? r.text() : null))
    .catch(() => null);
  fileCache.set(url, p);
  return p;
}

export function sourceTitle(source: GraphSource, graph?: Graph): string {
  if (graph) {
    return graph.repo.owner ? `${graph.repo.owner}/${graph.repo.name}` : graph.repo.name;
  }
  switch (source.kind) {
    case "github":
      return `${source.owner}/${source.repo}`;
    case "gallery":
      return source.slug;
    case "local":
      return "local repo";
    case "share":
      return "shared map";
  }
}
