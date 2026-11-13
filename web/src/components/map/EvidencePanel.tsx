"use client";

import { ChevronDown, ChevronRight, Crosshair, Flag, Route as RouteIcon, X } from "lucide-react";
import { useState, type ReactNode } from "react";
import {
  attrs,
  hopCertainty,
  type Edge,
  type Evidence,
  type Graph,
  type GraphIndex,
  type Hop,
  type Node,
} from "@/lib/graph";
import { reportWrong } from "@/lib/report";
import type {
  EnvVarAttrs,
  FunctionAttrs,
  MiddlewareAttrs,
  ModelAttrs,
  RouteAttrs,
  ServiceAttrs,
} from "@/lib/schema";
import { evidenceLink } from "@/lib/source";
import type { GraphSource } from "@/lib/url";
import { layerOf, TYPE_TAG, type VEdge, type ViewModel } from "@/lib/views";
import { Button, ExhibitTag, LAYER_BG, LayerTag, Mono, Severity, SourceBadge, cx } from "../ui";
import { Snippet } from "./Snippet";

export interface PanelActions {
  selectNode: (id: string) => void;
  trace: (routeId: string) => void;
  impact: (nodeId: string) => void;
  expand: (groupId: string) => void;
  close: () => void;
}

interface Props {
  graph: Graph;
  idx: GraphIndex;
  source: GraphSource;
  view: ViewModel;
  nodeId?: string;
  edge?: VEdge;
  actions: PanelActions;
}

export function EvidencePanel(props: Props) {
  const { idx, view, nodeId, edge } = props;
  let body: ReactNode = null;
  const group = nodeId ? props.graph.groups.find((g) => g.id === nodeId) : undefined;
  if (edge) body = <EdgeBody {...props} edge={edge} />;
  else if (group) body = <GroupBody {...props} groupId={group.id} />;
  else if (nodeId && idx.nodes.has(nodeId))
    body = <NodeBody {...props} node={idx.nodes.get(nodeId)!} />;
  else if (view.hops?.length) body = <HopList {...props} hops={view.hops} kind={view.kind} />;
  if (!body) return null;
  return (
    <aside
      aria-label="Evidence"
      className="float-shadow flex h-full w-full flex-col overflow-hidden border-l border-outline bg-surface-raised md:w-[var(--spacing-panel-width)]"
    >
      <div className="flex justify-end px-sm pt-sm">
        <Button variant="ghost" size="sm" onClick={props.actions.close} aria-label="Close panel">
          <X size={16} strokeWidth={1.5} />
        </Button>
      </div>
      <div className="flex-1 overflow-y-auto px-lg pb-xl text-body-sm">{body}</div>
    </aside>
  );
}

function Title({
  children,
  badge,
  confidence,
}: {
  children: ReactNode;
  badge: boolean;
  confidence?: number;
}) {
  return (
    <div className="mb-md">
      <h2 className="break-words font-condensed text-headline-md">{children}</h2>
      <div className="mt-sm flex flex-wrap items-center gap-sm">
        <SourceBadge inferred={badge} />
        {confidence !== undefined && (
          <Mono className="text-code-sm text-on-surface-muted">
            confidence {confidence.toFixed(2)}
          </Mono>
        )}
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-xl">
      <h3 className="mb-md font-condensed text-label-sm uppercase text-on-surface-muted">
        {title}
      </h3>
      {children}
    </section>
  );
}

