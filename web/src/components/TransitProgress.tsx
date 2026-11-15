"use client";

import { animate, stagger } from "animejs";
import { useEffect, useMemo, useRef } from "react";
import { cx } from "./ui";

/** Pipeline stops, in order. Names match the worker's progress events. */
export const STOPS = [
  ["fetch", "Fetch"],
  ["parse", "Parse"],
  ["extract", "Extract"],
  ["link", "Link"],
  ["analyse", "Analyse"],
  ["group", "Group"],
] as const;
export type StopId = (typeof STOPS)[number][0];

function reducedMotion(): boolean {
  return (
    typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

const X0 = 24;
const X1 = 976;
const stopX = (i: number) => X0 + (i * (X1 - X0)) / (STOPS.length - 1);

/**
 * The pipeline as a transit line: track already run is solid, the stretch being worked on is
 * laid as you watch, and a highlighter train rides to each stop as its stage starts.
 */
export function TransitLine({ reached, failed }: { reached: number; failed: boolean }) {
  const train = useRef<HTMLDivElement>(null);
  const laying = useRef<SVGLineElement>(null);
  const lastStop = useRef(-1);

  // Ride to the new stop: the only motion is the train arriving where the work now is.
  useEffect(() => {
    const el = train.current;
    if (!el || reached < 0) return;
    const to = `${(stopX(reached) / 1000) * 100}%`;
    if (reducedMotion() || lastStop.current < 0) {
      el.style.left = to;
    } else {
      animate(el, { left: to, duration: 700, ease: "inOutCubic" });
    }
    lastStop.current = reached;
  }, [reached]);

  // Track being laid toward the next stop while this stage runs.
  useEffect(() => {
    const el = laying.current;
    if (!el || reducedMotion() || failed) return;
    const a = animate(el, {
      strokeDashoffset: [0, -24],
      duration: 700,
      ease: "linear",
      loop: true,
    });
    return () => {
      a.pause();
    };
  }, [reached, failed]);

  const atEnd = reached >= STOPS.length - 1;
  return (
    <div className="relative w-full max-w-[48rem] pt-lg" aria-label="Pipeline progress">
      <svg
        viewBox="0 0 1000 24"
        className="block h-6 w-full"
        aria-hidden
        preserveAspectRatio="none"
      >
        <line x1={X0} y1="12" x2={X1} y2="12" stroke="var(--color-outline)" strokeWidth="4" />
        {reached > 0 && (
          <line
            x1={X0}
            y1="12"
            x2={stopX(reached)}
            y2="12"
            stroke="var(--color-layer-route)"
            strokeWidth="4"
            strokeLinecap="round"
          />
        )}
        {reached >= 0 && !atEnd && (
          <line
            ref={laying}
            x1={stopX(reached)}
            y1="12"
            x2={stopX(reached + 1)}
            y2="12"
            stroke={failed ? "var(--color-error)" : "var(--color-layer-route)"}
            strokeWidth="4"
            strokeDasharray="12 12"
            opacity="0.6"
          />
        )}
        {STOPS.map(([id], i) => (
          <circle
            key={id}
            cx={stopX(i)}
            cy="12"
            r="7"
            fill={i < reached ? "var(--color-layer-route)" : "var(--color-surface)"}
            stroke={i <= reached ? "var(--color-layer-route)" : "var(--color-outline-strong)"}
            strokeWidth="3"
          />
        ))}
      </svg>
      {reached >= 0 && (
        <div
          ref={train}
          aria-hidden
          className="absolute top-0 -translate-x-1/2"
          style={{ left: `${(stopX(reached) / 1000) * 100}%` }}
        >
          <svg width="34" height="18" viewBox="0 0 34 18">
            <rect x="1" y="1" width="32" height="13" rx="5" fill="var(--color-primary)" />
            <rect x="6" y="4" width="6" height="5" rx="1.5" fill="var(--color-on-primary)" />
            <rect x="14" y="4" width="6" height="5" rx="1.5" fill="var(--color-on-primary)" />
            <rect x="22" y="4" width="6" height="5" rx="1.5" fill="var(--color-on-primary)" />
            <circle cx="9" cy="16" r="1.8" fill="var(--color-on-surface-muted)" />
            <circle cx="25" cy="16" r="1.8" fill="var(--color-on-surface-muted)" />
          </svg>
        </div>
      )}
      <ol className="relative mt-xs h-6 w-full">
        {STOPS.map(([id, label], i) => (
          <li
            key={id}
            className={cx(
              "absolute -translate-x-1/2 text-label-md",
              i <= reached ? "text-on-surface" : "text-on-surface-muted",
            )}
            style={{ left: `${(stopX(i) / 1000) * 100}%` }}
            aria-current={i === reached ? "step" : undefined}
          >
            {label}
          </li>
        ))}
      </ol>
    </div>
  );
}

const FOUND: Record<StopId, (c: Record<string, number>) => string> = {
  fetch: () => "",
  parse: (c) => (c.files ? `${c.files} files` : ""),
  extract: (c) => (c.parsed !== undefined ? `${c.parsed} parsed` : ""),
  link: (c) => (c.routes !== undefined ? `${c.routes} routes · ${c.nodes ?? 0} nodes` : ""),
  analyse: (c) => (c.findings !== undefined ? `${c.findings} findings` : ""),
  group: (c) => (c.groups !== undefined ? `${c.groups} groups` : ""),
};

/** A departures board: each stage's status, when it left, and what it found. */
export function DeparturesBoard({
  reached,
  times,
  counts,
  failed,
}: {
  reached: number;
  times: Partial<Record<StopId, number>>;
  counts: Record<string, number>;
  failed: boolean;
}) {
  const start = times.fetch;
  return (
    <div
      aria-live="polite"
      className="w-full max-w-[34rem] overflow-hidden rounded-md border border-outline bg-surface-sunken text-left"
    >
      <div className="flex items-center justify-between border-b border-outline px-md py-xs font-condensed text-label-sm uppercase text-on-surface-muted">
        <span>Departures</span>
        <span>Evident line</span>
      </div>
      <table className="w-full font-mono text-code-sm tabular">
        <tbody>
          {STOPS.map(([id, label], i) => {
            const status =
              i < reached ? "departed" : i === reached ? (failed ? "stopped" : "boarding") : "";
            const t = times[STOPS[i + 1]?.[0]] ?? (i < reached ? times[id] : undefined);
            const elapsed = start && t && i < reached ? `+${((t - start) / 1000).toFixed(1)}s` : "";
            return (
              <tr key={id} className="border-b border-outline last:border-0">
                <td className="w-24 px-md py-xs text-on-surface">{label}</td>
                <td
                  className={cx(
                    "w-24 py-xs uppercase",
                    status === "boarding" && "text-layer-route",
                    status === "stopped" && "text-error",
                    status === "departed" && "text-on-surface-muted",
                  )}
                >
                  {status || "·"}
                </td>
                <td className="py-xs text-on-surface-muted">{FOUND[id](counts)}</td>
                <td className="w-16 px-md py-xs text-right text-on-surface-muted">{elapsed}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

const MAX_ROUTES = 60;
const MAX_OTHER = 90;
const MAX_FINDINGS = 24;

/** The map assembling itself: one square per node found, in layer colours, as counts arrive. */
export function AssemblingMap({ counts }: { counts: Record<string, number> }) {
  const box = useRef<HTMLDivElement>(null);
  const shown = useRef(0);
  const routes = Math.min(counts.routes ?? 0, MAX_ROUTES);
  const other = Math.min(Math.max((counts.nodes ?? 0) - (counts.routes ?? 0), 0), MAX_OTHER);
  const findings = Math.min(counts.findings ?? 0, MAX_FINDINGS);
  const cells = useMemo(
    () => [
      ...Array.from({ length: routes }, () => "bg-layer-route"),
      ...Array.from({ length: other }, () => "bg-layer-handler"),
      ...Array.from({ length: findings }, () => "bg-warning"),
    ],
    [routes, other, findings],
  );

  // Only the newly found nodes pop in, left to right.
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const fresh = [...el.children].slice(shown.current) as HTMLElement[];
    shown.current = el.children.length;
    if (!fresh.length || reducedMotion()) return;
    animate(fresh, {
      scale: [0, 1],
      opacity: [0, 1],
      duration: 260,
      delay: stagger(8),
      ease: "outBack(1.6)",
    });
  }, [cells.length]);

  if (!cells.length) return null;
  const total = (counts.nodes ?? 0) + (counts.findings ?? 0);
  return (
    <figure className="flex w-full max-w-[34rem] flex-col items-center gap-sm">
      <div ref={box} aria-hidden className="flex flex-wrap justify-center gap-[3px]">
        {cells.map((c, i) => (
          <span key={i} className={cx("h-2.5 w-2.5 rounded-[2px]", c)} />
        ))}
      </div>
      <figcaption className="text-body-sm text-on-surface-muted">
        {total} things found so far
        {cells.length < total ? " (sample shown)" : ""}: routes in blue, code in grey, findings in
        amber.
      </figcaption>
    </figure>
  );
}
