<script lang="ts">
  import { t } from "../i18n.svelte";
  import { pdfRectToViewport, type PageViewport } from "../viewer/pdf";
  import type { KvkkState, Rect } from "./state.svelte";

  let { page, viewport, kvkk }: { page: number; viewport: PageViewport; kvkk: KvkkState } = $props();

  let root: HTMLDivElement;
  let drag = $state<{ x0: number; y0: number; x1: number; y1: number } | null>(null);

  const items = $derived(kvkk.findings.filter((f) => f.page === page));

  function box(r: readonly number[]): { left: number; top: number; width: number; height: number } {
    return pdfRectToViewport(viewport, r);
  }

  function local(e: PointerEvent): [number, number] {
    const r = root.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  }

  function up(e: PointerEvent): void {
    const d = drag;
    drag = null;
    if (!d || Math.abs(d.x1 - d.x0) < 4 || Math.abs(d.y1 - d.y0) < 4) return;
    const [ax, ay] = viewport.convertToPdfPoint(d.x0, d.y0) as [number, number];
    const [bx, by] = viewport.convertToPdfPoint(d.x1, d.y1) as [number, number];
    const rect: Rect = [Math.min(ax, bx), Math.min(ay, by), Math.max(ax, bx), Math.max(ay, by)];
    kvkk.addManual(page, rect);
    if (root.hasPointerCapture(e.pointerId)) root.releasePointerCapture(e.pointerId);
  }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  class="overlay"
  bind:this={root}
  title={t("Elle alan eklemek için sürükleyin", "Drag to add an area by hand")}
  onpointerdown={(e) => {
    if (e.button !== 0 || (e.target as HTMLElement).closest(".finding")) return;
    const [x, y] = local(e);
    drag = { x0: x, y0: y, x1: x, y1: y };
    root.setPointerCapture(e.pointerId);
  }}
  onpointermove={(e) => {
    if (!drag) return;
    const [x, y] = local(e);
    drag.x1 = x;
    drag.y1 = y;
  }}
  onpointerup={up}
>
  {#each items as f (f.id)}
    {#each f.rects as r, i (i)}
      {@const b = box(r)}
      <button
        class="finding {f.action}"
        class:focused={kvkk.focused === f.id}
        style:left={`${b.left - 1}px`}
        style:top={`${b.top - 1}px`}
        style:width={`${b.width + 2}px`}
        style:height={`${b.height + 2}px`}
        style:font-size={`${Math.max(4, Math.min(16, b.height * 0.8))}px`}
        aria-label={`${f.kind}: ${f.text}`}
        onclick={() => (kvkk.focused = f.id)}
      >
        {#if f.action === "mask" && i === 0}<span>{f.mask}</span>{/if}
      </button>
    {/each}
  {/each}
  {#if drag}
    <div
      class="draft"
      style:left={`${Math.min(drag.x0, drag.x1)}px`}
      style:top={`${Math.min(drag.y0, drag.y1)}px`}
      style:width={`${Math.abs(drag.x1 - drag.x0)}px`}
      style:height={`${Math.abs(drag.y1 - drag.y0)}px`}
    ></div>
  {/if}
</div>

<style>
  .overlay {
    position: absolute;
    inset: 0;
    z-index: 2;
    cursor: crosshair;
    touch-action: none;
  }
  .finding {
    position: absolute;
    min-height: 0;
    padding: 0 2px;
    border: 1.5px solid transparent;
    border-radius: 2px;
    font-weight: 600;
    font-family: ui-monospace, monospace;
    line-height: 1;
    justify-content: flex-start;
    overflow: hidden;
    cursor: pointer;
  }
  /* Opaque like the result: the preview never shows what will be removed. */
  .finding.black {
    background: #000;
  }
  .finding.white {
    background: #fff;
    border-color: #999;
  }
  .finding.mask {
    background: #fff;
    border-color: #2f5496;
    color: #111;
  }
  .finding.blur {
    background: rgb(200 200 200 / 0.25);
    backdrop-filter: blur(4px);
    border-color: #888;
  }
  .finding.keep {
    background: transparent;
    border: 1.5px dashed #d08700;
  }
  .finding.focused {
    outline: 2.5px solid #ff7a00;
    outline-offset: 2px;
  }
  .draft {
    position: absolute;
    border: 1.5px dashed #c00;
    background: rgb(200 0 0 / 0.08);
  }
</style>
