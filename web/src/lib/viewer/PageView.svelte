<script lang="ts">
  import { onDestroy, type Snippet } from "svelte";
  import { pdfjs, type PDFPageProxy, type PageViewport } from "./pdf";
  import "./text-layer.css";

  let {
    page,
    scale,
    textLayer = true,
    hits = [],
    current = -1,
    overlay,
  }: {
    page: PDFPageProxy;
    scale: number;
    textLayer?: boolean;
    /** Indices of text items to highlight (search results). */
    hits?: number[];
    current?: number;
    overlay?: Snippet<[PageViewport]>;
  } = $props();

  // Never allocate more than ~16 MP per canvas, whatever the zoom and DPR.
  const MAX_CANVAS_PIXELS = 16_000_000;

  let wrapper: HTMLDivElement;
  let canvas: HTMLCanvasElement;
  let textDiv: HTMLDivElement | undefined = $state();
  let visible = $state(false);
  let renderTask: ReturnType<PDFPageProxy["render"]> | null = null;
  let textTask: InstanceType<typeof pdfjs.TextLayer> | null = null;
  let textDivs: HTMLElement[] = [];

  const viewport = $derived(page.getViewport({ scale }));

  $effect(() => {
    const io = new IntersectionObserver((entries) => (visible = entries.some((e) => e.isIntersecting)), {
      rootMargin: "800px 0px",
    });
    io.observe(wrapper);
    return () => io.disconnect();
  });

  $effect(() => {
    if (!visible) return;
    const vp = viewport;
    const timer = setTimeout(() => void draw(vp), 60); // debounce zoom bursts
    return () => clearTimeout(timer);
  });

  $effect(() => {
    const set = new Set(hits);
    textDivs.forEach((d, i) => {
      d.classList.toggle("hit", set.has(i));
      d.classList.toggle("current", i === current);
    });
    if (current >= 0) textDivs[current]?.scrollIntoView({ block: "center", behavior: "smooth" });
  });

  async function draw(vp: PageViewport): Promise<void> {
    renderTask?.cancel();
    textTask?.cancel();
    const ratio = Math.min(window.devicePixelRatio || 1, Math.sqrt(MAX_CANVAS_PIXELS / (vp.width * vp.height)));
    const off = document.createElement("canvas");
    off.width = Math.floor(vp.width * ratio);
    off.height = Math.floor(vp.height * ratio);
    const task = page.render({
      canvas: off,
      viewport: vp,
      transform: ratio !== 1 ? [ratio, 0, 0, ratio, 0, 0] : undefined,
    });
    renderTask = task;
    try {
      await task.promise;
    } catch {
      return; // cancelled by a newer render
    }
    if (renderTask !== task) return;
    // Swap in the finished bitmap at once: no blank flash while zooming.
    canvas.width = off.width;
    canvas.height = off.height;
    canvas.getContext("2d")?.drawImage(off, 0, 0);

    if (textLayer && textDiv) {
      textDiv.replaceChildren();
      const tl = new pdfjs.TextLayer({ textContentSource: page.streamTextContent(), container: textDiv, viewport: vp });
      textTask = tl;
      try {
        await tl.render();
        textDivs = tl.textDivs;
        const set = new Set(hits);
        textDivs.forEach((d, i) => {
          d.classList.toggle("hit", set.has(i));
          d.classList.toggle("current", i === current);
        });
      } catch {
        // cancelled
      }
    }
  }

  onDestroy(() => {
    renderTask?.cancel();
    textTask?.cancel();
  });
</script>

<div
  class="page"
  bind:this={wrapper}
  style:width={`${viewport.width}px`}
  style:height={`${viewport.height}px`}
  style:--scale-factor={scale}
  style:--total-scale-factor={scale}
  style:--user-unit="1"
  data-page={page.pageNumber}
>
  <canvas bind:this={canvas} style:width="100%" style:height="100%"></canvas>
  {#if textLayer}<div class="textLayer" bind:this={textDiv}></div>{/if}
  {#if overlay}{@render overlay(viewport)}{/if}
</div>

<style>
  .page {
    position: relative;
    background: #fff;
    box-shadow:
      0 1px 3px rgb(0 0 0 / 0.15),
      0 8px 24px rgb(0 0 0 / 0.08);
    flex: none;
  }
  canvas {
    display: block;
  }
</style>
