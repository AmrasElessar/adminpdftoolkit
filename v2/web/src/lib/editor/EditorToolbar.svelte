<script lang="ts">
  import { t } from "../i18n.svelte";
  import { fonts } from "./fonts.svelte";
  import type { EditorState, Tool } from "./model.svelte";
  import SignaturePad from "./SignaturePad.svelte";

  let { editor, saving = false, onsave }: { editor: EditorState; saving?: boolean; onsave: () => void } = $props();

  let showSignature = $state(false);
  let picker: HTMLInputElement;

  const TOOLS: { id: Tool; icon: string; tr: string; en: string; key?: string }[] = [
    { id: "select", icon: "⬚", tr: "Seç / taşı", en: "Select / move", key: "V" },
    { id: "replace", icon: "✎", tr: "Metni düzenle", en: "Edit text", key: "E" },
    { id: "text", icon: "T", tr: "Metin ekle", en: "Add text", key: "T" },
    { id: "highlight", icon: "▮", tr: "Vurgula", en: "Highlight", key: "H" },
    { id: "underline", icon: "U̲", tr: "Altını çiz", en: "Underline" },
    { id: "strikeout", icon: "S̶", tr: "Üstünü çiz", en: "Strikethrough" },
    { id: "note", icon: "🗨", tr: "Not", en: "Note", key: "N" },
    { id: "ink", icon: "✍", tr: "Serbest çizim", en: "Draw", key: "D" },
    { id: "rect", icon: "▭", tr: "Dikdörtgen", en: "Rectangle", key: "R" },
    { id: "ellipse", icon: "◯", tr: "Elips", en: "Ellipse" },
    { id: "line", icon: "╱", tr: "Çizgi", en: "Line", key: "L" },
    { id: "arrow", icon: "➚", tr: "Ok", en: "Arrow" },
    { id: "whiteout", icon: "▯", tr: "Beyazla kapat", en: "Whiteout" },
    { id: "image", icon: "🖼", tr: "Görsel", en: "Image" },
    { id: "signature", icon: "✒", tr: "İmza", en: "Signature" },
    { id: "link", icon: "🔗", tr: "Bağlantı", en: "Link" },
  ];

  const WEIGHTS = [
    [100, "Thin"],
    [300, "Light"],
    [400, "Regular"],
    [500, "Medium"],
    [600, "Semibold"],
    [700, "Bold"],
    [900, "Black"],
  ] as const;

  $effect(() => {
    void fonts.load();
  });

  function choose(tool: Tool): void {
    if (tool === "signature") {
      showSignature = true;
      return;
    }
    if (tool === "image") {
      picker.click();
      return;
    }
    editor.tool = tool;
    editor.selectedId = null;
  }

  function pickImage(): void {
    const file = picker.files?.[0];
    picker.value = "";
    if (!file) return;
    if (file.size > 15 * 1024 * 1024) {
      alert(t("Görsel 15 MB'tan küçük olmalı.", "The image must be under 15 MB."));
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      editor.pendingImage = String(reader.result);
      editor.tool = "image";
    };
    reader.readAsDataURL(file);
  }

  /** Apply a style change to the selection too, like any editor does. */
  function restyle(patch: Partial<typeof editor.style>): void {
    Object.assign(editor.style, patch);
    const o = editor.selected;
    if (!o) return;
    const next: Record<string, unknown> = { ...o };
    if (patch.color !== undefined) {
      if ("color" in o) next.color = patch.color;
      if ("stroke" in o) next.stroke = patch.color;
    }
    if (patch.fill !== undefined && "fill" in o) next.fill = patch.fill;
    if (patch.width !== undefined && "width" in o) next.width = patch.width;
    if (patch.opacity !== undefined && "opacity" in o) next.opacity = patch.opacity;
    if (patch.size !== undefined && "size" in o) next.size = patch.size;
    if (patch.font !== undefined && "font" in o) next.font = patch.font;
    editor.update(o.id, next as unknown as typeof o);
  }

  const family = $derived(fonts.family(editor.style.font.family_id));
  const textual = $derived(editor.tool === "text" || editor.tool === "replace" || editor.selected?.kind === "text" || editor.selected?.kind === "replace");
</script>

