// Every view is a commit-pinned permalink: the URL query is the whole UI state.
import { LAYERS, VIEWS, type Layer, type ViewKind } from "./views";

export type GraphSource =
  | { kind: "github"; owner: string; repo: string; sha: string }
  | { kind: "gallery"; slug: string }
  | { kind: "local" }
  | { kind: "share"; id: string };

export interface MapState {
  source: GraphSource | null;
  view: ViewKind;
  node?: string;
  edge?: string;
  root?: string;
  focus: string[];
  hidden: Set<Layer>;
  expanded: Set<string>;
}

const OWNER = /^[A-Za-z0-9][A-Za-z0-9-]{0,38}$/;
const REPO = /^[A-Za-z0-9._-]{1,100}$/;
const SHA = /^[0-9a-f]{40}$/;
const SLUG = /^[a-z0-9-]{1,80}$/;
const SHARE = /^[A-Za-z0-9_-]{8,64}$/;

function list(value: string | null): string[] {
  return value ? value.split(",").filter(Boolean) : [];
}

export function parseSource(q: URLSearchParams): GraphSource | null {
  if (q.get("local") === "1") return { kind: "local" };
  const share = q.get("share");
  if (share && SHARE.test(share)) return { kind: "share", id: share };
  const gallery = q.get("gallery");
  if (gallery && SLUG.test(gallery)) return { kind: "gallery", slug: gallery };
  const [owner, repo] = (q.get("repo") ?? "").split("/");
  const sha = q.get("sha") ?? "";
  if (owner && repo && OWNER.test(owner) && REPO.test(repo) && SHA.test(sha)) {
    return { kind: "github", owner, repo, sha };
  }
  return null;
}

export function parseState(q: URLSearchParams): MapState {
  const view = q.get("view");
  return {
    source: parseSource(q),
    view: (VIEWS as readonly string[]).includes(view ?? "") ? (view as ViewKind) : "overview",
    node: q.get("node") ?? undefined,
    edge: q.get("edge") ?? undefined,
    root: q.get("root") ?? undefined,
    focus: list(q.get("focus")),
    hidden: new Set(
      list(q.get("hide")).filter((l): l is Layer => (LAYERS as readonly string[]).includes(l)),
    ),
    expanded: new Set(list(q.get("open"))),
  };
}

export function sourceParams(source: GraphSource): [string, string][] {
  switch (source.kind) {
    case "local":
      return [["local", "1"]];
    case "share":
      return [["share", source.id]];
    case "gallery":
      return [["gallery", source.slug]];
    case "github":
      return [
        ["repo", `${source.owner}/${source.repo}`],
        ["sha", source.sha],
      ];
  }
}

export function stateToQuery(s: MapState): string {
  const q = new URLSearchParams();
  if (s.source) for (const [k, v] of sourceParams(s.source)) q.set(k, v);
  if (s.view !== "overview") q.set("view", s.view);
  if (s.node) q.set("node", s.node);
  if (s.edge) q.set("edge", s.edge);
  if (s.root) q.set("root", s.root);
  if (s.focus.length) q.set("focus", s.focus.join(","));
  if (s.hidden.size) q.set("hide", [...s.hidden].sort().join(","));
  if (s.expanded.size) q.set("open", [...s.expanded].sort().join(","));
  return q.toString();
}

export function mapHref(s: MapState): string {
  return `/map/?${stateToQuery(s)}`;
}

/** https://github.com/owner/repo[/tree/ref] → owner, repo, ref. Mirrors engine repo.parse_github. */
export function parseGithubUrl(
  input: string,
): { owner: string; repo: string; ref?: string } | null {
  const text = input
    .trim()
    .replace(/\.git$/, "")
    .replace(/\/+$/, "");
  const m = text.match(
    /^(?:https:\/\/)?(?:www\.)?github\.com\/([A-Za-z0-9][A-Za-z0-9-]{0,38})\/([A-Za-z0-9._-]{1,100})(?:\/tree\/([A-Za-z0-9._\/-]{1,200}))?$/,
  );
  if (!m) return null;
  return { owner: m[1], repo: m[2], ref: m[3] };
}
