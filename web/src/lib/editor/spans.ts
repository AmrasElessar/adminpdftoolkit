import { runAndWait } from "../api";
import type { FontChoice, Rect } from "./model.svelte";

export interface Span {
  id: string;
  text: string;
  rect: Rect;
  font: string;
  size: number;
  color: string;
  bold: boolean;
  italic: boolean;
  matched_font?: FontChoice;
  background?: string;
}

export interface PageSpans {
  page: number;
  spans: Span[];
}

type Granularity = "word" | "line" | "block";

/** Lazily fetched text spans per (file, granularity, page). */
export class SpanCache {
  private pending = new Map<string, Promise<Span[]>>();

  constructor(
    private fileId: string,
    private password: string,
  ) {}

  get(page: number, granularity: Granularity): Promise<Span[]> {
    const key = `${granularity}:${page}`;
    let p = this.pending.get(key);
    if (!p) {
      p = runAndWait("text_spans", [{ id: this.fileId, password: this.password || undefined }], {
        pages: String(page),
        granularity,
      })
        .then((job) => {
          const pages = (job.data?.pages ?? []) as PageSpans[];
          return pages.find((x) => x.page === page)?.spans ?? [];
        })
        .catch((e: unknown) => {
          this.pending.delete(key); // allow retry
          throw e;
        });
      this.pending.set(key, p);
    }
    return p;
  }
}
