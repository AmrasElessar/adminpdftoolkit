import { readFileSync } from "node:fs";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { defineConfig } from "vite";
import { licenses } from "./scripts/licenses";

// The build lands inside the Python package so the server ships the UI
// with no Node.js at runtime.
export default defineConfig({
  plugins: [
    svelte(),
    // Served at /licenses.txt: the project's attribution page followed by the
    // full licence text of every npm package in the bundle.
    licenses(readFileSync(new URL("../THIRD_PARTY_LICENSES.md", import.meta.url), "utf8")),
  ],
  build: {
    outDir: "../server/adminpdf/web_dist",
    emptyOutDir: true,
    target: "es2022",
  },
  server: {
    // `npm run dev` + `python -m adminpdf` on :8000
    proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: false } },
  },
});
