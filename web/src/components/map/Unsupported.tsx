import type { Graph } from "@/lib/graph";
import { ButtonLink, Mono } from "../ui";

/** Graceful fallback when the stack is detected but no adapter covers it yet. */
export function Unsupported({ graph }: { graph: Graph }) {
  const stack = graph.stack;
  const repo = graph.repo.owner ? `${graph.repo.owner}/${graph.repo.name}` : graph.repo.name;
  return (
    <main className="mx-auto flex min-h-dvh max-w-2xl flex-col justify-center gap-lg px-xl py-3xl">
      <Mono className="text-code-sm text-on-surface-muted">{repo}</Mono>
      <h1 className="text-headline-lg">We can&apos;t map this stack yet</h1>
      <p className="text-body-lg text-on-surface-muted">
        {stack?.message ??
          "No supported framework or ORM was found, so there are no routes or models to draw."}
      </p>
      {stack && (
        <dl className="grid grid-cols-[max-content_1fr] gap-x-lg gap-y-sm text-body-md">
          <dt className="text-on-surface-muted">Detected</dt>
          <dd>
            <Mono>{stack.detected.join(", ") || "nothing recognised"}</Mono>
          </dd>
          {stack.unsupported && stack.unsupported.length > 0 && (
            <>
              <dt className="text-on-surface-muted">Not supported yet</dt>
              <dd>
                <Mono>{stack.unsupported.join(", ")}</Mono>
              </dd>
            </>
          )}
        </dl>
      )}
      <p className="text-body-md text-on-surface-muted">
        We&apos;d rather show nothing than guess. Imports, env vars and services were still
        extracted and are in the graph JSON.
      </p>
      <div className="flex flex-wrap gap-sm">
        <ButtonLink href="/stacks/" variant="primary">
          See supported stacks
        </ButtonLink>
        <ButtonLink href="/gallery/">Try a gallery map</ButtonLink>
      </div>
    </main>
  );
}
