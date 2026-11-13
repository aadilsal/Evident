import Link from "next/link";
import { HeroMap } from "@/components/HeroMap";
import { CompareTable, Section, TraceExhibit, TransitSteps } from "@/components/landing";
import { RepoInput } from "@/components/RepoInput";
import { Page } from "@/components/SiteChrome";
import { ButtonLink, Mono, Severity } from "@/components/ui";
import { benchmarkLatest, gallery, pct, STACKS } from "@/lib/data";
import { showcase } from "@/lib/showcase";

const USES = [
  {
    name: "On the web",
    body: "Paste a public GitHub URL and get the map in under a minute. Every view has a link you can share, pinned to the commit.",
    code: "github.com/owner/repo  →  Map this repo",
  },
  {
    name: "In your terminal",
    body: "The same engine runs offline on private code. It writes only inside .evident/ and opens this map on localhost.",
    code: 'evident analyze .\nevident trace "POST /api/orders"\nevident impact Order\nevident open',
  },
  {
    name: "Inside Claude",
    body: "A Claude skill checks the blast radius before an agent edits a model, and cites file:line instead of guessing.",
    code: "skills/evident  →  evident impact User\n“3 routes write User: …”",
  },
];

export default function Home() {
  const bench = benchmarkLatest();
  const featured = gallery();
  const sample = featured[0] ? showcase(featured[0].slug) : null;
  const totalRepos = bench.repos.length;
  const frameworks = STACKS.adapters.filter((a) => a.kind === "framework").map((a) => a.label);
  const orms = STACKS.adapters.filter((a) => a.kind === "orm").map((a) => a.label);
  const routes = bench.categories.routes;
  const edges = bench.categories.edges;

  return (
    <Page>
      {/* 1. What it is, in one screen. */}
      <section className="grid grid-cols-12 gap-x-xl gap-y-2xl pt-2xl pb-xl">
        <div className="col-span-12 lg:col-span-7">
          <p className="font-condensed text-label-sm uppercase text-on-surface-muted">
            Architecture maps for JS/TS and Python web apps
          </p>
          <h1 className="mt-md text-headline-lg sm:text-display">
            Every arrow on this map has a receipt.
          </h1>
          <p className="mt-lg max-w-[36rem] text-body-lg text-on-surface-muted">
            Evident reads a codebase and draws what talks to what: routes, middleware, database
            tables and external services. Click anything and it shows the exact lines of code that
            prove it.
          </p>
          <div className="mt-xl max-w-[36rem]">
            <RepoInput autoFocus />
          </div>
          <ul className="mt-lg flex flex-wrap gap-x-lg gap-y-xs text-body-sm text-on-surface-muted">
            <li>
              <Mono className="text-on-surface">{pct(routes.precision)}</Mono> route precision
            </li>
            <li>
              <Mono className="text-on-surface">{pct(edges.recall)}</Mono> route→table recall
            </li>
            <li>
              <Mono className="text-on-surface">{totalRepos}</Mono> benchmark repos
            </li>
            <li>
              <Mono className="text-on-surface">0</Mono> lines of your code executed
            </li>
          </ul>
        </div>
        {sample && (
          <div className="col-span-12 lg:col-span-5">
            <TraceExhibit
              route={sample.trace.route}
              hops={sample.trace.hops}
              repo={sample.repo}
              sha={sample.sha}
            />
            <p className="mt-sm text-body-sm text-on-surface-muted">
              A real trace from the gallery. Each hop cites the line that creates it.
            </p>
          </div>
        )}
      </section>

      {/* 2. The product itself, not a screenshot. */}
      {featured[0] && (
        <section aria-label="Live sample map" className="pb-2xl">
          <HeroMap slug={featured[0].slug} />
        </section>
      )}

      {/* 3. Why it exists. */}
      <Section
        id="why"
        eyebrow="Why Evident"
        title="Most architecture diagrams are guesses. This one shows its work."
        lead="AI diagram tools ask a model to imagine your system from its folders. The result looks right until a box turns out not to exist. Evident extracts the facts first and lets the model do one small, checked job."
      >
        <CompareTable />
      </Section>

      {/* 4. How it works. */}
      <Section
        id="how"
        eyebrow="How it works"
        title="Five stops from repo to map"
        lead="The same pipeline runs on the web, in the CLI and in the Claude skill. Only the last stop involves an LLM, and its output is validated against the graph."
        className="mt-3xl"
      >
        <TransitSteps />
      </Section>

      {/* 5. What you can ask it, with real answers. */}
      {sample && (
        <Section
          id="questions"
          eyebrow="What it answers"
          title="The questions you have on day one of a new codebase"
          className="mt-3xl"
        >
          <div className="grid gap-2xl md:grid-cols-3">
            <div className="border-t-[3px] border-layer-route pt-md">
              <h3 className="text-headline-md">What does this request do?</h3>
              <p className="mt-sm text-body-md text-on-surface-muted">
                Pick a route. The path lights up through middleware, handlers and calls to every
                table and service it touches, with the code for each hop.
              </p>
              <Mono className="mt-md block text-code-sm">
                {sample.trace.route} → {sample.trace.hops.length - 1} hops
              </Mono>
            </div>
            <div className="border-t-[3px] border-layer-model pt-md">
              <h3 className="text-headline-md">What breaks if I change this?</h3>
              <p className="mt-sm text-body-md text-on-surface-muted">
                Select a table, file or env var and see everything that depends on it before you
                edit it.
              </p>
              {sample.blast.model && (
                <Mono className="mt-md block text-code-sm">
                  {sample.blast.model}: {sample.blast.routes.length} routes, {sample.blast.total}{" "}
                  dependents
                </Mono>
              )}
            </div>
            <div className="border-t-[3px] border-layer-middleware pt-md">
              <h3 className="text-headline-md">Is this endpoint safe?</h3>
              <p className="mt-sm text-body-md text-on-surface-muted">
                Health checks flag writes with no auth guard, unvalidated request bodies, import
                cycles, unused models and undocumented env vars.
              </p>
              {sample.finding && (
                <p className="mt-md text-code-sm">
                  <Severity severity={sample.finding.severity as "error" | "warning" | "info"} />{" "}
                  <span className="text-body-sm">{sample.finding.message}</span>
                </p>
              )}
            </div>
          </div>
          <p className="mt-xl text-body-sm text-on-surface-muted">
            Examples from{" "}
            <Link href={`/map/?gallery=${sample.slug}`} className="underline underline-offset-4">
              {sample.repo}
            </Link>
            , {sample.counts.routes} routes, {sample.counts.models} models, {sample.counts.services}{" "}
            services.
          </p>
        </Section>
      )}

      {/* 6. Proof. */}
      <Section
        id="accuracy"
        eyebrow="Accuracy"
        title="Measured, not promised"
        lead={`${totalRepos} repos, each pinned to a commit and labelled by hand. Every engine change is scored in CI, and the build fails if any number drops by more than 2 points.`}
        className="mt-3xl"
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[32rem] text-left">
            <thead>
              <tr className="border-b border-outline font-condensed text-label-sm uppercase text-on-surface-muted">
                <th className="py-sm font-semibold">Category</th>
                <th className="py-sm text-right font-semibold">Precision</th>
                <th className="py-sm text-right font-semibold">Recall</th>
                <th className="py-sm text-right font-semibold">Labelled items</th>
              </tr>
            </thead>
            <tbody>
              {(["routes", "models", "services", "edges"] as const).map((c) => {
                const m = bench.categories[c];
                return (
                  <tr key={c} className="border-b border-outline">
                    <td className="py-sm capitalize">
                      {c === "edges" ? "route → table edges" : c}
                    </td>
                    <td className="py-sm text-right">
                      <Mono>{pct(m.precision)}</Mono>
                    </td>
                    <td className="py-sm text-right">
                      <Mono>{pct(m.recall)}</Mono>
                    </td>
                    <td className="py-sm text-right">
                      <Mono className="text-on-surface-muted">{(m.tp ?? 0) + (m.fn ?? 0)}</Mono>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="mt-md text-body-sm text-on-surface-muted">
          <Link href="/benchmarks/" className="underline underline-offset-4">
            Full results and history
          </Link>{" "}
          · Supports {frameworks.join(", ")} with {orms.join(", ")}.{" "}
          <Link href="/stacks/" className="underline underline-offset-4">
            Per-adapter scores
          </Link>
        </p>
      </Section>

      {/* 7. Where to use it. */}
      <Section
        id="use"
        eyebrow="Three ways to use it"
        title="Same engine, wherever you work"
        className="mt-3xl"
      >
        <div className="grid gap-2xl md:grid-cols-3">
          {USES.map((u) => (
            <div key={u.name}>
              <h3 className="text-label-lg">{u.name}</h3>
              <p className="mt-sm text-body-md text-on-surface-muted">{u.body}</p>
              <pre className="mt-md overflow-x-auto rounded-md bg-surface-sunken p-md font-mono text-code-sm">
                <code>{u.code}</code>
              </pre>
            </div>
          ))}
        </div>
      </Section>

      {/* 8. Try it. */}
      <Section
        id="gallery"
        eyebrow="Try it now"
        title="Open a pre-analysed map, or map your own repo"
        className="mt-3xl"
      >
        <ul className="divide-y divide-outline border-y border-outline">
          {featured.map((g) => (
            <li key={g.slug}>
              <Link
                href={`/map/?gallery=${g.slug}`}
                className="flex flex-wrap items-baseline gap-x-lg gap-y-xs py-md hover:bg-surface-raised"
              >
                <Mono className="text-code-md">{g.repo}</Mono>
                <span className="text-body-sm text-on-surface-muted">{g.blurb}</span>
                <Mono className="ml-auto text-code-sm tabular text-on-surface-muted">
                  {g.routes} routes · {g.models} models · {g.findings} findings
                </Mono>
              </Link>
            </li>
          ))}
        </ul>
        <div className="mt-2xl grid gap-lg md:grid-cols-[1fr_auto] md:items-center">
          <div className="max-w-[36rem]">
            <RepoInput />
          </div>
          <ButtonLink href="/gallery/">Browse the gallery</ButtonLink>
        </div>
      </Section>
    </Page>
  );
}
