import type { Metadata } from "next";
import { Page } from "@/components/SiteChrome";

export const metadata: Metadata = { title: "Privacy" };

export default function PrivacyPage() {
  return (
    <Page>
      <article className="max-w-[48rem] pt-2xl text-body-md">
        <h1 className="text-headline-lg">Privacy</h1>
        <p className="mt-sm text-on-surface-muted">Last updated 2026-11-13.</p>
        <h2 className="mt-xl text-headline-md">What the hosted service stores</h2>
        <ul className="mt-sm list-disc space-y-sm pl-xl">
          <li>
            The public GitHub repos you submit, and the graphs built from them: names, paths, line
            numbers and labels. Source code is not stored; snippets are loaded from GitHub in your
            browser.
          </li>
          <li>Job records: repo, commit, status and timing.</li>
          <li>
            A salted hash of your IP address, used only for rate limiting. Raw IP addresses are not
            stored.
          </li>
          <li>
            Reports you send with &quot;Report wrong edge&quot;: the element ID and your optional
            note.
          </li>
          <li>
            Shared maps from <code className="font-mono">evident share</code>: graph metadata only,
            no code, deleted when the link expires.
          </li>
        </ul>
        <h2 className="mt-xl text-headline-md">What it never stores</h2>
        <ul className="mt-sm list-disc space-y-sm pl-xl">
          <li>Environment variable values. Evident reads variable names only.</li>
          <li>Private repositories. Only public GitHub URLs are accepted.</li>
          <li>
            Cookies or tracking identifiers. The theme choice stays in your browser&apos;s local
            storage.
          </li>
        </ul>
        <h2 className="mt-xl text-headline-md">Third parties</h2>
        <p className="mt-sm">
          Node IDs, types, labels and paths (never file contents) may be sent to Groq to suggest
          groups. Your browser loads code snippets directly from GitHub. The site is hosted on
          Vercel and the API on a single server we run.
        </p>
        <h2 className="mt-xl text-headline-md">The CLI and the Claude skill</h2>
        <p className="mt-sm">
          They run on your machine and send nothing unless you enable LLM grouping or run{" "}
          <code className="font-mono">evident share</code>. Telemetry is off unless you opt in.
        </p>
        <h2 className="mt-xl text-headline-md">Removal</h2>
        <p className="mt-sm">
          To remove a published map of your repo, open an issue on the Evident repository or follow
          SECURITY.md.
        </p>
      </article>
    </Page>
  );
}
