<script lang="ts">
  import { t } from "../i18n.svelte";
  import { fonts } from "./fonts.svelte";
  import { type EditorState, keyFor, type Tool } from "./model.svelte";
  import SignaturePad from "./SignaturePad.svelte";

  let { editor, saving = false, onsave }: { editor: EditorState; saving?: boolean; onsave: () => void } = $props();

  let showSignature = $state(false);
  let picker: HTMLInputElement;

  const GROUPS: { tr: string; en: string; tools: { id: Tool; icon: string; tr: string; en: string }[] }[] = [
    { tr: "Seç", en: "Select", tools: [{ id: "select", icon: "⬚", tr: "Seç / taşı", en: "Select" }] },
    {
      tr: "Metin",
      en: "Text",
      tools: [
        { id: "replace", icon: "✎", tr: "Metni düzenle", en: "Edit text" },
        { id: "text", icon: "T", tr: "Metin ekle", en: "Add text" },
      ],
    },
    {
      tr: "İşaretle",
      en: "Comment",
      tools: [
        { id: "highlight", icon: "▮", tr: "Vurgula", en: "Highlight" },
        { id: "underline", icon: "U̲", tr: "Altını çiz", en: "Underline" },
        { id: "strikeout", icon: "S̶", tr: "Üstünü çiz", en: "Strike" },
        { id: "note", icon: "🗨", tr: "Not", en: "Note" },
      ],
    },
    {
      tr: "Çiz",
      en: "Draw",
      tools: [
        { id: "ink", icon: "✍", tr: "Kalem", en: "Pen" },
        { id: "rect", icon: "▭", tr: "Dikdörtgen", en: "Rectangle" },
        { id: "ellipse", icon: "◯", tr: "Elips", en: "Ellipse" },
        { id: "line", icon: "╱", tr: "Çizgi", en: "Line" },
        { id: "arrow", icon: "➚", tr: "Ok", en: "Arrow" },
      ],
    },
    {
      tr: "Ekle",
      en: "Insert",
      tools: [
        { id: "image", icon: "🖼", tr: "Görsel", en: "Image" },
        { id: "signature", icon: "✒", tr: "İmza", en: "Signature" },
        { id: "link", icon: "🔗", tr: "Bağlantı", en: "Link" },
        { id: "field", icon: "☐", tr: "Form alanı", en: "Form field" },
      ],
    },
    { tr: "Kapat", en: "Cover", tools: [{ id: "whiteout", icon: "▯", tr: "Beyazla", en: "Whiteout" }] },
  ];

  const FIELD_TYPES = [
    ["text", "Metin kutusu", "Text box"],
    ["checkbox", "Onay kutusu", "Checkbox"],
    ["radio", "Seçenek düğmeleri", "Radio buttons"],
    ["combo", "Açılır liste", "Dropdown"],
    ["list", "Liste kutusu", "List box"],
    ["signature", "İmza alanı", "Signature field"],
  ] as const;

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

  /** Also called by keyboard shortcuts (image/signature open their pickers). */
  export function choose(tool: Tool): void {
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
  <div class="row tools">
    {#each GROUPS as g (g.en)}
      <div class="group" role="group" aria-label={t(g.tr, g.en)}>
        <span class="glabel">{t(g.tr, g.en)}</span>
        <div class="gtools">
          {#each g.tools as tool (tool.id)}
            {@const key = keyFor(tool.id)}
            <button
              class="tool"
              class:on={editor.tool === tool.id}
              aria-pressed={editor.tool === tool.id}
              aria-keyshortcuts={key}
              title={`${t(tool.tr, tool.en)}${key ? ` (${key})` : ""}`}
              onclick={() => choose(tool.id)}
            >
              <span class="ticon" aria-hidden="true">{tool.icon}</span>
              <span class="tlabel">{t(tool.tr, tool.en)}</span>
              {#if key}<kbd aria-hidden="true">{key}</kbd>{/if}
            </button>
          {/each}
        </div>
      </div>
    {/each}
    <div class="group actions" role="group" aria-label={t("Geçmiş", "History")}>
      <span class="glabel">{t("Geçmiş", "History")}</span>
      <div class="gtools">
        <button class="tool" onclick={() => editor.undo()} disabled={!editor.canUndo} title="Ctrl+Z" aria-keyshortcuts="Control+Z">
          <span class="ticon" aria-hidden="true">↶</span><span class="tlabel">{t("Geri al", "Undo")}</span>
        </button>
        <button class="tool" onclick={() => editor.redo()} disabled={!editor.canRedo} title="Ctrl+Y" aria-keyshortcuts="Control+Y">
          <span class="ticon" aria-hidden="true">↷</span><span class="tlabel">{t("Yinele", "Redo")}</span>
        </button>
        <button
          class="tool"
          onclick={() => editor.selectedId && editor.remove(editor.selectedId)}
          disabled={!editor.selectedId}
          title="Delete"
          aria-keyshortcuts="Delete"
        >
          <span class="ticon" aria-hidden="true">🗑</span><span class="tlabel">{t("Sil", "Delete")}</span>
        </button>
      </div>
    </div>
  </div>

  <div class="row style" role="group" aria-label={t("Biçim", "Format")}>
    {#if editor.tool === "field"}
      <label class="ctl">
        <span>{t("Alan türü", "Field type")}</span>
        <select bind:value={editor.style.fieldType}>
          {#each FIELD_TYPES as [id, tr, en] (id)}<option value={id}>{t(tr, en)}</option>{/each}
        </select>
      </label>
    {/if}
    {#if textual}
      <label class="ctl">
        <span>{t("Yazı tipi", "Font")}</span>
        <select value={editor.style.font.family_id} onchange={(e) => restyle({ font: { ...editor.style.font, family_id: e.currentTarget.value } })}>
          {#each ["standard", "bundled", "system"] as src (src)}
            {@const list = fonts.families.filter((f) => f.source === src)}
            {#if list.length}
              <optgroup label={src === "standard" ? t("Standart", "Standard") : src === "bundled" ? t("Uygulama", "Bundled") : t("Bu bilgisayar", "This computer")}>
                {#each list as f (f.id)}<option value={f.id}>{f.family}{f.restricted ? " 🔒" : ""}</option>{/each}
              </optgroup>
            {/if}
          {/each}
        </select>
      </label>
      <label class="ctl">
        <span>{t("Kalınlık", "Weight")}</span>
        <select value={editor.style.font.weight} onchange={(e) => restyle({ font: { ...editor.style.font, weight: Number(e.currentTarget.value) } })}>
          {#each WEIGHTS as [w, name] (w)}
            <option value={w} disabled={!!family?.styles.length && !family.styles.some((s) => s.weight === w)}>{name}</option>
          {/each}
        </select>
      </label>
      <label class="ctl">
        <span>{t("Boyut (pt)", "Size (pt)")}</span>
        <input class="num" type="number" min="4" max="200" step="0.5" value={editor.style.size} onchange={(e) => restyle({ size: Number(e.currentTarget.value) || 12 })} />
      </label>
      <label class="ctl check">
        <input type="checkbox" checked={editor.style.font.italic} onchange={(e) => restyle({ font: { ...editor.style.font, italic: e.currentTarget.checked } })} />
        <span><i>{t("İtalik", "Italic")}</i></span>
      </label>
    {/if}
    <label class="ctl">
      <span>{textual ? t("Yazı rengi", "Text colour") : t("Çizgi rengi", "Stroke")}</span>
      <input type="color" value={editor.style.color} onchange={(e) => restyle({ color: e.currentTarget.value })} />
    </label>
    {#if editor.tool === "rect" || editor.tool === "ellipse" || editor.tool === "whiteout" || editor.selected?.kind === "rect" || editor.selected?.kind === "ellipse"}
      <label class="ctl">
        <span>{t("Dolgu", "Fill")}</span>
        <input type="color" value={editor.style.fill ?? "#ffffff"} onchange={(e) => restyle({ fill: e.currentTarget.value })} />
      </label>
      <button class="small ghost" onclick={() => restyle({ fill: null })}>{t("Dolgusuz", "No fill")}</button>
    {/if}
    {#if !textual}
      <label class="ctl">
        <span>{t("Kalınlık (pt)", "Width (pt)")}</span>
        <input class="num" type="number" min="0.5" max="40" step="0.5" value={editor.style.width} onchange={(e) => restyle({ width: Number(e.currentTarget.value) || 1 })} />
      </label>
      <label class="ctl">
        <span>{t("Saydamlık", "Opacity")} {Math.round(editor.style.opacity * 100)}%</span>
        <input type="range" min="0.1" max="1" step="0.05" value={editor.style.opacity} oninput={(e) => restyle({ opacity: Number(e.currentTarget.value) })} />
      </label>
    {/if}
    <span class="status">
      {#if editor.selected}
        {t("Seçili", "Selected")}: <strong>{editor.selected.kind}</strong> · {t("ok tuşlarıyla taşıyın, Shift ile 10 pt", "move with arrow keys, Shift for 10 pt")}
      {:else}
        {t("Kısayollar için", "For shortcuts press")} <kbd>?</kbd>
      {/if}
    </span>
    <button class="primary save" disabled={!editor.count || saving} onclick={onsave} title="Ctrl+S" aria-keyshortcuts="Control+S">
      {saving ? t("Kaydediliyor…", "Saving…") : t("Kaydet", "Save")}
      {#if editor.count && !saving}<span class="badge">{editor.count}</span>{/if}
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
    display: grid;
    gap: 6px;
    padding: 6px 8px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
  }
  .row {
    display: flex;
    flex-wrap: wrap;
    gap: 6px 10px;
    align-items: center;
  }
  .group {
    display: grid;
    gap: 2px;
    padding-right: 10px;
    border-right: 1px solid var(--border);
  }
  .group:last-of-type {
    border-right: 0;
  }
  .glabel {
    font-size: 0.65rem;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--muted);
    padding-left: 2px;
  }
  .gtools {
    display: flex;
    gap: 2px;
  }
  .tool {
    position: relative;
    display: grid;
    justify-items: center;
    gap: 1px;
    min-width: 50px;
    min-height: 48px;
    padding: 4px 4px 2px;
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
  .ticon {
    font-size: 1.05rem;
    line-height: 1.2;
  }
  .tlabel {
    font-size: 0.68rem;
    white-space: nowrap;
  }
  kbd {
    position: absolute;
    top: 2px;
    right: 3px;
    font: 600 0.55rem/1 ui-monospace, monospace;
    color: var(--muted);
  }
  /* Touch screens: key hints and arrow-key tips do not apply. */
  @media (hover: none) and (pointer: coarse) {
    kbd,
    .status {
      display: none;
    }
  }
  .status kbd {
    position: static;
    padding: 1px 5px;
    border: 1px solid var(--border-strong);
    border-radius: 4px;
    font-size: 0.75rem;
  }
  .save {
    gap: 8px;
  }
  .badge {
    min-width: 20px;
    padding: 0 6px;
    border-radius: 999px;
    background: var(--on-accent);
    color: var(--accent);
    font-size: 0.75rem;
  }
  .style {
    padding-top: 6px;
    border-top: 1px solid var(--border);
  }
  .ctl {
    display: grid;
    gap: 2px;
    font-size: 0.7rem;
    color: var(--muted);
  }
  .ctl.check {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.85rem;
    color: var(--text);
  }
  .ctl select {
    width: auto;
    max-width: 200px;
    padding: 4px 8px;
  }
  .num {
    width: 72px !important;
    padding: 4px 8px !important;
  }
  .ctl input[type="color"] {
    width: 40px;
    height: 30px;
  }
  .status {
    margin-left: auto;
    font-size: 0.8rem;
    color: var(--muted);
  }
</style>
