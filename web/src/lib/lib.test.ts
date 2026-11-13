import { describe, expect, it } from "vitest";
import golden from "./__fixtures__/express-prisma.parity.json";
import { findRoute, GraphIndex, impact, routeReach, searchNodes, trace, type Graph } from "./graph";
import { labelPoint, roundedPath } from "./layout";
import { checkGraph, evidenceLink } from "./source";
import { mapHref, parseGithubUrl, parseState, stateToQuery } from "./url";
import { buildView } from "./views";

const graph = golden.graph as unknown as Graph;
const idx = new GraphIndex(graph);

describe("trace and impact match the engine CLI", () => {
  for (const [route, expected] of Object.entries(golden.trace)) {
    it(`trace ${route}`, () => {
      expect(trace(idx, route).map((h) => h.nodeId)).toEqual(expected);
    });
  }
  for (const [node, expected] of Object.entries(golden.impact)) {
    it(`impact ${node}`, () => {
      expect(impact(idx, node).map((h) => h.nodeId)).toEqual(expected);
    });
  }
});

describe("graph queries", () => {
  it("finds routes by method and path, normalising params", () => {
    const route = idx.ofType("route")[0];
    const [method, path] = route.label.split(" ");
    expect(findRoute(idx, `${method} ${path}`)?.id).toBe(route.id);
    expect(findRoute(idx, "not a route")).toBeUndefined();
  });

  it("reaches models through handlers, preferring writes over reads", () => {
    for (const r of idx.ofType("route")) {
      const reach = routeReach(idx, r.id);
      const writes = new Set(reach.filter((x) => x.type === "writes").map((x) => x.targetId));
      expect(reach.filter((x) => x.type === "reads" && writes.has(x.targetId))).toEqual([]);
    }
  });

  it("searches labels and never returns modules", () => {
    const hits = searchNodes(graph, "invoice");
    expect(hits.length).toBeGreaterThan(0);
    expect(hits.every((n) => n.type !== "module")).toBe(true);
  });
});

describe("views", () => {
  it("overview collapses every route into exactly one group", () => {
    const view = buildView(idx, "overview");
    const members = view.nodes.filter((n) => n.kind === "group").flatMap((n) => n.members ?? []);
    const routes = idx.ofType("route").map((r) => r.id);
    expect(routes.every((r) => members.filter((m) => m === r).length === 1)).toBe(true);
    const ids = new Set(view.nodes.map((n) => n.id));
    expect(view.edges.every((e) => ids.has(e.from) && ids.has(e.to))).toBe(true);
  });

  it("every drawn edge carries a receipt from the graph", () => {
    for (const kind of ["overview", "routes", "data"] as const) {
      for (const e of buildView(idx, kind).edges) {
        expect(e.edgeIds.length).toBeGreaterThan(0);
        expect(e.edgeIds.every((id) => idx.edges.has(id))).toBe(true);
      }
    }
  });

  it("layer filters drop nodes and their edges", () => {
    const view = buildView(idx, "routes", { hidden: new Set(["model"]) });
    expect(view.nodes.some((n) => n.layer === "model")).toBe(false);
    const ids = new Set(view.nodes.map((n) => n.id));
    expect(view.edges.every((e) => ids.has(e.from) && ids.has(e.to))).toBe(true);
  });

  it("a trace needs a route root", () => {
    const model = idx.ofType("model")[0];
    expect(buildView(idx, "trace", { root: model.id }).nodes).toEqual([]);
    const route = idx.ofType("route")[0];
    const view = buildView(idx, "trace", { root: route.id });
    expect(view.nodes[0].id).toBe(route.id);
    expect(view.hops?.length).toBe(view.nodes.length);
  });
});

describe("permalinks", () => {
  it("round-trips the full map state", () => {
    const q = new URLSearchParams(
      "repo=acme/app&sha=0123456789abcdef0123456789abcdef01234567&view=trace&root=route%3AGET%20%2Fx&hide=env,model&open=group:a",
    );
    const state = parseState(q);
    expect(state.source).toEqual({
      kind: "github",
      owner: "acme",
      repo: "app",
      sha: "0123456789abcdef0123456789abcdef01234567",
    });
    expect(parseState(new URLSearchParams(stateToQuery(state)))).toEqual(state);
    expect(mapHref(state).startsWith("/map/?")).toBe(true);
  });

  it("rejects malformed sources instead of guessing", () => {
    expect(parseState(new URLSearchParams("repo=acme/app&sha=main")).source).toBeNull();
    expect(parseState(new URLSearchParams("repo=../etc&sha=" + "a".repeat(40))).source).toBeNull();
    expect(parseState(new URLSearchParams("gallery=Not_Valid!")).source).toBeNull();
    expect(parseState(new URLSearchParams("view=bogus")).view).toBe("overview");
  });

  it("accepts only github.com repo URLs", () => {
    expect(parseGithubUrl("https://github.com/acme/app")).toEqual({
      owner: "acme",
      repo: "app",
      ref: undefined,
    });
    expect(parseGithubUrl("github.com/acme/app/tree/main")).toEqual({
      owner: "acme",
      repo: "app",
      ref: "main",
    });
    expect(parseGithubUrl("https://gitlab.com/acme/app")).toBeNull();
    expect(parseGithubUrl("https://github.com/acme/app?x=javascript:alert(1)")).toBeNull();
  });
});

describe("sources", () => {
  it("rejects graphs from another schema major", () => {
    expect(() => checkGraph({ ...graph, schemaVersion: "2.0.0" })).toThrow(/schema/);
    expect(() => checkGraph(null)).toThrow();
    expect(checkGraph(graph).nodes.length).toBe(graph.nodes.length);
  });

  it("links evidence to the exact commit, and nowhere for local graphs", () => {
    const ev = graph.nodes[0].evidence[0];
    expect(evidenceLink(graph, ev)).toBeNull(); // the fixture is a local folder
    const gh = {
      ...graph,
      repo: { ...graph.repo, host: "github.com" as const, owner: "acme", name: "app" },
    };
    expect(evidenceLink(gh, ev)).toBe(
      `https://github.com/acme/app/blob/${ev.sha}/${ev.file}#L${ev.startLine}${ev.endLine !== ev.startLine ? `-L${ev.endLine}` : ""}`,
    );
  });
});

describe("edge routing helpers", () => {
  it("rounds orthogonal corners and finds a label spot on the longest segment", () => {
    const pts = [
      { x: 0, y: 0 },
      { x: 100, y: 0 },
      { x: 100, y: 20 },
    ];
    expect(roundedPath(pts)).toBe("M 0 0 L 94 0 Q 100 0 100 6 L 100 20");
    expect(labelPoint(pts)).toEqual({ x: 50, y: 0 });
  });
});
