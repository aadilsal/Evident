"use client";

import { ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";
import { useSyncExternalStore } from "react";
import { currentPath, navDepth, subscribeNav } from "@/lib/navDepth";
import { cx } from "./ui";

type Target = "back" | "home" | "none";

function readTarget(): Target {
  if (navDepth() > 0) return "back";
  return currentPath() === "/" ? "none" : "home";
}

/**
 * Back is always offered except on the first page of a visit to the landing page: after
 * in-site navigation it goes back one step; on a page reached directly, it goes home.
 */
export function BackButton({ className }: { className?: string }) {
  const router = useRouter();
  const target = useSyncExternalStore(subscribeNav, readTarget, () => "none" as Target);
  if (target === "none") return null;
  return (
    <button
      type="button"
      onClick={() => (target === "back" ? router.back() : router.push("/"))}
      className={cx(
        "inline-flex h-8 items-center gap-xs rounded-md px-sm text-label-md text-on-surface-muted transition-colors duration-[var(--ev-motion-feedback)] hover:bg-surface-raised hover:text-on-surface",
        className,
      )}
      aria-label={target === "back" ? "Go back" : "Go to the home page"}
    >
      <ArrowLeft size={16} strokeWidth={1.5} />
      <span>{target === "back" ? "Back" : "Home"}</span>
    </button>
  );
}
