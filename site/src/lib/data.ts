// Build-time access to the JSON files the pipeline writes under data/.
import fs from "node:fs";
import path from "node:path";

const ROOT = path.resolve(process.cwd(), "..");
const DATA_DIR = process.env.DATA_DIR ? path.resolve(process.env.DATA_DIR) : path.join(ROOT, "data");

export type Ko = {
  one_liner: string;
  summary: string;
  features: string[];
  use_cases: string;
  category: string;
  generated_at: string;
  readme_truncated?: boolean;
};

export type Repo = {
  repo: string;
  url?: string;
  description?: string | null;
  homepage?: string | null;
  language?: string | null;
  topics?: string[];
  license?: string | null;
  stars?: number | null;
  forks?: number | null;
  created_at?: string | null;
  pushed_at?: string | null;
  owner_avatar?: string | null;
  first_seen?: string;
  last_seen?: string;
  ko?: Ko;
};

export type WeekEntry = {
  rank: number;
  repo: string;
  stars_week: number | null;
  stars_total: number | null;
  forks: number | null;
  language: string | null;
  prev_rank: number | null;
  is_new: boolean;
  weeks_on_chart: number;
  streak: number;
};

export type Week = {
  week: string;
  start: string;
  end: string;
  captured_at: string;
  source: string;
  entries: WeekEntry[];
};

export type RisingPick = {
  repo: string;
  score: number;
  stars_week: number;
  stars_week_estimated: boolean;
  stars: number;
  age_days: number | null;
  reason: string;
};

export type Rising = {
  week: string;
  generated_at: string;
  categories: { key: string; name: string; repos: RisingPick[] }[];
};

export type Category = { key: string; name: string; hint: string };

function readJson<T>(file: string): T {
  return JSON.parse(fs.readFileSync(file, "utf-8")) as T;
}

function readDir<T>(sub: string): T[] {
  const dir = path.join(DATA_DIR, sub);
  if (!fs.existsSync(dir)) return [];
  return fs
    .readdirSync(dir)
    .filter((f) => f.endsWith(".json"))
    .sort()
    .map((f) => readJson<T>(path.join(dir, f)));
}

let cache: { repos: Map<string, Repo>; weeks: Week[]; rising: Rising[] } | null = null;

function load() {
  if (!cache) {
    cache = {
      repos: new Map(readDir<Repo>("repos").map((r) => [r.repo, r])),
      weeks: readDir<Week>("weeks"),
      rising: readDir<Rising>("rising"),
    };
  }
  return cache;
}

export const categories: Category[] = readJson<Category[]>(path.join(ROOT, "pipeline", "categories.json"));
export const categoryName = (key?: string) => categories.find((c) => c.key === key)?.name;

export const allRepos = () => [...load().repos.values()];
export const getRepo = (name: string): Repo => load().repos.get(name) ?? { repo: name };

/** Weeks in chronological order. */
export const allWeeks = () => load().weeks;
export const latestWeek = () => allWeeks().at(-1);

export const allRising = () => load().rising;
export const latestRising = () => allRising().at(-1);

export function rankHistory(name: string) {
  return allWeeks().flatMap((w) => {
    const e = w.entries.find((x) => x.repo === name);
    return e ? [{ week: w.week, start: w.start, rank: e.rank, stars_week: e.stars_week }] : [];
  });
}

export function risingHistory(name: string) {
  return allRising().flatMap((r) =>
    r.categories.flatMap((c) =>
      c.repos.filter((p) => p.repo === name).map((p) => ({ week: r.week, category: c.name, reason: p.reason })),
    ),
  );
}

export const slug = (name: string) => name.replace("/", "__");
