import Link from "next/link";
import { HeroMap } from "@/components/HeroMap";
import { RepoInput } from "@/components/RepoInput";
import { Page } from "@/components/SiteChrome";
import { Mono } from "@/components/ui";
import { benchmarkLatest, gallery, pct, STACKS } from "@/lib/data";

const STEPS = [
  {
    n: "01",
    title: "Extract",
    body: "tree-sitter parses every file as text. Framework and ORM adapters find routes, middleware, handlers, models, services and env vars. Nothing in the repo is installed or run.",
  },
  {
    n: "02",
    title: "Link",
    body: "Imports, path aliases and re-exports are resolved so a route connects to the handler, the calls it makes and the tables it reads and writes.",
  },
  {
    n: "03",
    title: "Group",
    body: "An LLM may only group and label nodes that already exist. Anything that references an unknown ID is dropped, and every group is marked inferred.",
  },
];

export default function Home() {
  const bench = benchmarkLatest();
  const featured = gallery();
  const total = bench.repos.length;
  const cats = ["routes", "models", "services", "edges"] as const;
  const frameworks = STACKS.adapters.filter((a) => a.kind === "framework").map((a) => a.label);
  const orms = STACKS.adapters.filter((a) => a.kind === "orm").map((a) => a.label);

  return (
    <Page>
      <section className="grid grid-cols-12 gap-xl pt-2xl pb-xl">
        <div className="col-span-12 lg:col-span-10">
          <h1 className="text-headline-lg sm:text-display">
            An architecture map where every arrow has a receipt.
          </h1>
          <p className="mt-lg max-w-2xl text-body-lg text-on-surface-muted">
            Paste a GitHub URL. Evident maps the routes, middleware, database models and external
            services, and links each box and arrow to the exact line of code that proves it.
          </p>
          <div className="mt-xl max-w-2xl">
            <RepoInput autoFocus />
            <p className="mt-sm text-body-sm text-on-surface-muted">
              Public repos only. Code is parsed, never run. Supports {frameworks.join(", ")} with{" "}
              {orms.join(", ")}.
            </p>
          </div>
        </div>
      </section>

      {featured[0] && (
        <section aria-label="Sample map">
          <HeroMap slug={featured[0].slug} />
        </section>
      )}

      <section className="mt-3xl grid grid-cols-12 gap-xl">
        <div className="col-span-12 md:col-span-4">
          <h2 className="text-headline-md">Measured, not promised</h2>
          <p className="mt-sm text-body-md text-on-surface-muted">
            A hand-labelled benchmark of {total} repos runs in CI on every change. A drop of more
            than 2 points fails the build.
          </p>
          <Link
            href="/benchmarks/"
            className="mt-md inline-block text-body-md underline underline-offset-4"
          >
            See the benchmark
          </Link>
        </div>
        <div className="col-span-12 md:col-span-8">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-outline text-label-sm uppercase text-on-surface-muted">
                <th className="py-sm font-condensed font-semibold">Category</th>
                <th className="py-sm text-right font-condensed font-semibold">Precision</th>
                <th className="py-sm text-right font-condensed font-semibold">Recall</th>
                <th className="py-sm text-right font-condensed font-semibold">Items</th>
              </tr>
            </thead>
            <tbody>
              {cats.map((c) => {
                const m = bench.categories[c];
                return (
                  <tr key={c} className="border-b border-outline">
                    <td className="py-sm capitalize">{c}</td>
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
      </section>

      <section className="mt-3xl">
        <h2 className="text-headline-md">How it works</h2>
        <ol className="mt-lg grid gap-xl md:grid-cols-3">
          {STEPS.map((s) => (
            <li key={s.n} className="border-t border-outline pt-md">
              <Mono className="text-code-sm text-on-surface-muted">{s.n}</Mono>
              <h3 className="mt-xs text-label-lg">{s.title}</h3>
              <p className="mt-sm text-body-md text-on-surface-muted">{s.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="mt-3xl grid gap-xl md:grid-cols-2">
        <div>
          <h2 className="text-headline-md">On your machine, and in Claude</h2>
          <p className="mt-sm text-body-md text-on-surface-muted">
            The same engine runs locally as a CLI and as a Claude skill. It works offline, writes
            only inside <Mono>.evident/</Mono>, and opens this map for a private repo without
            uploading anything.
          </p>
        </div>
        <pre className="overflow-x-auto rounded-md bg-surface-sunken p-lg font-mono text-code-md">
          <code>
            {`uv tool install "git+https://github.com/aadilsal/Evident#subdirectory=engine"
evident analyze .
evident trace "POST /api/users"
evident impact User
evident open`}
          </code>
        </pre>
      </section>

      <section className="mt-3xl">
        <div className="flex items-baseline justify-between">
          <h2 className="text-headline-md">Gallery</h2>
          <Link href="/gallery/" className="text-body-sm underline underline-offset-4">
            All maps
          </Link>
        </div>
        <ul className="mt-lg divide-y divide-outline border-y border-outline">
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
      </section>
    </Page>
  );
}
