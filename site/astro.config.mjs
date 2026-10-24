import { defineConfig } from "astro/config";

// The deploy workflow passes SITE_URL and BASE_PATH from actions/configure-pages.
export default defineConfig({
  site: process.env.SITE_URL || "https://jmh-chem.github.io",
  base: process.env.BASE_PATH || "/github_ranking",
  trailingSlash: "ignore",
});
