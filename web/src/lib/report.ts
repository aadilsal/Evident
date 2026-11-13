// "Report a wrong edge": one click, feeds new benchmark cases. Never sends code.
import type { Graph } from "./graph";
import { API_URL, REPO_URL } from "./source";

export interface WrongElement {
  elementId: string;
  kind: "node" | "edge";
  note?: string;
}

export function issueUrl(graph: Graph, el: WrongElement): string {
  const repo = graph.repo.owner
    ? `${graph.repo.owner}/${graph.repo.name}`
    : `${graph.repo.name} (local)`;
  const title = `Wrong ${el.kind}: ${el.elementId}`.slice(0, 200);
  const body = [
    `**Repo:** ${repo} @ \`${graph.repo.sha}\``,
    `**Engine:** ${graph.engineVersion}`,
    `**${el.kind === "node" ? "Node" : "Edge"}:** \`${el.elementId}\``,
    "",
    "**What's wrong** (missing, phantom, wrong type, wrong line):",
    el.note ?? "",
  ].join("\n");
  const q = new URLSearchParams({ title, body, labels: "wrong-map" });
  return `${REPO_URL}/issues/new?${q.toString()}`;
}

/** Hosted GitHub graphs go to the API; local and shared graphs open a prefilled issue instead. */
export async function reportWrong(graph: Graph, el: WrongElement): Promise<"sent" | "issue"> {
  const canPost = Boolean(API_URL) && graph.repo.host === "github.com" && graph.repo.owner;
  if (canPost) {
    const res = await fetch(`${API_URL}/api/reports`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        owner: graph.repo.owner,
        repo: graph.repo.name,
        sha: graph.repo.sha,
        engineVersion: graph.engineVersion,
        elementId: el.elementId,
        kind: el.kind,
        note: el.note ?? "",
      }),
    }).catch(() => null);
    if (res?.ok) return "sent";
  }
  window.open(issueUrl(graph, el), "_blank", "noopener,noreferrer");
  return "issue";
}
