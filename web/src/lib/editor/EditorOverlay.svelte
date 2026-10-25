<script lang="ts">
  import { t } from "../i18n.svelte";
  import type { PageViewport } from "../viewer/pdf";
  import { fonts } from "./fonts.svelte";
  import {
    bboxOf,
    type EditObject,
    type EditorState,
    moved,
    newId,
    type Point,
    type Rect,
    resizable,
  } from "./model.svelte";
  import type { Span, SpanCache } from "./spans";

  let {
    page,
    viewport,
    editor,
    spans,
    onocr,
  }: { page: number; viewport: PageViewport; editor: EditorState; spans: SpanCache; onocr?: () => void } = $props();

  let root: HTMLDivElement;
  const objects = $derived(editor.forPage(page));
  const scale = $derived(viewport.scale);

  // ---- coordinate helpers ---------------------------------------------------
  function toPdf(x: number, y: number): Point {
    const [px, py] = viewport.convertToPdfPoint(x, y) as [number, number];
    return [px, py];
  }
  function toVp(p: Point): Point {
    const [x, y] = viewport.convertToViewportPoint(p[0], p[1]) as [number, number];
    return [x, y];
  }
  function box(r: Rect): { left: number; top: number; width: number; height: number } {
    const [x0, y0] = toVp([r[0], r[1]]);
    const [x1, y1] = toVp([r[2], r[3]]);
    return { left: Math.min(x0, x1), top: Math.min(y0, y1), width: Math.abs(x1 - x0), height: Math.abs(y1 - y0) };
  }
  function rectFromVp(a: Point, b: Point): Rect {
    const p = toPdf(a[0], a[1]);
    const q = toPdf(b[0], b[1]);
    return [Math.min(p[0], q[0]), Math.min(p[1], q[1]), Math.max(p[0], q[0]), Math.max(p[1], q[1])];
  }
  function local(e: PointerEvent): Point {
    const r = root.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  }
  function intersects(a: Rect, b: Rect): boolean {
    return a[0] < b[2] && a[2] > b[0] && a[1] < b[3] && a[3] > b[1];
  }

  // ---- replace-mode spans -----------------------------------------------------
  let lineSpans = $state<Span[]>([]);
  let spansLoaded = $state(false);
  let spanError = $state("");
  $effect(() => {
    if (editor.tool !== "replace") return;
    spanError = "";
    spans
      .get(page, "line")
      .then((s) => {
        lineSpans = s;
        spansLoaded = true;
      })
      .catch(() => (spanError = t("Metin okunamadı", "Could not read text")));
  });
  const replacedRects = $derived(objects.filter((o) => o.kind === "replace").map((o) => (o as { rect: Rect }).rect));

  // ---- gestures ----------------------------------------------------------------
  type Gesture =
    | { type: "draft"; start: Point; now: Point }
    | { type: "ink"; points: Point[] }
    | { type: "move"; id: string; start: Point; origin: EditObject }
    | { type: "resize"; id: string; corner: number; origin: Rect };
  let gesture = $state<Gesture | null>(null);

  const DRAFT_TOOLS = new Set(["field", "whiteout", "rect", "ellipse", "line", "arrow", "highlight", "underline", "strikeout", "link", "text", "image", "signature"]);

  function hitTest(p: Point): EditObject | null {
    const pdf = toPdf(p[0], p[1]);
    const pad = 4 / scale;
    for (let i = objects.length - 1; i >= 0; i--) {
      const o = objects[i]!;
      const b = bboxOf(o);
      if (pdf[0] >= b[0] - pad && pdf[0] <= b[2] + pad && pdf[1] >= b[1] - pad && pdf[1] <= b[3] + pad) return o;
    }
    return null;
  }

  function down(e: PointerEvent): void {
    if (e.button !== 0 || editor.editingId) return;
    const p = local(e);
    const tool = editor.tool;
    if (tool === "select") {
      const hit = hitTest(p);
      editor.selectedId = hit?.id ?? null;
      if (hit && hit.kind !== "delete_annot") {
        editor.beginGesture();
        gesture = { type: "move", id: hit.id, start: p, origin: $state.snapshot(hit) as EditObject };
        root.setPointerCapture(e.pointerId);
      }
      return;
    }
    if (tool === "replace") return; // spans handle their own clicks
    e.preventDefault();
    root.setPointerCapture(e.pointerId);
    if (tool === "ink") gesture = { type: "ink", points: [p] };
    else if (tool === "note") placeNote(p);
    else if (DRAFT_TOOLS.has(tool)) gesture = { type: "draft", start: p, now: p };
  }

  function move(e: PointerEvent): void {
    if (!gesture) return;
    const p = local(e);
    if (gesture.type === "draft") gesture.now = p;
    else if (gesture.type === "ink") {
      const last = gesture.points[gesture.points.length - 1]!;
      if (Math.hypot(p[0] - last[0], p[1] - last[1]) >= 1.5) gesture.points.push(p);
    } else if (gesture.type === "move") {
      const a = toPdf(gesture.start[0], gesture.start[1]);
      const b = toPdf(p[0], p[1]);
      editor.update(gesture.id, moved(gesture.origin, b[0] - a[0], b[1] - a[1]), false);
    } else if (gesture.type === "resize") {
      const id = gesture.id;
      const o = editor.objects.find((x) => x.id === id);
      if (!o || !resizable(o)) return;
      const q = toPdf(p[0], p[1]);
      const r: Rect = [...gesture.origin];
      // corners: 0 = (x0,y1) top-left in PDF space, 1 = (x1,y1), 2 = (x1,y0), 3 = (x0,y0)
      if (gesture.corner === 0 || gesture.corner === 3) r[0] = q[0];
      else r[2] = q[0];
      if (gesture.corner === 0 || gesture.corner === 1) r[3] = q[1];
      else r[1] = q[1];
      const norm: Rect = [Math.min(r[0], r[2]), Math.min(r[1], r[3]), Math.max(r[0], r[2]), Math.max(r[1], r[3])];
      editor.update(o.id, { ...o, rect: norm }, false);
    }
  }

  async function up(e: PointerEvent): Promise<void> {
    const g = gesture;
    gesture = null;
    if (root.hasPointerCapture(e.pointerId)) root.releasePointerCapture(e.pointerId);
    if (!g) return;
    const s = editor.style;
    if (g.type === "ink") {
      if (g.points.length < 2) return;
      editor.add({
        id: newId(),
        page,
        kind: "ink",
        paths: [g.points.map((p) => toPdf(p[0], p[1]))],
        color: s.color,
        width: s.width,
        opacity: s.opacity,
      });
      return;
    }
    if (g.type !== "draft") return;
    const tool = editor.tool;
    const dragged = Math.hypot(g.now[0] - g.start[0], g.now[1] - g.start[1]) > 4;
    const rect = rectFromVp(g.start, g.now);
    const id = newId();
    switch (tool) {
      case "line":
      case "arrow":
        if (!dragged) return;
        editor.add({ id, page, kind: tool, from: toPdf(...g.start), to: toPdf(...g.now), color: s.color, width: s.width, opacity: s.opacity });
        break;
      case "rect":
      case "ellipse":
        if (!dragged) return;
        editor.add({ id, page, kind: tool, rect, stroke: s.color, fill: s.fill, width: s.width, opacity: s.opacity });
        break;
      case "whiteout":
        if (!dragged) return;
        editor.add({ id, page, kind: "whiteout", rect, color: s.fill ?? "#ffffff" });
        break;
      case "text": {
        const r: Rect = dragged ? rect : [rect[0], rect[1] - s.size * 1.6, rect[0] + 220, rect[1]];
        editor.add({ id, page, kind: "text", rect: r, text: "", font: { ...s.font }, size: s.size, color: s.color, align: "left" });
        editor.editingId = id;
        break;
      }
      case "image":
      case "signature":
        await placeImage(rect, dragged);
        break;
      case "link": {
        if (!dragged) return;
        const answer = prompt(t("Bağlantı adresi (https://…) veya sayfa numarası:", "Link address (https://…) or page number:"), "https://");
        if (!answer) return;
        const n = Number.parseInt(answer, 10);
        const isPage = /^\d+$/.test(answer.trim());
        editor.add({ id, page, kind: "link", rect, uri: isPage ? "" : answer.trim(), targetPage: isPage ? n : 0 });
        break;
      }
      case "highlight":
      case "underline":
      case "strikeout":
        await markup(tool, rect);
        break;
      case "field": {
        const type = s.fieldType;
        const size = type === "checkbox" || type === "radio" ? 14 : 0;
        const r: Rect = dragged ? rect : size ? [rect[0], rect[1] - size, rect[0] + size, rect[1]] : [rect[0], rect[1] - 20, rect[0] + 180, rect[1]];
        let options: string[] = [];
        if (type === "combo" || type === "list" || type === "radio") {
          const answer = prompt(t("Seçenekler (virgülle ayırın):", "Options (comma-separated):"), t("Evet, Hayır", "Yes, No"));
          if (answer === null) return;
          options = answer.split(",").map((x) => x.trim()).filter(Boolean).slice(0, 500);
          if (!options.length) return;
        }
        editor.add({ id, page, kind: "field", rect: r, fieldType: type, name: editor.nextFieldName(type), options, required: false });
        break;
      }
    }
  }

  function placeNote(p: Point): void {
    const id = newId();
    editor.add({ id, page, kind: "note", point: toPdf(p[0], p[1]), text: "", color: "#ffd84d" });
    editor.editingId = id;
  }

  async function placeImage(rect: Rect, dragged: boolean): Promise<void> {
    const url = editor.pendingImage;
    if (!url) return;
    const img = new Image();
    img.src = url;
    await img.decode().catch(() => undefined);
    const aspect = img.naturalWidth && img.naturalHeight ? img.naturalHeight / img.naturalWidth : 0.5;
    let r = rect;
    if (!dragged) {
      const w = editor.tool === "signature" ? 160 : Math.min(240, img.naturalWidth || 240);
      r = [rect[0], rect[1] - w * aspect, rect[0] + w, rect[1]];
    } else {
      // Keep the picture's proportions inside the dragged box.
      const w = r[2] - r[0];
      const h = w * aspect;
      r = [r[0], r[3] - h, r[2], r[3]];
    }
    editor.add({ id: newId(), page, kind: "image", rect: r, dataUrl: url, opacity: 1 });
    editor.tool = "select";
  }

  async function markup(kind: "highlight" | "underline" | "strikeout", rect: Rect): Promise<void> {
    let rects: Rect[] = [];
    try {
      const words = await spans.get(page, "word");
      const hit = words.filter((w) => intersects(w.rect, rect)).map((w) => w.rect);
      // Merge words that sit on the same line into one rect per line.
      hit.sort((a, b) => b[1] - a[1] || a[0] - b[0]);
      for (const r of hit) {
        const line = rects.find((l) => Math.abs(l[1] - r[1]) < (r[3] - r[1]) * 0.5);
        if (line) {
          line[0] = Math.min(line[0], r[0]);
          line[2] = Math.max(line[2], r[2]);
          line[3] = Math.max(line[3], r[3]);
        } else rects.push([...r]);
      }
    } catch {
      // no text info: fall back to the dragged area
    }
    if (!rects.length) rects = [rect];
    const color = kind === "highlight" ? "#ffe14d" : kind === "strikeout" ? "#d22" : editor.style.color;
    editor.add({ id: newId(), page, kind, rects, color, opacity: kind === "highlight" ? 0.45 : 1 });
  }

  function startReplace(span: Span): void {
    const existing = objects.find((o) => o.kind === "replace" && o.rect.join() === span.rect.join());
    if (existing) {
      editor.selectedId = existing.id;
      editor.editingId = existing.id;
      return;
    }
    const id = newId();
    editor.add({
      id,
      page,
      kind: "replace",
      rect: span.rect,
      original: span.text,
      text: span.text,
      font: span.matched_font ?? { family_id: "standard:helvetica", weight: span.bold ? 700 : 400, italic: span.italic },
      size: Math.round(span.size * 10) / 10,
      color: span.color,
      background: "auto",
    });
    editor.editingId = id;
    // Mirror the detected style in the toolbar, like Acrobat does.
    editor.style.font = { ...(span.matched_font ?? editor.style.font) };
    editor.style.size = Math.round(span.size * 10) / 10;
    editor.style.color = span.color;
  }

  function startResize(e: PointerEvent, o: EditObject, corner: number): void {
    if (!resizable(o)) return;
    e.stopPropagation();
    editor.beginGesture();
    gesture = { type: "resize", id: o.id, corner, origin: [...o.rect] };
    root.setPointerCapture(e.pointerId);
  }

  function finishEdit(o: EditObject, value: string): void {
    editor.editingId = null;
    if ((o.kind === "text" || o.kind === "note") && !value.trim()) {
      editor.remove(o.id);
      return;
    }
    if ("text" in o && o.text !== value) editor.update(o.id, { ...o, text: value });
  }

  function focusOnMount(el: HTMLTextAreaElement): void {
    queueMicrotask(() => {
      el.focus();
      el.select();
    });
  }

  function arrowHead(from: Point, to: Point, w: number): string {
    const [x1, y1] = toVp(from);
    const [x2, y2] = toVp(to);
    const ang = Math.atan2(y2 - y1, x2 - x1);
    const len = 8 + w * 2 * scale;
    const a1 = ang + Math.PI - 0.45;
    const a2 = ang + Math.PI + 0.45;
    return `${x2},${y2} ${x2 + len * Math.cos(a1)},${y2 + len * Math.sin(a1)} ${x2 + len * Math.cos(a2)},${y2 + len * Math.sin(a2)}`;
  }

  const draftBox = $derived(
    gesture?.type === "draft"
      ? {
          left: Math.min(gesture.start[0], gesture.now[0]),
          top: Math.min(gesture.start[1], gesture.now[1]),
          width: Math.abs(gesture.now[0] - gesture.start[0]),
          height: Math.abs(gesture.now[1] - gesture.start[1]),
        }
      : null,
  );
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  class="overlay"
  class:drawing={editor.tool !== "select" && editor.tool !== "replace"}
  bind:this={root}
  onpointerdown={down}
  onpointermove={move}
  onpointerup={up}
  onpointercancel={() => (gesture = null)}
