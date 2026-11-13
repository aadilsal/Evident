"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { BenchmarkRun } from "@/lib/data";

const SERIES = [
  ["routes", "var(--color-layer-route)"],
  ["models", "var(--color-layer-model)"],
  ["services", "var(--color-layer-service)"],
  ["edges", "var(--color-layer-middleware)"],
] as const;

/** F1 per category over time, one line per category in layer colours; launch target dashed. */
export function HistoryChart({
  runs,
  metric = "f1",
}: {
  runs: BenchmarkRun[];
  metric?: "f1" | "precision" | "recall";
}) {
  const data = runs.map((r) => ({
    date: r.date,
    repos: r.repos,
    ...Object.fromEntries(SERIES.map(([c]) => [c, +(r.categories[c][metric] * 100).toFixed(1)])),
  }));
  return (
    <figure>
      <div className="h-64 w-full">
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
            <CartesianGrid stroke="var(--color-outline)" vertical={false} />
            <XAxis
              dataKey="date"
              stroke="var(--color-on-surface-muted)"
              tick={{ fontSize: 12, fontFamily: "var(--font-mono)" }}
            />
            <YAxis
              domain={[80, 100]}
              unit="%"
              stroke="var(--color-on-surface-muted)"
              tick={{ fontSize: 12, fontFamily: "var(--font-mono)" }}
              width={48}
            />
            <ReferenceLine
              y={90}
              stroke="var(--color-on-surface-muted)"
              strokeDasharray="6 4"
              label={{
                value: "target 90%",
                fill: "var(--color-on-surface-muted)",
                fontSize: 12,
                position: "insideBottomRight",
              }}
            />
            <Tooltip
              contentStyle={{
                background: "var(--color-surface-raised)",
                border: "1px solid var(--color-outline)",
                borderRadius: 6,
                fontFamily: "var(--font-mono)",
                fontSize: 12,
              }}
            />
            {SERIES.map(([c, color]) => (
              <Line
                key={c}
                type="linear"
                dataKey={c}
                stroke={color}
                strokeWidth={2}
                dot={{ r: 3 }}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="mt-sm flex flex-wrap gap-lg text-body-sm text-on-surface-muted">
        {SERIES.map(([c, color]) => (
          <span key={c} className="inline-flex items-center gap-xs">
            <span aria-hidden className="h-[3px] w-4" style={{ background: color }} />
            {c}
          </span>
        ))}
        <span className="inline-flex items-center gap-xs">
          <span aria-hidden className="w-4 border-t border-dashed border-on-surface-muted" />
          launch target
        </span>
      </figcaption>
    </figure>
  );
}
