import {
  Database,
  KeyRound,
  Plug,
  ShieldCheck,
  Signpost,
  SquareFunction,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import type { Layer } from "@/lib/views";

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

/** Layer colour classes, spelled out so Tailwind sees every one. */
export const LAYER_BG: Record<Layer, string> = {
  route: "bg-layer-route",
  middleware: "bg-layer-middleware",
  handler: "bg-layer-handler",
  model: "bg-layer-model",
  service: "bg-layer-service",
  env: "bg-layer-env",
};

export const LAYER_TEXT: Record<Layer, string> = {
  route: "text-layer-route",
  middleware: "text-layer-middleware",
  handler: "text-layer-handler",
  model: "text-layer-model",
  service: "text-layer-service",
  env: "text-layer-env",
};

export const LAYER_STROKE: Record<Layer, string> = {
  route: "var(--color-layer-route)",
  middleware: "var(--color-layer-middleware)",
  handler: "var(--color-layer-handler)",
  model: "var(--color-layer-model)",
  service: "var(--color-layer-service)",
  env: "var(--color-layer-env)",
};

export const LAYER_ICON: Record<Layer, LucideIcon> = {
  route: Signpost,
  middleware: ShieldCheck,
  handler: SquareFunction,
  model: Database,
  service: Plug,
  env: KeyRound,
};

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost";
  size?: "md" | "sm";
};

const BUTTON_BASE =
  "inline-flex items-center justify-center gap-sm rounded-md text-label-lg whitespace-nowrap transition-colors duration-[var(--ev-motion-feedback)] ease-standard disabled:opacity-50 disabled:pointer-events-none";

const BUTTON_VARIANT = {
  primary: "bg-primary text-on-primary hover:bg-primary-hover",
  secondary: "bg-surface-raised text-on-surface border border-outline hover:border-outline-strong",
  ghost: "text-on-surface-muted hover:text-on-surface hover:bg-surface-raised",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "secondary", size = "md", className, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      className={cx(
        BUTTON_BASE,
        BUTTON_VARIANT[variant],
        size === "md" ? "h-10 px-lg" : "h-8 px-md text-label-md",
        className,
      )}
      {...rest}
    />
  );
});

export function ButtonLink({
  href,
  variant = "secondary",
  children,
  className,
}: {
  href: string;
  variant?: "primary" | "secondary" | "ghost";
  children: ReactNode;
  className?: string;
}) {
  return (
    <Link href={href} className={cx(BUTTON_BASE, BUTTON_VARIANT[variant], "h-10 px-lg", className)}>
      {children}
    </Link>
  );
}

/** extracted = solid pill; inferred = recessed pill with the word repeated (DESIGN.md Shapes). */
export function SourceBadge({ inferred }: { inferred: boolean }) {
  return inferred ? (
    <span className="rounded-full border border-dashed border-outline-strong bg-surface px-sm py-[2px] font-condensed text-label-sm uppercase text-on-surface-muted">
      inferred
    </span>
  ) : (
    <span className="rounded-full border border-outline bg-surface-raised px-sm py-[2px] font-condensed text-label-sm uppercase text-on-surface">
      extracted
    </span>
  );
}

export function LayerTag({ layer, tag }: { layer: Layer; tag: string }) {
  const Icon = LAYER_ICON[layer];
  return (
    <span className="inline-flex items-center gap-xs rounded-sm bg-surface px-[6px] py-[2px] font-condensed text-label-sm uppercase text-on-surface-muted">
      <Icon aria-hidden size={12} strokeWidth={1.5} className={LAYER_TEXT[layer]} />
      {tag}
    </span>
  );
}

export function Severity({ severity }: { severity: "error" | "warning" | "info" }) {
  const cls =
    severity === "error"
      ? "text-error"
      : severity === "warning"
        ? "text-warning"
        : "text-on-surface-muted";
  return <span className={cx("font-condensed text-label-sm uppercase", cls)}>{severity}</span>;
}

/** EXHIBIT · path · L8–24: the sticker on every receipt. */
export function ExhibitTag({
  file,
  startLine,
  endLine,
  href,
}: {
  file: string;
  startLine: number;
  endLine: number;
  href?: string | null;
}) {
  const lines = startLine === endLine ? `L${startLine}` : `L${startLine}–${endLine}`;
  const body = (
    <>
      <span className="text-on-surface-muted">EXHIBIT ·</span>{" "}
      <span className="text-on-surface break-all">{file}</span>{" "}
      <span className="text-on-surface-muted">· {lines}</span>
    </>
  );
  const cls = "block rounded-sm bg-surface-sunken px-sm py-xs font-mono text-code-sm";
  return href ? (
    <a href={href} target="_blank" rel="noreferrer noopener" className={cx(cls, "hover:underline")}>
      {body}
    </a>
  ) : (
    <span className={cls}>{body}</span>
  );
}

export function Mono({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cx("font-mono tabular", className)}>{children}</span>;
}

export function shortSha(sha: string): string {
  return sha.slice(0, 7);
}
