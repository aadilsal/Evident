"use client";

import { Download, FileText, Link2, Search } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { Graph } from "@/lib/graph";
import { Button, Mono, shortSha } from "../ui";
import { ThemeToggle } from "../ThemeToggle";

interface Props {
  graph: Graph;
  reportHref: string;
  onSearch: () => void;
  onExport: (format: "png" | "svg" | "json") => void;
}

export function TopBar({ graph, reportHref, onSearch, onExport }: Props) {
  const [copied, setCopied] = useState(false);
  const [menu, setMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const repo = graph.repo.owner ? `${graph.repo.owner}/${graph.repo.name}` : graph.repo.name;
  const repoHref =
    graph.repo.host === "github.com" && graph.repo.owner
      ? `https://github.com/${graph.repo.owner}/${graph.repo.name}/tree/${graph.repo.sha}`
      : null;

  useEffect(() => {
    if (!menu) return;
    function close(e: MouseEvent) {
      if (!menuRef.current?.contains(e.target as Node)) setMenu(false);
    }
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [menu]);

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked: the URL bar still has the permalink */
    }
  }

  return (
    <header className="no-print flex h-14 shrink-0 items-center gap-md border-b border-outline bg-surface px-lg">
      <Link href="/" className="font-condensed text-label-lg tracking-wide">
        EVIDENT
      </Link>
      <span className="h-5 w-px bg-outline" aria-hidden />
      <div className="flex min-w-0 flex-1 items-baseline gap-sm">
        {repoHref ? (
          <a
            href={repoHref}
            target="_blank"
            rel="noreferrer noopener"
            className="truncate font-mono text-code-md hover:underline"
          >
            {repo}
          </a>
        ) : (
          <Mono className="truncate text-code-md">{repo}</Mono>
        )}
        <Mono className="text-code-sm text-on-surface-muted">@ {shortSha(graph.repo.sha)}</Mono>
        {graph.repo.dirty && (
          <span className="text-label-sm text-warning">uncommitted changes</span>
        )}
      </div>
      <Button variant="ghost" size="sm" onClick={onSearch} aria-label="Find a node (Ctrl K)">
        <Search size={16} strokeWidth={1.5} />
        <span className="hidden lg:inline">Find</span>
        <kbd className="hidden rounded-sm border border-outline px-xs font-mono text-code-sm text-on-surface-muted lg:inline">
          ⌘K
        </kbd>
      </Button>
      <div className="relative" ref={menuRef}>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setMenu(!menu)}
          aria-expanded={menu}
          aria-haspopup="menu"
        >
          <Download size={16} strokeWidth={1.5} />
          <span className="hidden lg:inline">Export</span>
        </Button>
        {menu && (
          <div
            role="menu"
            className="float-shadow absolute right-0 top-10 z-30 w-56 rounded-md border border-outline bg-surface-raised p-xs"
          >
            {(
              [
                ["png", "PNG image of this view"],
                ["svg", "SVG image of this view"],
                ["json", "Graph JSON"],
              ] as const
            ).map(([f, label]) => (
              <button
                key={f}
                role="menuitem"
                type="button"
                onClick={() => {
                  setMenu(false);
                  onExport(f);
                }}
                className="block w-full rounded-sm px-sm py-sm text-left text-body-sm hover:bg-surface-sunken"
              >
                {label}
              </button>
            ))}
            <Link
              role="menuitem"
              href={reportHref}
              className="flex items-center gap-sm rounded-sm px-sm py-sm text-body-sm hover:bg-surface-sunken"
            >
              <FileText size={14} strokeWidth={1.5} /> Architecture report (PDF)
            </Link>
          </div>
        )}
      </div>
      <Button
        variant="ghost"
        size="sm"
        onClick={copyLink}
        aria-label="Copy a permalink to this view"
      >
        <Link2 size={16} strokeWidth={1.5} />
        <span className="hidden lg:inline">{copied ? "Copied" : "Copy link"}</span>
      </Button>
      <ThemeToggle />
    </header>
  );
}