function Facts({ rows }: { rows: [string, ReactNode][] }) {
  const shown = rows.filter(([, v]) => v !== undefined && v !== null && v !== "");
  if (!shown.length) return null;
  return (
    <dl className="grid grid-cols-[max-content_1fr] gap-x-lg gap-y-xs">
      {shown.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-on-surface-muted">{k}</dt>
          <dd className="min-w-0 break-words">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function Receipts({ props, evidence }: { props: Props; evidence: readonly Evidence[] }) {
  const [open, setOpen] = useState(1);
  return (
    <div className="flex flex-col gap-md">
      {evidence.slice(0, open).map((ev, i) => (
        <div key={`${ev.file}:${ev.startLine}:${i}`} className="flex flex-col gap-sm">
          <ExhibitTag {...ev} href={evidenceLink(props.graph, ev)} />
          <Snippet source={props.source} graph={props.graph} ev={ev} />
        </div>
      ))}
      {evidence.length > open && (
        <Button variant="ghost" size="sm" onClick={() => setOpen(evidence.length)}>
          Show {evidence.length - open} more receipt{evidence.length - open > 1 ? "s" : ""}
        </Button>
      )}
    </div>
  );
}

function ReportButton({
  graph,
  elementId,
  kind,
}: {
  graph: Graph;
  elementId: string;
  kind: "node" | "edge";
}) {
  const [state, setState] = useState<"idle" | "sent" | "issue">("idle");
  return (
    <Button
      variant="ghost"
      size="sm"
      disabled={state === "sent"}
      onClick={async () => setState(await reportWrong(graph, { elementId, kind }))}
    >
      <Flag size={14} strokeWidth={1.5} />
      {state === "sent"
        ? "Reported, thanks"
        : state === "issue"
          ? "Opened an issue"
          : `Report wrong ${kind}`}
    </Button>
  );
}

function nodeFacts(n: Node): [string, ReactNode][] {
  switch (n.type) {
    case "route": {
      const a = attrs<RouteAttrs>(n);
      return [
        ["Method", <Mono key="m">{a.method}</Mono>],
        ["Path", <Mono key="p">{a.path}</Mono>],
        ["Kind", a.kind],
        ["Framework", <Mono key="f">{a.framework}</Mono>],
        ["Registration", a.dynamic ? "computed path (low confidence)" : undefined],
      ];
    }
    case "model": {
      const a = attrs<ModelAttrs>(n);
      return [
        ["Table", <Mono key="t">{a.tableName}</Mono>],
        ["ORM", a.orm ? <Mono key="o">{a.orm}</Mono> : undefined],
        ["Fields", <Mono key="f">{a.fields?.length ?? 0}</Mono>],
      ];
    }
    case "service": {
      const a = attrs<ServiceAttrs>(n);
      return [
        ["Provider", <Mono key="p">{a.provider}</Mono>],
        ["Packages", <Mono key="k">{a.packages?.join(", ")}</Mono>],
      ];
    }
    case "envVar": {
      const a = attrs<EnvVarAttrs>(n);
      return [
        ["Name", <Mono key="n">{a.name}</Mono>],
        ["Documented", a.documented ? "yes, in .env.example" : "no"],
        ["Value", "never read"],
      ];
    }
    case "middleware": {
      const a = attrs<MiddlewareAttrs>(n);
      return [
        ["File", <Mono key="f">{a.file}</Mono>],
        ["Matchers", a.matchers?.length ? <Mono key="m">{a.matchers.join(", ")}</Mono> : undefined],
        [
          "Checks auth",
          a.checksAuth === undefined ? undefined : a.checksAuth ? "yes (heuristic)" : "no",
        ],
      ];
    }
    case "handler":
    case "function": {
      const a = attrs<FunctionAttrs>(n);
      return [
        ["File", <Mono key="f">{a.file}</Mono>],
        ["Export", a.exportName ? <Mono key="e">{a.exportName}</Mono> : undefined],
        [
          "Checks auth",
          a.checksAuth === undefined ? undefined : a.checksAuth ? "yes (heuristic)" : "no",
        ],
        [
          "Validates body",
          a.validatesBody === undefined ? undefined : a.validatesBody ? "yes" : "no",
        ],
      ];
    }
    default:
      return [];
  }
}

function NodeBody({ node, ...props }: Props & { node: Node }) {
  const { idx, actions, graph } = props;
  const layer = layerOf(node.type);
  const group = graph.groups.find((g) => g.members.includes(node.id));
  const findings = graph.findings.filter((f) => f.nodeIds.includes(node.id));
  const links = [...idx.out(node.id), ...idx.in(node.id)].filter((e) => e.type !== "imports");
  return (
    <>
      <LayerTag layer={layer} tag={TYPE_TAG[node.type]} />
      <div className="mt-sm">
        <Title badge={node.source === "inferred"} confidence={node.confidence}>
          {node.label}
        </Title>
      </div>
      <Facts rows={nodeFacts(node)} />
      <div className="mt-lg flex flex-wrap gap-sm">
        {node.type === "route" && (
          <Button size="sm" onClick={() => actions.trace(node.id)}>
            <RouteIcon size={14} strokeWidth={1.5} />
            Trace request
          </Button>
        )}
        <Button size="sm" onClick={() => actions.impact(node.id)}>
          <Crosshair size={14} strokeWidth={1.5} />
          Blast radius
        </Button>
      </div>
      {findings.length > 0 && (
        <Section title="Findings">
          <ul className="flex flex-col gap-sm">
            {findings.map((f) => (
              <li key={f.id} className="flex flex-col gap-xs">
                <Severity severity={f.severity} />
                <span>{f.message}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}
      <Section title={`Receipts · ${node.evidence.length}`}>
        <Receipts props={props} evidence={node.evidence} />
      </Section>
      {links.length > 0 && (
        <Section title={`Connections · ${links.length}`}>
          <Connections idx={idx} nodeId={node.id} edges={links} onSelect={actions.selectNode} />
        </Section>
      )}
      {group && (
        <Section title="Group">
          <p className="font-medium">{group.label}</p>
          {group.summary && <p className="mt-xs text-on-surface-muted">{group.summary}</p>}
          <div className="mt-sm">
            <SourceBadge inferred />
          </div>
        </Section>
      )}
      <div className="mt-xl">
        <ReportButton graph={graph} elementId={node.id} kind="node" />
      </div>
    </>
  );
}

function Connections({
  idx,
  nodeId,
  edges,
  onSelect,
}: {
  idx: GraphIndex;
  nodeId: string;
  edges: Edge[];
  onSelect: (id: string) => void;
}) {
  const [all, setAll] = useState(false);
  const shown = all ? edges : edges.slice(0, 12);
  return (
    <ul className="flex flex-col">
      {shown.map((e) => {
        const otherId = e.from === nodeId ? e.to : e.from;
        const other = idx.nodes.get(otherId);
        if (!other) return null;
        const out = e.from === nodeId;
        return (
          <li key={e.id}>
            <button
              type="button"
              onClick={() => onSelect(otherId)}
              className="flex w-full items-center gap-sm rounded-sm px-xs py-xs text-left hover:bg-surface-sunken"
            >
              <Mono className="w-20 shrink-0 text-code-sm text-on-surface-muted">
                {out ? `${e.type} →` : `← ${e.type}`}
              </Mono>
              <span className="min-w-0 flex-1 truncate font-condensed text-label-md">
                {other.label}
              </span>
              {e.source === "inferred" && (
                <span className="text-label-sm text-on-surface-muted">inferred</span>
              )}
            </button>
          </li>
        );
      })}
      {edges.length > shown.length && (
        <li>
          <Button variant="ghost" size="sm" onClick={() => setAll(true)}>
            Show all {edges.length}
          </Button>
        </li>
      )}
    </ul>
  );
}

function EdgeBody({ edge, ...props }: Props & { edge: VEdge }) {
  const { idx, actions, graph } = props;
  const real = edge.edgeIds.map((id) => idx.edges.get(id)).filter((e): e is Edge => Boolean(e));
  const from =
    idx.nodes.get(edge.from)?.label ?? graph.groups.find((g) => g.id === edge.from)?.label;
  const to = idx.nodes.get(edge.to)?.label ?? graph.groups.find((g) => g.id === edge.to)?.label;
  const [open, setOpen] = useState<string | null>(real[0]?.id ?? null);
  return (
    <>
      <LayerTag layer={edge.layer} tag={edge.type.toUpperCase()} />
      <div className="mt-sm">
        <Title
          badge={edge.inferred}
          confidence={real.length === 1 ? real[0].confidence : undefined}
        >
          {from} <span className="text-on-surface-muted">{edge.type}</span> {to}
        </Title>
      </div>
      {edge.derived && (
        <p className="text-on-surface-muted">
          Drawn through intermediate code: the receipts below are the calls that do the{" "}
          {edge.type === "uses" ? "work" : edge.type}.
        </p>
      )}
      <Section title={`Receipts · ${real.length}`}>
        <ul className="flex flex-col gap-md">
          {real.slice(0, 30).map((e) => {
            const src = idx.nodes.get(e.from);
            const op = (e.attrs as { operation?: string } | undefined)?.operation;
            return (
              <li key={e.id} className="flex flex-col gap-sm">
                <button
                  type="button"
                  onClick={() => setOpen(open === e.id ? null : e.id)}
                  className="flex items-center gap-sm text-left"
                  aria-expanded={open === e.id}
                >
                  {open === e.id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                  <span className="min-w-0 flex-1 truncate font-condensed text-label-md">
                    {src?.label ?? e.from}
                  </span>
                  {op && <Mono className="text-code-sm text-on-surface-muted">{op}</Mono>}
                  {e.source === "inferred" && (
                    <span className="text-label-sm text-on-surface-muted">inferred</span>
                  )}
                </button>
                {open === e.id && <Receipts props={props} evidence={e.evidence} />}
              </li>
            );
          })}
        </ul>
        {real.length > 30 && (
          <p className="mt-md text-on-surface-muted">{real.length - 30} more not shown.</p>
        )}
      </Section>
      {real.length === 1 && (
        <div className="mt-xl flex gap-sm">
          <Button variant="ghost" size="sm" onClick={() => actions.selectNode(real[0].from)}>
            Open source node
          </Button>
          <ReportButton graph={graph} elementId={real[0].id} kind="edge" />
        </div>
      )}
    </>
  );
}

function GroupBody({ groupId, ...props }: Props & { groupId: string }) {
  const { graph, idx, actions } = props;
  const group = graph.groups.find((g) => g.id === groupId)!;
  const members = group.members.map((m) => idx.nodes.get(m)).filter((n): n is Node => Boolean(n));
  return (
    <>
      <LayerTag layer="route" tag="GROUP" />
      <div className="mt-sm">
        <Title badge confidence={group.confidence}>
          {group.label}
        </Title>
      </div>
      {group.summary && <p className="text-on-surface-muted">{group.summary}</p>}
      <p className="mt-sm text-body-sm text-on-surface-muted">
        Groups are suggestions. They never add nodes or edges; every member below was extracted from
        code.
      </p>
      <div className="mt-lg">
        <Button size="sm" onClick={() => actions.expand(group.id)}>
          Expand on the map
        </Button>
      </div>
      <Section title={`Members · ${members.length}`}>
        <ul className="flex flex-col">
          {members.map((m) => (
            <li key={m.id}>
              <button
                type="button"
                onClick={() => actions.selectNode(m.id)}
                className="flex w-full items-center gap-sm rounded-sm px-xs py-xs text-left hover:bg-surface-sunken"
              >
                <LayerTag layer={layerOf(m.type)} tag={TYPE_TAG[m.type]} />
                <span className="min-w-0 flex-1 truncate font-condensed text-label-md">
                  {m.label}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </Section>
    </>
  );
}

function HopList({ hops, kind, ...props }: Props & { hops: Hop[]; kind: ViewModel["kind"] }) {
  const { idx, actions } = props;
  const [open, setOpen] = useState<number | null>(null);
  const root = idx.nodes.get(hops[0]?.nodeId ?? "");
  if (!root) return null;
  return (
    <>
      <LayerTag
        layer={layerOf(root.type)}
        tag={kind === "trace" ? "REQUEST TRACE" : "BLAST RADIUS"}
      />
      <div className="mt-sm">
        <Title badge={false}>{root.label}</Title>
      </div>
      <p className="text-on-surface-muted">
        {kind === "trace"
          ? `${hops.length - 1} hops from this route, following handlers, calls, reads, writes and services.`
          : `${hops.length - 1} nodes depend on this within 3 hops. Changing it can affect each one.`}
      </p>
      <ol className="mt-lg flex flex-col gap-xs">
        {hops.map((h, i) => {
          const n = idx.nodes.get(h.nodeId);
          if (!n) return null;
          const c = hopCertainty(idx, h);
          const ev = h.edge?.evidence ?? n.evidence;
          return (
            <li key={`${h.nodeId}-${i}`} className="flex flex-col gap-sm">
              <div className="flex items-center gap-sm">
                <Mono className="w-6 shrink-0 text-right text-code-sm text-on-surface-muted">
                  {i + 1}
                </Mono>
                <button
                  type="button"
                  onClick={() => setOpen(open === i ? null : i)}
                  className="flex min-w-0 flex-1 items-center gap-sm rounded-sm px-xs py-xs text-left hover:bg-surface-sunken"
                  aria-expanded={open === i}
                >
                  <span
                    aria-hidden
                    className={cx("h-3 w-[3px] shrink-0 rounded-full", LAYER_BG[layerOf(n.type)])}
                  />
                  <span className="min-w-0 flex-1 truncate font-condensed text-label-md">
                    {n.label}
                  </span>
                  {h.edge && (
                    <Mono className="text-code-sm text-on-surface-muted">{h.edge.type}</Mono>
                  )}
                  {c.source === "inferred" && (
                    <span className="text-label-sm text-on-surface-muted">inferred</span>
                  )}
                </button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => actions.selectNode(n.id)}
                  aria-label={`Open ${n.label}`}
                >
                  <ChevronRight size={14} />
                </Button>
              </div>
              {open === i && (
                <div className="ml-8">
                  <Receipts props={props} evidence={ev} />
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </>
  );
}
