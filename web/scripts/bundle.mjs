// Copies the static export into the Python package so `evident open` needs no Node (tracker §8).
import { cpSync, existsSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const out = join(root, "out");
const dest = join(root, "..", "engine", "src", "evident", "webui");

if (!existsSync(join(out, "index.html"))) {
  console.error("web/out is missing: run `npm run build` first.");
  process.exit(1);
}
rmSync(dest, { recursive: true, force: true });
cpSync(out, dest, { recursive: true });
writeFileSync(join(dest, ".gitignore"), "*\n");
console.log(`bundled ${out} -> ${dest}`);
