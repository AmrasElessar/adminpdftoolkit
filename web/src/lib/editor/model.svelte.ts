/**
 * Editor document model.
 *
 * Every object lives in PDF user space (origin bottom-left, unrotated, points)
 * so it is independent of zoom and page rotation; overlays convert through
 * the pdf.js viewport. Saving turns the objects into the server's `edit`
 * operation list in one request.
 */

export type Rect = [number, number, number, number];
export type Point = [number, number];

export interface FontChoice {
  family_id: string;
  weight: number;
  italic: boolean;
}

interface Base {
  id: string;
  page: number; // 1-based
}

export type EditObject = Base &
  (
    | { kind: "text"; rect: Rect; text: string; font: FontChoice; size: number; color: string; align: "left" | "center" | "right" }
    | {
        kind: "replace";
        rect: Rect;
        original: string;
        text: string;
        font: FontChoice;
        size: number;
        color: string;
        background: string; // "auto" or #RRGGBB
      }
    | { kind: "whiteout"; rect: Rect; color: string }
    | { kind: "rect" | "ellipse"; rect: Rect; stroke: string | null; fill: string | null; width: number; opacity: number }
    | { kind: "line" | "arrow"; from: Point; to: Point; color: string; width: number; opacity: number }
    | { kind: "ink"; paths: Point[][]; color: string; width: number; opacity: number }
    | { kind: "highlight" | "underline" | "strikeout"; rects: Rect[]; color: string; opacity: number }
    | { kind: "note"; point: Point; text: string; color: string }
    | { kind: "image"; rect: Rect; dataUrl: string; opacity: number }
    | { kind: "link"; rect: Rect; uri: string; targetPage: number }
    | { kind: "delete_annot"; xref: number; rect: Rect }
    | { kind: "field"; rect: Rect; fieldType: FieldType; name: string; options: string[]; required: boolean }
  );

export type FieldType = "text" | "checkbox" | "radio" | "combo" | "list" | "signature";

export type Kind = EditObject["kind"];

export type Tool =
  | "select"
  | "text"
  | "replace"
  | "whiteout"
  | "rect"
  | "ellipse"
  | "line"
  | "arrow"
  | "ink"
  | "highlight"
  | "underline"
  | "strikeout"
  | "note"
  | "image"
  | "signature"
  | "link"
  | "field";

/** Single-key tool shortcuts (Acrobat-like). Shared by toolbar and viewer. */
export const TOOL_KEYS: Record<string, Tool> = {
  v: "select",
  e: "replace",
  t: "text",
  h: "highlight",
  u: "underline",
  k: "strikeout",
  n: "note",
  d: "ink",
  r: "rect",
  o: "ellipse",
  l: "line",
  a: "arrow",
  w: "whiteout",
  i: "image",
  s: "signature",
  g: "link",
  f: "field",
};

export const keyFor = (tool: Tool): string | undefined =>
  Object.entries(TOOL_KEYS)
    .find(([, v]) => v === tool)?.[0]
    ?.toUpperCase();

export interface Style {
  color: string;
  fill: string | null;
  width: number;
  opacity: number;
  font: FontChoice;
  size: number;
  fieldType: FieldType;
}

let seq = 0;
export const newId = (): string => `o${Date.now().toString(36)}${(++seq).toString(36)}`;

export function bboxOf(o: EditObject): Rect {
  switch (o.kind) {
    case "line":
    case "arrow":
      return [Math.min(o.from[0], o.to[0]), Math.min(o.from[1], o.to[1]), Math.max(o.from[0], o.to[0]), Math.max(o.from[1], o.to[1])];
    case "ink": {
      const pts = o.paths.flat();
      const xs = pts.map((p) => p[0]);
      const ys = pts.map((p) => p[1]);
      return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
    }
    case "highlight":
    case "underline":
    case "strikeout": {
      const xs = o.rects.flatMap((r) => [r[0], r[2]]);
      const ys = o.rects.flatMap((r) => [r[1], r[3]]);
      return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
    }
    case "note":
      return [o.point[0], o.point[1] - 18, o.point[0] + 18, o.point[1]];
    default:
      return o.rect;
  }
}

/** Translate an object by (dx, dy) PDF points. */
export function moved(o: EditObject, dx: number, dy: number): EditObject {
  const r = (q: Rect): Rect => [q[0] + dx, q[1] + dy, q[2] + dx, q[3] + dy];
  const p = (q: Point): Point => [q[0] + dx, q[1] + dy];
  switch (o.kind) {
    case "line":
    case "arrow":
      return { ...o, from: p(o.from), to: p(o.to) };
    case "ink":
      return { ...o, paths: o.paths.map((path) => path.map(p)) };
    case "highlight":
    case "underline":
    case "strikeout":
      return { ...o, rects: o.rects.map(r) };
    case "note":
      return { ...o, point: p(o.point) };
    case "delete_annot":
      return o;
    default:
      return { ...o, rect: r(o.rect) };
  }
}

/** Whether the object supports free resizing through its rect. */
export function resizable(o: EditObject): o is Extract<EditObject, { rect: Rect }> {
  return "rect" in o && o.kind !== "delete_annot" && o.kind !== "replace";
}

export class EditorState {
  objects = $state<EditObject[]>([]);
  selectedId = $state<string | null>(null);
  editingId = $state<string | null>(null);
  tool = $state<Tool>("select");
  style = $state<Style>({
    color: "#1f3a93",
    fill: null,
    width: 2,
    opacity: 1,
    font: { family_id: "standard:helvetica", weight: 400, italic: false },
    size: 12,
    fieldType: "text",
  });
  /** Pending image (signature or picture) to place with the next click/drag. */
  pendingImage = $state<string | null>(null);

