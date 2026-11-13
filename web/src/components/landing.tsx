import type { ReactNode } from "react";
import type { ShowHop } from "@/lib/showcase";
import { layerOf } from "@/lib/views";
import type { NodeType } from "@/lib/graph";
import { LAYER_BG, Mono, cx } from "./ui";

export function Section({
  id,
  eyebrow,
  title,
  lead,
  children,
  className,
}: {
  id?: string;
  eyebrow: string;
  title: string;
  lead?: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <section id={id} className={cx("scroll-mt-xl border-t border-outline pt-2xl", className)}>
      <p className="font-condensed text-label-sm uppercase text-on-surface-muted">{eyebrow}</p>
      <h2 className="mt-sm max-w-[42rem] text-headline-lg">{title}</h2>
      {lead && <p className="mt-md max-w-[42rem] text-body-lg text-on-surface-muted">{lead}</p>}
      {children && <div className="mt-xl">{children}</div>}
    </section>
  );
}

/** A trace as a numbered hop list, each hop with its receipt: the product in one glance. */
export function TraceExhibit({
  route,
  hops,
  repo,
  sha,
}: {
  route: string;
  hops: ShowHop[];
  repo: string;
  sha: string;
}) {
  return (
    <figure className="overflow-hidden rounded-lg border border-outline bg-surface-raised">
      <figcaption className="flex flex-wrap items-baseline gap-x-sm border-b border-outline px-lg py-md">
        <span className="font-condensed text-label-sm uppercase text-on-surface-muted">
          Request trace
        </span>
        <Mono className="text-code-md">{route}</Mono>
        <Mono className="ml-auto text-code-sm text-on-surface-muted">
          {repo} @ {sha.slice(0, 7)}
        </Mono>
      </figcaption>
      <ol className="px-lg py-md">
        {hops.map((h, i) => (
          <li
            key={`${h.label}-${i}`}
            className="grid grid-cols-[1.5rem_3px_1fr] items-start gap-x-md py-[3px]"
          >
            <Mono className="pt-[2px] text-right text-code-sm text-on-surface-muted">{i + 1}</Mono>
            <span
              aria-hidden
              className={cx(
                "mt-[5px] h-[14px] w-[3px] rounded-full",
                LAYER_BG[layerOf(h.type as NodeType)],
              )}
            />
            <span className="min-w-0">
              <span className="flex flex-wrap items-baseline gap-x-sm">
                <span className="font-condensed text-label-md">{h.label}</span>
                {h.via && <Mono className="text-code-sm text-on-surface-muted">{h.via}</Mono>}
              </span>
              <Mono className="block truncate text-code-sm text-on-surface-muted">{h.ref}</Mono>
            </span>
          </li>
        ))}
      </ol>
    </figure>
  );
}

const STOPS = [
  {
    name: "Parse",
    body: "tree-sitter reads every file as text. Nothing is installed, imported or run.",
    sample: "npm install: never · eval: never",
  },
  {
    name: "Extract",
    body: "Framework and ORM adapters find routes, middleware, handlers, models, SDK calls and env vars.",
    sample: "route:POST /api/orders",
  },
  {
    name: "Link",
    body: "Imports, aliases and calls are resolved, so each route connects to the tables it touches.",
    sample: "POST /api/orders → createOrder() → Order",
  },
  {
    name: "Check",
    body: "Health rules flag writes without auth, unvalidated bodies, import cycles and unused models.",
    sample: "unguarded-write · POST /api/orders",
  },
  {
    name: "Group",
    body: "An LLM may only label groups of nodes that already exist. Anything else is rejected.",
    sample: "group:orders  (inferred)",
  },
] as const;

/** How it works, drawn as the transit line the map itself uses. */
export function TransitSteps() {
  return (
    <ol className="relative grid gap-xl md:grid-cols-5 md:gap-lg">
      <span
        aria-hidden
        className="absolute left-[7px] top-2 bottom-2 w-[3px] bg-layer-route md:hidden"
      />
      <span
        aria-hidden
        className="absolute left-2 right-2 top-[7px] hidden h-[3px] bg-layer-route md:block"
      />
      {STOPS.map((s, i) => (
        <li key={s.name} className="relative pl-xl md:pl-0 md:pt-xl">
          <span
            aria-hidden
            className="absolute left-0 top-0 h-4 w-4 rounded-full border-[3px] border-layer-route bg-surface"
          />
          <p className="flex items-baseline gap-sm">
            <Mono className="text-code-sm text-on-surface-muted">0{i + 1}</Mono>
            <span className="text-label-lg">{s.name}</span>
          </p>
          <p className="mt-sm text-body-sm text-on-surface-muted">{s.body}</p>
          <Mono className="mt-sm block break-words rounded-sm bg-surface-sunken px-sm py-xs text-code-sm">
            {s.sample}
          </Mono>
        </li>
      ))}
    </ol>
  );
}

const COMPARE: [string, string, string][] = [
  [
    "Where boxes come from",
    "An LLM reading the file tree and README",
    "Static analysis of the code",
  ],
  [
    "Level of detail",
    "Folders and modules",
    "Routes → middleware → handlers → tables, services, env vars",
  ],
  ["Proof for an arrow", "None", "file:line at the exact commit, one click away"],
  ["Accuracy", "Not measured", "Hand-labelled benchmark, re-run in CI on every change"],
  [
    "What the LLM decides",
    "What exists and how it connects",
    "Only group names, over nodes that already exist; it can't add a box",
  ],
];

export function CompareTable() {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[40rem] text-left text-body-md">
        <thead>
          <tr className="border-b border-outline font-condensed text-label-sm uppercase text-on-surface-muted">
            <th className="w-1/4 py-sm pr-lg font-semibold" />
            <th className="py-sm pr-lg font-semibold">Typical AI diagram tools</th>
            <th className="py-sm font-semibold text-on-surface">Evident</th>
          </tr>
        </thead>
        <tbody>
          {COMPARE.map(([row, them, us]) => (
            <tr key={row} className="border-b border-outline align-top">
              <th scope="row" className="py-md pr-lg text-left font-medium">
                {row}
              </th>
              <td className="py-md pr-lg text-on-surface-muted">{them}</td>
              <td className="py-md">{us}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
