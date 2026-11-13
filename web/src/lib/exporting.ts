// PNG / SVG / JSON exports. Images capture exactly the current view and filters, stamped with repo, SHA and date.
import type { Graph } from "./graph";

export function stamp(graph: Graph, viewLabel: string): string {
  const repo = graph.repo.owner ? `${graph.repo.owner}/${graph.repo.name}` : graph.repo.name;
  const date = new Date().toISOString().slice(0, 10);
  return `${repo} @ ${graph.repo.sha.slice(0, 12)} · ${viewLabel} · exported ${date} · evident ${graph.engineVersion}`;
}

export function fileBase(graph: Graph, viewLabel: string): string {
  const repo = (graph.repo.owner ? `${graph.repo.owner}-${graph.repo.name}` : graph.repo.name)
    .toLowerCase()
    .replace(/[^a-z0-9.-]+/g, "-");
  return `${repo}-${graph.repo.sha.slice(0, 7)}-${viewLabel.toLowerCase().replace(/\s+/g, "-")}`;
}

export function download(name: string, href: string): void {
  const a = document.createElement("a");
  a.href = href;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

export function downloadJson(graph: Graph): void {
  const blob = new Blob([JSON.stringify(graph, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  download(`${fileBase(graph, "graph")}.json`, url);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Captures the canvas element; controls and the minimap are left out. */
export async function exportImage(
  el: HTMLElement,
  graph: Graph,
  viewLabel: string,
  format: "png" | "svg",
): Promise<void> {
  const { toPng, toSvg } = await import("html-to-image");
  const bg = getComputedStyle(document.body).backgroundColor;
  const options = {
    backgroundColor: bg,
    pixelRatio: 2,
    filter: (node: Element) =>
      !(node instanceof HTMLElement) ||
      !(
        node.classList.contains("react-flow__controls") ||
        node.classList.contains("react-flow__minimap")
      ),
  };
  el.dataset.exporting = "1";
  try {
    const url = format === "png" ? await toPng(el, options) : await toSvg(el, options);
    download(`${fileBase(graph, viewLabel)}.${format}`, url);
  } finally {
    delete el.dataset.exporting;
  }
}
