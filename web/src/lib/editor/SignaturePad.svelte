<script lang="ts">
  import { t } from "../i18n.svelte";

  let { onpick, onclose }: { onpick: (dataUrl: string) => void; onclose: () => void } = $props();

  let mode = $state<"draw" | "type" | "upload">("draw");
  let canvas: HTMLCanvasElement | undefined = $state();
  let drawing = false;
  let hasInk = $state(false);
  let typed = $state("");
  let color = $state("#0b2a6f");
  let dialog: HTMLDialogElement;

  $effect(() => {
    dialog.showModal();
  });

  $effect(() => {
    if (mode !== "draw" || !canvas) return;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = canvas.clientWidth * ratio;
    canvas.height = canvas.clientHeight * ratio;
    const ctx = canvas.getContext("2d")!;
    ctx.scale(ratio, ratio);
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    hasInk = false;
  });

  function pos(e: PointerEvent): [number, number] {
    const r = canvas!.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  }

  function start(e: PointerEvent): void {
    drawing = true;
    canvas!.setPointerCapture(e.pointerId);
    const ctx = canvas!.getContext("2d")!;
    ctx.strokeStyle = color;
    ctx.lineWidth = 2.6;
    ctx.beginPath();
    ctx.moveTo(...pos(e));
  }

  function draw(e: PointerEvent): void {
    if (!drawing) return;
    const ctx = canvas!.getContext("2d")!;
    // Pressure-aware width where the device reports it (pens, some touch).
    ctx.lineWidth = e.pressure > 0 && e.pointerType === "pen" ? 1.2 + e.pressure * 3 : 2.6;
    ctx.lineTo(...pos(e));
    ctx.stroke();
    hasInk = true;
  }

  function clear(): void {
    const ctx = canvas!.getContext("2d")!;
    ctx.clearRect(0, 0, canvas!.width, canvas!.height);
    hasInk = false;
  }

  /** Crop transparent margins so the placed signature hugs the ink. */
  function trimmed(src: HTMLCanvasElement): string {
    const ctx = src.getContext("2d")!;
    const { width, height } = src;
    const data = ctx.getImageData(0, 0, width, height).data;
    let x0 = width,
      y0 = height,
      x1 = 0,
      y1 = 0;
    for (let y = 0; y < height; y++)
      for (let x = 0; x < width; x++)
        if (data[(y * width + x) * 4 + 3]! > 8) {
          if (x < x0) x0 = x;
          if (y < y0) y0 = y;
          if (x > x1) x1 = x;
          if (y > y1) y1 = y;
        }
    if (x1 <= x0 || y1 <= y0) return src.toDataURL("image/png");
    const pad = 6;
    const out = document.createElement("canvas");
    out.width = x1 - x0 + pad * 2;
    out.height = y1 - y0 + pad * 2;
    out.getContext("2d")!.drawImage(src, x0 - pad, y0 - pad, out.width, out.height, 0, 0, out.width, out.height);
    return out.toDataURL("image/png");
  }

  function useTyped(): void {
    const c = document.createElement("canvas");
    c.width = 900;
    c.height = 220;
    const ctx = c.getContext("2d")!;
    ctx.fillStyle = color;
    ctx.font = "italic 96px 'Segoe Script', 'Brush Script MT', 'Lucida Handwriting', cursive";
    ctx.textBaseline = "middle";
    ctx.fillText(typed, 20, 110, 860);
    onpick(trimmed(c));
  }

  function upload(e: Event): void {
    const file = (e.currentTarget as HTMLInputElement).files?.[0];
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) {
      alert(t("Görsel 10 MB'tan küçük olmalı.", "The image must be under 10 MB."));
      return;
    }
    const reader = new FileReader();
    reader.onload = () => onpick(String(reader.result));
    reader.readAsDataURL(file);
  }
</script>

<dialog bind:this={dialog} onclose={onclose} aria-labelledby="sig-title">
  <h2 id="sig-title">{t("İmza oluştur", "Create signature")}</h2>
  <div class="tabs" role="tablist">
    <button role="tab" aria-selected={mode === "draw"} class:on={mode === "draw"} onclick={() => (mode = "draw")}>{t("Çiz", "Draw")}</button>
    <button role="tab" aria-selected={mode === "type"} class:on={mode === "type"} onclick={() => (mode = "type")}>{t("Yaz", "Type")}</button>
    <button role="tab" aria-selected={mode === "upload"} class:on={mode === "upload"} onclick={() => (mode = "upload")}>{t("Görsel yükle", "Upload image")}</button>
    <input type="color" bind:value={color} aria-label={t("Renk", "Colour")} />
  </div>

  {#if mode === "draw"}
    <canvas bind:this={canvas} class="pad" onpointerdown={start} onpointermove={draw} onpointerup={() => (drawing = false)}></canvas>
    <p class="hint">{t("Fare, parmak veya kalemle imzalayın.", "Sign with mouse, finger or pen.")}</p>
  {:else if mode === "type"}
    <input class="typed" bind:value={typed} placeholder={t("Ad Soyad", "Full name")} style:color />
  {:else}
    <input type="file" accept="image/png,image/jpeg,image/webp" onchange={upload} />
    <p class="hint">{t("Şeffaf arka planlı PNG en iyi sonucu verir.", "A PNG with a transparent background works best.")}</p>
  {/if}

  <div class="buttons">
    {#if mode === "draw"}<button class="ghost" onclick={clear} disabled={!hasInk}>{t("Temizle", "Clear")}</button>{/if}
    <span class="grow"></span>
    <button class="ghost" onclick={() => dialog.close()}>{t("Vazgeç", "Cancel")}</button>
    {#if mode === "draw"}
      <button class="primary" disabled={!hasInk} onclick={() => onpick(trimmed(canvas!))}>{t("Kullan", "Use")}</button>
    {:else if mode === "type"}
      <button class="primary" disabled={!typed.trim()} onclick={useTyped}>{t("Kullan", "Use")}</button>
    {/if}
  </div>
</dialog>

<style>
  dialog {
    width: min(560px, calc(100vw - 32px));
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
    color: var(--text);
    padding: 20px;
  }
  dialog::backdrop {
    background: rgb(0 0 0 / 0.4);
  }
  h2 {
    margin: 0 0 12px;
    font-size: 1.15rem;
  }
  .tabs {
    display: flex;
    gap: 6px;
    margin-bottom: 12px;
    align-items: center;
  }
  .tabs button.on {
    background: var(--accent);
    color: var(--on-accent);
    border-color: var(--accent);
  }
  .tabs input[type="color"] {
    margin-left: auto;
  }
  .pad {
    width: 100%;
    height: 200px;
    border: 1.5px dashed var(--border-strong);
    border-radius: 10px;
    background: #fff;
    touch-action: none;
    cursor: crosshair;
  }
  .typed {
    font: italic 2.2rem "Segoe Script", "Brush Script MT", "Lucida Handwriting", cursive;
    background: #fff;
  }
  .hint {
    margin: 6px 0 0;
    color: var(--muted);
    font-size: 0.85rem;
  }
  .buttons {
    display: flex;
    gap: 8px;
    margin-top: 16px;
  }
  .grow {
    flex: 1;
  }
</style>
