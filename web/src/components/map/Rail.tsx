"use client";

import { Check } from "lucide-react";
import type { Finding } from "@/lib/schema";
import { LAYERS, LAYER_LABEL, layerOf, type Layer, type ViewKind } from "@/lib/views";
import type { GraphIndex } from "@/lib/graph";
import { LAYER_BG, LAYER_ICON, LAYER_TEXT, Mono, Severity, cx } from "../ui";

const VIEW_ITEMS: { kind: ViewKind; label: string }[] = [
  { kind: "overview", label: "System overview" },
  { kind: "routes", label: "Route map" },
  { kind: "data", label: "Data model" },
  { kind: "trace", label: "Request tracer" },
  { kind: "impact", label: "Blast radius" },
];

const SEVERITY_RANK = { error: 0, warning: 1, info: 2 } as const;

interface Props {
  idx: GraphIndex;
  view: ViewKind;
  hidden: ReadonlySet<Layer>;
  layerCounts: Record<Layer, number>;
  onView: (v: ViewKind) => void;
  onToggleLayer: (l: Layer) => void;
  onFinding: (f: Finding) => void;
  activeFinding?: string;
}

export function Rail(props: Props) {
  const findings = [...props.idx.graph.findings].sort(
    (a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity] || a.id.localeCompare(b.id),
  );
  const filterable = props.view === "overview" || props.view === "routes" || props.view === "data";
  return (
    <nav
      aria-label="Map controls"
      className="flex h-full w-60 shrink-0 flex-col overflow-y-auto border-r border-outline bg-surface px-md py-lg"
    >
      <RailHeading>Views</RailHeading>
      <ul className="flex flex-col">
        {VIEW_ITEMS.map((v) => (
          <li key={v.kind}>
            <button
              type="button"
              onClick={() => props.onView(v.kind)}
              aria-current={props.view === v.kind ? "page" : undefined}
              className={cx(
                "w-full rounded-sm px-sm py-xs text-left text-body-sm transition-colors duration-[var(--ev-motion-feedback)]",
                props.view === v.kind
                  ? "bg-surface-raised text-on-surface"
                  : "text-on-surface-muted hover:text-on-surface",
              )}
            >
              {v.label}
            </button>
          </li>
        ))}
      </ul>

      <RailHeading className="mt-xl">Layers</RailHeading>
      <ul className={cx("flex flex-col", !filterable && "opacity-50")}>
        {LAYERS.map((l) => {
          const Icon = LAYER_ICON[l];
          const on = !props.hidden.has(l);
          return (
            <li key={l}>
              <button
                type="button"
                role="checkbox"
                aria-checked={on}
                disabled={!filterable}
                onClick={() => props.onToggleLayer(l)}
                className="flex w-full items-center gap-sm rounded-sm px-sm py-xs text-left text-body-sm hover:bg-surface-raised"
              >
                <span
                  className={cx(
                    "flex h-4 w-4 items-center justify-center rounded-sm border",
                    on ? cx("border-transparent", LAYER_BG[l]) : "border-outline-strong",
                  )}
                >
                  {on && <Check size={12} strokeWidth={2.5} className="text-on-primary" />}
                </span>
                <Icon aria-hidden size={14} strokeWidth={1.5} className={LAYER_TEXT[l]} />
                <span className="flex-1">{LAYER_LABEL[l]}</span>
                <Mono className="text-code-sm text-on-surface-muted">{props.layerCounts[l]}</Mono>
              </button>
            </li>
          );
        })}
      </ul>

      <RailHeading className="mt-xl">
        Findings <Mono className="ml-xs text-on-surface-muted">{findings.length}</Mono>
      </RailHeading>
      {findings.length === 0 ? (
        <p className="px-sm text-body-sm text-on-surface-muted">No findings.</p>
      ) : (
        <ul className="flex flex-col gap-xs">
          {findings.map((f) => (
            <li key={f.id}>
              <button
                type="button"
                onClick={() => props.onFinding(f)}
                aria-current={props.activeFinding === f.id ? "true" : undefined}
                className={cx(
                  "flex w-full flex-col gap-xs rounded-sm px-sm py-sm text-left hover:bg-surface-raised",
                  props.activeFinding === f.id && "bg-surface-raised",
                )}
              >
                <span className="flex items-center gap-sm">
                  <Severity severity={f.severity} />
                  <Mono className="text-code-sm text-on-surface-muted">{f.rule}</Mono>
                </span>
                <span className="text-body-sm">{f.message}</span>
                <span className="flex flex-wrap gap-xs">
                  {f.nodeIds.slice(0, 3).map((id) => {
                    const n = props.idx.nodes.get(id);
                    if (!n) return null;
                    return (
                      <span
                        key={id}
                        className="max-w-full truncate rounded-sm bg-surface-sunken px-[6px] py-[2px] font-condensed text-label-sm"
                      >
                        <span className={LAYER_TEXT[layerOf(n.type)]}>■</span> {n.label}
                      </span>
                    );
                  })}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </nav>
  );
}

function RailHeading({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <h2
      className={cx(
        "mb-sm px-sm font-condensed text-label-sm uppercase text-on-surface-muted",
        className,
      )}
    >
      {children}
    </h2>
  );
}
