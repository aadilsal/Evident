// Shiki tokens with a CSS-variable theme. We render tokens as React text, never as HTML (security.md T7).
import type { HighlighterCore, ThemedToken } from "shiki/core";

export type Lang = "typescript" | "tsx" | "javascript" | "jsx" | "python" | "prisma" | "json";

const BY_EXT: Record<string, Lang> = {
  ts: "typescript",
  mts: "typescript",
  cts: "typescript",
  tsx: "tsx",
  js: "javascript",
  mjs: "javascript",
  cjs: "javascript",
  jsx: "jsx",
  py: "python",
  prisma: "prisma",
  json: "json",
};

export function langFor(file: string): Lang | null {
  const ext = file.split(".").pop()?.toLowerCase() ?? "";
  return BY_EXT[ext] ?? null;
}

let highlighter: Promise<HighlighterCore> | null = null;

function load(): Promise<HighlighterCore> {
  highlighter ??= (async () => {
    const [{ createHighlighterCore, createCssVariablesTheme }, { createJavaScriptRegexEngine }] =
      await Promise.all([import("shiki/core"), import("shiki/engine/javascript")]);
    return createHighlighterCore({
      themes: [createCssVariablesTheme({ name: "evident", variablePrefix: "--shiki-" })],
      langs: [
        import("@shikijs/langs/typescript"),
        import("@shikijs/langs/tsx"),
        import("@shikijs/langs/javascript"),
        import("@shikijs/langs/jsx"),
        import("@shikijs/langs/python"),
        import("@shikijs/langs/prisma"),
        import("@shikijs/langs/json"),
      ],
      engine: createJavaScriptRegexEngine({ forgiving: true }),
    });
  })();
  return highlighter;
}

export interface Line {
  number: number;
  tokens: { content: string; color?: string }[];
}

/** Tokenise lines [from, to] of a file. Falls back to plain text for unknown languages. */
export async function highlightLines(
  file: string,
  text: string,
  from: number,
  to: number,
): Promise<Line[]> {
  const all = text.replace(/\r\n/g, "\n").split("\n");
  const start = Math.max(1, from);
  const end = Math.min(all.length, to);
  const slice = all.slice(start - 1, end);
  const lang = langFor(file);
  const plain = () => slice.map((l, i) => ({ number: start + i, tokens: [{ content: l }] }));
  if (!lang) return plain();
  try {
    const hl = await load();
    // Tokenise from the top of the file so multi-line strings and comments colour correctly.
    const tokens: ThemedToken[][] = hl.codeToTokensBase(all.slice(0, end).join("\n"), {
      lang,
      theme: "evident",
    });
    return tokens.slice(start - 1, end).map((line, i) => ({
      number: start + i,
      tokens: line.map((t) => ({ content: t.content, color: t.color })),
    }));
  } catch {
    return plain();
  }
}
