// End-to-end accessibility audit (WCAG 2.1 A/AA via axe-core) of the main
// screens, light and dark. Needs a running server on $APT_URL (default
// https://localhost:8000) and a sample PDF path as the first argument.
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { chromium } from "playwright";

const require = createRequire(import.meta.url);
const axeSrc = readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const base = process.env.APT_URL ?? "https://localhost:8000";
const sample = process.argv[2];
if (!sample) throw new Error("usage: node e2e/a11y.mjs <sample.pdf>");

const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
let failures = 0;
for (const scheme of ["light", "dark"]) {
  // The app's CSP rightly blocks injected scripts; bypass it for the audit only.
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 900 }, locale: "tr-TR", colorScheme: scheme, bypassCSP: true, ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  const audit = async (name) => {
    await page.addScriptTag({ content: axeSrc });
    const violations = await page.evaluate(async () => {
      const r = await window.axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] } });
      return r.violations.map((v) => `${v.id} (${v.impact}) × ${v.nodes.length}: ${v.nodes[0]?.target?.join(" ")}`);
    });
    console.log(`${scheme}/${name}: ${violations.length ? violations.join("; ") : "ok"}`);
    failures += violations.length;
  };
  await page.goto(base);
  await page.setInputFiles("input[type=file]", [sample]);
  await page.locator(".tray li .meta").filter({ hasText: /sayfa/ }).first().waitFor();
  await audit("home");
  await page.locator(".tool").first().click();
  await audit("tool-panel");
  await page.locator('[aria-label="Araçlara dön"]').click();
  await page.locator(".feature").nth(3).click(); // View & search
  await page.locator(".pages .page canvas").first().waitFor();
  await audit("viewer");
  await page.locator(".modes [role=tab]").nth(2).click();
  await audit("editor");
  await page.locator(".modes [role=tab]").nth(3).click();
  await page.locator(".kvkk .summary").waitFor({ timeout: 60000 });
  await audit("kvkk");
  await page.keyboard.press("?");
  await audit("shortcuts");
  await ctx.close();
}
await browser.close();
if (failures) {
  console.error(`${failures} accessibility violation(s)`);
  process.exit(1);
}
