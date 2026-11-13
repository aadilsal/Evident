import type { Metadata } from "next";
import { HistoryChart } from "@/components/HistoryChart";
import { Page } from "@/components/SiteChrome";
import { Mono, shortSha } from "@/components/ui";
import { benchmarkHistory, benchmarkLatest, pct, type Metric } from "@/lib/data";
import { REPO_URL } from "@/lib/source";

export const metadata: Metadata = { title: "Benchmarks" };

const CATS = ["routes", "models", "services", "edges"] as const;

function MetricRow({ name, m }: { name: string; m?: Metric }) {
  if (!m) return null;
  return (
    <tr className="border-b border-outline">
      <td className="py-sm capitalize">{name}</td>
      <td className="py-sm text-right">
        <Mono>{pct(m.precision)}</Mono>
      </td>
      <td className="py-sm text-right">
        <Mono>{pct(m.recall)}</Mono>
      </td>
      <td className="py-sm text-right">
        <Mono>{pct(m.f1)}</Mono>
      </td>
      <td className="py-sm text-right">
        <Mono className="text-on-surface-muted">{pct(m.hallucinationRate)}</Mono>
      </td>
      <td className="py-sm text-right">
        <Mono className="text-on-surface-muted">
          {m.tp ?? "–"} / {m.fp ?? "–"} / {m.fn ?? "–"}
        </Mono>
      </td>
    </tr>
  );
}

function Head() {
  return (
    <thead>
      <tr className="border-b border-outline font-condensed text-label-sm uppercase text-on-surface-muted">
        <th className="py-sm text-left font-semibold">Category</th>
        <th className="py-sm text-right font-semibold">Precision</th>
        <th className="py-sm text-right font-semibold">Recall</th>
        <th className="py-sm text-right font-semibold">F1</th>
        <th className="py-sm text-right font-semibold">Hallucination</th>
        <th className="py-sm text-right font-semibold">TP / FP / FN</th>
      </tr>
    </thead>
  );
}

export default function BenchmarksPage() {
  const latest = benchmarkLatest();
  const runs = benchmarkHistory();
  return (
    <Page>
      <h1 className="pt-2xl text-headline-lg">Benchmarks</h1>
      <p className="mt-sm max-w-3xl text-body-lg text-on-surface-muted">
        {latest.repos.length} repos, each pinned to a commit and labelled by hand following the{" "}
        <a
          className="underline underline-offset-4"
          href={`${REPO_URL}/blob/main/docs/labelling-guide.md`}
        >
          labelling guide
        </a>
        . The engine runs on every change in CI and the build fails if any category drops more than
        2 points.
      </p>

      <section className="mt-2xl overflow-x-auto">
        <h2 className="text-headline-md">Latest run</h2>
        <table className="mt-md w-full min-w-[640px] text-left">
          <Head />
          <tbody>
            {CATS.map((c) => (
              <MetricRow key={c} name={c} m={latest.categories[c]} />
            ))}
          </tbody>
        </table>
      </section>

      <section className="mt-2xl">
        <h2 className="text-headline-md">F1 over time</h2>
        <div className="mt-md">
          <HistoryChart runs={runs} />
        </div>
      </section>

      <section className="mt-2xl overflow-x-auto">
        <h2 className="text-headline-md">Per repo</h2>
        <table className="mt-md w-full min-w-[640px] text-left">
          <thead>
            <tr className="border-b border-outline font-condensed text-label-sm uppercase text-on-surface-muted">
              <th className="py-sm font-semibold">Repo</th>
              {CATS.map((c) => (
                <th key={c} className="py-sm text-right font-semibold">
                  {c} F1
                </th>
              ))}
              <th className="py-sm text-right font-semibold">Time</th>
            </tr>
          </thead>
          <tbody>
            {latest.repos.map((r) => (
              <tr key={r.repo} className="border-b border-outline">
                <td className="py-sm">
                  <Mono className="text-code-md">{r.repo}</Mono>{" "}
                  <Mono className="text-code-sm text-on-surface-muted">@ {shortSha(r.sha)}</Mono>
                </td>
                {CATS.map((c) => (
                  <td key={c} className="py-sm text-right">
                    <Mono className={r.categories[c] ? "" : "text-on-surface-muted"}>
                      {r.categories[c] ? pct(r.categories[c].f1) : "n/a"}
                    </Mono>
                  </td>
                ))}
                <td className="py-sm text-right">
                  <Mono className="text-on-surface-muted">{r.seconds.toFixed(1)}s</Mono>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="mt-2xl max-w-3xl text-body-md text-on-surface-muted">
        <h2 className="text-headline-md text-on-surface">How to read this</h2>
        <ul className="mt-md list-disc space-y-sm pl-xl">
          <li>
            Precision: of what Evident drew, how much is real. Recall: of what&apos;s really there,
            how much it drew.
          </li>
          <li>
            Hallucination: the share of drawn items that match nothing in the labels. Routes the
            engine itself marks as dynamic (computed paths, low confidence) are drawn dashed and
            counted here, not as false positives.
          </li>
          <li>
            The benchmark repos so far are the author&apos;s own public projects. Labels are written
            from the source, and third-party repos are being added for the remaining adapters.
          </li>
          <li>
            Re-run it yourself: <Mono>uv run evident-bench</Mono> in <Mono>engine/</Mono>.
          </li>
        </ul>
      </section>
    </Page>
  );
}
