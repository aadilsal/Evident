import type { Metadata } from "next";
import { Page } from "@/components/SiteChrome";

export const metadata: Metadata = { title: "Terms" };

export default function TermsPage() {
  return (
    <Page>
      <article className="max-w-3xl pt-2xl text-body-md">
        <h1 className="text-headline-lg">Terms</h1>
        <p className="mt-sm text-on-surface-muted">Last updated 2026-11-13.</p>
        <ul className="mt-xl list-disc space-y-md pl-xl">
          <li>
            Evident is a free demo service provided as is, without warranty. Maps can be incomplete
            or wrong; the evidence links exist so you can check.
          </li>
          <li>
            Submit only public repositories you are allowed to share. Don&apos;t use the service to
            attack it or anyone else, or to get around its rate limits.
          </li>
          <li>
            Analyses may be cached and shown again for the same commit. We may remove maps or block
            abuse at any time.
          </li>
          <li>
            The Evident software is open source under the MIT licence. Analysed repositories keep
            their own licences.
          </li>
        </ul>
      </article>
    </Page>
  );
}
