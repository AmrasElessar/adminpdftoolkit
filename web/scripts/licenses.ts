// Vite plugin: emits `licenses.txt` with the licence text of every npm
// package whose code ends up in the bundle (MIT/Apache notices travel with
// the code we ship). Packages are read from the bundle's module ids, so the
// list is always exactly what was bundled.
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join, sep } from "node:path";
import type { Plugin } from "vite";

const LICENSE_FILE = /^(licen[cs]e|copying|notice)(\..*)?$/i;

function packageRoot(id: string): string | null {
  const marker = `${sep}node_modules${sep}`;
  const at = id.lastIndexOf(marker);
  if (at < 0) return null;
  const rest = id.slice(at + marker.length).split(sep);
  const depth = rest[0]?.startsWith("@") ? 2 : 1;
  return id.slice(0, at + marker.length) + rest.slice(0, depth).join(sep);
}

export function licenses(header: string): Plugin {
  return {
    name: "apt-licenses",
    apply: "build",
    generateBundle(_options, bundle) {
      const roots = new Set<string>();
      for (const chunk of Object.values(bundle)) {
        if (chunk.type !== "chunk") continue;
        for (const id of chunk.moduleIds) {
          const root = packageRoot(id.replace(/^\0/, "").split("?")[0]!);
          if (root && existsSync(join(root, "package.json"))) roots.add(root);
        }
      }
      const sections = [...roots]
        .map((root) => {
          const pkg = JSON.parse(readFileSync(join(root, "package.json"), "utf8")) as {
            name: string;
            version: string;
            license?: string;
            homepage?: string;
          };
          const files = readdirSync(root).filter((f) => LICENSE_FILE.test(f));
          const text = files.map((f) => readFileSync(join(root, f), "utf8").trim()).join("\n\n");
          return { pkg, text };
        })
        .sort((a, b) => a.pkg.name.localeCompare(b.pkg.name));
      const body = sections
        .map(({ pkg, text }) =>
          [
            "=".repeat(72),
            `${pkg.name} ${pkg.version} — ${pkg.license ?? "see below"}`,
            pkg.homepage ?? "",
            "=".repeat(72),
            text || `(licence: ${pkg.license ?? "unknown"})`,
          ].join("\n"),
        )
        .join("\n\n");
      // Machine-readable list for the in-app About & Licences page.
      this.emitFile({
        type: "asset",
        fileName: "licenses.json",
        source: JSON.stringify(
          sections.map(({ pkg }) => ({
            name: pkg.name,
            version: pkg.version,
            license: pkg.license ?? "?",
            url: pkg.homepage ?? `https://www.npmjs.com/package/${pkg.name}`,
          })),
        ),
      });
      this.emitFile({ type: "asset", fileName: "licenses.txt", source: `${header.trim()}\n\n\n# Web arayüzüne paketlenen bileşenlerin lisans metinleri / Licence texts of bundled web components\n\n${body}\n` });
    },
  };
}

