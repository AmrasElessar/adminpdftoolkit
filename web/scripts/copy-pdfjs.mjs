// Copy pdf.js runtime assets (CMaps, standard fonts, wasm decoders) into
// public/ so they are served same-origin under a strict CSP and work offline.
import { cpSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const src = join(root, "node_modules", "pdfjs-dist");
const dst = join(root, "public", "pdfjs");
mkdirSync(dst, { recursive: true });
for (const dir of ["cmaps", "standard_fonts", "wasm", "iccs"]) {
  cpSync(join(src, dir), join(dst, dir), { recursive: true });
}
// Apache-2.0 §4: ship pdf.js's licence with the copied files.
cpSync(join(src, "LICENSE"), join(dst, "LICENSE"));
console.log("pdf.js assets copied to public/pdfjs");
