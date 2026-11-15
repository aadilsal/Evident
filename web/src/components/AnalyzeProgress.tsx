"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { API_URL } from "@/lib/source";
import { parseGithubUrl } from "@/lib/url";
import { AssemblingMap, DeparturesBoard, STOPS, TransitLine, type StopId } from "./TransitProgress";
import { ButtonLink, Mono } from "./ui";
import { BackButton } from "./BackButton";

/** DESIGN.md: Pipeline progress. Stage names match the worker's events. */
type Stage = StopId | "queued" | "done" | "failed";

interface Progress {
  stage: Stage;
  counts: Record<string, number>;
  error?: string;
}

export function AnalyzeProgress() {
  const params = useSearchParams();
  const router = useRouter();
  const url = params.get("url") ?? "";
  const gh = parseGithubUrl(url);
  const [progress, setProgress] = useState<Progress>({ stage: "queued", counts: {} });
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [error, setError] = useState<string | null>(null);
  const [times, setTimes] = useState<Partial<Record<StopId, number>>>({});

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
        const stop = p.stage as StopId;
        if (STOPS.some(([s]) => s === stop))
          setTimes((t) => (t[stop] ? t : { ...t, [stop]: Date.now() }));
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
      <TransitLine reached={reached} failed={Boolean(error)} />
      <div className="mt-lg flex w-full flex-col items-center gap-xl">
        <DeparturesBoard reached={reached} times={times} counts={counts} failed={Boolean(error)} />
        <AssemblingMap counts={counts} />
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
    <main className="relative mx-auto flex min-h-dvh max-w-4xl flex-col items-center justify-center gap-md px-lg text-center">
      <BackButton className="absolute left-lg top-lg" />
      {children}
    </main>
  );
}
