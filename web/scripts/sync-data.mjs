// Copies published benchmark results into public/data so /benchmarks works even if the API is down.
import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const results = join(root, "..", "benchmark", "results");
const out = join(root, "public", "data", "benchmarks");
mkdirSync(out, { recursive: true });

for (const [from, to] of [
  ["baseline.json", "latest.json"],
  ["history.json", "history.json"],
]) {
  const src = join(results, from);
  if (!existsSync(src)) {
    console.error(`missing ${src}`);
    process.exit(1);
  }
  copyFileSync(src, join(out, to));
}
// ELK's worker must load as a plain script; bundlers wrap it and break its message protocol.
copyFileSync(
  join(root, "node_modules", "elkjs", "lib", "elk-worker.min.js"),
  join(root, "public", "elk-worker.min.js"),
);
console.log(`synced benchmark results into ${out} and the ELK worker into public/`);
