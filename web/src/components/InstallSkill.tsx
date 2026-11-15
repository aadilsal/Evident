"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { Mono } from "./ui";

export const SKILL_INSTALL = "npx skills add aadilsal/Evident";

/** The one-line install for coding agents, with a copy button. */
export function InstallSkill() {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(SKILL_INSTALL);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked: the command stays selectable */
    }
  }

  return (
    <div className="flex items-center gap-sm rounded-md border border-outline bg-surface-sunken py-xs pl-md pr-xs">
      <Mono className="select-all text-code-md text-on-surface-muted">$</Mono>
      <Mono className="min-w-0 flex-1 select-all truncate text-code-md">{SKILL_INSTALL}</Mono>
      <button
        type="button"
        onClick={copy}
        aria-label={copied ? "Copied" : "Copy the install command"}
        className="flex h-8 w-8 items-center justify-center rounded-sm text-on-surface-muted hover:bg-surface-raised hover:text-on-surface"
      >
        {copied ? <Check size={16} strokeWidth={1.5} /> : <Copy size={16} strokeWidth={1.5} />}
      </button>
    </div>
  );
}
