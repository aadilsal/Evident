"use client";

import { useRouter } from "next/navigation";
import { useId, useState, type FormEvent } from "react";
import { API_URL } from "@/lib/source";
import { parseGithubUrl } from "@/lib/url";
import { Button, cx } from "./ui";

/** The hero of the landing page and the top bar of the app (DESIGN.md: Repo URL input). */
export function RepoInput({
  compact = false,
  autoFocus = false,
}: {
  compact?: boolean;
  autoFocus?: boolean;
}) {
  const router = useRouter();
  const id = useId();
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  function submit(e: FormEvent) {
    e.preventDefault();
    const gh = parseGithubUrl(value);
    if (!gh) {
      setError("Paste a public repo URL like https://github.com/owner/repo.");
      return;
    }
    if (!API_URL) {
      setError("This build can't analyse repos. Run `evident analyze` and `evident open` locally.");
      return;
    }
    setError(null);
    const url = `https://github.com/${gh.owner}/${gh.repo}${gh.ref ? `/tree/${gh.ref}` : ""}`;
    router.push(`/analyze/?url=${encodeURIComponent(url)}`);
  }

  return (
    <form onSubmit={submit} className="w-full" noValidate>
      <label htmlFor={id} className="sr-only">
        GitHub repository URL
      </label>
      <div className={cx("flex w-full gap-sm", compact ? "flex-row" : "flex-col sm:flex-row")}>
        <input
          id={id}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="github.com/owner/repo"
          autoComplete="off"
          spellCheck={false}
          autoFocus={autoFocus}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? `${id}-error` : undefined}
          className={cx(
            "min-w-0 flex-1 rounded-md border border-outline bg-surface-sunken px-lg font-mono text-code-md text-on-surface placeholder:text-on-surface-muted focus:border-outline-strong focus:outline-none",
            compact ? "h-8" : "h-12",
          )}
        />
        <Button
          type="submit"
          variant="primary"
          size={compact ? "sm" : "md"}
          className={compact ? "" : "h-12"}
        >
          Map this repo
        </Button>
      </div>
      {error && (
        <p id={`${id}-error`} role="alert" className="mt-sm text-body-sm text-error">
          {error}
        </p>
      )}
    </form>
  );
}
