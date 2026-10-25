import type { PDFDocumentProxy } from "./pdf";

export interface Hit {
  page: number; // 1-based
  items: number[]; // text-item indices (match pdf.js TextLayer.textDivs order)
}

type PageText = { text: string; starts: number[] };

/** Full-text search over pdf.js text content, Turkish-aware case folding. */
export class Searcher {
  private cache = new Map<number, PageText>();

  constructor(private doc: PDFDocumentProxy) {}

  private async pageText(n: number): Promise<PageText> {
    const hit = this.cache.get(n);
    if (hit) return hit;
    const content = await (await this.doc.getPage(n)).getTextContent();
    const starts: number[] = [];
    let text = "";
    for (const item of content.items) {
      starts.push(text.length);
      text += "str" in item ? item.str : "";
      if ("hasEOL" in item && item.hasEOL) text += " ";
    }
    const entry = { text: fold(text), starts };
    this.cache.set(n, entry);
    return entry;
  }

  async find(query: string, signal?: AbortSignal): Promise<Hit[]> {
    const q = fold(query.trim());
    if (!q) return [];
    const hits: Hit[] = [];
    for (let n = 1; n <= this.doc.numPages; n++) {
      if (signal?.aborted) break;
      const { text, starts } = await this.pageText(n);
      let from = 0;
      for (;;) {
        const at = text.indexOf(q, from);
        if (at < 0) break;
        hits.push({ page: n, items: itemsCovering(starts, at, at + q.length) });
        from = at + q.length;
        if (hits.length >= 5000) return hits;
      }
    }
    return hits;
  }
}

function fold(s: string): string {
  return s.toLocaleLowerCase("tr").normalize("NFC").replace(/\s+/g, " ");
}

function itemsCovering(starts: number[], a: number, b: number): number[] {
  const out: number[] = [];
  for (let i = 0; i < starts.length; i++) {
    const s = starts[i]!;
    const e = i + 1 < starts.length ? starts[i + 1]! : Number.POSITIVE_INFINITY;
    if (s < b && e > a) out.push(i);
  }
  return out;
}
