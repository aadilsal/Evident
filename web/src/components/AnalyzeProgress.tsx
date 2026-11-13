"use client";

import { animate } from "animejs";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { API_URL } from "@/lib/source";
import { parseGithubUrl } from "@/lib/url";
import { ButtonLink, Mono, cx } from "./ui";

/** Six-stop transit line (DESIGN.md: Pipeline progress). Stage names match the worker's events. */
const STOPS = [
  ["fetch", "Fetch"],
  ["parse", "Parse"],
  ["extract", "Extract"],
  ["link", "Link"],
  ["analyse", "Analyse"],
  ["group", "Group"],
] as const;
type Stage = (typeof STOPS)[number][0] | "queued" | "done" | "failed";

interface Progress {
  stage: Stage;
  counts: Record<string, number>;
  error?: string;
}

const COUNT_LABEL: Record<string, string> = {
  files: "files",
  parsed: "parsed",
  nodes: "nodes",
  edges: "edges",
  routes: "routes",
  findings: "findings",
  groups: "groups",
};

function Count({ value, label }: { value: number; label: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      el.textContent = String(value);
      return;
    }
    const state = { n: Number(el.textContent) || 0 };
    const a = animate(state, {
      n: value,
      duration: 600,
      ease: "outQuad",
      onUpdate: () => {
        el.textContent = String(Math.round(state.n));
      },
    });
    return () => {
      a.pause();
    };
  }, [value]);
  return (
    <Mono className="text-code-sm text-on-surface-muted">
      <span ref={ref}>0</span> {label}
    </Mono>
  );
}

export function AnalyzeProgress() {
  const params = useSearchParams();
  const router = useRouter();
  const url = params.get("url") ?? "";
  const gh = parseGithubUrl(url);
  const [progress, setProgress] = useState<Progress>({ stage: "queued", counts: {} });
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!gh || !API_URL) return;
    let source: EventSource | null = null;
    let live = true;
    const fail = (message: string) => live && setError(message);

    const finish = (sha: string) => {
      router.replace(`/map/?repo=${gh.owner}/${gh.repo}&sha=${sha}`);
    };

    (async () => {
      let res: Response;
      try {
        res = await fetch(`${API_URL}/api/analyses`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url }),
        });
      } catch {
        return fail(
          "Couldn't reach the analysis service. It may be down; try a gallery map meanwhile.",
        );
      }
      const body = (await res.json().catch(() => ({}))) as {
        status?: string;
        sha?: string;
        jobId?: string;
        detail?: string;
      };
      if (!res.ok) return fail(body.detail ?? `The service refused this repo (${res.status}).`);
      if (body.status === "done" && body.sha) return finish(body.sha);
      if (!body.jobId || !body.sha) return fail("The service gave an unexpected answer.");
      const sha = body.sha;
      source = new EventSource(`${API_URL}/api/analyses/${body.jobId}/events`);
      source.addEventListener("progress", (e) => {
        const p = JSON.parse((e as MessageEvent<string>).data) as Progress;
        setProgress(p);
        setCounts((c) => ({ ...c, ...p.counts }));
        if (p.stage === "done") {
          source?.close();
          finish(sha);
        } else if (p.stage === "failed") {
          source?.close();
          fail(p.error ?? "The analysis failed.");
        }
      });
      source.onerror = () => {
        if (source?.readyState === EventSource.CLOSED)
          fail("Lost the progress stream. Reload to check again.");
      };
    })();

    return () => {
      live = false;
      source?.close();
    };
    // gh is derived from url; re-run only when the URL changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url]);

  if (!gh) {
    return (
      <Shell>
        <p role="alert">That isn&apos;t a GitHub repo URL.</p>
        <ButtonLink href="/">Back</ButtonLink>
      </Shell>
    );
  }
  if (!API_URL) {
    return (
      <Shell>
        <p>This build has no analysis service. Run Evident locally instead:</p>
        <pre className="rounded-md bg-surface-sunken p-md font-mono text-code-md">
          evident analyze {url}
          {"\n"}evident open
        </pre>
      </Shell>
    );
  }

  const reached = STOPS.findIndex(([s]) => s === progress.stage);
  return (
    <Shell>
      <Mono className="break-all text-code-md">
        {gh.owner}/{gh.repo}
        {gh.ref ? ` @ ${gh.ref}` : ""}
      </Mono>
      <h1 className="text-headline-md">
        {error ? "Analysis stopped" : progress.stage === "queued" ? "Queued" : "Mapping the repo"}
      </h1>
      <ol
        className="relative mt-lg flex w-full max-w-[48rem] justify-between"
        aria-label="Pipeline progress"
      >
        <span aria-hidden className="absolute left-2 right-2 top-[7px] h-[3px] bg-outline" />
        <span
          aria-hidden
          className="absolute left-2 top-[7px] h-[3px] bg-layer-route transition-[width] duration-[var(--ev-motion-panel)] ease-standard"
          style={{
            width: reached < 0 ? 0 : `calc(${(reached / (STOPS.length - 1)) * 100}% - 16px)`,
          }}
        />
        {STOPS.map(([stage, label], i) => {
          const state = i < reached ? "done" : i === reached ? "now" : "todo";
          return (
            <li
              key={stage}
              className="relative flex flex-col items-center gap-sm"
              aria-current={state === "now" ? "step" : undefined}
            >
              <span
                className={cx(
                  "h-4 w-4 rounded-full border-[3px]",
                  state === "todo" ? "border-outline bg-surface" : "border-layer-route",
                  state === "done" ? "bg-layer-route" : "bg-surface",
                )}
              />
              <span
                className={cx(
                  "text-label-md",
                  state === "todo" ? "text-on-surface-muted" : "text-on-surface",
                )}
              >
                {label}
              </span>
            </li>
          );
        })}
      </ol>
      <div className="mt-md flex flex-wrap justify-center gap-x-lg gap-y-xs" aria-live="polite">
        {Object.entries(counts)
          .filter(([k]) => COUNT_LABEL[k])
          .map(([k, v]) => (
            <Count key={k} value={v} label={COUNT_LABEL[k]} />
          ))}
      </div>
      {error && (
        <div className="mt-lg flex flex-col items-center gap-md">
          <p role="alert" className="max-w-[32rem] text-center text-error">
            {error}
          </p>
          <ButtonLink href="/gallery/">Open a gallery map</ButtonLink>
        </div>
      )}
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="mx-auto flex min-h-dvh max-w-4xl flex-col items-center justify-center gap-md px-lg text-center">
      {children}
    </main>
  );
}
