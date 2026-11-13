import type { Metadata } from "next";
import { Page } from "@/components/SiteChrome";
import { Mono } from "@/components/ui";
import { benchmarkLatest, pct, STACKS } from "@/lib/data";

export const metadata: Metadata = { title: "Supported stacks" };

const ECOSYSTEM: Record<string, string> = { js: "JavaScript / TypeScript", py: "Python" };

export default function StacksPage() {
  const bench = benchmarkLatest();
  const groups = Object.entries(
    STACKS.adapters.reduce<Record<string, typeof STACKS.adapters>>((acc, a) => {
      (acc[a.ecosystem] ??= []).push(a);
      return acc;
    }, {}),
  );
  return (
    <Page>
      <h1 className="pt-2xl text-headline-lg">Supported stacks</h1>
      <p className="mt-sm max-w-[48rem] text-body-lg text-on-surface-muted">
        Imports, env vars, external SDKs and docker-compose services are found in any JS, TS or
        Python repo. Routes and models need an adapter for the framework or ORM. Scores are from the
        benchmark; an adapter without labelled repos yet says so.
      </p>
      {groups.map(([eco, adapters]) => (
        <section key={eco} className="mt-2xl overflow-x-auto">
          <h2 className="text-headline-md">{ECOSYSTEM[eco] ?? eco}</h2>
          <table className="mt-md w-full min-w-[560px] text-left">
            <thead>
              <tr className="border-b border-outline font-condensed text-label-sm uppercase text-on-surface-muted">
                <th className="py-sm font-semibold">Adapter</th>
                <th className="py-sm font-semibold">Finds</th>
                <th className="py-sm text-right font-semibold">Precision</th>
                <th className="py-sm text-right font-semibold">Recall</th>
                <th className="py-sm text-right font-semibold">Labelled items</th>
              </tr>
            </thead>
            <tbody>
              {adapters.map((a) => {
                const scores = bench.byAdapter[a.name] ?? {};
                const cats = Object.entries(scores);
                const finds =
                  a.kind === "orm" ? "models, reads and writes" : "routes, middleware, handlers";
                if (!cats.length) {
                  return (
                    <tr key={a.name} className="border-b border-outline">
                      <td className="py-sm">{a.label}</td>
                      <td className="py-sm text-on-surface-muted">{finds}</td>
                      <td
                        colSpan={3}
                        className="py-sm text-right text-body-sm text-on-surface-muted"
                      >
                        fixture-tested; no benchmark repo yet
                      </td>
                    </tr>
                  );
                }
                return cats.map(([cat, m], i) => (
                  <tr key={`${a.name}-${cat}`} className="border-b border-outline">
                    <td className="py-sm">{i === 0 ? a.label : ""}</td>
                    <td className="py-sm text-on-surface-muted">{cat}</td>
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
                ));
              })}
            </tbody>
          </table>
        </section>
      ))}
      <section className="mt-2xl max-w-[48rem]">
        <h2 className="text-headline-md">Detected, not mapped yet</h2>
        <p className="mt-sm text-body-md text-on-surface-muted">
          These are recognised in manifests. You get a clear message instead of a guessed map:{" "}
          <Mono>{STACKS.notYet.join(", ")}</Mono>. Next on the roadmap: Spring, Laravel, Rails,
          ASP.NET and Go.
        </p>
      </section>
    </Page>
  );
}
