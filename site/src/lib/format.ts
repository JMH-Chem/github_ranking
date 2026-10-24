const base = import.meta.env.BASE_URL.replace(/\/$/, "");

/** Internal link that respects the deploy base path. */
export const href = (p: string) => `${base}/${p.replace(/^\//, "")}`;

const num = new Intl.NumberFormat("ko-KR");
const compact = new Intl.NumberFormat("ko-KR", { notation: "compact", maximumFractionDigits: 1 });

export const n = (v?: number | null) => (v == null ? "–" : num.format(v));
export const short = (v?: number | null) => (v == null ? "–" : v >= 10000 ? compact.format(v) : num.format(v));

/** "2026-W43" -> "2026년 43주차" */
export function weekTitle(label: string) {
  const [y, w] = label.split("-W");
  return `${y}년 ${Number(w)}주차`;
}

/** "2026-10-19" -> "10월 19일" */
export function day(iso?: string | null) {
  if (!iso) return "";
  const [, m, d] = iso.slice(0, 10).split("-");
  return `${Number(m)}월 ${Number(d)}일`;
}

export const range = (start: string, end: string) => `${day(start)} ~ ${day(end)}`;

/** Colors from github-linguist for the languages that show up most. */
const LANG_COLORS: Record<string, string> = {
  Python: "#3572A5", TypeScript: "#3178c6", JavaScript: "#f1e05a", Rust: "#dea584",
  Go: "#00ADD8", Java: "#b07219", "C++": "#f34b7d", C: "#555555", "C#": "#178600",
  Swift: "#F05138", Kotlin: "#A97BFF", Ruby: "#701516", PHP: "#4F5D95", Dart: "#00B4AB",
  Shell: "#89e051", Zig: "#ec915c", HTML: "#e34c26", CSS: "#663399", Vue: "#41b883",
  Svelte: "#ff3e00", Lua: "#000080", "Jupyter Notebook": "#DA5B0B", Elixir: "#6e4a7e",
  Haskell: "#5e5086", Scala: "#c22d40", "Objective-C": "#438eff", MDX: "#fcb32c",
};
export const langColor = (lang?: string | null) => (lang && LANG_COLORS[lang]) || "#8b949e";