  private undoStack: EditObject[][] = [];
  private redoStack: EditObject[][] = [];
  canUndo = $state(false);
  canRedo = $state(false);

  readonly selected = $derived(this.objects.find((o) => o.id === this.selectedId) ?? null);
  readonly count = $derived(this.objects.length);

  forPage(page: number): EditObject[] {
    return this.objects.filter((o) => o.page === page);
  }

  private checkpoint(): void {
    this.undoStack.push($state.snapshot(this.objects) as EditObject[]);
    if (this.undoStack.length > 300) this.undoStack.shift();
    this.redoStack = [];
    this.sync();
  }

  private sync(): void {
    this.canUndo = this.undoStack.length > 0;
    this.canRedo = this.redoStack.length > 0;
  }

  add(o: EditObject, select = true): void {
    this.checkpoint();
    this.objects.push(o);
    if (select) this.selectedId = o.id;
  }

  /** Replace an object. `record=false` for live drags (one checkpoint per gesture). */
  update(id: string, next: EditObject, record = true): void {
    const i = this.objects.findIndex((o) => o.id === id);
    if (i < 0) return;
    if (record) this.checkpoint();
    this.objects[i] = next;
  }

  /** Call once at the start of a drag that will use `update(..., false)`. */
  beginGesture(): void {
    this.checkpoint();
  }

  remove(id: string): void {
    const i = this.objects.findIndex((o) => o.id === id);
    if (i < 0) return;
    this.checkpoint();
    this.objects.splice(i, 1);
    if (this.selectedId === id) this.selectedId = null;
    if (this.editingId === id) this.editingId = null;
  }

  undo(): void {
    const prev = this.undoStack.pop();
    if (!prev) return;
    this.redoStack.push($state.snapshot(this.objects) as EditObject[]);
    this.objects = prev;
    this.selectedId = null;
    this.editingId = null;
    this.sync();
  }

  redo(): void {
    const next = this.redoStack.pop();
    if (!next) return;
    this.undoStack.push($state.snapshot(this.objects) as EditObject[]);
    this.objects = next;
    this.sync();
  }

  clear(): void {
    this.objects = [];
    this.undoStack = [];
    this.redoStack = [];
    this.selectedId = null;
    this.editingId = null;
    this.sync();
  }

  /** The server `edit` operation list. Replaces go first per page server-side. */
  toOperations(): Record<string, unknown>[] {
    const ops: Record<string, unknown>[] = [];
    for (const o of this.objects) {
      const { page } = o;
      switch (o.kind) {
        case "text":
          if (o.text.trim())
            ops.push({ type: "text", page, rect: o.rect, text: o.text, font: o.font, size: o.size, color: o.color, align: o.align });
          break;
        case "replace":
          if (o.text !== o.original)
            ops.push({
              type: "replace",
              page,
              rect: o.rect,
              text: o.text,
              font: o.font,
              size: o.size,
              color: o.color,
              background: o.background,
            });
          break;
        case "whiteout":
          ops.push({ type: "whiteout", page, rect: o.rect, color: o.color });
          break;
        case "rect":
        case "ellipse":
          ops.push({ type: o.kind, page, rect: o.rect, stroke: o.stroke, fill: o.fill, width: o.width, opacity: o.opacity });
          break;
        case "line":
        case "arrow":
          ops.push({ type: o.kind, page, from: o.from, to: o.to, color: o.color, width: o.width, opacity: o.opacity });
          break;
        case "ink":
          ops.push({ type: "ink", page, paths: o.paths, color: o.color, width: o.width, opacity: o.opacity });
          break;
        case "highlight":
        case "underline":
        case "strikeout":
          ops.push({ type: o.kind, page, rects: o.rects, color: o.color, opacity: o.opacity });
          break;
        case "note":
          ops.push({ type: "note", page, point: o.point, text: o.text, color: o.color });
          break;
        case "image":
          ops.push({ type: "image", page, rect: o.rect, data_url: o.dataUrl, opacity: o.opacity });
          break;
        case "link":
          ops.push(o.uri ? { type: "link", page, rect: o.rect, uri: o.uri } : { type: "link", page, rect: o.rect, target_page: o.targetPage });
          break;
        case "delete_annot":
          ops.push({ type: "delete_annot", page, xref: o.xref });
          break;
        case "field":
          break; // created by form_create after the edit save; see toFieldSpecs
      }
    }
    return ops;
  }

  /** New form fields, for the server `form_create` operation. */
  toFieldSpecs(): Record<string, unknown>[] {
    return this.objects.flatMap((o) =>
      o.kind === "field"
        ? [{ page: o.page, type: o.fieldType, name: o.name, rect: o.rect, options: o.options, required: o.required }]
        : [],
    );
  }

  /** A field name not used yet in this session, e.g. "metin_3". */
  nextFieldName(type: FieldType): string {
    const base = { text: "metin", checkbox: "onay", radio: "secim", combo: "acilir", list: "liste", signature: "imza" }[type];
    const taken = new Set(this.objects.flatMap((o) => (o.kind === "field" ? [o.name] : [])));
    let n = 1;
    while (taken.has(`${base}_${n}`)) n++;
    return `${base}_${n}`;
  }
}
