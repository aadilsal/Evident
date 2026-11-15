import { cx } from "./ui";

// The route "e": one transit line drawn as a lowercase e, ending at a highlighter station (DESIGN.md Logo).
const ROUTE = "M10 25H38V19Q38 11 30 11H18Q10 11 10 19V29Q10 37 18 37H31";
// Small sizes thicken the line and enlarge the station so the mark survives 16 px.
const SMALL_ROUTE = "M10 25H38V19Q38 11 30 11H18Q10 11 10 19V29Q10 37 18 37H30";

export function LogoMark({ size = 20, className }: { size?: number; className?: string }) {
  const small = size <= 24;
  return (
    <svg
      viewBox="0 0 48 48"
      width={size}
      height={size}
      aria-hidden="true"
      className={cx("shrink-0", className)}
    >
      <path
        d={small ? SMALL_ROUTE : ROUTE}
        fill="none"
        stroke="var(--color-on-surface)"
        strokeWidth={small ? 5.5 : 4.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle
        cx={small ? 36.5 : 36}
        cy="37"
        r={small ? 4.8 : 4.2}
        fill="var(--color-primary)"
        stroke="var(--ev-logo-ring)"
        strokeWidth="2"
      />
    </svg>
  );
}

/** Mark + lowercase wordmark. The accessible name is the product name. */
export function Logo({ size = 20, className }: { size?: number; className?: string }) {
  return (
    <span className={cx("inline-flex items-center gap-sm", className)}>
      <LogoMark size={size} />
      <span
        className="font-semibold tracking-[-0.02em] text-on-surface"
        style={{ fontSize: Math.round(size * 0.9) }}
      >
        evident
      </span>
    </span>
  );
}
