// Build-time reads of the static data shipped with the site (gallery, benchmarks, stacks).
import { readFileSync } from "node:fs";
import { join } from "node:path";
import stacks from "@/data/stacks.json";

export interface GalleryEntry {
  slug: string;
  repo: string;
  sha: string;
  blurb: string;
  stack: string[];
  routes: number;
  models: number;
  findings: number;
}

export interface Metric {
  tp?: number;
  fp?: number;
  fn?: number;
  precision: number;
  recall: number;
  f1: number;
  hallucinationRate: number;
}

export interface BenchmarkLatest {
  categories: Record<string, Metric>;
  byAdapter: Record<string, Record<string, Metric>>;
  repos: { repo: string; sha: string; seconds: number; categories: Record<string, Metric> }[];
}

export interface BenchmarkRun {
  date: string;
  evidentSha: string;
  repos: number;
  categories: Record<string, Metric>;
}

const PUBLIC = join(process.cwd(), "public", "data");

function read<T>(...parts: string[]): T {
  return JSON.parse(readFileSync(join(PUBLIC, ...parts), "utf8")) as T;
}

export function gallery(): GalleryEntry[] {
  return read<{ repos: GalleryEntry[] }>("gallery", "index.json").repos;
}

export function benchmarkLatest(): BenchmarkLatest {
  return read<BenchmarkLatest>("benchmarks", "latest.json");
}

export function benchmarkHistory(): BenchmarkRun[] {
  return read<{ runs: BenchmarkRun[] }>("benchmarks", "history.json").runs;
}

export type StackAdapter = (typeof stacks.adapters)[number];
export const STACKS = stacks;

export function pct(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}
