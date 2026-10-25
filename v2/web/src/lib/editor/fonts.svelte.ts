import { type FontFamily, listFonts } from "../api";
import type { FontChoice } from "./model.svelte";

const STANDARD: FontFamily[] = [
  { id: "helv", family: "Helvetica", source: "standard", restricted: false, styles: [] },
  { id: "tiro", family: "Times", source: "standard", restricted: false, styles: [], serif: true },
  { id: "cour", family: "Courier", source: "standard", restricted: false, styles: [], monospace: true },
];

const CSS_FALLBACK: Record<string, string> = {
  helv: "Helvetica, Arial, 'Liberation Sans', sans-serif",
  tiro: "'Times New Roman', Times, 'Liberation Serif', serif",
  cour: "'Courier New', Courier, monospace",
};

class FontCatalogue {
  families = $state<FontFamily[]>(STANDARD);
  loaded = $state(false);
  private faces = new Map<string, Promise<void>>();

  async load(): Promise<void> {
    if (this.loaded) return;
    const list = await listFonts();
    if (list.length) {
      const ids = new Set(list.map((f) => f.id));
      this.families = [...STANDARD.filter((s) => !ids.has(s.id)), ...list];
    }
    this.loaded = true;
  }

  family(id: string): FontFamily | undefined {
    return this.families.find((f) => f.id === id);
  }

  /** Closest available style of a family (same italic, nearest weight). */
  styleFor(choice: FontChoice): { id: string; weight: number; italic: boolean } | null {
    const fam = this.family(choice.family_id);
    if (!fam?.styles.length) return null;
    const pool = fam.styles.filter((s) => s.italic === choice.italic);
    const candidates = pool.length ? pool : fam.styles;
    return candidates.reduce((a, b) => (Math.abs(b.weight - choice.weight) < Math.abs(a.weight - choice.weight) ? b : a));
  }

  /** CSS font-family for WYSIWYG preview; loads the real file when served. */
  css(choice: FontChoice): string {
    const style = this.styleFor(choice);
    if (!style) return CSS_FALLBACK[choice.family_id] ?? "sans-serif";
    const name = `apt-${style.id}`;
    if (!this.faces.has(style.id)) {
      const face = new FontFace(name, `url(/api/fonts/${encodeURIComponent(style.id)}/file)`, {
        weight: String(style.weight),
        style: style.italic ? "italic" : "normal",
      });
      this.faces.set(
        style.id,
        face.load().then(
          (f) => void document.fonts.add(f),
          () => undefined,
        ),
      );
    }
    const fam = this.family(choice.family_id);
    return `'${name}', ${fam?.serif ? "serif" : fam?.monospace ? "monospace" : "sans-serif"}`;
  }
}

export const fonts = new FontCatalogue();