>
  <svg width={viewport.width} height={viewport.height} aria-hidden="true">
    {#each objects as o (o.id)}
      {#if o.kind === "rect" || o.kind === "whiteout" || o.kind === "link"}
        {@const b = box(o.rect)}
        <rect
          x={b.left}
          y={b.top}
          width={b.width}
          height={b.height}
          fill={o.kind === "whiteout" ? o.color : o.kind === "rect" ? (o.fill ?? "none") : "rgb(47 84 150 / 0.08)"}
          stroke={o.kind === "rect" ? (o.stroke ?? "none") : o.kind === "link" ? "#2f5496" : "none"}
          stroke-width={o.kind === "rect" ? o.width * scale : 1}
          stroke-dasharray={o.kind === "link" ? "4 3" : undefined}
          opacity={o.kind === "rect" ? o.opacity : 1}
        />
      {:else if o.kind === "ellipse"}
        {@const b = box(o.rect)}
        <ellipse
          cx={b.left + b.width / 2}
          cy={b.top + b.height / 2}
          rx={b.width / 2}
          ry={b.height / 2}
          fill={o.fill ?? "none"}
          stroke={o.stroke ?? "none"}
          stroke-width={o.width * scale}
          opacity={o.opacity}
        />
      {:else if o.kind === "line" || o.kind === "arrow"}
        {@const a = toVp(o.from)}
        {@const b = toVp(o.to)}
        <g opacity={o.opacity}>
          <line x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke={o.color} stroke-width={o.width * scale} stroke-linecap="round" />
          {#if o.kind === "arrow"}<polygon points={arrowHead(o.from, o.to, o.width)} fill={o.color} />{/if}
        </g>
      {:else if o.kind === "ink"}
        {#each o.paths as path, i (i)}
          <polyline
            points={path.map((p) => toVp(p).join(",")).join(" ")}
            fill="none"
            stroke={o.color}
            stroke-width={o.width * scale}
            stroke-linecap="round"
            stroke-linejoin="round"
            opacity={o.opacity}
          />
        {/each}
      {:else if o.kind === "highlight" || o.kind === "underline" || o.kind === "strikeout"}
        {#each o.rects as r, i (i)}
          {@const b = box(r)}
          {#if o.kind === "highlight"}
            <rect x={b.left} y={b.top} width={b.width} height={b.height} fill={o.color} opacity={o.opacity} style="mix-blend-mode:multiply" />
          {:else}
            {@const y = o.kind === "underline" ? b.top + b.height - 1 : b.top + b.height / 2}
            <line x1={b.left} x2={b.left + b.width} y1={y} y2={y} stroke={o.color} stroke-width={Math.max(1, scale)} />
          {/if}
        {/each}
      {:else if o.kind === "field"}
        {@const b = box(o.rect)}
        <rect x={b.left} y={b.top} width={b.width} height={b.height} fill="rgb(47 84 150 / 0.10)" stroke="#2f5496" stroke-width="1.2" />
      {:else if o.kind === "delete_annot"}
        {@const b = box(o.rect)}
        <rect x={b.left} y={b.top} width={b.width} height={b.height} fill="rgb(220 0 0 / 0.12)" stroke="#d22" stroke-dasharray="3 3" />
      {/if}
    {/each}

    {#if gesture?.type === "ink"}
      <polyline
        points={gesture.points.map((p) => p.join(",")).join(" ")}
        fill="none"
        stroke={editor.style.color}
        stroke-width={editor.style.width * scale}
        stroke-linecap="round"
        stroke-linejoin="round"
      />
    {/if}
    {#if gesture?.type === "draft" && draftBox}
      {#if editor.tool === "line" || editor.tool === "arrow"}
        <line x1={gesture.start[0]} y1={gesture.start[1]} x2={gesture.now[0]} y2={gesture.now[1]} stroke={editor.style.color} stroke-width={editor.style.width * scale} />
      {:else if editor.tool === "ellipse"}
        <ellipse
          cx={draftBox.left + draftBox.width / 2}
          cy={draftBox.top + draftBox.height / 2}
          rx={draftBox.width / 2}
          ry={draftBox.height / 2}
          fill="none"
          stroke={editor.style.color}
          stroke-dasharray="4 3"
        />
      {:else}
        <rect x={draftBox.left} y={draftBox.top} width={draftBox.width} height={draftBox.height} fill="rgb(47 84 150 / 0.08)" stroke="#2f5496" stroke-dasharray="4 3" />
      {/if}
    {/if}
  </svg>

  {#each objects as o (o.id)}
    {#if o.kind === "text" || o.kind === "replace"}
      {@const b = box(o.rect)}
      {@const editing = editor.editingId === o.id}
      <div
        class="textobj"
        class:replace={o.kind === "replace"}
        style:left={`${b.left}px`}
        style:top={`${b.top}px`}
        style:width={`${b.width}px`}
        style:min-height={`${b.height}px`}
        style:font-family={fonts.css(o.font)}
        style:font-weight={o.font.weight}
        style:font-style={o.font.italic ? "italic" : "normal"}
        style:font-size={`${o.size * scale}px`}
        style:color={o.color}
        style:text-align={o.kind === "text" ? o.align : "left"}
        style:background={o.kind === "replace" ? (o.background === "auto" ? "#fff" : o.background) : "transparent"}
      >
        {#if editing}
          <textarea
            use:focusOnMount
            value={o.text}
            onpointerdown={(e) => e.stopPropagation()}
            onkeydown={(e) => {
              if (e.key === "Escape") {
                e.stopPropagation();
                finishEdit(o, o.kind === "replace" ? o.text : (e.currentTarget as HTMLTextAreaElement).value);
              } else if (e.key === "Enter" && (o.kind === "replace" || e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                (e.currentTarget as HTMLTextAreaElement).blur();
              }
            }}
            onblur={(e) => finishEdit(o, e.currentTarget.value)}
          ></textarea>
        {:else}
          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <span
            class="content"
            ondblclick={() => {
              editor.selectedId = o.id;
              editor.editingId = o.id;
            }}>{o.text || " "}</span
          >
        {/if}
      </div>
    {:else if o.kind === "field"}
      {@const b = box(o.rect)}
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <span
        class="field-label"
        style:left={`${b.left}px`}
        style:top={`${Math.max(0, b.top - 16)}px`}
        ondblclick={() => {
          const name = prompt(t("Alan adı:", "Field name:"), o.name);
          if (name && name.trim() && !/[.\x00-\x1f]/.test(name)) editor.update(o.id, { ...o, name: name.trim().slice(0, 128) });
        }}>{o.fieldType} · {o.name}</span
      >
    {:else if o.kind === "image"}
      {@const b = box(o.rect)}
      <img
        class="imgobj"
        src={o.dataUrl}
        alt=""
        draggable="false"
        style:left={`${b.left}px`}
        style:top={`${b.top}px`}
        style:width={`${b.width}px`}
        style:height={`${b.height}px`}
        style:opacity={o.opacity}
      />
    {:else if o.kind === "note"}
      {@const [x, y] = toVp(o.point)}
      <div class="note" style:left={`${x}px`} style:top={`${y}px`} style:background={o.color}>
        <span aria-hidden="true">✎</span>
        {#if editor.editingId === o.id}
          <textarea
            class="note-text"
            use:focusOnMount
            value={o.text}
            placeholder={t("Not…", "Note…")}
            onpointerdown={(e) => e.stopPropagation()}
            onkeydown={(e) => e.key === "Escape" && (e.currentTarget as HTMLTextAreaElement).blur()}
            onblur={(e) => finishEdit(o, e.currentTarget.value)}
          ></textarea>
        {/if}
      </div>
    {/if}
  {/each}

  {#if editor.tool === "replace"}
    {#each lineSpans as s (s.id)}
      {#if !replacedRects.some((r) => r.join() === s.rect.join())}
        {@const b = box(s.rect)}
        <button
          class="span"
          title={s.text}
          aria-label={`${t("Değiştir", "Replace")}: ${s.text}`}
          style:left={`${b.left}px`}
          style:top={`${b.top}px`}
          style:width={`${b.width}px`}
          style:height={`${b.height}px`}
          onpointerdown={(e) => e.stopPropagation()}
          onclick={() => startReplace(s)}
        ></button>
      {/if}
    {/each}
    {#if spanError}<p class="span-error">{spanError}</p>{/if}
    {#if spansLoaded && !lineSpans.length}
      <div class="no-text" role="status">
        <p>{t("Bu sayfada seçilebilir metin yok (taranmış / görsel).", "This page has no selectable text (scanned / image).")}</p>
        {#if onocr}
          <button class="primary small" onpointerdown={(e) => e.stopPropagation()} onclick={onocr}
            >{t("OCR ile metni tanı ve düzenle", "Recognise text with OCR and edit")}</button
          >
        {/if}
      </div>
    {/if}
  {/if}

  {#if editor.selected && editor.selected.page === page && !editor.editingId}
    {@const o = editor.selected}
    {@const b = box(bboxOf(o))}
    <div class="selection" style:left={`${b.left - 3}px`} style:top={`${b.top - 3}px`} style:width={`${b.width + 6}px`} style:height={`${b.height + 6}px`}>
      {#if resizable(o)}
        {#each [0, 1, 2, 3] as c (c)}
          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <span class="handle h{c}" onpointerdown={(e) => startResize(e, o, c)}></span>
        {/each}
      {/if}
    </div>
  {/if}
</div>

<style>
  .overlay {
    position: absolute;
    inset: 0;
    z-index: 2;
    touch-action: pan-x pan-y pinch-zoom;
  }
  .overlay.drawing {
    cursor: crosshair;
    touch-action: none;
  }
  svg {
    position: absolute;
    inset: 0;
    pointer-events: none;
  }
  .textobj {
    position: absolute;
    line-height: 1.2;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    outline: 1px dashed rgb(47 84 150 / 0.45);
  }
  .textobj.replace {
    outline-color: rgb(24 121 78 / 0.6);
    /* The server shrinks replacement text to the original line; mirror it. */
    white-space: pre;
    overflow: visible;
  }
  .textobj textarea {
    position: absolute;
    inset: 0;
    width: 100%;
    min-height: 100%;
    padding: 0;
    margin: 0;
    border: 0;
    outline: 2px solid var(--accent);
    background: rgb(255 255 255 / 0.9);
    font: inherit;
    color: inherit;
    text-align: inherit;
    line-height: inherit;
    resize: none;
  }
  .content {
    display: block;
    min-height: 1em;
  }
  .field-label {
    position: absolute;
    padding: 0 4px;
    border-radius: 3px;
    background: #2f5496;
    color: #fff;
    font: 600 10px/16px system-ui, sans-serif;
    white-space: nowrap;
    cursor: text;
  }
  .imgobj {
    position: absolute;
    pointer-events: none;
    user-select: none;
  }
  .note {
    position: absolute;
    width: 22px;
    height: 22px;
    display: grid;
    place-items: center;
    border-radius: 4px;
    box-shadow: 0 1px 3px rgb(0 0 0 / 0.3);
    font-size: 13px;
    color: #3d3000;
  }
  .note-text {
    position: absolute;
    left: 26px;
    top: 0;
    width: 220px;
    height: 110px;
    padding: 6px;
    border: 1px solid #c9a800;
    border-radius: 6px;
    background: #fff8c4;
    font: 13px/1.35 system-ui, sans-serif;
    color: #222;
    z-index: 3;
  }
  .span {
    position: absolute;
    padding: 0;
    min-height: 0;
    border: 1px solid transparent;
    border-radius: 2px;
    background: transparent;
    cursor: text;
  }
  .span:hover,
  .span:focus-visible {
    border-color: rgb(24 121 78 / 0.8);
    background: rgb(24 121 78 / 0.08);
  }
  .span-error {
    position: absolute;
    top: 6px;
    left: 6px;
    margin: 0;
    padding: 4px 8px;
    border-radius: 6px;
    background: var(--danger);
    color: #fff;
    font-size: 0.8rem;
  }
  .no-text {
    position: absolute;
    top: 12px;
    left: 50%;
    transform: translateX(-50%);
    display: grid;
    gap: 8px;
    justify-items: center;
    max-width: 90%;
    padding: 12px 16px;
    border-radius: 10px;
    background: var(--surface);
    border: 1px solid var(--border);
    box-shadow: 0 6px 20px rgb(0 0 0 / 0.15);
    text-align: center;
    font-size: 0.9rem;
  }
  .no-text p {
    margin: 0;
  }
  .selection {
    position: absolute;
    border: 1.5px solid var(--accent);
    border-radius: 3px;
    pointer-events: none;
  }
  .handle {
    position: absolute;
    width: 10px;
    height: 10px;
    background: #fff;
    border: 1.5px solid var(--accent);
    border-radius: 2px;
    pointer-events: auto;
  }
  .h0 {
    left: -6px;
    top: -6px;
    cursor: nwse-resize;
  }
  .h1 {
    right: -6px;
    top: -6px;
    cursor: nesw-resize;
  }
  .h2 {
    right: -6px;
    bottom: -6px;
    cursor: nwse-resize;
  }
  .h3 {
    left: -6px;
    bottom: -6px;
    cursor: nesw-resize;
  }
</style>
