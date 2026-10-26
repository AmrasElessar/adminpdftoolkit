import { runAndWait } from "../api";
import type { Text } from "../i18n.svelte";

export type Action = "black" | "white" | "mask" | "blur" | "keep";
export type Rect = [number, number, number, number];

export interface Finding {
  id: string;
  page: number;
  kind: string;
  text: string;
  mask: string;
  rects: Rect[];
  suggested: Action;
  action: Action;
}

export interface KindInfo extends Text {
  suggested: Action;
  special: boolean;
}

export const ACTIONS: { id: Action; tr: string; en: string }[] = [
  { id: "black", tr: "Karart", en: "Black out" },
  { id: "blur", tr: "Bulanıklaştır", en: "Blur" },
  { id: "mask", tr: "Maskele", en: "Mask" },
  { id: "white", tr: "Beyazla", en: "White out" },
  { id: "keep", tr: "Dokunma", en: "Keep" },
];

let manualSeq = 0;

export class KvkkState {
  findings = $state<Finding[]>([]);
  kinds = $state<Record<string, KindInfo>>({});
  status = $state<"idle" | "scanning" | "ready" | "error">("idle");
  progress = $state(0);
  focused = $state<string | null>(null);
  /** "Extra-secure PDF": the result is page images only, no text left. */
  flatten = $state(false);

  readonly active = $derived(this.findings.filter((f) => f.action !== "keep"));

  constructor(
    private fileId: string,
    private password: string,
  ) {}

  async scan(): Promise<void> {
    this.status = "scanning";
    try {
      const job = await runAndWait(
        "kvkk_scan",
        [{ id: this.fileId, password: this.password || undefined }],
        { include_special: true },
        (j) => (this.progress = j.progress),
      );
      const data = job.data as { findings: Omit<Finding, "action">[]; kinds: Record<string, KindInfo> };
      this.kinds = data.kinds;
      this.findings = data.findings.map((f) => ({ ...f, action: f.suggested }));
      this.status = "ready";
    } catch {
      this.status = "error";
    }
  }

  groups(): { kind: string; items: Finding[] }[] {
    const map = new Map<string, Finding[]>();
    for (const f of this.findings) map.set(f.kind, [...(map.get(f.kind) ?? []), f]);
    // Special-category hints last: they need a human decision.
    return [...map.entries()]
      .sort((a, b) => Number(this.kinds[a[0]]?.special ?? false) - Number(this.kinds[b[0]]?.special ?? false))
      .map(([kind, items]) => ({ kind, items }));
  }

  setKind(kind: string, action: Action): void {
    for (const f of this.findings) if (f.kind === kind) f.action = action;
  }

  setAll(action: Action): void {
    for (const f of this.findings) if (!this.kinds[f.kind]?.special) f.action = action;
  }

  addManual(page: number, rect: Rect): void {
    const f: Finding = {
      id: `m${++manualSeq}`,
      page,
      kind: "manual",
      text: "",
      mask: "****",
      rects: [rect],
      suggested: "black",
      action: "black",
    };
    this.findings.push(f);
    this.focused = f.id;
  }

  remove(id: string): void {
    this.findings = this.findings.filter((f) => f.id !== id);
  }

  payload(): Record<string, unknown>[] {
    return this.active.map((f) => ({ page: f.page, rects: f.rects, action: f.action, mask: f.mask }));
  }
}
