import { svelte } from "@sveltejs/vite-plugin-svelte";
import { defineConfig } from "vite";

// The build lands inside the Python package so the server ships the UI
// with no Node.js at runtime.
export default defineConfig({
  plugins: [svelte()],
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