<div class="toolbar" role="toolbar" aria-label={t("Düzenleme araçları", "Editing tools")}>
  <div class="tools">
    {#each TOOLS as tool (tool.id)}
      <button
        class="tool"
        class:on={editor.tool === tool.id}
        aria-pressed={editor.tool === tool.id}
        title={`${t(tool.tr, tool.en)}${tool.key ? ` (${tool.key})` : ""}`}
        aria-label={t(tool.tr, tool.en)}
        onclick={() => choose(tool.id)}>{tool.icon}</button
      >
    {/each}
  </div>

  <div class="style">
    {#if textual}
      <select
        aria-label={t("Font", "Font")}
        value={editor.style.font.family_id}
        onchange={(e) => restyle({ font: { ...editor.style.font, family_id: e.currentTarget.value } })}
      >
        {#each ["standard", "bundled", "system"] as src (src)}
          {@const list = fonts.families.filter((f) => f.source === src)}
          {#if list.length}
            <optgroup label={src === "standard" ? t("Standart", "Standard") : src === "bundled" ? t("Uygulama", "Bundled") : t("Bu bilgisayar", "This computer")}>
              {#each list as f (f.id)}<option value={f.id}>{f.family}{f.restricted ? " 🔒" : ""}</option>{/each}
            </optgroup>
          {/if}
        {/each}
      </select>
      <select
        aria-label={t("Kalınlık", "Weight")}
        value={editor.style.font.weight}
        onchange={(e) => restyle({ font: { ...editor.style.font, weight: Number(e.currentTarget.value) } })}
      >
        {#each WEIGHTS as [w, name] (w)}
          <option value={w} disabled={!!family?.styles.length && !family.styles.some((s) => s.weight === w)}>{name}</option>
        {/each}
      </select>
      <button
        class="tool"
        class:on={editor.style.font.italic}
        aria-pressed={editor.style.font.italic}
        aria-label={t("İtalik", "Italic")}
        onclick={() => restyle({ font: { ...editor.style.font, italic: !editor.style.font.italic } })}><i>I</i></button
      >
      <input
        class="num"
        type="number"
        min="4"
        max="200"
        step="0.5"
        aria-label={t("Yazı boyutu", "Font size")}
        value={editor.style.size}
        onchange={(e) => restyle({ size: Number(e.currentTarget.value) || 12 })}
      />
    {/if}
    <label class="swatch" title={t("Renk", "Colour")}>
      <input type="color" value={editor.style.color} onchange={(e) => restyle({ color: e.currentTarget.value })} />
    </label>
    {#if editor.tool === "rect" || editor.tool === "ellipse" || editor.tool === "whiteout" || editor.selected?.kind === "rect" || editor.selected?.kind === "ellipse"}
      <label class="swatch fill" title={t("Dolgu", "Fill")}>
        <input type="color" value={editor.style.fill ?? "#ffffff"} onchange={(e) => restyle({ fill: e.currentTarget.value })} />
      </label>
      <button class="small ghost" onclick={() => restyle({ fill: null })}>{t("Dolgusuz", "No fill")}</button>
    {/if}
    {#if !textual}
      <input
        class="num"
        type="number"
        min="0.5"
        max="40"
        step="0.5"
        aria-label={t("Çizgi kalınlığı", "Stroke width")}
        value={editor.style.width}
        onchange={(e) => restyle({ width: Number(e.currentTarget.value) || 1 })}
      />
      <input
        type="range"
        min="0.1"
        max="1"
        step="0.05"
        aria-label={t("Saydamlık", "Opacity")}
        value={editor.style.opacity}
        onchange={(e) => restyle({ opacity: Number(e.currentTarget.value) })}
      />
    {/if}
  </div>

  <div class="actions">
    <button class="tool" onclick={() => editor.undo()} disabled={!editor.canUndo} title="Ctrl+Z" aria-label={t("Geri al", "Undo")}>↶</button>
    <button class="tool" onclick={() => editor.redo()} disabled={!editor.canRedo} title="Ctrl+Y" aria-label={t("Yinele", "Redo")}>↷</button>
    <button
      class="tool"
      onclick={() => editor.selectedId && editor.remove(editor.selectedId)}
      disabled={!editor.selectedId}
      title="Delete"
      aria-label={t("Seçileni sil", "Delete selected")}>🗑</button
    >
    <button class="primary" disabled={!editor.count || saving} onclick={onsave}>
      {saving ? t("Kaydediliyor…", "Saving…") : `${t("Kaydet", "Save")}${editor.count ? ` (${editor.count})` : ""}`}
    </button>
  </div>
  <input bind:this={picker} type="file" accept="image/png,image/jpeg,image/webp" hidden onchange={pickImage} />
</div>

{#if showSignature}
  <SignaturePad
    onclose={() => (showSignature = false)}
    onpick={(url) => {
      showSignature = false;
      editor.pendingImage = url;
      editor.tool = "signature";
    }}
  />
{/if}

<style>
  .toolbar {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 14px;
    align-items: center;
    padding: 8px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
  }
  .tools,
  .style,
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    align-items: center;
  }
  .actions {
    margin-left: auto;
  }
  .tool {
    width: 36px;
    min-height: 36px;
    padding: 0;
    font-size: 1rem;
    border-color: transparent;
    background: transparent;
  }
  .tool:hover:not(:disabled) {
    background: var(--surface-2);
  }
  .tool.on {
    background: var(--accent-soft);
    border-color: var(--accent);
    color: var(--accent);
  }
  select {
    width: auto;
    max-width: 180px;
    padding: 6px 8px;
  }
  .num {
    width: 64px !important;
    padding: 6px 8px !important;
  }
  .swatch input {
    width: 34px;
    height: 34px;
  }
</style>
