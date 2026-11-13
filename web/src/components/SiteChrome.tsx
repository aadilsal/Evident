import Link from "next/link";
import { REPO_URL } from "@/lib/source";
import { ThemeToggle } from "./ThemeToggle";

const NAV = [
  ["/gallery/", "Gallery"],
  ["/benchmarks/", "Benchmarks"],
  ["/stacks/", "Supported stacks"],
] as const;

export function SiteHeader() {
  return (
    <header className="mx-auto flex h-16 w-full max-w-[1120px] items-center gap-lg px-lg">
      <Link href="/" className="font-condensed text-label-lg tracking-wide">
        EVIDENT
      </Link>
      <nav
        aria-label="Site"
        className="ml-auto flex items-center gap-lg text-body-sm text-on-surface-muted"
      >
        {NAV.map(([href, label]) => (
          <Link key={href} href={href} className="hidden hover:text-on-surface sm:inline">
            {label}
          </Link>
        ))}
        <a
          href={REPO_URL}
          target="_blank"
          rel="noreferrer noopener"
          className="hover:text-on-surface"
        >
          GitHub
        </a>
        <ThemeToggle />
      </nav>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="mt-3xl border-t border-outline">
      <div className="mx-auto flex max-w-[1120px] flex-wrap items-center gap-x-xl gap-y-sm px-lg py-xl text-body-sm text-on-surface-muted">
        <span>Evident · MIT licensed</span>
        {NAV.map(([href, label]) => (
          <Link key={href} href={href} className="hover:text-on-surface">
            {label}
          </Link>
        ))}
        <Link href="/privacy/" className="hover:text-on-surface">
          Privacy
        </Link>
        <Link href="/terms/" className="hover:text-on-surface">
          Terms
        </Link>
        <a
          href={REPO_URL}
          target="_blank"
          rel="noreferrer noopener"
          className="hover:text-on-surface"
        >
          Source
        </a>
      </div>
    </footer>
  );
}

export function Page({ children }: { children: React.ReactNode }) {
  return (
    <>
      <SiteHeader />
      <main className="mx-auto w-full max-w-[1120px] px-lg">{children}</main>
      <SiteFooter />
    </>
  );
}
