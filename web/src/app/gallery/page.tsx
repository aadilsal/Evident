import type { Metadata } from "next";
import Link from "next/link";
import { Page } from "@/components/SiteChrome";
import { Mono, shortSha } from "@/components/ui";
import { gallery } from "@/lib/data";

export const metadata: Metadata = { title: "Gallery" };

export default function GalleryPage() {
  const repos = gallery();
  return (
    <Page>
      <h1 className="pt-2xl text-headline-lg">Gallery</h1>
      <p className="mt-sm max-w-[42rem] text-body-lg text-on-surface-muted">
        Pre-analysed maps, served as static files so they open instantly. Each is pinned to a commit
        and every snippet links to that commit on GitHub.
      </p>
      <ul className="mt-xl divide-y divide-outline border-y border-outline">
        {repos.map((g) => (
          <li key={g.slug}>
            <Link
              href={`/map/?gallery=${g.slug}`}
              className="grid gap-xs py-lg hover:bg-surface-raised sm:grid-cols-[1fr_auto] sm:items-baseline sm:gap-x-xl"
            >
              <span>
                <Mono className="text-code-md">{g.repo}</Mono>{" "}
                <Mono className="text-code-sm text-on-surface-muted">@ {shortSha(g.sha)}</Mono>
                <span className="mt-xs block text-body-sm text-on-surface-muted">{g.blurb}</span>
              </span>
              <Mono className="text-code-sm tabular text-on-surface-muted">
                {g.routes} routes · {g.models} models · {g.findings} findings
              </Mono>
            </Link>
          </li>
        ))}
      </ul>
      <p className="mt-lg text-body-sm text-on-surface-muted">
        These repos are public projects by Evident&apos;s author, also used in the benchmark. Larger
        open-source repos join the gallery as the benchmark grows; each will credit its project and
        license here.
      </p>
    </Page>
  );
}
